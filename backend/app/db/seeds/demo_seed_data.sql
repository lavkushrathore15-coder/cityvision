-- ============================================================================
-- CITYVISION AI - PostgreSQL & PostGIS Demo Seed Data
-- [DEMO / SEED DATA ONLY - NOT ACTUAL SENSOR READINGS]
-- Problem Statement ID: SIH26127
-- Description:
--   Populates standard CCTV camera nodes from topology configuration and
--   inserts simulated tracking observations, cross-camera associations,
--   reconstructed trajectory, and watchlist alert for validation & testing.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. CCTV Camera Nodes (from config/cameras.yaml)
-- Coordinates in WGS-84 (SRID 4326): ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
-- ----------------------------------------------------------------------------
INSERT INTO cameras (camera_id, camera_name, location_name, geom, latitude, longitude, heading_deg, fps, source_type, stream_uri, status)
VALUES
('CAM-001', 'North Gateway Intersection', 'North Corridor Junction', ST_SetSRID(ST_MakePoint(77.2090, 28.6139), 4326), 28.6139, 77.2090, 45.0, 15, 'file', 'data/sample_videos/cam_01.mp4', 'configured'),
('CAM-002', 'Central Ring Road Eastbound', 'East Ring Road', ST_SetSRID(ST_MakePoint(77.2150, 28.6180), 4326), 28.6180, 77.2150, 90.0, 15, 'file', 'data/sample_videos/cam_02.mp4', 'configured'),
('CAM-003', 'South Metro Junction', 'South Arterial Interchange', ST_SetSRID(ST_MakePoint(77.2120, 28.6090), 4326), 28.6090, 77.2120, 180.0, 15, 'file', 'data/sample_videos/cam_03.mp4', 'configured'),
('CAM-004', 'West Tech Park Avenue', 'Tech Corridor Gateway', ST_SetSRID(ST_MakePoint(77.2020, 28.6145), 4326), 28.6145, 77.2020, 270.0, 15, 'file', 'data/sample_videos/cam_04.mp4', 'configured'),
('CAM-005', 'City Terminal Outer Exit', 'North-East Highway Merge', ST_SetSRID(ST_MakePoint(77.2185, 28.6220), 4326), 28.6220, 77.2185, 120.0, 15, 'file', 'data/sample_videos/cam_05.mp4', 'configured')
ON CONFLICT (camera_id) DO UPDATE SET
    camera_name = EXCLUDED.camera_name,
    geom = EXCLUDED.geom,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    stream_uri = EXCLUDED.stream_uri;

-- ----------------------------------------------------------------------------
-- 2. Demo Vehicle: RJ14-AB-1234
-- Simulated vehicle tracked across CAM-001 -> CAM-002 -> CAM-005
-- ----------------------------------------------------------------------------
INSERT INTO vehicles (global_vehicle_id, primary_plate, vehicle_class, first_seen, last_seen, total_observations, total_cameras_visited, is_flagged, flag_reason)
VALUES (
    'GV-DEMO-9901',
    'RJ14AB1234',
    'car',
    '2026-09-04 10:00:00+00',
    '2026-09-04 10:08:45+00',
    3,
    3,
    true,
    'Stolen vehicle alert match in NCR database'
)
ON CONFLICT (global_vehicle_id) DO UPDATE SET
    primary_plate = EXCLUDED.primary_plate,
    last_seen = EXCLUDED.last_seen,
    is_flagged = EXCLUDED.is_flagged,
    flag_reason = EXCLUDED.flag_reason;

