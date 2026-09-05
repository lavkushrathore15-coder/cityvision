"""
CITYVISION AI - Unified Pipeline Orchestration Subsystem
Problem Statement ID: SIH26127

Connects all system components into a single coherent processing pipeline:
Video Ingestion
  -> Vehicle Detection (YOLOv8)
  -> Multi-Object Tracking (ByteTrack)
  -> License Plate Recognition (ANPR / EasyOCR)
  -> Vehicle Appearance Re-Identification (Re-ID)
  -> Cross-Camera Spatio-Temporal Association
  -> Global Vehicle Identity Assignment
  -> Database Persistence (PostgreSQL / SQLite)
  -> Trajectory Reconstruction
  -> Security & Traffic Alert Engine
  -> WebSocket Broadcast updates to React Dashboard & GIS Map

Strict Compliance:
- No hardcoded API responses
- No fabricated detections
- No fabricated OCR
- No fabricated Re-ID vectors
- No fake map coordinates
- Graceful error handling and meaningful logging
"""
import os
import time
import logging
import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Callable
import cv2
import numpy as np

from ai.detectors.base import BoundingBox, DetectionResult
from ai.detectors.yolo import YOLOVehicleDetector
from ai.trackers.base import TrackedVehicle
from ai.matching.base import VehicleObservation, ConfidenceTier, CrossCameraMatchRecord
from backend.app.core.config import settings
from backend.app.schemas.trajectory import (
    VehicleObservationEntity,
    CameraMovementSchema,
    AlertSchema,
)
from backend.app.services.video_ingestion import (
    VideoIngestionEngine,
    FramePacket,
    LocalFileCameraSource,
    CameraLocation,
)
from backend.app.services.detection import VehicleDetectionService, VehicleDetectionPacket
from backend.app.services.tracking import TrackingService
from backend.app.services.anpr import ANPRService
from ai.anpr.base import PlateObservationRecord
from backend.app.services.reid import ReIDService
from ai.reid.base import VehicleEmbeddingRecord
from backend.app.services.cross_camera import CrossCameraAssociationService
from backend.app.services.trajectory import TrajectoryService, AlertService
from backend.app.services.websocket_manager import ws_manager

logger = logging.getLogger("cityvision.pipeline")


@dataclass
class FrameTelemetry:
    """Detailed telemetry record for a processed frame."""
    camera_id: str
    frame_index: int
    timestamp_ms: float
    detections_count: int
    active_tracks_count: int
    plates_detected_count: int
    reid_embeddings_count: int
    matches_count: int
    alerts_triggered_count: int
    processing_time_sec: float


