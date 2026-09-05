"""
Unit and Integration Tests for CITYVISION AI DEMO MODE
Problem Statement ID: SIH26127

Verifies:
1. Complete 11-stage pipeline execution across Camera 01 (North), Camera 02 (Central), and Camera 03 (South).
2. Strict database isolation (records stored ONLY in cityvision_demo.db, production DB untouched).
3. Honest model provenance and [DEMO DATA] labeling.
4. Watchlist Blacklist Alert generation on verified stolen vehicle DL01AB1234.
5. System operational mode switching between REAL and DEMO.
6. REST API endpoints for demo execution and status.
"""
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.demo_pipeline import demo_pipeline, DemoStage, DEMO_CAMERAS
import backend.app.api.routes as routes_module


@pytest.fixture(autouse=True)
def cleanup_demo_state():
    """Ensures clean demo pipeline state before and after each test."""
    routes_module.ACTIVE_SYSTEM_MODE = "real"
    demo_pipeline.reset_demo()
    yield
    demo_pipeline.reset_demo()
    routes_module.ACTIVE_SYSTEM_MODE = "real"


@pytest.fixture
def client():
    return TestClient(app)


def test_demo_pipeline_11_stages_sequence():
    """Tests the sequential advancement through all 11 stages of the demo pipeline."""
    demo_pipeline.reset_demo()
    assert demo_pipeline.current_stage == DemoStage.IDLE

    # Step 1: Vehicle enters Camera 01 (North)
    s1 = demo_pipeline.step(1)
    assert s1["current_stage"] == 1
    assert "North" in s1["stage_info"]["title"]

    # Step 2: Vehicle is detected (YOLOv8)
    s2 = demo_pipeline.step(2)
    assert s2["current_stage"] == 2
    assert s2["stage_info"]["provenance"]["is_live_model_output"] is True

    # Step 3: Local track assigned
    s3 = demo_pipeline.step(3)
    assert s3["current_stage"] == 3

    # Step 4: ANPR plate attempted
    s4 = demo_pipeline.step(4)
    assert s4["current_stage"] == 4

    # Step 5: Re-ID embedding generated
    s5 = demo_pipeline.step(5)
    assert s5["current_stage"] == 5

    # Step 6: Observation stored in isolated demo DB
    s6 = demo_pipeline.step(6)
    assert s6["current_stage"] == 6

    # Step 7: Cross-camera matched with CAM-002 (Central)
    s7 = demo_pipeline.step(7)
    assert s7["current_stage"] == 7

    # Step 8: Global Vehicle ID assigned
    s8 = demo_pipeline.step(8)
    assert s8["current_stage"] == 8
    assert s8["active_vehicle"] is not None
    assert s8["active_vehicle"]["primary_plate"] == "DL01AB1234"

    # Step 9: Trajectory transition built
    s9 = demo_pipeline.step(9)
    assert s9["current_stage"] == 9
    assert s9["trajectory"] is not None
    assert len(s9["trajectory"]["movements"]) == 2

    # Step 10: Dashboard telemetry updated
    s10 = demo_pipeline.step(10)
    assert s10["current_stage"] == 10

    # Step 11: Watchlist Blacklist Alert generated
    s11 = demo_pipeline.step(11)
    assert s11["current_stage"] == 11
    assert len(s11["alerts"]) == 1
    assert s11["alerts"][0]["type"] == "BLACKLIST"
    assert s11["alerts"][0]["severity"] == "CRITICAL"


def test_strict_database_isolation():
    """
    CRITICAL TEST: Ensures demo records are persisted in data/cityvision_demo.db
    and ZERO demo records are written into the production database.
    """
    demo_pipeline.run_full()

    # Verify demo database contains demo vehicle
    assert os.path.exists(demo_pipeline.demo_db_path)
    with sqlite3.connect(demo_pipeline.demo_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM global_vehicles WHERE global_vehicle_id = 'GV-DEMO-001'")
        count = cursor.fetchone()[0]
        assert count == 1, "Demo vehicle must exist in isolated demo database"

        cursor.execute("SELECT COUNT(*) FROM vehicle_observations WHERE global_vehicle_id = 'GV-DEMO-001'")
        obs_count = cursor.fetchone()[0]
        assert obs_count == 3, "3 observations (North, Central, South) must exist in demo DB"

    # Check production database (if SQLite exists) to ensure zero demo records exist
    prod_db_path = "data/cityvision.db"
    if os.path.exists(prod_db_path):
        with sqlite3.connect(prod_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM global_vehicles WHERE global_vehicle_id = 'GV-DEMO-001'")
            prod_count = cursor.fetchone()[0]
            assert prod_count == 0, "Production database must NEVER contain demo records"


def test_system_mode_switch_api(client):
    """Tests switching between REAL and DEMO mode via REST API."""
    # 1. Default mode is 'real'
    r1 = client.get("/api/v1/system/mode")
    assert r1.status_code == 200
    assert r1.json()["mode"] == "real"
    assert r1.json()["is_demo"] is False

    # 2. Switch to 'demo'
    r2 = client.post("/api/v1/system/mode", json={"mode": "demo"})
    assert r2.status_code == 200
    assert r2.json()["mode"] == "demo"
    assert r2.json()["is_demo"] is True

    # 3. In demo mode, cameras endpoint returns demo cameras (CAM-001 North, CAM-002 Central, CAM-003 South)
    rcam = client.get("/api/v1/cameras")
    assert rcam.status_code == 200
    cams = rcam.json()
    assert len(cams) == 3
    assert cams[0]["id"] == "CAM-001"
    assert cams[1]["id"] == "CAM-002"
    assert cams[2]["id"] == "CAM-003"

    # 4. Switch back to 'real'
    r3 = client.post("/api/v1/system/mode", json={"mode": "real"})
    assert r3.status_code == 200
    assert r3.json()["mode"] == "real"
    assert r3.json()["is_demo"] is False

    # Invalid mode rejected with 400
    r_err = client.post("/api/v1/system/mode", json={"mode": "unsupported_mode"})
    assert r_err.status_code == 400


def test_demo_api_controls(client):
    """Tests /api/v1/demo/start, /step, /status, /reset, /full endpoints."""
    # Reset
    r_reset = client.post("/api/v1/demo/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["current_stage"] == 0

    # Start
    r_start = client.post("/api/v1/demo/start")
    assert r_start.status_code == 200
    assert r_start.json()["current_stage"] == 1

    # Step
    r_step = client.post("/api/v1/demo/step")
    assert r_step.status_code == 200
    assert r_step.json()["current_stage"] == 2

    # Status
    r_stat = client.get("/api/v1/demo/status")
    assert r_stat.status_code == 200
    assert r_stat.json()["current_stage"] == 2
    assert len(r_stat.json()["stages_progress"]) == 11

    # Full
    r_full = client.post("/api/v1/demo/full")
    assert r_full.status_code == 200
    assert r_full.json()["current_stage"] == 11
    assert r_full.json()["active_vehicle"]["primary_plate"] == "DL01AB1234"
    assert len(r_full.json()["alerts"]) == 1
