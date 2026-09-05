"""
Unit tests for data schemas
"""
from backend.app.schemas.camera import CameraBase
from backend.app.schemas.trajectory import (
    TrajectoryWaypoint,
    GlobalVehicleRecord,
    AlertSchema,
    TrafficAnalyticsSchema,
)


def test_camera_schema():
    cam = CameraBase(
        id="CAM-001",
        name="Test Camera",
        latitude=28.6139,
        longitude=77.2090,
        heading_deg=45.0,
        fps=15,
        source_type="file",
        stream_uri="sample.mp4",
        status="configured",
    )
    assert cam.id == "CAM-001"
    assert cam.fps == 15


def test_trajectory_waypoint():
    wp = TrajectoryWaypoint(
        camera_id="CAM-001",
        camera_name="Test Camera",
        latitude=28.6139,
        longitude=77.2090,
        timestamp_iso="2026-09-04T12:00:00Z",
        speed_estimate_kmh=42.5,
        confidence=0.92,
    )
    assert wp.camera_id == "CAM-001"
    assert wp.speed_estimate_kmh == 42.5


def test_alert_schema():
    alert = AlertSchema(
        id="ALT-101",
        alert_type="WATCHLIST_MATCH",
        severity="CRITICAL",
        camera_id="CAM-001",
        global_vehicle_id="GV-501",
        plate_text="DL01AB1234",
        message="Stolen vehicle flagged",
        timestamp_iso="2026-09-04T12:05:00Z",
        status="active",
    )
    assert alert.id == "ALT-101"
    assert alert.severity == "CRITICAL"
