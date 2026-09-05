-- ============================================================================
-- CITYVISION AI - PostgreSQL & PostGIS Schema Migration
-- Migration: 001_initial_postgis_schema
-- Problem Statement ID: SIH26127
-- Target Database: PostgreSQL 16+ with PostGIS 3.4+
-- ============================================================================

-- Step 1: Enable PostGIS extension for spatial types (POINT, LINESTRING) and spatial indexing (GIST)
CREATE EXTENSION IF NOT EXISTS postgis;

-- ----------------------------------------------------------------------------
-- Table: cameras
-- Stores registered CCTV camera nodes with WGS-84 Point coordinates.
-- Note: Video streams and files are NOT stored in PostgreSQL; stream_uri stores
-- the RTSP/file URI reference.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cameras (
    camera_id VARCHAR(64) PRIMARY KEY,
    camera_name VARCHAR(128) NOT NULL,
    location_name VARCHAR(256),
    geom GEOMETRY(Point, 4326),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    heading_deg REAL DEFAULT 0.0,
    fps INTEGER DEFAULT 15,
    source_type VARCHAR(32) DEFAULT 'file',
    stream_uri TEXT,
    status VARCHAR(32) DEFAULT 'configured',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Spatial GIST index for camera proximity and GIS queries
CREATE INDEX IF NOT EXISTS idx_cameras_geom ON cameras USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_cameras_status ON cameras (status);

-- ----------------------------------------------------------------------------
-- Table: vehicles
-- Persistent global vehicle identity resolved across multiple cameras.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicles (
    global_vehicle_id VARCHAR(64) PRIMARY KEY,
    primary_plate VARCHAR(32),
    vehicle_class VARCHAR(32) NOT NULL DEFAULT 'car',
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    total_observations INTEGER NOT NULL DEFAULT 1,
    total_cameras_visited INTEGER NOT NULL DEFAULT 1,
    is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vehicles_primary_plate ON vehicles (primary_plate);
CREATE INDEX IF NOT EXISTS idx_vehicles_class ON vehicles (vehicle_class);
CREATE INDEX IF NOT EXISTS idx_vehicles_is_flagged ON vehicles (is_flagged);
CREATE INDEX IF NOT EXISTS idx_vehicles_last_seen ON vehicles (last_seen DESC);

-- ----------------------------------------------------------------------------
-- Table: tracks
-- Single-camera multi-object continuous tracking session.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tracks (
    track_id VARCHAR(96) PRIMARY KEY,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    local_track_id INTEGER NOT NULL,
    global_vehicle_id VARCHAR(64) REFERENCES vehicles(global_vehicle_id) ON DELETE SET NULL,
    vehicle_class VARCHAR(32) NOT NULL DEFAULT 'car',
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    detection_confidence REAL NOT NULL,
    total_frames INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tracks_camera_local ON tracks (camera_id, local_track_id);
CREATE INDEX IF NOT EXISTS idx_tracks_global_vehicle ON tracks (global_vehicle_id);
CREATE INDEX IF NOT EXISTS idx_tracks_time ON tracks (start_time, end_time);

-- ----------------------------------------------------------------------------
-- Table: observations
-- Frame-level vehicle detection with camera location, bounding box, and confidence.
-- Note: Raw frames are stored on disk/storage; source_frame_uri references the file.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS observations (
    observation_id VARCHAR(96) PRIMARY KEY,
    global_vehicle_id VARCHAR(64) NOT NULL REFERENCES vehicles(global_vehicle_id) ON DELETE CASCADE,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    local_track_id INTEGER NOT NULL,
    frame_number INTEGER NOT NULL DEFAULT 0,
    timestamp TIMESTAMPTZ NOT NULL,
    geom GEOMETRY(Point, 4326),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    bbox_x1 REAL NOT NULL,
    bbox_y1 REAL NOT NULL,
    bbox_x2 REAL NOT NULL,
    bbox_y2 REAL NOT NULL,
    detection_confidence REAL NOT NULL DEFAULT 1.0,
    source_frame_uri TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Spatial and temporal indexes for high-frequency queries
CREATE INDEX IF NOT EXISTS idx_observations_geom ON observations USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_observations_camera_time ON observations (camera_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_observations_global_time ON observations (global_vehicle_id, timestamp ASC);
CREATE INDEX IF NOT EXISTS idx_observations_timestamp ON observations (timestamp);

-- ----------------------------------------------------------------------------
-- Table: ocr_observations
-- License plate OCR detections associated with a vehicle observation.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ocr_observations (
    ocr_id VARCHAR(96) PRIMARY KEY,
    observation_id VARCHAR(96) NOT NULL REFERENCES observations(observation_id) ON DELETE CASCADE,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    local_track_id INTEGER NOT NULL,
    frame_number INTEGER NOT NULL DEFAULT 0,
    timestamp TIMESTAMPTZ NOT NULL,
    raw_text VARCHAR(64) NOT NULL,
    normalized_text VARCHAR(64) NOT NULL,
    ocr_confidence REAL NOT NULL,
    plate_bbox_x1 REAL,
    plate_bbox_y1 REAL,
    plate_bbox_x2 REAL,
    plate_bbox_y2 REAL,
    is_blurry BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ocr_normalized_plate ON ocr_observations (normalized_text);
CREATE INDEX IF NOT EXISTS idx_ocr_observation_id ON ocr_observations (observation_id);
CREATE INDEX IF NOT EXISTS idx_ocr_camera_id ON ocr_observations (camera_id);
CREATE INDEX IF NOT EXISTS idx_ocr_timestamp ON ocr_observations (timestamp);

-- ----------------------------------------------------------------------------
-- Table: reid_embeddings
-- Deep convolutional visual appearance embedding vectors for re-identification.
-- Embeddings are stored as packed 32-bit float byte arrays (256 * 4 = 1024 bytes).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reid_embeddings (
    embedding_id VARCHAR(96) PRIMARY KEY,
    observation_id VARCHAR(96) NOT NULL REFERENCES observations(observation_id) ON DELETE CASCADE,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    local_track_id INTEGER NOT NULL,
    frame_number INTEGER NOT NULL DEFAULT 0,
    timestamp TIMESTAMPTZ NOT NULL,
    model_identifier VARCHAR(64) NOT NULL,
    dimension INTEGER NOT NULL DEFAULT 256,
    distance_metric VARCHAR(32) NOT NULL DEFAULT 'cosine',
    embedding BYTEA NOT NULL,
    embedding_preview TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reid_obs_id ON reid_embeddings (observation_id);
CREATE INDEX IF NOT EXISTS idx_reid_camera_track ON reid_embeddings (camera_id, local_track_id);
CREATE INDEX IF NOT EXISTS idx_reid_timestamp ON reid_embeddings (timestamp);

-- ----------------------------------------------------------------------------
-- Table: vehicle_matches
-- Cross-camera association records with explainable multi-signal evidence breakdown.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicle_matches (
    match_id VARCHAR(96) PRIMARY KEY,
    global_vehicle_id VARCHAR(64) NOT NULL REFERENCES vehicles(global_vehicle_id) ON DELETE CASCADE,
    source_observation_id VARCHAR(96) NOT NULL REFERENCES observations(observation_id) ON DELETE CASCADE,
    target_observation_id VARCHAR(96) NOT NULL REFERENCES observations(observation_id) ON DELETE CASCADE,
    source_camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    target_camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    match_score REAL NOT NULL,
    confidence_tier VARCHAR(32) NOT NULL,
    plate_score REAL,
    reid_score REAL,
    spatial_score REAL,
    temporal_score REAL,
    explanation TEXT NOT NULL,
    evidence_breakdown JSONB NOT NULL,
    matched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_matches_global_vehicle ON vehicle_matches (global_vehicle_id);
CREATE INDEX IF NOT EXISTS idx_matches_confidence_tier ON vehicle_matches (confidence_tier);
CREATE INDEX IF NOT EXISTS idx_matches_pair ON vehicle_matches (source_camera_id, target_camera_id, matched_at);
CREATE INDEX IF NOT EXISTS idx_matches_evidence ON vehicle_matches USING GIN (evidence_breakdown);

-- ----------------------------------------------------------------------------
-- Table: trajectories
-- Chronologically reconstructed multi-camera trajectory with PostGIS LineString geometry.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trajectories (
    trajectory_id VARCHAR(96) PRIMARY KEY,
    global_vehicle_id VARCHAR(64) NOT NULL REFERENCES vehicles(global_vehicle_id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    total_distance_km REAL,
    avg_speed_kmh REAL,
    visited_cameras_count INTEGER NOT NULL DEFAULT 1,
    geom_path GEOMETRY(LineString, 4326),
    waypoints JSONB NOT NULL,
    is_spatial_available BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Spatial GIST index for trajectory corridor and spatial bounding-box searches
CREATE INDEX IF NOT EXISTS idx_trajectories_geom_path ON trajectories USING GIST (geom_path);
CREATE INDEX IF NOT EXISTS idx_trajectories_global_vehicle ON trajectories (global_vehicle_id);
CREATE INDEX IF NOT EXISTS idx_trajectories_time_range ON trajectories (start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_trajectories_waypoints ON trajectories USING GIN (waypoints);

-- ----------------------------------------------------------------------------
-- Table: alerts
-- Urban traffic and surveillance alerts (watchlist hits, speeding, anomalies).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    alert_id VARCHAR(96) PRIMARY KEY,
    alert_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    global_vehicle_id VARCHAR(64) REFERENCES vehicles(global_vehicle_id) ON DELETE SET NULL,
    plate_text VARCHAR(32),
    camera_id VARCHAR(64) REFERENCES cameras(camera_id) ON DELETE SET NULL,
    geom GEOMETRY(Point, 4326),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    timestamp TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'NEW',
    acknowledged_by VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_geom ON alerts USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_alerts_status_severity ON alerts (status, severity, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_plate ON alerts (plate_text);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_details ON alerts USING GIN (details);
