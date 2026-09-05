"""
Comprehensive API Integration and Endpoint Tests for CITYVISION AI FastAPI Backend
Problem Statement ID: SIH26127
"""
import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.routes import trajectory_service, alert_service

client = TestClient(app)

# Ensure at least one test vehicle & observation exist in the DB for endpoint testing
@pytest.fixture(scope="session", autouse=True)
def setup_test_vehicle_and_observations():
    now = time.time()
    # Record observation 1 at CAM-001
    trajectory_service.record_observation(
        global_vehicle_id="GV-TEST-1001",
        camera_id="CAM-001",
        local_track_id=1,
        timestamp=now - 200,
        plate_text="RJ14AB1234",
        ocr_confidence=0.92,
        vehicle_class="car",
    )
    # Record observation 2 at CAM-002
    trajectory_service.record_observation(
        global_vehicle_id="GV-TEST-1001",
        camera_id="CAM-002",
        local_track_id=2,
        timestamp=now - 100,
        plate_text="RJ14AB1234",
        ocr_confidence=0.95,
        vehicle_class="car",
    )


# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================
def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CITYVISION AI"
    assert data["status"] == "operational"
    assert "documentation" in data


def test_frontend_browser_root():
    """Verify that a browser request with Accept: text/html receives the React SPA index."""
    response = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<div id=\"root\">" in response.text or "CITYVISION" in response.text


def test_frontend_dashboard_endpoint():
    """Verify that /dashboard serves the React single-page application."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["app"] == "CITYVISION AI"
    assert "inference_device" in data


def test_openapi_documentation_generation():
    """Verify OpenAPI JSON schema compiles and contains all route tags."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/v1/cameras" in schema["paths"]
    assert "/api/v1/vehicles" in schema["paths"]
    assert "/api/v1/alerts" in schema["paths"]
    assert "/api/v1/analytics/congestion" in schema["paths"]


# ============================================================================
# CAMERAS ENDPOINTS
# ============================================================================
def test_list_cameras():
    response = client.get("/api/v1/cameras")
    assert response.status_code == 200
    cameras = response.json()
    assert isinstance(cameras, list)
    assert len(cameras) >= 5
    first = cameras[0]
    assert "id" in first
    assert "name" in first
    assert "latitude" in first
    assert "longitude" in first


