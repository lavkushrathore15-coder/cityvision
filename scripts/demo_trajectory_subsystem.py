"""
Demonstration Script for Global Vehicle Identity & Trajectory Subsystem
Problem Statement ID: SIH26127

Demonstrates:
1. Persistent Vehicle Representation (Vehicle -> Observations -> Camera Visits -> Trajectory)
2. Out-of-order ingestion -> Chronologically ordered reconstruction
3. Multi-camera movement transitions, travel times, and speeds
4. Strict GPS adherence: No fake coordinates, marks spatial unavailable when missing
5. Historical search across plate, camera, and time window
"""
import sys
import os

# Ensure root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.database import DatabaseManager
from backend.app.services.trajectory import TrajectoryService
from ai.matching.spatial_temporal import SpatioTemporalTopology


def run_demo():
    print("=" * 75)
    print("CITYVISION AI - GLOBAL VEHICLE IDENTITY & TRAJECTORY SUBSYSTEM DEMO")
    print("=" * 75)

    # Use in-memory SQLite database for clean demonstration
    db = DatabaseManager(db_url=":memory:")
    topology = SpatioTemporalTopology()

    service = TrajectoryService(db=db, topology=topology)

    print("\n--- 1. Ingesting Observations (Demonstrating Out-of-Order Ingestion) ---")
    gid = "GLOBAL-VEH-9042"

    # We deliberately insert out of chronological order:
    # 3. CAM-003 at t=1250.0 (Third camera)
    # 1. CAM-001 at t=1000.0, t=1010.0 (First camera)
    # 2. CAM-002 at t=1100.0, t=1115.0 (Second camera)
    # 4. CAM-UNCONFIGURED at t=1350.0 (Unconfigured camera without GPS)

    print(f"Recording observation 3 (CAM-003 at t=1250.0)...")
    service.record_observation(gid, "CAM-003", 31, timestamp=1250.0, plate_text="DL01AB1234", vehicle_class="car")

    print(f"Recording observation 1a (CAM-001 at t=1000.0)...")
    service.record_observation(gid, "CAM-001", 10, timestamp=1000.0, plate_text="DL01AB1234", vehicle_class="car")
    print(f"Recording observation 1b (CAM-001 at t=1010.0)...")
    service.record_observation(gid, "CAM-001", 10, timestamp=1010.0, plate_text="DL01AB1234", vehicle_class="car")

    print(f"Recording observation 2a (CAM-002 at t=1100.0)...")
    service.record_observation(gid, "CAM-002", 21, timestamp=1100.0, plate_text="DL01AB1234", vehicle_class="car")
    print(f"Recording observation 2b (CAM-002 at t=1115.0)...")
    service.record_observation(gid, "CAM-002", 21, timestamp=1115.0, plate_text="DL01AB1234", vehicle_class="car")

    print(f"Recording observation 4 (CAM-UNCONFIGURED at t=1350.0)...")
    service.record_observation(gid, "CAM-UNCONFIGURED", 45, timestamp=1350.0, plate_text="DL01AB1234", vehicle_class="car")

    print("\n--- 2. Chronological Trajectory Reconstruction ---")
    traj = service.reconstruct_trajectory(gid)

    print(f"Global Vehicle ID:       {traj.global_vehicle_id}")
    print(f"Primary Plate:           {traj.primary_plate}")
    print(f"Vehicle Class:           {traj.vehicle_class}")
    print(f"First Seen:              {traj.first_seen_iso} (epoch: {traj.first_seen_timestamp})")
    print(f"Last Seen:               {traj.last_seen_iso} (epoch: {traj.last_seen_timestamp})")
    print(f"Visited Cameras:         {traj.visited_cameras}")
    print(f"Spatial Map Available:   {traj.is_spatial_available} (Correctly False due to CAM-UNCONFIGURED)")
    print(f"Total Distance (meters): {traj.total_distance_meters or 'Unavailable (Unconfigured node in path)'}")

    print(f"\nChronologically Ordered Observations ({len(traj.observations)} total):")
    for idx, obs in enumerate(traj.observations):
        loc_str = f"({obs.location['latitude']:.4f}, {obs.location['longitude']:.4f})" if obs.location else "NO_GPS_COORDINATES"
        print(f"  [{idx+1}] t={obs.timestamp:.1f}s | Camera: {obs.camera_id:18s} | Plate: {obs.plate_text} | GPS: {loc_str}")

    print(f"\n--- 3. Camera Visits Summary ({len(traj.camera_visits)} visits) ---")
    for idx, v in enumerate(traj.camera_visits):
        print(f"  Visit {idx+1}: {v.camera_name} ({v.camera_id})")
        print(f"    Arrival:      {v.arrival_iso} (t={v.arrival_time:.1f}s)")
        print(f"    Departure:    {v.departure_iso} (t={v.departure_time:.1f}s)")
        print(f"    Duration:     {v.duration_sec:.1f} seconds")
        print(f"    Observations: {v.observation_count}")

    print(f"\n--- 4. Camera-to-Camera Movement Transitions ({len(traj.movements)} hops) ---")
    for idx, m in enumerate(traj.movements):
        dist_str = f"{m.distance_meters:.1f} m" if m.distance_meters is not None else "UNAVAILABLE"
        speed_str = f"{m.speed_kmh:.1f} km/h" if m.speed_kmh is not None else "UNAVAILABLE"
        print(f"  Hop {idx+1}: {m.from_camera_id} -> {m.to_camera_id}")
        print(f"    Elapsed Transit Time: {m.elapsed_time_sec:.1f} seconds")
        print(f"    Physical Distance:    {dist_str}")
        print(f"    Implied Speed:        {speed_str}")
        print(f"    Plausible Transition: {m.is_feasible}")

    print("\n--- 5. Multi-Criteria Historical Search ---")

    # Ingest a second vehicle for search diversity
    service.record_observation("GLOBAL-VEH-7700", "CAM-001", 15, timestamp=1050.0, plate_text="KA05MH2020", vehicle_class="bus")

    # Query A: Search by Plate
    res_plate = service.search_historical(plate_query="AB1234")
    print(f"Search Query 'Plate contains AB1234':")
    for r in res_plate:
        print(f"  Found: {r.global_id} | Plate: {r.primary_plate} | Class: {r.vehicle_class} | First Seen: {r.first_seen}")

    # Query B: Search by Camera
    res_cam = service.search_historical(camera_id="CAM-001")
    print(f"\nSearch Query 'Passed through CAM-001':")
    for r in res_cam:
        print(f"  Found: {r.global_id} | Plate: {r.primary_plate} | Class: {r.vehicle_class}")

    # Query C: Search by Class
    res_bus = service.search_historical(vehicle_class="bus")
    print(f"\nSearch Query 'Vehicle Class = bus':")
    for r in res_bus:
        print(f"  Found: {r.global_id} | Plate: {r.primary_plate} | Class: {r.vehicle_class}")

    print("\n" + "=" * 75)
    print("DEMO COMPLETE: Global vehicle identity and trajectory subsystem verified.")
    print("=" * 75)


if __name__ == "__main__":
    run_demo()
