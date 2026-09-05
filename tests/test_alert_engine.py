"""
Unit and Integration Tests for the CITYVISION AI Alert Engine
Problem Statement ID: SIH26127

Requirements Tested:
1. BLACKLIST: Reliable plate recognition vs configured blacklist.
2. False-positive prevention: Suppress low-confidence OCR and missing plates.
3. ANOMALY: Configurable movement anomalies (speeding, impossible transit times).
4. CONGESTION: Zone vehicle density and corridor bottleneck thresholds.
5. Alert Envelope: alert_id, type, severity, timestamp, camera/zone, related vehicle, evidence, status.
6. Demonstration mode isolation: Zero fabricated alerts when demo_mode=False.
7. Configurable thresholds.
"""
import pytest
import time
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.trajectory import CameraMovementSchema, AlertSchema
from backend.app.services.alert_engine import AlertEngine, AlertEngineConfig
from backend.app.services.trajectory import AlertService

client = TestClient(app)


# =====================================================================
# 1. BLACKLIST EVALUATION & FALSE-POSITIVE PREVENTION
# =====================================================================

def test_blacklist_match_high_confidence():
    """Verify that a high-confidence OCR read matching a blacklisted plate triggers an alert."""
    config = AlertEngineConfig(
        min_plate_confidence=0.80,
        watchlist_path="data/watchlist/stolen_vehicles.json",
        demo_mode=False,
    )
    engine = AlertEngine(config=config)

    # DL01AB1234 is in stolen_vehicles.json with alert_level CRITICAL
    alert = engine.evaluate_plate_blacklist(
        plate_text="DL01AB1234",
        ocr_confidence=0.94,
        camera_id="CAM-001",
        global_vehicle_id="GLOBAL-000001",
    )

    assert alert is not None
    assert alert.alert_id.startswith("ALT-BLK-")
    assert alert.type == "BLACKLIST"
    assert alert.severity == "CRITICAL"
    assert alert.camera_id == "CAM-001"
    assert alert.global_vehicle_id == "GLOBAL-000001"
    assert alert.plate_text == "DL01AB1234"
    assert alert.status == "NEW"

    # Verify structured evidence audit trail
    assert "evidence" in alert.model_dump()
    evidence = alert.evidence
    assert evidence["plate_number"] == "DL01AB1234"
    assert evidence["ocr_confidence"] == 0.94
    assert evidence["confidence_threshold"] == 0.80
    assert evidence["rule"] == "RELIABLE_PLATE_MATCH"
    assert "reason" in evidence


def test_blacklist_suppressed_on_low_confidence_ocr():
    """
    CRITICAL REQUIREMENT:
    Do not trigger a blacklist alert from low-confidence OCR.
    """
    config = AlertEngineConfig(
        min_plate_confidence=0.80,
        watchlist_path="data/watchlist/stolen_vehicles.json",
        demo_mode=False,
    )
    engine = AlertEngine(config=config)

    # Blacklisted plate, but low OCR confidence (0.68 < 0.80)
    alert = engine.evaluate_plate_blacklist(
        plate_text="DL01AB1234",
        ocr_confidence=0.68,
        camera_id="CAM-001",
        global_vehicle_id="GLOBAL-000001",
    )

    # Must be strictly suppressed to prevent false positive law enforcement alarms
    assert alert is None
    assert len(engine.list_alerts()) == 0


def test_blacklist_suppressed_on_missing_confidence():
    """Verify that missing OCR confidence (None) suppresses blacklist alerts."""
    config = AlertEngineConfig(min_plate_confidence=0.80, demo_mode=False)
    engine = AlertEngine(config=config)

    alert = engine.evaluate_plate_blacklist(
        plate_text="DL01AB1234",
        ocr_confidence=None,
        camera_id="CAM-001",
    )
    assert alert is None


def test_blacklist_suppressed_on_empty_or_missing_plate():
    """Verify that empty, blank, or None plate texts never trigger alerts."""
    config = AlertEngineConfig(min_plate_confidence=0.80, demo_mode=False)
    engine = AlertEngine(config=config)

    assert engine.evaluate_plate_blacklist(None, 0.95, "CAM-001") is None
    assert engine.evaluate_plate_blacklist("", 0.95, "CAM-001") is None
    assert engine.evaluate_plate_blacklist("   ", 0.95, "CAM-001") is None


def test_blacklist_no_match_for_innocent_vehicle():
    """Verify that a legitimate vehicle not on the watchlist generates zero alerts."""
    config = AlertEngineConfig(min_plate_confidence=0.80, demo_mode=False)
    engine = AlertEngine(config=config)

    alert = engine.evaluate_plate_blacklist(
        plate_text="MH12AB9999",
        ocr_confidence=0.98,
        camera_id="CAM-002",
    )
    assert alert is None
    assert len(engine.list_alerts()) == 0


# =====================================================================
# 2. ANOMALY EVALUATION (SPEED & TEMPORAL DISCONTINUITY)
# =====================================================================

