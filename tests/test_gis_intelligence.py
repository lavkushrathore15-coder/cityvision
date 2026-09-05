"""
Unit and Integration Tests for the GIS Intelligence Layer and Trajectory Mapping
Problem Statement ID: SIH26127

Requirements Tested:
1. Stored camera coordinates (real/demo)
2. Trajectory reconstruction & corridor movements
3. Zero geographic fabrication (missing coordinates are explicitly unmapped)
4. Camera coordinate update/configuration API
5. Multi-filter GIS summary (camera, vehicle, alert type, time)
"""
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.trajectory import TrajectoryService
from backend.app.services.video_ingestion import VideoIngestionEngine, CameraLocation

client = TestClient(app)


# =====================================================================
# Test 1: Camera Location Update API (PUT /api/v1/cameras/{id}/location)
# =====================================================================

def test_camera_location_update_valid():
    """Verify camera coordinates can be updated via PUT /api/v1/cameras/{id}/location."""
    payload = {
        "latitude": 28.6250,
        "longitude": 77.2200,
        "heading_deg": 135.0,
        "description": "Updated North Junction Test Node",
    }
    resp = client.put("/api/v1/cameras/CAM-001/location", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == "CAM-001"
    assert data["latitude"] == 28.6250
    assert data["longitude"] == 77.2200
    assert data["heading_deg"] == 135.0

    # Restore original CAM-001 coordinates
    restore_payload = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "heading_deg": 45.0,
        "description": "North Gateway Intersection",
    }
    restore_resp = client.put("/api/v1/cameras/CAM-001/location", json=restore_payload)
    assert restore_resp.status_code == 200


def test_camera_location_update_invalid_coordinates_rejected():
    """Verify that impossible latitude/longitude ranges are strictly rejected with 422."""
    # Latitude > 90
    bad_lat = {"latitude": 95.0, "longitude": 77.0}
    resp = client.put("/api/v1/cameras/CAM-001/location", json=bad_lat)
    assert resp.status_code == 422

    # Longitude < -180
    bad_lng = {"latitude": 28.0, "longitude": -195.0}
    resp = client.put("/api/v1/cameras/CAM-001/location", json=bad_lng)
    assert resp.status_code == 422


def test_camera_location_update_nonexistent_camera_returns_404():
    """Verify updating a non-existent camera returns 404."""
    resp = client.put(
        "/api/v1/cameras/CAM-NONEXISTENT/location",
        json={"latitude": 28.0, "longitude": 77.0},
    )
    assert resp.status_code == 404


# =====================================================================
# Test 2: GIS Summary with Configured Real Coordinates
# =====================================================================

def test_gis_summary_full_payload():
    """Verify GET /api/v1/trajectories/gis-summary returns all 5 GIS layers."""
    resp = client.get("/api/v1/trajectories/gis-summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "cameras" in data
    assert "trajectories" in data
    assert "corridors" in data
    assert "zones" in data
    assert "alerts" in data
    assert "unconfigured_camera_count" in data
    assert "total_cameras" in data

    # Verify camera coordinates integrity
    cameras = data["cameras"]
    assert len(cameras) >= 5
    for cam in cameras:
        assert "id" in cam
        assert "latitude" in cam
        assert "longitude" in cam
        assert "is_gps_available" in cam
        if cam["latitude"] is not None and cam["longitude"] is not None:
            assert cam["is_gps_available"] is True
            assert -90.0 <= cam["latitude"] <= 90.0
            assert -180.0 <= cam["longitude"] <= 180.0


# =====================================================================
# Test 3: Zero Geographic Fabrication with Missing Coordinates
# =====================================================================

def test_missing_coordinates_zero_fabrication():
    """
    Requirement:
    The map must never silently display invented locations.
    If camera coordinates are missing, is_spatial_available must be False
    and coordinates must be None, never fabricated (e.g. 0,0).
    """
    service = TrajectoryService()
    gid = "GLOBAL-VEH-ZERO-FABRICATION-TEST"

    # Observation at CAM-UNMAPPED (which does not exist in cameras.json and has no GPS)
    service.record_observation(gid, "CAM-UNMAPPED", 101, timestamp=1000.0)
    service.record_observation(gid, "CAM-UNMAPPED", 102, timestamp=1010.0)

    traj = service.reconstruct_trajectory(gid)
    assert traj is not None
    assert traj.is_spatial_available is False  # Explicitly marked unavailable
    assert traj.total_distance_meters is None  # Never fabricated

    for obs in traj.observations:
        # Location must be None or explicitly lack latitude/longitude
        assert obs.location is None


# =====================================================================
# Test 4: GIS Multi-Filter Filtering
# =====================================================================

def test_gis_summary_filtering_by_camera():
    """Verify filtering GIS features by a specific camera node."""
    resp = client.get("/api/v1/trajectories/gis-summary?camera_id=CAM-001")
    assert resp.status_code == 200
    data = resp.json()

    # Filtered cameras list should only contain CAM-001
    assert len(data["cameras"]) == 1
    assert data["cameras"][0]["id"] == "CAM-001"

    # Corridors should touch CAM-001
    for corr in data["corridors"]:
        assert corr["from_camera_id"] == "CAM-001" or corr["to_camera_id"] == "CAM-001"


def test_gis_summary_filtering_by_alert_type():
    """Verify filtering GIS georeferenced alerts by type."""
    resp = client.get("/api/v1/trajectories/gis-summary?alert_type=BLACKLIST_MATCH")
    assert resp.status_code == 200
    data = resp.json()

    for alert in data["alerts"]:
        assert alert["alert_type"] == "BLACKLIST_MATCH"


def test_gis_summary_filtering_by_vehicle_id():
    """Verify filtering GIS summary by a specific vehicle ID."""
    resp = client.get("/api/v1/trajectories/gis-summary?vehicle_id=GLOBAL-000001")
    assert resp.status_code == 200
    data = resp.json()

    for traj in data["trajectories"]:
        assert traj["global_id"] == "GLOBAL-000001"