def test_get_camera_metadata():
    response = client.get("/api/v1/cameras/CAM-001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "CAM-001"
    assert "North Gateway" in data["name"]
    assert data["fps"] == 15


def test_get_camera_metadata_not_found():
    response = client.get("/api/v1/cameras/CAM-NONEXISTENT")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "detail" in data
    assert data["code"] == "ERR_HTTP_404"


def test_get_camera_status():
    response = client.get("/api/v1/cameras/CAM-001/status")
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "CAM-001"
    assert "is_connected" in data
    assert "processing_status" in data
    assert "resolution" in data
    assert "location" in data
    assert data["location"]["is_gps_available"] is True


def test_get_camera_status_not_found():
    response = client.get("/api/v1/cameras/CAM-9999/status")
    assert response.status_code == 404


# ============================================================================
# VEHICLES ENDPOINTS
# ============================================================================
def test_list_vehicles():
    response = client.get("/api/v1/vehicles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    veh = data[0]
    assert "global_id" in veh
    assert "primary_plate" in veh
    assert "vehicle_class" in veh


def test_search_vehicles_by_plate():
    response = client.get("/api/v1/vehicles/search?plate=RJ14")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any("RJ14" in v["primary_plate"] for v in data if v.get("primary_plate"))


def test_search_vehicles_filter_by_class():
    response = client.get("/api/v1/vehicles/search?vehicle_class=car")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_vehicle_details():
    response = client.get("/api/v1/vehicles/GV-TEST-1001")
    assert response.status_code == 200
    data = response.json()
    assert data["global_id"] == "GV-TEST-1001"
    assert data["primary_plate"] == "RJ14AB1234"


def test_get_vehicle_details_not_found():
    response = client.get("/api/v1/vehicles/GV-NONEXISTENT-9999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data


def test_get_vehicle_history():
    response = client.get("/api/v1/vehicles/GV-TEST-1001/history")
    assert response.status_code == 200
    data = response.json()
    assert data["global_vehicle_id"] == "GV-TEST-1001"
    assert "camera_visits" in data
    assert "movements" in data
    assert len(data["camera_visits"]) >= 1


def test_get_vehicle_history_not_found():
    response = client.get("/api/v1/vehicles/GV-UNKNOWN-000/history")
    assert response.status_code == 404


# ============================================================================
# OBSERVATIONS ENDPOINTS
# ============================================================================
def test_get_observation_details():
    # First get an observation ID from the trajectory service
    traj = trajectory_service.reconstruct_trajectory("GV-TEST-1001")
    assert traj is not None and len(traj.observations) > 0
    obs_id = traj.observations[0].observation_id

    response = client.get(f"/api/v1/observations/{obs_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["observation_id"] == obs_id
    assert data["global_vehicle_id"] == "GV-TEST-1001"
    assert "bounding_box" in data
    assert "plate_text" in data


def test_get_observation_not_found():
    response = client.get("/api/v1/observations/OBS-NONEXISTENT-999")
    assert response.status_code == 404


# ============================================================================
# TRAJECTORIES ENDPOINTS
# ============================================================================
def test_get_trajectory_by_id():
    response = client.get("/api/v1/trajectories/GV-TEST-1001")
    assert response.status_code == 200
    data = response.json()
    assert data["global_vehicle_id"] == "GV-TEST-1001"
    assert "visited_cameras" in data
    assert "camera_visits" in data
    assert "movements" in data


def test_get_trajectory_not_found():
    response = client.get("/api/v1/trajectories/GV-NONEXISTENT")
    assert response.status_code == 404


def test_get_camera_movements():
    response = client.get("/api/v1/trajectories/GV-TEST-1001/movements")
    assert response.status_code == 200
    movements = response.json()
    assert isinstance(movements, list)
    if len(movements) > 0:
        hop = movements[0]
        assert "from_camera_id" in hop
        assert "to_camera_id" in hop
        assert "speed_kmh" in hop


def test_get_camera_movements_not_found():
    response = client.get("/api/v1/trajectories/GV-UNKNOWN-999/movements")
    assert response.status_code == 404


# ============================================================================
# ALERTS ENDPOINTS
# ============================================================================
def test_list_alerts():
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    alert = data[0]
    assert "alert_id" in alert
    assert "severity" in alert
    assert "status" in alert


def test_list_alerts_with_filters():
    response = client.get("/api/v1/alerts?status=NEW&severity=CRITICAL")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_alert_details():
    response = client.get("/api/v1/alerts/ALT-DEMO-101")
    assert response.status_code == 200
    data = response.json()
    assert data["alert_id"] == "ALT-DEMO-101"
    assert data["alert_type"] == "WATCHLIST_HIT"


def test_get_alert_not_found():
    response = client.get("/api/v1/alerts/ALT-NOTFOUND")
    assert response.status_code == 404


def test_update_alert_status():
    payload = {"status": "ACKNOWLEDGED", "acknowledged_by": "Officer_Sharma_402"}
    response = client.patch("/api/v1/alerts/ALT-DEMO-101/status", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["acknowledged_by"] == "Officer_Sharma_402"


def test_update_alert_not_found():
    payload = {"status": "RESOLVED"}
    response = client.patch("/api/v1/alerts/ALT-NONEXISTENT/status", json=payload)
    assert response.status_code == 404


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================
def test_analytics_traffic_counts():
    response = client.get("/api/v1/analytics/traffic-counts")
    assert response.status_code == 200
    data = response.json()
    assert "total_tracked_vehicles" in data
    assert "active_camera_count" in data
    assert "hourly_vehicle_counts" in data
    assert len(data["hourly_vehicle_counts"]) == 24


def test_analytics_camera_activity():
    response = client.get("/api/v1/analytics/camera-activity")
    assert response.status_code == 200
    data = response.json()
    assert "cameras" in data
    assert isinstance(data["cameras"], list)
    assert len(data["cameras"]) >= 5


def test_analytics_zone_density():
    response = client.get("/api/v1/analytics/zone-density")
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert "city_average_density" in data
    assert isinstance(data["zones"], list)


def test_analytics_congestion():
    response = client.get("/api/v1/analytics/congestion")
    assert response.status_code == 200
    data = response.json()
    assert "corridors" in data
    assert "citywide_congestion_index_percent" in data
    assert isinstance(data["corridors"], list)
    assert len(data["corridors"]) >= 1
    corr = data["corridors"][0]
    assert "from_camera_id" in corr
    assert "to_camera_id" in corr
    assert "congestion_level" in corr


def test_analytics_legacy():
    response = client.get("/api/v1/analytics/traffic")
    assert response.status_code == 200
    data = response.json()
    assert "active_camera_count" in data


# ============================================================================
# WEBSOCKET TELEMETRY
# ============================================================================
def test_websocket_telemetry_handshake():
    """Verify WebSocket connection, initial handshake, and ping/pong."""
    with client.websocket_connect("/api/v1/ws/dashboard") as ws:
        # Expect greeting
        initial = ws.receive_json()
        assert initial["event"] == "connected"
        assert "CITYVISION AI" in initial["message"]

        # Send test message
        ws.send_text("client_heartbeat_ping")
        echo = ws.receive_json()
        assert echo["event"] == "pong"
        assert echo["received"] == "client_heartbeat_ping"