-- ----------------------------------------------------------------------------
-- 3. Demo Tracks (Intra-camera tracks for CAM-001, CAM-002, CAM-005)
-- ----------------------------------------------------------------------------
INSERT INTO tracks (track_id, camera_id, local_track_id, global_vehicle_id, vehicle_class, start_time, end_time, detection_confidence, total_frames)
VALUES
('TRK-CAM001-01', 'CAM-001', 1, 'GV-DEMO-9901', 'car', '2026-09-04 10:00:00+00', '2026-09-04 10:00:20+00', 0.94, 30),
('TRK-CAM002-04', 'CAM-002', 4, 'GV-DEMO-9901', 'car', '2026-09-04 10:04:10+00', '2026-09-04 10:04:35+00', 0.91, 28),
('TRK-CAM005-02', 'CAM-005', 2, 'GV-DEMO-9901', 'car', '2026-09-04 10:08:20+00', '2026-09-04 10:08:45+00', 0.95, 32)
ON CONFLICT (track_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. Demo Observations (Frame-level detections with Point geometries)
-- ----------------------------------------------------------------------------
INSERT INTO observations (observation_id, global_vehicle_id, camera_id, local_track_id, frame_number, timestamp, geom, latitude, longitude, bbox_x1, bbox_y1, bbox_x2, bbox_y2, detection_confidence, source_frame_uri)
VALUES
('OBS-001-1001', 'GV-DEMO-9901', 'CAM-001', 1, 15, '2026-09-04 10:00:10+00', ST_SetSRID(ST_MakePoint(77.2090, 28.6139), 4326), 28.6139, 77.2090, 120.0, 180.0, 480.0, 420.0, 0.94, 'data/sample_images/bus.jpg'),
('OBS-002-2004', 'GV-DEMO-9901', 'CAM-002', 4, 20, '2026-09-04 10:04:25+00', ST_SetSRID(ST_MakePoint(77.2150, 28.6180), 4326), 28.6180, 77.2150, 140.0, 210.0, 510.0, 450.0, 0.91, 'data/sample_images/bus.jpg'),
('OBS-005-5002', 'GV-DEMO-9901', 'CAM-005', 2, 18, '2026-09-04 10:08:35+00', ST_SetSRID(ST_MakePoint(77.2185, 28.6220), 4326), 28.6220, 77.2185, 110.0, 190.0, 490.0, 430.0, 0.95, 'data/sample_images/bus.jpg')
ON CONFLICT (observation_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 5. Demo OCR Observations (License Plate Reads)
-- ----------------------------------------------------------------------------
INSERT INTO ocr_observations (ocr_id, observation_id, camera_id, local_track_id, frame_number, timestamp, raw_text, normalized_text, ocr_confidence, plate_bbox_x1, plate_bbox_y1, plate_bbox_x2, plate_bbox_y2, is_blurry)
VALUES
('OCR-001-1', 'OBS-001-1001', 'CAM-001', 1, 15, '2026-09-04 10:00:10+00', 'RJ 14 AB 1234', 'RJ14AB1234', 0.93, 220.0, 350.0, 380.0, 395.0, false),
('OCR-002-1', 'OBS-002-2004', 'CAM-002', 4, 20, '2026-09-04 10:04:25+00', 'RJ14-AB-1234', 'RJ14AB1234', 0.89, 240.0, 370.0, 400.0, 415.0, false),
('OCR-005-1', 'OBS-005-5002', 'CAM-005', 2, 18, '2026-09-04 10:08:35+00', 'RJ14 AB 1234', 'RJ14AB1234', 0.91, 215.0, 360.0, 375.0, 405.0, false)
ON CONFLICT (ocr_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 6. Demo Re-ID Embeddings (256-dim L2-normalized vector)
-- ----------------------------------------------------------------------------
INSERT INTO reid_embeddings (embedding_id, observation_id, camera_id, local_track_id, frame_number, timestamp, model_identifier, dimension, distance_metric, embedding, embedding_preview)
VALUES
('REID-001-1', 'OBS-001-1001', 'CAM-001', 1, 15, '2026-09-04 10:00:10+00', 'yolov8n-backbone-256', 256, 'cosine', decode(repeat('01020304', 256), 'hex'), '[0.062, 0.045, -0.012, 0.088, -0.034]'),
('REID-002-1', 'OBS-002-2004', 'CAM-002', 4, 20, '2026-09-04 10:04:25+00', 'yolov8n-backbone-256', 256, 'cosine', decode(repeat('01020304', 256), 'hex'), '[0.060, 0.044, -0.010, 0.086, -0.033]'),
('REID-005-1', 'OBS-005-5002', 'CAM-005', 2, 18, '2026-09-04 10:08:35+00', 'yolov8n-backbone-256', 256, 'cosine', decode(repeat('01020304', 256), 'hex'), '[0.061, 0.046, -0.011, 0.087, -0.035]')
ON CONFLICT (embedding_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 7. Demo Vehicle Matches (Cross-Camera Association)
-- ----------------------------------------------------------------------------
INSERT INTO vehicle_matches (match_id, global_vehicle_id, source_observation_id, target_observation_id, source_camera_id, target_camera_id, match_score, confidence_tier, plate_score, reid_score, spatial_score, temporal_score, explanation, evidence_breakdown)
VALUES
(
    'MATCH-001-002',
    'GV-DEMO-9901',
    'OBS-001-1001',
    'OBS-002-2004',
    'CAM-001',
    'CAM-002',
    0.92,
    'HIGH',
    1.0,
    0.88,
    0.95,
    0.90,
    'High confidence match: Exact plate match RJ14AB1234 with Re-ID similarity 0.88 and feasible transit time 255s (13.7 km/h)',
    '{"plate_match": true, "plate_raw": "RJ14AB1234", "ocr_confidence": 0.91, "reid_similarity": 0.88, "distance_km": 0.97, "elapsed_seconds": 255, "transit_speed_kmh": 13.7, "is_speed_feasible": true}'::jsonb
),
(
    'MATCH-002-005',
    'GV-DEMO-9901',
    'OBS-002-2004',
    'OBS-005-5002',
    'CAM-002',
    'CAM-005',
    0.93,
    'HIGH',
    1.0,
    0.89,
    0.94,
    0.92,
    'High confidence match: Exact plate match RJ14AB1234 with Re-ID similarity 0.89 and feasible transit time 250s (10.2 km/h)',
    '{"plate_match": true, "plate_raw": "RJ14AB1234", "ocr_confidence": 0.90, "reid_similarity": 0.89, "distance_km": 0.71, "elapsed_seconds": 250, "transit_speed_kmh": 10.2, "is_speed_feasible": true}'::jsonb
)
ON CONFLICT (match_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 8. Demo Trajectory (PostGIS LineString Geometry Path)
-- Connecting CAM-001 (77.2090, 28.6139) -> CAM-002 (77.2150, 28.6180) -> CAM-005 (77.2185, 28.6220)
-- ----------------------------------------------------------------------------
INSERT INTO trajectories (trajectory_id, global_vehicle_id, start_time, end_time, total_distance_km, avg_speed_kmh, visited_cameras_count, geom_path, waypoints, is_spatial_available)
VALUES (
    'TRJ-DEMO-9901',
    'GV-DEMO-9901',
    '2026-09-04 10:00:10+00',
    '2026-09-04 10:08:35+00',
    1.68,
    12.0,
    3,
    ST_SetSRID(ST_MakeLine(ARRAY[
        ST_MakePoint(77.2090, 28.6139),
        ST_MakePoint(77.2150, 28.6180),
        ST_MakePoint(77.2185, 28.6220)
    ]), 4326),
    '[
        {"camera_id": "CAM-001", "name": "North Gateway Intersection", "latitude": 28.6139, "longitude": 77.2090, "timestamp": "2026-09-04T10:00:10Z", "plate": "RJ14AB1234"},
        {"camera_id": "CAM-002", "name": "Central Ring Road Eastbound", "latitude": 28.6180, "longitude": 77.2150, "timestamp": "2026-09-04T10:04:25Z", "plate": "RJ14AB1234"},
        {"camera_id": "CAM-005", "name": "City Terminal Outer Exit", "latitude": 28.6220, "longitude": 77.2185, "timestamp": "2026-09-04T10:08:35Z", "plate": "RJ14AB1234"}
    ]'::jsonb,
    true
)
ON CONFLICT (trajectory_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 9. Demo Alerts (Watchlist Stolen Vehicle Hit)
-- ----------------------------------------------------------------------------
INSERT INTO alerts (alert_id, alert_type, severity, global_vehicle_id, plate_text, camera_id, geom, latitude, longitude, timestamp, details, status)
VALUES (
    'ALT-DEMO-101',
    'WATCHLIST_HIT',
    'CRITICAL',
    'GV-DEMO-9901',
    'RJ14AB1234',
    'CAM-005',
    ST_SetSRID(ST_MakePoint(77.2185, 28.6220), 4326),
    28.6220,
    77.2185,
    '2026-09-04 10:08:36+00',
    '{"category": "STOLEN_VEHICLE", "incident_id": "FIR-2026-8812", "vehicle_model": "White Hatchback", "last_known_camera": "City Terminal Outer Exit", "confidence": 0.95}'::jsonb,
    'NEW'
)
ON CONFLICT (alert_id) DO NOTHING;
