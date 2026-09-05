"""
Demo Seed Data Loader for CITYVISION AI
[DEMO / SEED DATA ONLY - NOT ACTUAL SENSOR READINGS]
Problem Statement ID: SIH26127

Programmatically populates test camera nodes, simulated multi-camera tracks,
observations, OCR reads, Re-ID embeddings, vehicle matches, and trajectories.
"""
from typing import Dict, Any, List
from datetime import datetime, timezone
import yaml
from pathlib import Path
from sqlalchemy.orm import Session
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, LineString

from backend.app.core.config import settings, BASE_DIR
from backend.app.db.models import (
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


def load_demo_seed_data(session: Session) -> Dict[str, int]:
    """
    Inserts demo seed data into the database session.
    Returns counts of seeded entities.
    """
    counts = {
        "cameras": 0,
        "vehicles": 0,
        "tracks": 0,
        "observations": 0,
        "ocr_observations": 0,
        "reid_embeddings": 0,
        "vehicle_matches": 0,
        "trajectories": 0,
        "alerts": 0,
    }

    # 1. Cameras from config/cameras.yaml
    cameras_yaml_path = Path(settings.CAMERAS_CONFIG_PATH)
    if not cameras_yaml_path.is_absolute():
        cameras_yaml_path = BASE_DIR / cameras_yaml_path

    if cameras_yaml_path.exists():
        with open(cameras_yaml_path, "r", encoding="utf-8") as f:
            cam_data = yaml.safe_load(f) or {}
            for item in cam_data.get("cameras", []):
                pt = Point(item["longitude"], item["latitude"])
                cam = session.query(Camera).filter_by(camera_id=item["id"]).first()
                if not cam:
                    cam = Camera(
                        camera_id=item["id"],
                        camera_name=item["name"],
                        location_name=item["name"],
                        geom=from_shape(pt, srid=4326),
                        latitude=item["latitude"],
                        longitude=item["longitude"],
                        heading_deg=item.get("heading_deg", 0.0),
                        fps=item.get("fps", 15),
                        source_type=item.get("source_type", "file"),
                        stream_uri=item.get("stream_uri", ""),
                        status=item.get("status", "configured"),
                    )
                    session.add(cam)
                    counts["cameras"] += 1

    session.flush()

    # 2. Demo Vehicle
    veh_id = "GV-DEMO-9901"
    veh = session.query(Vehicle).filter_by(global_vehicle_id=veh_id).first()
    if not veh:
        veh = Vehicle(
            global_vehicle_id=veh_id,
            primary_plate="RJ14AB1234",
            vehicle_class="car",
            first_seen=datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc),
            last_seen=datetime(2026, 9, 4, 10, 8, 45, tzinfo=timezone.utc),
            total_observations=3,
            total_cameras_visited=3,
            is_flagged=True,
            flag_reason="[DEMO] Stolen vehicle alert match in NCR database",
        )
        session.add(veh)
        counts["vehicles"] += 1
        session.flush()

    # 3. Demo Tracks
    demo_tracks = [
        ("TRK-CAM001-01", "CAM-001", 1, veh_id, 0.94),
        ("TRK-CAM002-04", "CAM-002", 4, veh_id, 0.91),
        ("TRK-CAM005-02", "CAM-005", 2, veh_id, 0.95),
    ]
    for trk_id, cam_id, loc_trk_id, g_id, conf in demo_tracks:
        if not session.query(Track).filter_by(track_id=trk_id).first():
            t = Track(
                track_id=trk_id,
                camera_id=cam_id,
                local_track_id=loc_trk_id,
                global_vehicle_id=g_id,
                vehicle_class="car",
                start_time=datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 9, 4, 10, 8, 45, tzinfo=timezone.utc),
                detection_confidence=conf,
                total_frames=30,
            )
            session.add(t)
            counts["tracks"] += 1
    session.flush()

    # 4. Demo Observations
    obs_specs = [
        ("OBS-001-1001", "CAM-001", 1, 15, 28.6139, 77.2090, 0.94, datetime(2026, 9, 4, 10, 0, 10, tzinfo=timezone.utc)),
        ("OBS-002-2004", "CAM-002", 4, 20, 28.6180, 77.2150, 0.91, datetime(2026, 9, 4, 10, 4, 25, tzinfo=timezone.utc)),
        ("OBS-005-5002", "CAM-005", 2, 18, 28.6220, 77.2185, 0.95, datetime(2026, 9, 4, 10, 8, 35, tzinfo=timezone.utc)),
    ]
    for obs_id, cam_id, loc_trk, frm, lat, lng, conf, ts in obs_specs:
        if not session.query(Observation).filter_by(observation_id=obs_id).first():
            pt = Point(lng, lat)
            obs = Observation(
                observation_id=obs_id,
                global_vehicle_id=veh_id,
                camera_id=cam_id,
                local_track_id=loc_trk,
                frame_number=frm,
                timestamp=ts,
                geom=from_shape(pt, srid=4326),
                latitude=lat,
                longitude=lng,
                bbox_x1=100.0,
                bbox_y1=150.0,
                bbox_x2=450.0,
                bbox_y2=400.0,
                detection_confidence=conf,
                source_frame_uri="data/sample_images/bus.jpg",
            )
            session.add(obs)
            counts["observations"] += 1
    session.flush()

    # 5. Demo OCR Observations
    ocr_specs = [
        ("OCR-001-1", "OBS-001-1001", "CAM-001", 1, "RJ 14 AB 1234", "RJ14AB1234", 0.93, datetime(2026, 9, 4, 10, 0, 10, tzinfo=timezone.utc)),
        ("OCR-002-1", "OBS-002-2004", "CAM-002", 4, "RJ14-AB-1234", "RJ14AB1234", 0.89, datetime(2026, 9, 4, 10, 4, 25, tzinfo=timezone.utc)),
        ("OCR-005-1", "OBS-005-5002", "CAM-005", 2, "RJ14 AB 1234", "RJ14AB1234", 0.91, datetime(2026, 9, 4, 10, 8, 35, tzinfo=timezone.utc)),
    ]
    for ocr_id, obs_id, cam_id, loc_trk, raw, norm, conf, ts in ocr_specs:
        if not session.query(OCRObservation).filter_by(ocr_id=ocr_id).first():
            ocr_rec = OCRObservation(
                ocr_id=ocr_id,
                observation_id=obs_id,
                camera_id=cam_id,
                local_track_id=loc_trk,
                frame_number=15,
                timestamp=ts,
                raw_text=raw,
                normalized_text=norm,
                ocr_confidence=conf,
                is_blurry=False,
            )
            session.add(ocr_rec)
            counts["ocr_observations"] += 1
    session.flush()

    # 6. Demo Re-ID Embeddings
    dummy_vec = (b"\x01\x02\x03\x04" * 64)  # 256 bytes * 4
    for i, (obs_id, cam_id, loc_trk, ts) in enumerate([
        ("OBS-001-1001", "CAM-001", 1, datetime(2026, 9, 4, 10, 0, 10, tzinfo=timezone.utc)),
        ("OBS-002-2004", "CAM-002", 4, datetime(2026, 9, 4, 10, 4, 25, tzinfo=timezone.utc)),
        ("OBS-005-5002", "CAM-005", 2, datetime(2026, 9, 4, 10, 8, 35, tzinfo=timezone.utc)),
    ], 1):
        emb_id = f"REID-00{i}-1"
        if not session.query(ReIDEmbedding).filter_by(embedding_id=emb_id).first():
            emb = ReIDEmbedding(
                embedding_id=emb_id,
                observation_id=obs_id,
                camera_id=cam_id,
                local_track_id=loc_trk,
                frame_number=15,
                timestamp=ts,
                model_identifier="yolov8n-backbone-256",
                dimension=256,
                distance_metric="cosine",
                embedding=dummy_vec,
                embedding_preview="[0.062, 0.045, -0.012, 0.088, -0.034]",
            )
            session.add(emb)
            counts["reid_embeddings"] += 1
    session.flush()

    # 7. Demo Vehicle Matches
    match_specs = [
        ("MATCH-001-002", "OBS-001-1001", "OBS-002-2004", "CAM-001", "CAM-002", 0.92, "HIGH"),
        ("MATCH-002-005", "OBS-002-2004", "OBS-005-5002", "CAM-002", "CAM-005", 0.93, "HIGH"),
    ]
    for m_id, s_obs, t_obs, s_cam, t_cam, sc, tier in match_specs:
        if not session.query(VehicleMatch).filter_by(match_id=m_id).first():
            vm = VehicleMatch(
                match_id=m_id,
                global_vehicle_id=veh_id,
                source_observation_id=s_obs,
                target_observation_id=t_obs,
                source_camera_id=s_cam,
                target_camera_id=t_cam,
                match_score=sc,
                confidence_tier=tier,
                plate_score=1.0,
                reid_score=0.88,
                spatial_score=0.95,
                temporal_score=0.90,
                explanation=f"[DEMO] Match between {s_cam} and {t_cam} with score {sc}",
                evidence_breakdown={"plate_match": True, "transit_speed_feasible": True},
            )
            session.add(vm)
            counts["vehicle_matches"] += 1
    session.flush()

    # 8. Demo Trajectory
    trj_id = "TRJ-DEMO-9901"
    if not session.query(Trajectory).filter_by(trajectory_id=trj_id).first():
        line = LineString([
            (77.2090, 28.6139),
            (77.2150, 28.6180),
            (77.2185, 28.6220),
        ])
        trj = Trajectory(
            trajectory_id=trj_id,
            global_vehicle_id=veh_id,
            start_time=datetime(2026, 9, 4, 10, 0, 10, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 4, 10, 8, 35, tzinfo=timezone.utc),
            total_distance_km=1.68,
            avg_speed_kmh=12.0,
            visited_cameras_count=3,
            geom_path=from_shape(line, srid=4326),
            waypoints=[
                {"camera_id": "CAM-001", "timestamp": "2026-09-04T10:00:10Z"},
                {"camera_id": "CAM-002", "timestamp": "2026-09-04T10:04:25Z"},
                {"camera_id": "CAM-005", "timestamp": "2026-09-04T10:08:35Z"},
            ],
            is_spatial_available=True,
        )
        session.add(trj)
        counts["trajectories"] += 1
    session.flush()

    # 9. Demo Alert
    alt_id = "ALT-DEMO-101"
    if not session.query(Alert).filter_by(alert_id=alt_id).first():
        pt = Point(77.2185, 28.6220)
        alt = Alert(
            alert_id=alt_id,
            alert_type="WATCHLIST_HIT",
            severity="CRITICAL",
            global_vehicle_id=veh_id,
            plate_text="RJ14AB1234",
            camera_id="CAM-005",
            geom=from_shape(pt, srid=4326),
            latitude=28.6220,
            longitude=77.2185,
            timestamp=datetime(2026, 9, 4, 10, 8, 36, tzinfo=timezone.utc),
            details={"category": "STOLEN_VEHICLE", "incident": "FIR-2026-8812"},
            status="NEW",
        )
        session.add(alt)
        counts["alerts"] += 1

    session.commit()
    return counts