def test_anomaly_excessive_speed_triggers_alert():
    """Verify that transit velocity exceeding threshold triggers an ANOMALY alert."""
    config = AlertEngineConfig(max_feasible_speed_kmh=120.0, demo_mode=False)
    engine = AlertEngine(config=config)

    # Clocked at 145.5 km/h across corridor
    movement = CameraMovementSchema(
        from_camera_id="CAM-001",
        to_camera_id="CAM-002",
        departure_time=100.0,
        arrival_time=124.0,
        elapsed_time_sec=24.0,
        distance_meters=970.0,
        speed_kmh=145.5,
    )

    alert = engine.evaluate_movement_anomaly(movement, global_vehicle_id="GV-SPEEDER-01")

    assert alert is not None
    assert alert.type == "ANOMALY"
    assert alert.severity == "HIGH"
    assert alert.camera_id == "CAM-002"
    assert alert.global_vehicle_id == "GV-SPEEDER-01"

    evidence = alert.evidence
    assert evidence["anomaly_type"] == "EXCESSIVE_TRANSIT_SPEED"
    assert evidence["speed_kmh"] == 145.5
    assert evidence["speed_threshold_kmh"] == 120.0
    assert evidence["rule"] == "TRANSIT_SPEED_VIOLATION"


def test_anomaly_impossible_transit_time_triggers_alert():
    """Verify that an impossibly short travel time (< 3.0s for 600m) triggers an ANOMALY alert."""
    config = AlertEngineConfig(min_transit_time_sec=3.0, demo_mode=False)
    engine = AlertEngine(config=config)

    movement = CameraMovementSchema(
        from_camera_id="CAM-001",
        to_camera_id="CAM-004",
        departure_time=100.0,
        arrival_time=101.5,
        elapsed_time_sec=1.5,  # 1.5 seconds to travel 880 meters = physically impossible (~2100 km/h)
        distance_meters=880.0,
        speed_kmh=2112.0,
    )

    alert = engine.evaluate_movement_anomaly(movement, global_vehicle_id="GV-WARP-01")

    assert alert is not None
    assert alert.type == "ANOMALY"
    assert alert.severity in ("CRITICAL", "HIGH")
    evidence = alert.evidence
    assert "anomaly_type" in evidence


def test_anomaly_normal_movement_no_alert():
    """Verify that lawful normal traffic movement generates zero anomaly alerts."""
    config = AlertEngineConfig(max_feasible_speed_kmh=120.0, demo_mode=False)
    engine = AlertEngine(config=config)

    # 45.0 km/h
    movement = CameraMovementSchema(
        from_camera_id="CAM-001",
        to_camera_id="CAM-002",
        departure_time=100.0,
        arrival_time=177.6,
        elapsed_time_sec=77.6,
        distance_meters=970.0,
        speed_kmh=45.0,
    )

    alert = engine.evaluate_movement_anomaly(movement, global_vehicle_id="GV-NORMAL-01")
    assert alert is None


def test_anomaly_missing_metrics_handled_gracefully():
    """Verify that missing speed or unconfigured distances do not produce false alarms."""
    config = AlertEngineConfig(demo_mode=False)
    engine = AlertEngine(config=config)

    # Coordinates unconfigured, speed is None
    movement = CameraMovementSchema(
        from_camera_id="CAM-001",
        to_camera_id="CAM-UNMAPPED",
        departure_time=100.0,
        arrival_time=120.0,
        elapsed_time_sec=20.0,
        distance_meters=None,
        speed_kmh=None,
    )

    alert = engine.evaluate_movement_anomaly(movement, global_vehicle_id="GV-NOMETRIC-01")
    assert alert is None


# =====================================================================
# 3. CONGESTION EVALUATION (ZONE DENSITY & CORRIDOR DELAYS)
# =====================================================================

def test_congestion_zone_density_threshold_exceeded():
    """Verify that active zone density exceeding threshold triggers a CONGESTION alert."""
    config = AlertEngineConfig(congestion_density_threshold=15, demo_mode=False)
    engine = AlertEngine(config=config)

    # Density = 18 vehicles (exceeds threshold 15)
    alert = engine.evaluate_congestion(
        camera_id="CAM-002",
        active_density=18,
        zone_name="Central Ring Road",
    )

    assert alert is not None
    assert alert.type == "CONGESTION"
    assert alert.severity == "MEDIUM"
    assert alert.camera_id == "CAM-002"
    assert alert.global_vehicle_id is None
    evidence = alert.evidence
    assert evidence["active_density"] == 18
    assert evidence["density_threshold"] == 15
    assert evidence["rule"] == "ZONE_CAPACITY_EXCEEDED"