@dataclass
class PipelineTelemetry:
    """Aggregated operational telemetry across cameras."""
    total_frames_processed: int = 0
    total_detections: int = 0
    total_tracks: int = 0
    total_plates_recognized: int = 0
    total_reid_extractions: int = 0
    total_cross_camera_matches: int = 0
    total_alerts_triggered: int = 0
    is_running: bool = False
    camera_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class CityVisionPipelineOrchestrator:
    """
    Unified production pipeline orchestrator connecting all AI and backend subsystems.
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        device: str = "cpu",
        confidence_threshold: float = 0.35,
        sample_stride: int = 1,
        trajectory_service: Optional[TrajectoryService] = None,
        alert_service: Optional[AlertService] = None,
        cross_camera_service: Optional[CrossCameraAssociationService] = None,
        lazy_ocr: bool = True,
    ):
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.sample_stride = max(1, sample_stride)

        # 1. Trajectory and Database Persistence
        self.trajectory_service = trajectory_service or TrajectoryService()

        # 2. Alert Engine
        self.alert_service = alert_service or AlertService(watchlist_path=settings.WATCHLIST_PATH)

        # 3. Cross-Camera Association Service
        self.cross_camera_service = cross_camera_service or CrossCameraAssociationService(
            temporal_window_sec=7200.0,
        )

        # 4. Vehicle Detector (YOLOv8)
        resolved_weights = weights_path or "ai/weights/yolov8n.pt"
        if not Path(resolved_weights).is_file():
            fallback = "models/weights/yolov8n.pt"
            if Path(fallback).is_file():
                resolved_weights = fallback

        self.detector = YOLOVehicleDetector(
            weights_path=resolved_weights if Path(resolved_weights).is_file() else None,
            device=device,
        )
        if not self.detector.is_loaded and Path(resolved_weights).is_file():
            try:
                self.detector.load_model(resolved_weights, device=device)
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}")

        self.detection_service = VehicleDetectionService(
            detector=self.detector if self.detector.is_loaded else None,
            confidence_threshold=confidence_threshold,
            sample_stride=sample_stride,
        )

        # 5. Tracking Service (SingleCameraByteTracker per camera)
        self.tracking_service = TrackingService()

        # 6. ANPR Service (EasyOCR + Morphological Filter)
        self.anpr_service = ANPRService(lazy_ocr=lazy_ocr)

        # 7. Re-ID Service (YOLO deep visual embeddings)
        self.reid_service = ReIDService()

        # Telemetry State
        self.telemetry = PipelineTelemetry()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    # =========================================================================
    # CORE FRAME PROCESSING PIPELINE (14 STAGES)
    # =========================================================================

    def process_frame(
        self,
        camera_id: str,
        frame: np.ndarray,
        frame_index: int,
        timestamp_ms: float,
    ) -> FrameTelemetry:
        """
        Executes the full pipeline for a single ingested frame:
        Detection -> Tracking -> ANPR -> Re-ID -> Matching -> DB -> Trajectory -> Alerts -> WS.
        """
        t_start = time.time()

        if frame is None or frame.size == 0:
            return FrameTelemetry(
                camera_id=camera_id,
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                detections_count=0,
                active_tracks_count=0,
                plates_detected_count=0,
                reid_embeddings_count=0,
                matches_count=0,
                alerts_triggered_count=0,
                processing_time_sec=0.0,
            )

        h, w = frame.shape[:2]
        timestamp_sec = timestamp_ms / 1000.0 if timestamp_ms > 0 else time.time()

        # ---------------------------------------------------------------------
        # STAGE 2: VEHICLE DETECTION (YOLOv8)
        # ---------------------------------------------------------------------
        detection_packets: List[VehicleDetectionPacket] = self.detection_service.detect_in_frame(
            frame=frame,
            camera_id=camera_id,
            frame_number=frame_index,
            timestamp_ms=timestamp_ms,
        )

        # Mismatch 1 Fix: Convert VehicleDetectionPacket -> DetectionResult
        detections_for_tracker: List[DetectionResult] = [
            DetectionResult(
                bbox=pkt.bbox,
                confidence=pkt.confidence,
                class_name=pkt.class_name,
            )
            for pkt in detection_packets
        ]

        # ---------------------------------------------------------------------
        # STAGE 3: MULTI-OBJECT TRACKING (ByteTrack)
        # ---------------------------------------------------------------------
        active_tracks: List[TrackedVehicle] = self.tracking_service.update_tracks(
            camera_id=camera_id,
            detections=detections_for_tracker,
            frame=frame,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
        )

        plates_detected_count = 0
        reid_embeddings_count = 0
        matches_count = 0
        alerts_triggered_count = 0

        # Process each active tracked vehicle
        for track in active_tracks:
            # Mismatch 2 Fix: Extract valid boundary-clamped vehicle crop
            x1 = max(0, min(w - 1, int(track.bbox.x1)))
            y1 = max(0, min(h - 1, int(track.bbox.y1)))
            x2 = max(0, min(w, int(track.bbox.x2)))
            y2 = max(0, min(h, int(track.bbox.y2)))

            # Verify minimum dimensions for valid visual inference
            if (x2 - x1) < 15 or (y2 - y1) < 15:
                continue

            vehicle_crop = frame[y1:y2, x1:x2]
            if vehicle_crop.size == 0:
                continue

            # -----------------------------------------------------------------
            # STAGE 4: ANPR (License Plate Recognition)
            # -----------------------------------------------------------------
            plate_obs: Optional[PlateObservationRecord] = None
            try:
                plate_obs = self.anpr_service.process_vehicle_frame(
                    camera_id=camera_id,
                    local_track_id=track.local_track_id,
                    vehicle_crop=vehicle_crop,
                    frame_number=frame_index,
                    timestamp=timestamp_sec,
                )
                if plate_obs and plate_obs.normalized_text:
                    plates_detected_count += 1
            except Exception as e:
                logger.error(f"ANPR error for track {track.local_track_id} on {camera_id}: {e}")

            # -----------------------------------------------------------------
            # STAGE 5: RE-ID (Appearance Feature Embedding)
            # -----------------------------------------------------------------
            reid_record: Optional[VehicleEmbeddingRecord] = None
            try:
                reid_record = self.reid_service.process_vehicle_crop(
                    camera_id=camera_id,
                    local_track_id=track.local_track_id,
                    vehicle_crop=vehicle_crop,
                    frame_number=frame_index,
                    timestamp=timestamp_sec,
                )
                if reid_record and reid_record.embedding is not None:
                    reid_embeddings_count += 1
            except Exception as e:
                logger.error(f"Re-ID error for track {track.local_track_id} on {camera_id}: {e}")

            # -----------------------------------------------------------------
            # STAGE 6: CROSS-CAMERA ASSOCIATION & GLOBAL IDENTITY
            # -----------------------------------------------------------------
            # Mismatch 3 Fix: Assemble standardized VehicleObservation
            observation = VehicleObservation(
                camera_id=camera_id,
                local_track_id=track.local_track_id,
                timestamp=timestamp_sec,
                normalized_plate=plate_obs.normalized_text if plate_obs else None,
                raw_plate=plate_obs.raw_text if plate_obs else None,
                ocr_confidence=plate_obs.ocr_confidence if plate_obs else 0.0,
                embedding=reid_record.embedding if reid_record else None,
                vehicle_class=track.class_name,
                bbox_coords=(x1, y1, x2, y2),
                timestamp_ms=timestamp_ms,
            )

            assigned_gid, match_record = self.cross_camera_service.process_observation(observation)
            if match_record and match_record.is_matched:
                matches_count += 1

            # -----------------------------------------------------------------
            # STAGE 7 & 8: DATABASE PERSISTENCE & TRAJECTORY UPDATES
            # -----------------------------------------------------------------
            # Mismatch 4 Fix: Persist observation and update vehicle record in DB
            db_obs: Optional[VehicleObservationEntity] = None
            try:
                db_obs = self.trajectory_service.record_observation(
                    global_vehicle_id=assigned_gid,
                    camera_id=camera_id,
                    local_track_id=track.local_track_id,
                    timestamp=timestamp_sec,
                    plate_text=observation.normalized_plate,
                    ocr_confidence=observation.ocr_confidence if observation.normalized_plate else None,
                    reid_embedding=observation.embedding,
                    confidence=1.0,
                    source_frame=frame_index,
                    vehicle_class=track.class_name,
                )
            except Exception as e:
                logger.error(f"Failed to persist observation for {assigned_gid} in database: {e}")

            # -----------------------------------------------------------------
            # STAGE 9 & 10: ALERT ENGINE EVALUATION
            # -----------------------------------------------------------------
            # Mismatch 5 Fix: Evaluate alert conditions based on actual signals
            alerts_for_obs: List[AlertSchema] = []

            # 1. Blacklist evaluation (only on reliable plate recognition)
            if observation.normalized_plate and observation.ocr_confidence >= self.alert_service.engine.config.min_plate_confidence:
                blacklist_hit = self.alert_service.evaluate_plate_blacklist(
                    plate_text=observation.normalized_plate,
                    ocr_confidence=observation.ocr_confidence,
                    camera_id=camera_id,
                    global_vehicle_id=assigned_gid,
                    timestamp=timestamp_sec,
                )
                if blacklist_hit:
                    alerts_for_obs.append(blacklist_hit)

            # 2. Movement anomaly evaluation (on multi-camera transition)
            if match_record and match_record.is_matched:
                try:
                    movements = self.trajectory_service.get_camera_movements(assigned_gid)
                    if movements:
                        latest_movement = movements[-1]
                        anomaly_alert = self.alert_service.evaluate_movement_anomaly(
                            movement=latest_movement,
                            global_vehicle_id=assigned_gid,
                        )
                        if anomaly_alert:
                            alerts_for_obs.append(anomaly_alert)
                except Exception as e:
                    logger.warning(f"Error checking movement anomaly for {assigned_gid}: {e}")

            # Persist and broadcast alerts
            for alert in alerts_for_obs:
                alerts_triggered_count += 1
                try:
                    self.trajectory_service.record_alert(alert)
                except Exception as e:
                    logger.error(f"Failed to record alert {alert.alert_id} in DB: {e}")

                # WebSocket alert broadcast
                self._dispatch_websocket({
                    "event": "alert_triggered",
                    "alert": alert.model_dump() if hasattr(alert, "model_dump") else alert.dict(),
                })

            # -----------------------------------------------------------------
            # STAGE 11 & 12: REAL-TIME WEBSOCKET BROADCAST TO DASHBOARD / GIS
            # -----------------------------------------------------------------
            # Mismatch 6 Fix: Dispatch real vehicle detection event to live dashboard
            self._dispatch_websocket({
                "event": "vehicle_detected",
                "data": {
                    "camera_id": camera_id,
                    "global_vehicle_id": assigned_gid,
                    "local_track_id": track.local_track_id,
                    "class_name": track.class_name,
                    "plate": observation.normalized_plate,
                    "ocr_confidence": round(observation.ocr_confidence, 3) if observation.normalized_plate else 0.0,
                    "timestamp": timestamp_sec,
                    "is_match": match_record.is_matched if match_record else False,
                },
            })

        # Congestion evaluation per frame if vehicle count exceeds threshold
        if len(active_tracks) >= self.alert_service.engine.config.congestion_density_threshold:
            congestion_alert = self.alert_service.evaluate_zone_congestion(
                camera_id=camera_id,
                active_vehicle_count=len(active_tracks),
            )
            if congestion_alert:
                alerts_triggered_count += 1
                try:
                    self.trajectory_service.record_alert(congestion_alert)
                except Exception as e:
                    logger.error(f"Failed to record congestion alert: {e}")
                self._dispatch_websocket({
                    "event": "alert_triggered",
                    "alert": congestion_alert.model_dump() if hasattr(congestion_alert, "model_dump") else congestion_alert.dict(),
                })

        proc_time = time.time() - t_start

        # Update aggregated telemetry
        self.telemetry.total_frames_processed += 1
        self.telemetry.total_detections += len(detection_packets)
        self.telemetry.total_tracks += len(active_tracks)
        self.telemetry.total_plates_recognized += plates_detected_count
        self.telemetry.total_reid_extractions += reid_embeddings_count
        self.telemetry.total_cross_camera_matches += matches_count
        self.telemetry.total_alerts_triggered += alerts_triggered_count

        self.telemetry.camera_status[camera_id] = {
            "last_frame_index": frame_index,
            "last_timestamp_ms": timestamp_ms,
            "active_tracks": len(active_tracks),
            "detections": len(detection_packets),
            "last_processing_time_sec": round(proc_time, 4),
        }

        return FrameTelemetry(
            camera_id=camera_id,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            detections_count=len(detection_packets),
            active_tracks_count=len(active_tracks),
            plates_detected_count=plates_detected_count,
            reid_embeddings_count=reid_embeddings_count,
            matches_count=matches_count,
            alerts_triggered_count=alerts_triggered_count,
            processing_time_sec=proc_time,
        )

    # =========================================================================
    # VIDEO FILE / STREAM PROCESSING
    # =========================================================================

    def process_video_file(
        self,
        camera_id: str,
        video_path: str,
        max_frames: Optional[int] = None,
        sample_stride: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, FrameTelemetry], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end processing across frames of a local video file.
        Reports exact stage results without fabricating synthetic outputs.
        """
        path = Path(video_path)
        if not path.is_file():
            raise FileNotFoundError(f"Video file '{video_path}' not found.")

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"OpenCV failed to open video source '{video_path}'.")

        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        stride = max(1, sample_stride or self.sample_stride)

        logger.info(
            f"Starting end-to-end video processing: {camera_id} from {path.name} "
            f"({total_video_frames} frames, {fps:.1f} fps, stride={stride})"
        )

        frames_processed = 0
        stage_records: List[FrameTelemetry] = []
        frame_idx = 0

        try:
            while cap.isOpened():
                if self._stop_event.is_set():
                    logger.info("Video processing halted by stop event.")
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % stride == 0:
                    timestamp_ms = (frame_idx / fps) * 1000.0
                    telem = self.process_frame(
                        camera_id=camera_id,
                        frame=frame,
                        frame_index=frame_idx,
                        timestamp_ms=timestamp_ms,
                    )
                    stage_records.append(telem)
                    frames_processed += 1

                    if progress_callback:
                        progress_callback(frame_idx, total_video_frames, telem)

                    if max_frames and frames_processed >= max_frames:
                        break

                frame_idx += 1
        finally:
            cap.release()

        total_dets = sum(r.detections_count for r in stage_records)
        total_tracks = sum(r.active_tracks_count for r in stage_records)
        total_plates = sum(r.plates_detected_count for r in stage_records)
        total_reid = sum(r.reid_embeddings_count for r in stage_records)
        total_matches = sum(r.matches_count for r in stage_records)
        total_alerts = sum(r.alerts_triggered_count for r in stage_records)

        summary = {
            "camera_id": camera_id,
            "video_path": str(video_path),
            "total_video_frames": total_video_frames,
            "frames_evaluated": frames_processed,
            "sample_stride": stride,
            "total_detections": total_dets,
            "total_active_tracks": total_tracks,
            "total_plates_recognized": total_plates,
            "total_reid_embeddings": total_reid,
            "total_cross_camera_matches": total_matches,
            "total_alerts_triggered": total_alerts,
            "status": "completed",
        }
        logger.info(f"Completed video processing on {camera_id}: {summary}")
        return summary

    # =========================================================================
    # BACKGROUND CONTINUOUS INGESTION CONTROLS
    # =========================================================================

    def start_background_pipeline(
        self,
        cameras: Optional[List[Dict[str, Any]]] = None,
        sample_stride: int = 5,
    ) -> Dict[str, Any]:
        """Starts multi-camera background ingestion loop."""
        if self._worker_thread and self._worker_thread.is_alive():
            return {"status": "already_running", "message": "Pipeline is already running in background."}

        self._stop_event.clear()
        self.telemetry.is_running = True

        def _run_loop():
            logger.info("Background pipeline worker thread started.")
            target_cameras = cameras or []
            if not target_cameras:
                # Read from cameras.json
                cams_file = Path("data/cameras/cameras.json")
                if cams_file.is_file():
                    import json
                    with open(cams_file, "r", encoding="utf-8") as f:
                        target_cameras = json.load(f)

            while not self._stop_event.is_set():
                for cam in target_cameras:
                    if self._stop_event.is_set():
                        break
                    cam_id = cam.get("id", "CAM-001")
                    uri = cam.get("stream_uri", "")
                    if uri and Path(uri).is_file():
                        try:
                            # Process a short chunk or single cycle
                            self.process_video_file(
                                camera_id=cam_id,
                                video_path=uri,
                                max_frames=10,
                                sample_stride=sample_stride,
                            )
                        except Exception as e:
                            logger.error(f"Error processing camera {cam_id}: {e}")
                time.sleep(1.0)
            self.telemetry.is_running = False
            logger.info("Background pipeline worker thread stopped.")

        self._worker_thread = threading.Thread(target=_run_loop, daemon=True)
        self._worker_thread.start()

        return {"status": "started", "message": "Background pipeline ingestion started."}

    def stop_background_pipeline(self) -> Dict[str, Any]:
        """Stops background ingestion loop."""
        if not self._worker_thread or not self._worker_thread.is_alive():
            self.telemetry.is_running = False
            return {"status": "not_running", "message": "Pipeline was not running."}

        self._stop_event.set()
        self._worker_thread.join(timeout=3.0)
        self.telemetry.is_running = False
        return {"status": "stopped", "message": "Background pipeline stopped."}

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns current operational telemetry snapshot."""
        return {
            "is_running": self.telemetry.is_running,
            "total_frames_processed": self.telemetry.total_frames_processed,
            "total_detections": self.telemetry.total_detections,
            "total_tracks": self.telemetry.total_tracks,
            "total_plates_recognized": self.telemetry.total_plates_recognized,
            "total_reid_extractions": self.telemetry.total_reid_extractions,
            "total_cross_camera_matches": self.telemetry.total_cross_camera_matches,
            "total_alerts_triggered": self.telemetry.total_alerts_triggered,
            "camera_status": self.telemetry.camera_status,
        }

    # =========================================================================
    # WEBSOCKET BROADCAST DISPATCHER
    # =========================================================================

    def _dispatch_websocket(self, payload: Dict[str, Any]) -> None:
        """Dispatches an asynchronous broadcast message via the global connection manager in a thread-safe manner."""
        ws_manager.dispatch_broadcast(payload)


# Global singleton instance for use across API routes
pipeline_orchestrator = CityVisionPipelineOrchestrator()
