"""
Unit and Integration Tests for Global Vehicle Identity and Trajectory Subsystem
Problem Statement ID: SIH26127
"""
import pytest
import time
import os
import tempfile
import sqlite3

from backend.app.db.database import DatabaseManager
from backend.app.services.trajectory import TrajectoryService, format_iso_timestamp
from ai.matching.spatial_temporal import SpatioTemporalTopology


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for test isolation."""
    import gc
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_url=f"sqlite:///{path}")
    yield db
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


@pytest.fixture
def topology():
    """Topology fixture with configured urban CCTV locations."""
    topo = SpatioTemporalTopology()
    topo.add_camera("CAM-001", latitude=28.6139, longitude=77.2090, name="North Gateway")
    topo.add_camera("CAM-002", latitude=28.6180, longitude=77.2150, name="Central Ring Road")
    topo.add_camera("CAM-003", latitude=28.6090, longitude=77.2120, name="South Metro Junction")
    # Note: CAM-UNCONFIGURED has no entry
    return topo


@pytest.fixture
def service(temp_db, topology):
    return TrajectoryService(db=temp_db, topology=topology)


# =====================================================================
# Test 1: Chronological Ordering
# =====================================================================

def test_chronological_ordering_of_out_of_order_observations(service):
    """
    Requirement: Trajectory must be ordered chronologically regardless of ingestion order.
    """
    gid = "GLOBAL-VEH-CHRONO"

    # Ingest out of order: t=300, t=100, t=200
    service.record_observation(gid, "CAM-001", 1, timestamp=300.0, plate_text="DL01AB1234")
    service.record_observation(gid, "CAM-001", 1, timestamp=100.0, plate_text="DL01AB1234")
    service.record_observation(gid, "CAM-002", 2, timestamp=200.0, plate_text="DL01AB1234")

    # Fetch history
    history = service.get_vehicle_history(gid)
    assert len(history) == 3
    timestamps = [obs.timestamp for obs in history]
    assert timestamps == [100.0, 200.0, 300.0]

    # Reconstruct trajectory
    traj = service.reconstruct_trajectory(gid)
    assert traj is not None
    traj_ts = [obs.timestamp for obs in traj.observations]
    assert traj_ts == [100.0, 200.0, 300.0]


# =====================================================================
# Test 2: Camera-to-Camera Movement & Camera Visits
# =====================================================================

def test_camera_visits_and_inter_camera_movements(service):
    """
    Requirement: Track camera visits, duration, transitions, and transit speed.
    """
    gid = "GLOBAL-VEH-TRANSIT"

    # Sighting at CAM-001 (duration 10s: 100s to 110s)
    service.record_observation(gid, "CAM-001", 1, timestamp=100.0, plate_text="KA05MH2020")
    service.record_observation(gid, "CAM-001", 1, timestamp=105.0, plate_text="KA05MH2020")
    service.record_observation(gid, "CAM-001", 1, timestamp=110.0, plate_text="KA05MH2020")

    # Movement to CAM-002 (arrival at 180s, departure at 190s)
    service.record_observation(gid, "CAM-002", 5, timestamp=180.0, plate_text="KA05MH2020")
    service.record_observation(gid, "CAM-002", 5, timestamp=190.0, plate_text="KA05MH2020")

    traj = service.reconstruct_trajectory(gid)
    assert traj is not None

    # Verify Visits
    assert len(traj.camera_visits) == 2
    visit1, visit2 = traj.camera_visits[0], traj.camera_visits[1]

    assert visit1.camera_id == "CAM-001"
    assert visit1.arrival_time == 100.0
    assert visit1.departure_time == 110.0
    assert visit1.duration_sec == 10.0
    assert visit1.observation_count == 3

    assert visit2.camera_id == "CAM-002"
    assert visit2.arrival_time == 180.0
    assert visit2.departure_time == 190.0
    assert visit2.duration_sec == 10.0
    assert visit2.observation_count == 2

    # Verify Movement Hop
    assert len(traj.movements) == 1
    movement = traj.movements[0]
    assert movement.from_camera_id == "CAM-001"
    assert movement.to_camera_id == "CAM-002"
    assert movement.departure_time == 110.0
    assert movement.arrival_time == 180.0
    assert movement.elapsed_time_sec == 70.0  # 180 - 110
    assert movement.distance_meters is not None
    assert movement.distance_meters > 500.0  # CAM-001 to CAM-002 is ~740m
    assert movement.speed_kmh is not None
    assert 20.0 <= movement.speed_kmh <= 60.0  # ~38 km/h
    assert movement.is_feasible is True


# =====================================================================
# Test 3: First Seen, Last Seen, and Visited Cameras
# =====================================================================

def test_first_seen_last_seen_and_visited_cameras(service):
    gid = "GLOBAL-VEH-TIMELINE"

    service.record_observation(gid, "CAM-001", 1, timestamp=500.0)
    service.record_observation(gid, "CAM-002", 2, timestamp=600.0)
    service.record_observation(gid, "CAM-003", 3, timestamp=750.0)

    traj = service.reconstruct_trajectory(gid)
    assert traj.first_seen_timestamp == 500.0
    assert traj.last_seen_timestamp == 750.0
    assert traj.first_seen_iso == format_iso_timestamp(500.0)
    assert traj.last_seen_iso == format_iso_timestamp(750.0)
    assert traj.visited_cameras == ["CAM-001", "CAM-002", "CAM-003"]


# =====================================================================
# Test 4: Missing GPS Coordinates (No Fake GPS)
# =====================================================================

def test_missing_coordinates_marks_spatial_unavailable(service):
    """
    Requirement:
    Do not invent GPS coordinates.
    If camera coordinates are not configured, show trajectory as unavailable
    rather than creating fake coordinates.
    """
    gid = "GLOBAL-VEH-NO-GPS"

    # CAM-001 has valid coordinates
    service.record_observation(gid, "CAM-001", 1, timestamp=100.0)
    # CAM-UNCONFIGURED does NOT exist in topology
    service.record_observation(gid, "CAM-UNCONFIGURED", 2, timestamp=200.0)

    history = service.get_vehicle_history(gid)
    assert history[0].location is not None
    # Must NOT invent fake coordinates
    assert history[1].location is None

    traj = service.reconstruct_trajectory(gid)
    assert traj is not None
    # Spatial trajectory must be marked as UNAVAILABLE
    assert traj.is_spatial_available is False
    assert traj.total_distance_meters is None


# =====================================================================
# Test 5: Historical Search
# =====================================================================

def test_historical_search_by_plate_camera_and_time(service):
    """
    Requirement: Implement historical search across plate, camera, time window, and class.
    """
    # Vehicle A: Red Car with plate MH12DE1433
    service.record_observation(
        "GLOBAL-VEH-A", "CAM-001", 10, timestamp=1000.0,
        plate_text="MH12DE1433", vehicle_class="car"
    )
    service.record_observation(
        "GLOBAL-VEH-A", "CAM-002", 11, timestamp=1100.0,
        plate_text="MH12DE1433", vehicle_class="car"
    )

    # Vehicle B: White Truck with plate HR26DK8337
    service.record_observation(
        "GLOBAL-VEH-B", "CAM-003", 20, timestamp=1050.0,
        plate_text="HR26DK8337", vehicle_class="truck"
    )

    # 1. Search by Plate (exact & substring)
    res_plate_exact = service.search_historical(plate_query="MH12DE1433")
    assert len(res_plate_exact) == 1
    assert res_plate_exact[0].global_id == "GLOBAL-VEH-A"

    res_plate_sub = service.search_historical(plate_query="DK8337")
    assert len(res_plate_sub) == 1
    assert res_plate_sub[0].global_id == "GLOBAL-VEH-B"

    # 2. Search by Camera ID
    res_cam1 = service.search_historical(camera_id="CAM-001")
    assert len(res_cam1) == 1
    assert res_cam1[0].global_id == "GLOBAL-VEH-A"

    res_cam3 = service.search_historical(camera_id="CAM-003")
    assert len(res_cam3) == 1
    assert res_cam3[0].global_id == "GLOBAL-VEH-B"

    # 3. Search by Time Window
    res_time = service.search_historical(start_time=1080.0, end_time=1200.0)
    assert len(res_time) == 1
    assert res_time[0].global_id == "GLOBAL-VEH-A"

    # 4. Search by Vehicle Class
    res_truck = service.search_historical(vehicle_class="truck")
    assert len(res_truck) == 1
    assert res_truck[0].global_id == "GLOBAL-VEH-B"


# =====================================================================
# Test 6: Database Persistence
# =====================================================================

def test_database_persistence_across_service_instances(temp_db, topology):
    """
    Requirement: Add database persistence only using the existing backend architecture.
    """
    gid = "GLOBAL-VEH-PERSIST"

    # Instance 1: Write data
    svc1 = TrajectoryService(db=temp_db, topology=topology)
    svc1.record_observation(gid, "CAM-001", 1, timestamp=100.0, plate_text="DL3CAF1111")
    svc1.record_observation(gid, "CAM-002", 2, timestamp=180.0, plate_text="DL3CAF1111")

    # Instance 2: Connect to the same database and verify state
    svc2 = TrajectoryService(db=temp_db, topology=topology)
    history = svc2.get_vehicle_history(gid)
    assert len(history) == 2
    assert history[0].plate_text == "DL3CAF1111"
    assert history[1].camera_id == "CAM-002"

    traj = svc2.reconstruct_trajectory(gid)
    assert traj is not None
    assert traj.primary_plate == "DL3CAF1111"
    assert traj.visited_cameras == ["CAM-001", "CAM-002"]
    assert len(traj.movements) == 1