def test_congestion_severe_density_critical_severity():
    """Verify that extreme density (>= 1.5x threshold) produces CRITICAL severity."""
    config = AlertEngineConfig(congestion_density_threshold=15, demo_mode=False)
    engine = AlertEngine(config=config)

    # Density = 28 vehicles (>= 22.5)
    alert = engine.evaluate_congestion(
        camera_id="CAM-003",
        active_density=28,
        zone_name="South Metro Junction",
    )

    assert alert is not None
    assert alert.severity == "CRITICAL"


def test_congestion_normal_density_no_alert():
    """Verify that normal traffic density (< threshold) generates no alert."""
    config = AlertEngineConfig(congestion_density_threshold=15, demo_mode=False)
    engine = AlertEngine(config=config)

    alert = engine.evaluate_congestion(
        camera_id="CAM-001",
        active_density=8,
        zone_name="North Gateway",
    )
    assert alert is None


# =====================================================================
# 4. DEMO MODE ISOLATION (ZERO FABRICATION SAFEGUARD)
# =====================================================================

def test_zero_alerts_fabricated_when_demo_mode_false():
    """
    CRITICAL REQUIREMENT:
    Never generate alerts solely for demonstration unless the system is explicitly running in DEMO MODE.
    """
    config = AlertEngineConfig(demo_mode=False)
    engine = AlertEngine(config=config)

    # Verify zero pre-seeded or fake alerts exist
    assert len(engine.list_alerts()) == 0
    assert engine.get_alert("ALT-DEMO-101") is None


def test_demo_alert_seeded_only_when_demo_mode_true():
    """Verify that demo fixtures are only available when demo_mode=True."""
    config = AlertEngineConfig(demo_mode=True)
    engine = AlertEngine(config=config)

    assert len(engine.list_alerts()) == 1
    assert engine.get_alert("ALT-DEMO-101") is not None


# =====================================================================
# 5. CONFIGURABLE THRESHOLDS
# =====================================================================

def test_configurable_ocr_threshold_sensitivity():
    """Verify custom OCR threshold restricts matching appropriately."""
    # Stricter threshold of 0.90
    strict_config = AlertEngineConfig(min_plate_confidence=0.90, demo_mode=False)
    engine = AlertEngine(config=strict_config)

    # Confidence 0.85 would pass default (0.80) but must fail strict (0.90)
    alert = engine.evaluate_plate_blacklist(
        plate_text="DL01AB1234",
        ocr_confidence=0.85,
        camera_id="CAM-001",
    )
    assert alert is None

    # Confidence 0.93 passes strict
    alert_passed = engine.evaluate_plate_blacklist(
        plate_text="DL01AB1234",
        ocr_confidence=0.93,
        camera_id="CAM-001",
    )
    assert alert_passed is not None


# =====================================================================
# 6. API EVALUATION ENDPOINT (POST /api/v1/alerts/evaluate)
# =====================================================================

def test_api_evaluate_blacklist_valid():
    """Verify POST /api/v1/alerts/evaluate triggers a valid BLACKLIST alert."""
    params = {
        "event_type": "BLACKLIST",
        "camera_id": "CAM-001",
        "plate_text": "DL01AB1234",
        "ocr_confidence": 0.95,
        "global_vehicle_id": "GLOBAL-TEST-001",
    }
    resp = client.post("/api/v1/alerts/evaluate", params=params)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data is not None
    assert data["type"] == "BLACKLIST"
    assert data["severity"] == "CRITICAL"
    assert data["plate_text"] == "DL01AB1234"
    assert "evidence" in data


def test_api_evaluate_blacklist_low_confidence_suppressed():
    """Verify POST /api/v1/alerts/evaluate returns null for low confidence OCR."""
    params = {
        "event_type": "BLACKLIST",
        "camera_id": "CAM-001",
        "plate_text": "DL01AB1234",
        "ocr_confidence": 0.50,  # Below threshold
    }
    resp = client.post("/api/v1/alerts/evaluate", params=params)
    assert resp.status_code == 200
    assert resp.json() is None


def test_api_evaluate_speed_anomaly():
    """Verify POST /api/v1/alerts/evaluate triggers an ANOMALY alert on excessive speed."""
    params = {
        "event_type": "ANOMALY",
        "camera_id": "CAM-002",
        "from_camera_id": "CAM-001",
        "speed_kmh": 142.0,
        "elapsed_time_sec": 25.0,
        "distance_meters": 980.0,
        "global_vehicle_id": "GLOBAL-SPEEDER-API",
    }
    resp = client.post("/api/v1/alerts/evaluate", params=params)
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert data["type"] == "ANOMALY"
    assert data["severity"] == "HIGH"
    assert data["evidence"]["speed_kmh"] == 142.0


def test_api_evaluate_congestion():
    """Verify POST /api/v1/alerts/evaluate triggers a CONGESTION alert on high density."""
    params = {
        "event_type": "CONGESTION",
        "camera_id": "CAM-003",
        "active_density": 22,
    }
    resp = client.post("/api/v1/alerts/evaluate", params=params)
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert data["type"] == "CONGESTION"
    assert data["evidence"]["active_density"] == 22
