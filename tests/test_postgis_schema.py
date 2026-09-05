"""
Tests for PostgreSQL & PostGIS Persistent Storage, Schema, Migrations, and Seed Data
Problem Statement ID: SIH26127
"""
import subprocess
import sys
from pathlib import Path
import pytest
from geoalchemy2 import Geometry
from sqlalchemy import inspect

from backend.app.core.config import BASE_DIR, settings
from backend.app.db.models import (
    Base,
    Camera,
    Vehicle,
    Track,
    Observation,
    OCRObservation,
    ReIDEmbedding,
    VehicleMatch,
    Trajectory,
    Alert,
)
from backend.app.db.database import DatabaseManager


def test_schema_all_tables_registered():
    """Verify that all 9 required tables are registered in SQLAlchemy metadata."""
    expected_tables = {
        "cameras",
        "vehicles",
        "tracks",
        "observations",
        "ocr_observations",
        "reid_embeddings",
        "vehicle_matches",
        "trajectories",
        "alerts",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(registered_tables), (
        f"Missing tables in metadata: {expected_tables - registered_tables}"
    )


def test_postgis_spatial_geometry_definitions():
    """Verify PostGIS geometry columns have correct geometry_type, SRID 4326, and spatial index flag."""
    # 1. Camera geom (Point, 4326)
    camera_geom = Camera.__table__.columns["geom"].type
    assert isinstance(camera_geom, Geometry)
    assert camera_geom.geometry_type.upper() == "POINT"
    assert camera_geom.srid == 4326
    assert camera_geom.spatial_index is True

    # 2. Observation geom (Point, 4326)
    obs_geom = Observation.__table__.columns["geom"].type
    assert isinstance(obs_geom, Geometry)
    assert obs_geom.geometry_type.upper() == "POINT"
    assert obs_geom.srid == 4326
    assert obs_geom.spatial_index is True

    # 3. Trajectory geom_path (LineString, 4326)
    traj_geom = Trajectory.__table__.columns["geom_path"].type
    assert isinstance(traj_geom, Geometry)
    assert traj_geom.geometry_type.upper() == "LINESTRING"
    assert traj_geom.srid == 4326
    assert traj_geom.spatial_index is True

    # 4. Alert geom (Point, 4326)
    alert_geom = Alert.__table__.columns["geom"].type
    assert isinstance(alert_geom, Geometry)
    assert alert_geom.geometry_type.upper() == "POINT"
    assert alert_geom.srid == 4326
    assert alert_geom.spatial_index is True


def test_foreign_key_relationships():
    """Verify cascading rules and foreign key integrity across tables."""
    # Track foreign keys
    track_fks = {fk.target_fullname for fk in Track.__table__.foreign_keys}
    assert "cameras.camera_id" in track_fks
    assert "vehicles.global_vehicle_id" in track_fks

    # Observation foreign keys
    obs_fks = {fk.target_fullname for fk in Observation.__table__.foreign_keys}
    assert "cameras.camera_id" in obs_fks
    assert "vehicles.global_vehicle_id" in obs_fks

    # OCR observation foreign keys
    ocr_fks = {fk.target_fullname for fk in OCRObservation.__table__.foreign_keys}
    assert "observations.observation_id" in ocr_fks
    assert "cameras.camera_id" in ocr_fks

    # ReID embedding foreign keys
    reid_fks = {fk.target_fullname for fk in ReIDEmbedding.__table__.foreign_keys}
    assert "observations.observation_id" in reid_fks
    assert "cameras.camera_id" in reid_fks

    # VehicleMatch foreign keys
    match_fks = {fk.target_fullname for fk in VehicleMatch.__table__.foreign_keys}
    assert "vehicles.global_vehicle_id" in match_fks
    assert "observations.observation_id" in match_fks
    assert "cameras.camera_id" in match_fks

    # Trajectory foreign key
    traj_fks = {fk.target_fullname for fk in Trajectory.__table__.foreign_keys}
    assert "vehicles.global_vehicle_id" in traj_fks

    # Alert foreign keys
    alert_fks = {fk.target_fullname for fk in Alert.__table__.foreign_keys}
    assert "cameras.camera_id" in alert_fks
    assert "vehicles.global_vehicle_id" in alert_fks


def test_index_definitions():
    """Verify performance indices for high-frequency queries."""
    # Check observation indexes
    obs_indices = {idx.name for idx in Observation.__table__.indexes}
    assert "idx_observations_camera_time" in obs_indices
    assert "idx_observations_global_time" in obs_indices

    # Check alert indexes
    alert_indices = {idx.name for idx in Alert.__table__.indexes}
    assert "idx_alerts_status_severity" in alert_indices

    # Check track indexes
    track_indices = {idx.name for idx in Track.__table__.indexes}
    assert "idx_tracks_camera_local" in track_indices


def test_alembic_offline_sql_generation():
    """Execute Alembic offline migration generation and verify PostGIS DDL."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
    )
    assert result.returncode == 0, f"Alembic failed: {result.stderr}"
    sql_output = result.stdout
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql_output
    assert "CREATE TABLE cameras" in sql_output
    assert "CREATE TABLE vehicles" in sql_output
    assert "CREATE TABLE observations" in sql_output
    assert "CREATE TABLE ocr_observations" in sql_output
    assert "CREATE TABLE reid_embeddings" in sql_output
    assert "CREATE TABLE vehicle_matches" in sql_output
    assert "CREATE TABLE trajectories" in sql_output
    assert "CREATE TABLE alerts" in sql_output
    assert "geometry(POINT,4326)" in sql_output
    assert "geometry(LINESTRING,4326)" in sql_output
    assert "USING gist (geom)" in sql_output


def test_standalone_sql_migration_script():
    """Verify standalone SQL migration script exists and has valid PostGIS DDL."""
    sql_path = BASE_DIR / "backend" / "app" / "db" / "migrations" / "001_initial_postgis_schema.sql"
    assert sql_path.exists()
    content = sql_path.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS postgis;" in content
    assert "CREATE TABLE IF NOT EXISTS cameras" in content
    assert "CREATE TABLE IF NOT EXISTS vehicles" in content
    assert "CREATE TABLE IF NOT EXISTS trajectories" in content
    assert "idx_cameras_geom" in content
    assert "idx_trajectories_geom_path" in content


def test_explicit_demo_seed_data_disclaimer_and_content():
    """Verify demo seed files are strictly annotated as [DEMO / SEED DATA ONLY]."""
    seed_sql = BASE_DIR / "backend" / "app" / "db" / "seeds" / "demo_seed_data.sql"
    assert seed_sql.exists()
    sql_text = seed_sql.read_text(encoding="utf-8")
    assert "[DEMO / SEED DATA ONLY - NOT ACTUAL SENSOR READINGS]" in sql_text
    assert "CAM-001" in sql_text
    assert "CAM-005" in sql_text
    assert "GV-DEMO-9901" in sql_text
    assert "ST_MakeLine" in sql_text

    seed_py = BASE_DIR / "backend" / "app" / "db" / "seeds" / "demo_seed_data.py"
    assert seed_py.exists()
    py_text = seed_py.read_text(encoding="utf-8")
    assert "[DEMO / SEED DATA ONLY - NOT ACTUAL SENSOR READINGS]" in py_text
    assert "load_demo_seed_data" in py_text


def test_database_manager_postgres_detection():
    """Verify DatabaseManager parses postgresql URLs and prepares SQLAlchemy engines."""
    pg_url = "postgresql://cityvision:cityvision@localhost:5432/cityvision_db"
    db_m = DatabaseManager(db_url=pg_url)
    assert db_m.is_postgres is True
    assert db_m.get_engine() is not None
    assert str(db_m.get_engine().url).startswith("postgresql+psycopg://")
