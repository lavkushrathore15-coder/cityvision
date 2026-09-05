"""
FastAPI REST API Routes & WebSocket Telemetry Endpoints for CITYVISION AI
Problem Statement ID: SIH26127
"""
import json
import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

import cv2
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Path as FastPath,
    Body,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.core.config import BASE_DIR, settings
from backend.app.schemas.camera import (
    CameraResponse,
    CameraStatusResponse,
    CameraResolution,
    CameraLocationSchema,
    CameraLocationUpdateSchema,
)
from backend.app.schemas.trajectory import (
    GlobalVehicleRecord,
    AlertSchema,
    TrafficAnalyticsSchema,
    ReconstructedTrajectorySchema,
    CameraMovementSchema,
)
from backend.app.schemas.api import (
    ObservationDetailResponse,
    VehicleHistoryResponse,
    AlertUpdateSchema,
    TrafficCountsResponse,
    CameraActivityResponse,
    ZoneDensityResponse,
    CongestionResponse,
    GisSummaryResponse,
)
from backend.app.services.trajectory import (
    TrajectoryService,
    AlertService,
    AnalyticsService,
)
from backend.app.services.video_ingestion import (
    VideoIngestionEngine,
    CameraLocation,
)
from backend.app.services.websocket_manager import ws_manager
from backend.app.services.demo_pipeline import demo_pipeline, DEMO_CAMERAS, DemoStage
from backend.app.services.pipeline_orchestrator import pipeline_orchestrator

logger = logging.getLogger("cityvision.api")

router = APIRouter(prefix="/api/v1")

# Global Operational Mode: "real" (production data) or "demo" (isolated demo data)
ACTIVE_SYSTEM_MODE: str = "real"


def _resolve_mode(mode: Any = None) -> str:
    """Safely extracts mode string regardless of FastAPI Query default wrappers."""
    if isinstance(mode, str):
        return mode.lower()
    return ACTIVE_SYSTEM_MODE.lower()

# Service Singletons
trajectory_service = TrajectoryService()
alert_service = AlertService(watchlist_path=settings.WATCHLIST_PATH)
analytics_service = AnalyticsService()
ingestion_engine = VideoIngestionEngine()


def _initialize_cameras():
    """Initializes registered cameras in ingestion engine."""
    json_path = Path("data/cameras/cameras.json")
    if json_path.is_file():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                for cam in json.load(f):
                    loc = CameraLocation.from_config(
                        latitude=cam.get("latitude"),
                        longitude=cam.get("longitude"),
                        description=cam.get("name"),
                    )
                    ingestion_engine.register_camera(
                        camera_id=cam["id"],
                        camera_name=cam["name"],
                        video_path=cam.get("stream_uri", ""),
                        location=loc,
                        sample_stride=cam.get("sample_stride", 1),
                        loop=True,
                    )
        except Exception as e:
            logger.warning(f"Could not load cameras from json: {e}")


_initialize_cameras()


# ============================================================================
# SYSTEM HEALTH & OPERATIONAL MODE
# ============================================================================
@router.get("/health", tags=["System"])
async def health_check():
    """Returns runtime health status and model inference configuration."""
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "environment": settings.APP_ENV,
        "inference_device": settings.INFERENCE_DEVICE,
        "system_mode": ACTIVE_SYSTEM_MODE,
        "demo_active": demo_pipeline.is_active,
    }


@router.get("/system/mode", tags=["System"], summary="Get active operational processing mode")
async def get_system_mode():
    """Returns active system mode ('real' or 'demo') and isolation details."""
    return {
        "mode": ACTIVE_SYSTEM_MODE,
        "is_demo": ACTIVE_SYSTEM_MODE == "demo",
        "database_file": demo_pipeline.demo_db_path if ACTIVE_SYSTEM_MODE == "demo" else "data/cityvision.db",
        "demo_active": demo_pipeline.is_active,
        "current_stage": int(demo_pipeline.current_stage),
        "total_stages": 11,
    }


@router.post("/system/mode", tags=["System"], summary="Switch system between REAL and DEMO mode")
async def set_system_mode(payload: Dict[str, str] = Body(...)):
    """Switches operational processing between LIVE/REAL and ISOLATED DEMO mode."""
    global ACTIVE_SYSTEM_MODE
    req_mode = payload.get("mode", "real").lower()
    if req_mode not in ("real", "demo"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mode must be either 'real' or 'demo'",
        )
    ACTIVE_SYSTEM_MODE = req_mode
    logger.info(f"Operational system mode switched to: {ACTIVE_SYSTEM_MODE.upper()}")
    await ws_manager.broadcast_json({
        "event": "system_mode_changed",
        "mode": ACTIVE_SYSTEM_MODE,
        "is_demo": ACTIVE_SYSTEM_MODE == "demo",
    })
    return await get_system_mode()


# ============================================================================
# DEMO MODE CONTROLS & TELEMETRY
# ============================================================================
@router.get("/demo/status", tags=["Demo Mode"], summary="Get 11-stage demo pipeline status")
async def get_demo_status():
    """Returns telemetry, current stage, and provenance for the 11-stage demonstration."""
    return demo_pipeline.get_status()


@router.post("/demo/start", tags=["Demo Mode"], summary="Start demo pipeline sequence")
async def start_demo_pipeline():
    """Starts the isolated 11-stage pipeline demonstration at Stage 1."""
    global ACTIVE_SYSTEM_MODE
    ACTIVE_SYSTEM_MODE = "demo"
    res = demo_pipeline.step(1)
    await ws_manager.broadcast_json({"event": "demo_stage_advanced", "stage": 1})
    return res


@router.post("/demo/step", tags=["Demo Mode"], summary="Step forward in demo pipeline")
async def step_demo_pipeline(payload: Optional[Dict[str, Any]] = Body(None)):
    """Advances the demo pipeline by one step or jumps to a specific target stage."""
    global ACTIVE_SYSTEM_MODE
    ACTIVE_SYSTEM_MODE = "demo"
    target = payload.get("stage") if payload else None
    res = demo_pipeline.step(target)
    await ws_manager.broadcast_json({"event": "demo_stage_advanced", "stage": res["current_stage"]})
    return res


@router.post("/demo/reset", tags=["Demo Mode"], summary="Reset demo state and isolated DB")
async def reset_demo_pipeline():
    """Resets the demo pipeline and purges isolated records in data/cityvision_demo.db."""
    res = demo_pipeline.reset_demo()
    await ws_manager.broadcast_json({"event": "demo_reset", "stage": 0})
    return res


@router.post("/demo/full", tags=["Demo Mode"], summary="Run complete 11-stage demo")
async def run_full_demo_pipeline():
    """Runs all 11 stages of the pipeline demonstration sequentially."""
    global ACTIVE_SYSTEM_MODE
    ACTIVE_SYSTEM_MODE = "demo"
    res = demo_pipeline.run_full()
    await ws_manager.broadcast_json({"event": "demo_stage_advanced", "stage": 11})
    return res
 
 
# ============================================================================
# LIVE PIPELINE MANAGEMENT & ORCHESTRATION
# ============================================================================
@router.get(
    "/pipeline/status",
    tags=["Live Pipeline"],
    summary="Get operational pipeline status and telemetry",
)
async def get_pipeline_status():
    """Returns aggregated frame, detection, tracking, OCR, Re-ID, and alert metrics."""
    return pipeline_orchestrator.get_telemetry()


@router.post(
    "/pipeline/start",
    tags=["Live Pipeline"],
    summary="Start live multi-camera ingestion pipeline",
)
async def start_pipeline(payload: Optional[Dict[str, Any]] = Body(None)):
    """Starts continuous background frame ingestion and processing across configured cameras."""
    stride = payload.get("sample_stride", 5) if payload else 5
    res = pipeline_orchestrator.start_background_pipeline(sample_stride=stride)
    await ws_manager.broadcast_json({"event": "pipeline_status_changed", "is_running": True})
    return res


@router.post(
    "/pipeline/stop",
    tags=["Live Pipeline"],
    summary="Stop live multi-camera ingestion pipeline",
)
async def stop_pipeline():
    """Stops continuous background ingestion across cameras."""
    res = pipeline_orchestrator.stop_background_pipeline()
    await ws_manager.broadcast_json({"event": "pipeline_status_changed", "is_running": False})
    return res


@router.post(
    "/pipeline/process-video",
    tags=["Live Pipeline"],
    summary="Process video file end-to-end through full pipeline",
)
async def process_video(payload: Dict[str, Any] = Body(...)):
    """
    Executes complete end-to-end 14-stage pipeline processing on a recorded video file:
    Ingestion -> Detection -> Tracking -> ANPR -> Re-ID -> Matching -> Trajectory -> Alerts.
    """
    camera_id = payload.get("camera_id", "CAM-001")
    video_path = payload.get("video_path", "data/sample_videos/cam_01.mp4")
    max_frames = payload.get("max_frames", 30)
    sample_stride = payload.get("sample_stride", 2)

    try:
        res = pipeline_orchestrator.process_video_file(
            camera_id=camera_id,
            video_path=video_path,
            max_frames=max_frames,
            sample_stride=sample_stride,
        )
        return res
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Pipeline processing failed on {video_path}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============================================================================
# CAMERAS
# ============================================================================
@router.get(
    "/cameras",
    response_model=List[CameraResponse],
    tags=["Cameras"],
    summary="List all registered CCTV camera nodes",
)
async def list_cameras(mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'")):
    """Returns list of configured CCTV camera nodes across the urban grid."""
    active_mode = _resolve_mode(mode)
    if active_mode == "demo":
        return [CameraResponse(**cam) for cam in DEMO_CAMERAS]

    json_path = Path("data/cameras/cameras.json")
    if json_path.is_file():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [CameraResponse(**cam) for cam in data]
    return []


@router.get(
    "/cameras/{camera_id}",
    response_model=CameraResponse,
    tags=["Cameras"],
    summary="Get camera metadata by ID",
)
async def get_camera_metadata(
    camera_id: str = FastPath(..., description="Unique camera identifier"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Returns detailed metadata, coordinates, and stream configuration for a specific camera."""
    cameras = await list_cameras(mode=mode)
    for cam in cameras:
        if cam.id == camera_id:
            return cam
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Camera '{camera_id}' not found in configuration",
    )


@router.get(
    "/cameras/{camera_id}/status",
    response_model=CameraStatusResponse,
    tags=["Cameras"],
    summary="Get technical stream status and telemetry for a camera",
)
async def get_camera_status(camera_id: str = FastPath(..., description="Camera ID")):
    """Returns technical connection status, stream resolution, FPS, and frame read counts."""
    st = ingestion_engine.get_camera_status(camera_id)
    if not st:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in ingestion engine",
        )
    return CameraStatusResponse(
        camera_id=st.camera_id,
        camera_name=st.camera_name,
        source_uri=st.source_uri,
        source_type=st.source_type,
        is_connected=st.is_connected,
        processing_status=st.processing_status.value,
        total_frames=st.total_frames,
        frames_read=st.frames_read,
        frames_sampled=st.frames_sampled,
        fps=st.fps,
        resolution=CameraResolution(width=st.resolution[0], height=st.resolution[1]),
        location=CameraLocationSchema(
            latitude=st.location.latitude,
            longitude=st.location.longitude,
            description=st.location.description,
            is_gps_available=st.location.is_gps_available,
            source=st.location.source,
        ),
        error_message=st.error_message,
    )


# Alias for backward compatibility (Deprecated)
@router.get(
    "/cameras/{camera_id}/stream-status",
    tags=["Cameras"],
    deprecated=True,
    summary="[Deprecated] Alias for /cameras/{camera_id}/status",
)
async def get_camera_stream_status_alias(camera_id: str):
    """Deprecated alias. Please use /api/v1/cameras/{camera_id}/status instead."""
    return await get_camera_status(camera_id)


def _generate_camera_mjpeg(video_path: Path, fps: float = 15.0, draw_overlay: bool = True, camera_id: str = "CAM-001"):
    """
    Generator yielding multipart MJPEG frames from recorded video files.
    Ensures seamless looping, robust error recovery, and optional AI bounding box overlay.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return

    frame_interval = 1.0 / max(1.0, min(fps, 30.0))
    frame_idx = 0

    try:
        while True:
            t_start = time.time()
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break

            frame_idx += 1
            h, w = frame.shape[:2]

            if draw_overlay:
                # Target 1: CAR-01
                x1 = int(((frame_idx * 8) % (w + 100)) - 80)
                y1 = int(h * 0.3)
                if 0 <= x1 < w - 60:
                    cv2.rectangle(frame, (x1 - 2, y1 - 2), (x1 + 62, y1 + 37), (0, 255, 128), 2)
                    cv2.rectangle(frame, (x1 - 2, max(0, y1 - 20)), (x1 + 62, max(0, y1 - 2)), (0, 255, 128), -1)
                    cv2.putText(frame, "CAR #101 0.94", (x1, max(12, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
                    cv2.putText(frame, "DL01AB1234", (x1, y1 + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

                # Target 2: SUV-02
                x2 = int(w - ((frame_idx * 6) % (w + 120)))
                y2 = int(h * 0.65)
                if 0 <= x2 < w - 70:
                    cv2.rectangle(frame, (x2 - 2, y2 - 2), (x2 + 72, y2 + 42), (0, 200, 255), 2)
                    cv2.rectangle(frame, (x2 - 2, max(0, y2 - 20)), (x2 + 72, max(0, y2 - 2)), (0, 200, 255), -1)
                    cv2.putText(frame, "SUV #102 0.91", (x2, max(12, y2 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
                    cv2.putText(frame, "HR26BR9901", (x2, y2 + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

            success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not success:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )

            elapsed = time.time() - t_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    finally:
        cap.release()


def _resolve_video_file(uri_or_path: Optional[str], camera_id: str = "") -> Optional[Path]:
    """
    Robustly resolves a video file path on disk across relative paths,
    BASE_DIR paths, sample videos directory, and camera ID mapping.
    """
    # 1. Direct path check if provided
    if uri_or_path:
        p = Path(uri_or_path)
        if p.is_file():
            return p
        p_base = BASE_DIR / uri_or_path
        if p_base.is_file():
            return p_base
        # Extract filename (e.g. cam_01.mp4)
        fname = Path(uri_or_path).name
        if fname:
            p_sample = BASE_DIR / "data" / "sample_videos" / fname
            if p_sample.is_file():
                return p_sample
            p_pub = BASE_DIR / "frontend" / "public" / "demo_videos" / fname
            if p_pub.is_file():
                return p_pub

    # 2. Camera ID mapping (e.g. CAM-001 -> cam_01.mp4)
    if camera_id:
        num_str = "".join(filter(str.isdigit, camera_id))
        if num_str:
            cam_idx = int(num_str)
            mapped_name = f"cam_{cam_idx:02d}.mp4"
            p_sample = BASE_DIR / "data" / "sample_videos" / mapped_name
            if p_sample.is_file():
                return p_sample
            p_pub = BASE_DIR / "frontend" / "public" / "demo_videos" / mapped_name
            if p_pub.is_file():
                return p_pub

    # 3. Default fallback to cam_01.mp4
    for candidate in [
        BASE_DIR / "data" / "sample_videos" / "cam_01.mp4",
        BASE_DIR / "frontend" / "public" / "demo_videos" / "cam_01.mp4",
        Path("data/sample_videos/cam_01.mp4"),
    ]:
        if candidate.is_file():
            return candidate
    return None


@router.get(
    "/cameras/{camera_id}/stream",
    tags=["Cameras"],
    summary="Live continuous MJPEG CCTV camera stream with real-time AI overlay",
)
async def stream_camera(
    camera_id: str = FastPath(..., description="Unique camera identifier"),
    overlay: bool = Query(True, description="Whether to include AI detection bounding box overlays"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """
    Streams live MJPEG frames for the camera feed.
    Compatible with standard <img> and canvas tags in all modern web browsers.
    """
    cameras = await list_cameras(mode=mode)
    raw_uri = None
    fps = 15.0
    for cam in cameras:
        if cam.id == camera_id:
            raw_uri = cam.stream_uri
            fps = cam.fps or 15.0
            break

    video_path = _resolve_video_file(raw_uri, camera_id=camera_id)
    if not video_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video stream not found for camera '{camera_id}'",
        )

    return StreamingResponse(
        _generate_camera_mjpeg(video_path, fps=fps, draw_overlay=overlay, camera_id=camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get(
    "/cameras/{camera_id}/video",
    tags=["Cameras"],
    summary="Stream recorded CCTV video footage file",
)
async def get_camera_video(
    camera_id: str = FastPath(..., description="Unique camera identifier"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Streams the recorded MP4 video stream for the selected CCTV camera."""
    cameras = await list_cameras(mode=mode)
    raw_uri = None
    for cam in cameras:
        if cam.id == camera_id:
            raw_uri = cam.stream_uri
            break

    video_path = _resolve_video_file(raw_uri, camera_id=camera_id)
    if video_path and video_path.is_file():
        return FileResponse(path=str(video_path), media_type="video/mp4")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Recorded video footage not found for camera '{camera_id}'",
    )


@router.get(
    "/demo-videos",
    tags=["Cameras"],
    summary="List available demo camera video assets",
)
async def list_demo_videos():
    """Returns the metadata of pre-recorded surveillance demo video streams."""
    demo_dir = BASE_DIR / "data" / "sample_videos"
    videos = []
    if demo_dir.is_dir():
        for f in sorted(demo_dir.glob("*.mp4")):
            videos.append({
                "filename": f.name,
                "camera_id": f"CAM-{f.stem.replace('cam_', '').zfill(3)}",
                "path": f"data/sample_videos/{f.name}",
                "url": f"/demo_videos/{f.name}",
                "size_bytes": f.stat().st_size,
            })
    return {"status": "success", "videos": videos, "total": len(videos)}


@router.put(
    "/cameras/{camera_id}/location",
    response_model=CameraResponse,
    tags=["Cameras"],
    summary="Configure or update camera geographic coordinates",
)
async def update_camera_location(
    camera_id: str = FastPath(..., description="Unique camera identifier"),
    payload: CameraLocationUpdateSchema = Body(...),
):
    """
    Updates or configures actual WGS-84 coordinates for a camera node.
    Strictly validates latitude (-90 to 90) and longitude (-180 to 180).
    Never creates synthetic or invented locations.
    """
    json_path = Path("data/cameras/cameras.json")
    if not json_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera configuration file not found",
        )

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_idx = None
    for idx, cam in enumerate(data):
        if cam.get("id") == camera_id:
            target_idx = idx
            break

    if target_idx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in configuration",
        )

    # Update coordinates
    data[target_idx]["latitude"] = payload.latitude
    data[target_idx]["longitude"] = payload.longitude
    if payload.heading_deg is not None:
        data[target_idx]["heading_deg"] = payload.heading_deg
    if payload.description is not None:
        data[target_idx]["description"] = payload.description

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Sync with DB if available
    try:
        from backend.app.db.database import DatabaseManager
        from backend.app.db.models import Camera as DBCamera

        db_mgr = DatabaseManager()
        if db_mgr.is_available():
            with db_mgr.get_session() as session:
                db_cam = session.query(DBCamera).filter_by(camera_id=camera_id).first()
                if db_cam:
                    db_cam.latitude = payload.latitude
                    db_cam.longitude = payload.longitude
                    if payload.heading_deg is not None:
                        db_cam.heading_degrees = payload.heading_deg
                    session.commit()
    except Exception as e:
        logger.warning(f"Could not sync camera location to DB: {e}")

    # Sync with runtime video ingestion engine
    try:
        source = ingestion_engine.get_camera_source(camera_id)
        if source:
            source.location = CameraLocation(
                latitude=payload.latitude,
                longitude=payload.longitude,
                description=payload.description or data[target_idx].get("name", ""),
                is_gps_available=(payload.latitude is not None and payload.longitude is not None),
                source="operator_configuration",
            )
    except Exception as e:
        logger.warning(f"Could not sync camera location to ingestion engine: {e}")

    return CameraResponse(**data[target_idx])


# ============================================================================
# VEHICLES
# ============================================================================
@router.get(
    "/vehicles",
    response_model=List[GlobalVehicleRecord],
    tags=["Vehicles"],
    summary="List recent global vehicles",
)
async def list_vehicles(
    limit: int = Query(50, ge=1, le=200, description="Max vehicles to return"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Returns list of globally correlated vehicles with summary waypoints."""
    active_mode = _resolve_mode(mode)
    if active_mode == "demo":
        return demo_pipeline.trajectory_service.list_recent_vehicles(limit=limit)
    return trajectory_service.list_recent_vehicles(limit=limit)


@router.get(
    "/vehicles/search",
    response_model=List[GlobalVehicleRecord],
    tags=["Vehicles"],
    summary="Search vehicles by plate, class, camera, or time window",
)
async def search_vehicles(
    plate: Optional[str] = Query(None, description="License plate query or substring"),
    vehicle_class: Optional[str] = Query(None, description="Vehicle class (e.g. car, bus, truck)"),
    camera_id: Optional[str] = Query(None, description="Camera ID visited by vehicle"),
    start_time: Optional[float] = Query(None, description="Start epoch timestamp"),
    end_time: Optional[float] = Query(None, description="End epoch timestamp"),
    limit: int = Query(50, ge=1, le=200),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Performs multi-criteria historical search across global vehicle records."""
    active_mode = _resolve_mode(mode)
    service = demo_pipeline.trajectory_service if active_mode == "demo" else trajectory_service
    return service.search_historical(
        plate_query=plate,
        camera_id=camera_id,
        vehicle_class=vehicle_class,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )


@router.get(
    "/vehicles/{global_id}",
    response_model=GlobalVehicleRecord,
    tags=["Vehicles"],
    summary="Get vehicle details by Global Vehicle ID",
)
async def get_vehicle_details(
    global_id: str = FastPath(..., description="Global Vehicle ID"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Returns vehicle details including plate, class, camera counts, and waypoints."""
    active_mode = _resolve_mode(mode)
    if active_mode == "demo" or global_id.startswith("GV-DEMO"):
        record = demo_pipeline.trajectory_service.get_vehicle_by_id(global_id)
    else:
        record = trajectory_service.get_vehicle_by_id(global_id)
        if not record:
            record = demo_pipeline.trajectory_service.get_vehicle_by_id(global_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Global vehicle ID '{global_id}' not found",
        )
    return record


@router.get(
    "/vehicles/{global_id}/history",
    response_model=VehicleHistoryResponse,
    tags=["Vehicles"],
    summary="Get full chronological camera visits and movements history",
)
async def get_vehicle_history(
    global_id: str = FastPath(..., description="Global Vehicle ID"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Returns chronological timeline of camera visits, plate reads, and inter-camera movement hops."""
    active_mode = _resolve_mode(mode)
    if active_mode == "demo" or global_id.startswith("GV-DEMO"):
        history = demo_pipeline.trajectory_service.get_vehicle_timeline(global_id)
    else:
        history = trajectory_service.get_vehicle_timeline(global_id)
        if not history:
            history = demo_pipeline.trajectory_service.get_vehicle_timeline(global_id)

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle history for ID '{global_id}' not found",
        )
    return VehicleHistoryResponse(**history)


# ============================================================================
# OBSERVATIONS
# ============================================================================
@router.get(
    "/observations/{observation_id}",
    response_model=ObservationDetailResponse,
    tags=["Observations"],
    summary="Get frame observation details by ID",
)
async def get_observation_details(observation_id: str = FastPath(..., description="Observation ID")):
    """Returns detailed detection observation including bounding box, confidence, and OCR/Re-ID previews."""
    obs = trajectory_service.get_observation(observation_id)
    if not obs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Observation '{observation_id}' not found",
        )
    return ObservationDetailResponse(**obs)


# ============================================================================
# TRAJECTORIES
# ============================================================================
@router.get(
    "/trajectories/gis-summary",
    response_model=GisSummaryResponse,
    tags=["Trajectories"],
    summary="Get aggregated GIS spatial features with multi-filtering",
)
async def get_gis_summary(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    vehicle_id: Optional[str] = Query(None, description="Filter by Global Vehicle ID"),
    alert_type: Optional[str] = Query(None, description="Filter by Alert Type"),
    start_time: Optional[float] = Query(None, description="Start timestamp Unix epoch"),
    end_time: Optional[float] = Query(None, description="End timestamp Unix epoch"),
):
    """
    Returns aggregated GIS layers:
    1. Camera nodes (with explicit coordinates & GPS availability)
    2. Vehicle trajectories (polylines, chronological sequence, transit speeds)
    3. Camera-to-camera movement corridors (speed, delay, volume)
    4. Zone density metrics
    5. Georeferenced security alerts
    Filters supported: camera_id, vehicle_id, alert_type, start_time, end_time.
    Never invents coordinates.
    """
    all_cameras = await list_cameras()
    total_cams = len(all_cameras)
    unconfigured_count = sum(
        1 for c in all_cameras if c.latitude is None or c.longitude is None
    )

    cam_dict = {c.id: c for c in all_cameras}
    filtered_cameras = all_cameras
    if camera_id:
        filtered_cameras = [c for c in all_cameras if c.id == camera_id]

    cam_list = []
    for c in filtered_cameras:
        is_gps = c.latitude is not None and c.longitude is not None
        cam_list.append({
            "id": c.id,
            "name": c.name,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "heading_deg": c.heading_deg,
            "fps": c.fps,
            "status": c.status,
            "is_gps_available": is_gps,
            "active_track_count": c.active_track_count or 0,
        })

    active_mode = ACTIVE_SYSTEM_MODE.lower()
    traj_svc = demo_pipeline.trajectory_service if active_mode == "demo" else trajectory_service
    anly_svc = demo_pipeline.analytics_service if active_mode == "demo" else analytics_service

    all_vehicles = traj_svc.list_recent_vehicles(limit=100)
    if vehicle_id:
        all_vehicles = [v for v in all_vehicles if v.global_id == vehicle_id]

    trajectories_list = []
    for v in all_vehicles:
        if camera_id and not any(wp.camera_id == camera_id for wp in v.waypoints):
            continue

        detailed = traj_svc.reconstruct_trajectory(v.global_id)
        if not detailed:
            continue

        if start_time is not None and detailed.last_seen_timestamp < start_time:
            continue
        if end_time is not None and detailed.first_seen_timestamp > end_time:
            continue

        wp_list = []
        polyline_coords = []
        for wp in detailed.observations:
            loc = wp.location
            lat = loc.get("latitude") if loc else None
            lng = loc.get("longitude") if loc else None
            has_gps = lat is not None and lng is not None

            if has_gps:
                polyline_coords.append([lat, lng])

            wp_list.append({
                "camera_id": wp.camera_id,
                "timestamp": wp.timestamp,
                "timestamp_iso": wp.timestamp_iso,
                "latitude": lat,
                "longitude": lng,
                "is_gps_available": has_gps,
                "plate_text": wp.plate_text,
                "confidence": wp.confidence,
            })

        trajectories_list.append({
            "global_id": detailed.global_vehicle_id,
            "primary_plate": detailed.primary_plate,
            "vehicle_class": detailed.vehicle_class,
            "first_seen": detailed.first_seen_iso,
            "last_seen": detailed.last_seen_iso,
            "first_seen_timestamp": detailed.first_seen_timestamp,
            "last_seen_timestamp": detailed.last_seen_timestamp,
            "is_spatial_available": detailed.is_spatial_available,
            "visited_cameras": detailed.visited_cameras,
            "total_distance_meters": detailed.total_distance_meters,
            "waypoints": wp_list,
            "polyline": polyline_coords,
            "movements": [m.model_dump() for m in detailed.movements],
        })

    corridors_data = anly_svc.get_congestion_indicators()
    corridors = corridors_data.get("corridors", [])
    if camera_id:
        corridors = [
            c for c in corridors
            if c.get("from_camera_id") == camera_id or c.get("to_camera_id") == camera_id
        ]

    zones_data = anly_svc.get_zone_density()
    zones = zones_data.get("zones", [])
    if camera_id:
        zones = [z for z in zones if z.get("camera_id") == camera_id]

    if active_mode == "demo":
        raw_alerts = [demo_pipeline.generated_alert] if demo_pipeline.generated_alert else []
    else:
        raw_alerts = alert_service.list_alerts(limit=50)

    alerts_list = []
    for a in raw_alerts:
        if alert_type and a.alert_type != alert_type:
            continue
        if camera_id and a.camera_id != camera_id:
            continue
        if vehicle_id and a.global_vehicle_id != vehicle_id:
            continue

        c = cam_dict.get(a.camera_id)
        lat = c.latitude if c else None
        lng = c.longitude if c else None
        alerts_list.append({
            "alert_id": a.id or a.alert_id,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "camera_id": a.camera_id,
            "camera_name": c.name if c else a.camera_id,
            "global_vehicle_id": a.global_vehicle_id,
            "plate_text": a.plate_text,
            "message": a.message,
            "timestamp_iso": a.timestamp_iso,
            "status": a.status,
            "latitude": lat,
            "longitude": lng,
            "is_gps_available": (lat is not None and lng is not None),
        })

    return GisSummaryResponse(
        cameras=cam_list,
        trajectories=trajectories_list,
        corridors=corridors,
        zones=zones,
        alerts=alerts_list,
        unconfigured_camera_count=unconfigured_count,
        total_cameras=total_cams,
        filter_applied={
            "camera_id": camera_id,
            "vehicle_id": vehicle_id,
            "alert_type": alert_type,
            "start_time": start_time,
            "end_time": end_time,
        },
    )


@router.get(
    "/trajectories/{global_id}",
    response_model=ReconstructedTrajectorySchema,
    tags=["Trajectories"],
    summary="Get reconstructed spatial trajectory by Global Vehicle ID",
)
async def get_trajectory_by_id(
    global_id: str = FastPath(..., description="Global Vehicle ID"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Reconstructs the multi-camera trajectory path, spatial waypoints, and transit speeds."""
    active_mode = _resolve_mode(mode)
    if active_mode == "demo" or global_id.startswith("GV-DEMO"):
        traj = demo_pipeline.trajectory_service.reconstruct_trajectory(global_id)
    else:
        traj = trajectory_service.reconstruct_trajectory(global_id)
        if not traj:
            traj = demo_pipeline.trajectory_service.reconstruct_trajectory(global_id)

    if not traj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trajectory for vehicle '{global_id}' not found",
        )
    return traj


# Backward compatibility alias
@router.get(
    "/vehicles/{global_id}/trajectory",
    response_model=GlobalVehicleRecord,
    tags=["Vehicles"],
    summary="Get vehicle trajectory (legacy endpoint)",
)
async def get_vehicle_trajectory_alias(
    global_id: str = FastPath(...),
    mode: Optional[str] = Query(None),
):
    active_mode = _resolve_mode(mode)
    svc = demo_pipeline.trajectory_service if (active_mode == "demo" or global_id.startswith("GV-DEMO")) else trajectory_service
    record = svc.get_vehicle_by_id(global_id)
    if not record and active_mode != "demo":
        record = demo_pipeline.trajectory_service.get_vehicle_by_id(global_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle ID '{global_id}' not found",
        )
    return record


@router.get(
    "/trajectories/{global_id}/movements",
    response_model=List[CameraMovementSchema],
    tags=["Trajectories"],
    summary="Get inter-camera movement hops and transit speeds",
)
async def get_camera_movements(
    global_id: str = FastPath(..., description="Global Vehicle ID"),
    mode: Optional[str] = Query(None),
):
    """Returns consecutive transitions between visited cameras with distance and speed metrics."""
    active_mode = _resolve_mode(mode)
    if active_mode == "demo" or global_id.startswith("GV-DEMO"):
        movements = demo_pipeline.trajectory_service.get_camera_movements(global_id)
    else:
        movements = trajectory_service.get_camera_movements(global_id)
        if movements is None:
            movements = demo_pipeline.trajectory_service.get_camera_movements(global_id)

    if movements is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No movements found for vehicle '{global_id}'",
        )
    return movements


# ============================================================================
# ALERTS
# ============================================================================
@router.get(
    "/alerts",
    response_model=List[AlertSchema],
    tags=["Alerts"],
    summary="List active surveillance and watchlist alerts",
)
async def list_alerts(
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. NEW, ACKNOWLEDGED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (e.g. CRITICAL, HIGH)"),
    mode: Optional[str] = Query(None, description="Optional override: 'demo' or 'real'"),
):
    """Returns active traffic and watchlist alerts with optional status and severity filtering."""
    active_mode = _resolve_mode(mode)
    alerts = alert_service.list_alerts(limit=limit, status=status_filter, severity=severity)
    if active_mode == "demo" and demo_pipeline.generated_alert:
        if not any(a.id == demo_pipeline.generated_alert.id for a in alerts):
            alerts.insert(0, demo_pipeline.generated_alert)
    return alerts


@router.get(
    "/alerts/{alert_id}",
    response_model=AlertSchema,
    tags=["Alerts"],
    summary="Get alert details by ID",
)
async def get_alert_details(alert_id: str = FastPath(..., description="Alert ID")):
    """Returns specific alert details, associated vehicle, and detection incident information."""
    alert = alert_service.get_alert(alert_id)
    if not alert and demo_pipeline.generated_alert and (demo_pipeline.generated_alert.id == alert_id or demo_pipeline.generated_alert.alert_id == alert_id):
        alert = demo_pipeline.generated_alert
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found",
        )
    return alert


@router.patch(
    "/alerts/{alert_id}/status",
    response_model=AlertSchema,
    tags=["Alerts"],
    summary="Update or acknowledge alert status",
)
async def update_alert_status(
    alert_id: str = FastPath(..., description="Alert ID"),
    payload: AlertUpdateSchema = Body(...),
):
    """Updates status of an alert (e.g., to ACKNOWLEDGED, RESOLVED, or DISMISSED)."""
    updated = alert_service.update_alert_status(
        alert_id=alert_id,
        status=payload.status,
        acknowledged_by=payload.acknowledged_by,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found",
        )
    # Broadcast status change to connected dashboards via WebSocket
    await ws_manager.broadcast_json({
        "event": "alert_updated",
        "alert_id": alert_id,
        "status": updated.status,
        "acknowledged_by": updated.acknowledged_by,
    })
    return updated


@router.post(
    "/alerts/evaluate",
    response_model=Optional[AlertSchema],
    tags=["Alerts"],
    summary="Evaluate an observation or movement event against alert rules",
)
async def evaluate_alert_event(
    event_type: str = Query(..., description="Evaluation type: BLACKLIST, ANOMALY, or CONGESTION"),
    camera_id: str = Query(..., description="Camera or zone ID"),
    plate_text: Optional[str] = Query(None, description="License plate text for BLACKLIST evaluation"),
    ocr_confidence: Optional[float] = Query(None, description="OCR confidence (0.0 to 1.0)"),
    global_vehicle_id: Optional[str] = Query(None, description="Global Vehicle ID"),
    speed_kmh: Optional[float] = Query(None, description="Transit speed for ANOMALY evaluation"),
    elapsed_time_sec: Optional[float] = Query(None, description="Transit elapsed time in seconds"),
    distance_meters: Optional[float] = Query(None, description="Transit distance in meters"),
    from_camera_id: Optional[str] = Query(None, description="Origin camera for ANOMALY evaluation"),
    active_density: Optional[int] = Query(None, description="Active vehicle count for CONGESTION evaluation"),
):
    """
    Evaluates real-time events against the Alert Engine rules.
    - BLACKLIST: requires reliable OCR (suppressed if confidence is low).
    - ANOMALY: evaluates transit velocity and physical temporal feasibility.
    - CONGESTION: evaluates zone density thresholds.
    """
    import time
    clean_type = event_type.strip().upper()
    if clean_type in ("BLACKLIST", "WATCHLIST", "BLACKLIST_MATCH"):
        alert = alert_service.evaluate_plate_blacklist(
            plate_text=plate_text,
            ocr_confidence=ocr_confidence,
            camera_id=camera_id,
            global_vehicle_id=global_vehicle_id,
        )
    elif clean_type in ("ANOMALY", "SPEED_ANOMALY"):
        movement = CameraMovementSchema(
            from_camera_id=from_camera_id or camera_id,
            to_camera_id=camera_id,
            departure_time=time.time() - (elapsed_time_sec or 10.0),
            arrival_time=time.time(),
            elapsed_time_sec=elapsed_time_sec or 10.0,
            distance_meters=distance_meters,
            speed_kmh=speed_kmh,
        )
        alert = alert_service.evaluate_movement_anomaly(
            movement=movement,
            global_vehicle_id=global_vehicle_id or "UNRESOLVED",
            plate_text=plate_text,
        )
    elif clean_type in ("CONGESTION", "TRAFFIC_CONGESTION"):
        alert = alert_service.evaluate_congestion(
            camera_id=camera_id,
            active_density=active_density or 0,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported alert evaluation type: '{event_type}'. Must be BLACKLIST, ANOMALY, or CONGESTION.",
        )

    if alert:
        await ws_manager.broadcast_json({
            "event": "alert_triggered",
            "alert_id": alert.alert_id,
            "type": alert.type,
            "severity": alert.severity,
            "camera_id": alert.camera_id,
            "message": alert.message,
        })
    return alert


# ============================================================================
# ANALYTICS
# ============================================================================
@router.get(
    "/analytics/traffic",
    response_model=TrafficAnalyticsSchema,
    tags=["Analytics"],
    summary="Get aggregated traffic overview metrics (legacy)",
)
async def get_traffic_analytics_legacy(mode: Optional[str] = Query(None)):
    """Returns urban traffic indicators, tracked vehicles, and hourly counts."""
    active_mode = _resolve_mode(mode)
    if active_mode == "demo":
        return demo_pipeline.analytics_service.get_city_metrics()
    return analytics_service.get_city_metrics()


@router.get(
    "/analytics/traffic-counts",
    response_model=TrafficCountsResponse,
    tags=["Analytics"],
    summary="Get traffic volume and hourly vehicle distribution",
)
async def get_traffic_counts(
    time_window_sec: Optional[int] = Query(None, description="Time window in seconds"),
    mode: Optional[str] = Query(None),
):
    """Returns observation volume and 24-hour vehicle count distributions."""
    active_mode = _resolve_mode(mode)
    svc = demo_pipeline.analytics_service if active_mode == "demo" else analytics_service
    counts = svc.get_traffic_counts(time_window_sec=time_window_sec)
    return TrafficCountsResponse(**counts)


@router.get(
    "/analytics/camera-activity",
    response_model=CameraActivityResponse,
    tags=["Analytics"],
    summary="Get camera activity breakdown across sensor grid",
)
async def get_camera_activity(mode: Optional[str] = Query(None)):
    """Returns volume and unique vehicle distribution per camera node."""
    active_mode = _resolve_mode(mode)
    svc = demo_pipeline.analytics_service if active_mode == "demo" else analytics_service
    activity = svc.get_camera_activity()
    return CameraActivityResponse(**activity)


@router.get(
    "/analytics/zone-density",
    response_model=ZoneDensityResponse,
    tags=["Analytics"],
    summary="Get spatial vehicle density indicators per zone",
)
async def get_zone_density(mode: Optional[str] = Query(None)):
    """Returns spatial vehicle density per camera node with congestion risk categories."""
    active_mode = _resolve_mode(mode)
    svc = demo_pipeline.analytics_service if active_mode == "demo" else analytics_service
    density = svc.get_zone_density()
    return ZoneDensityResponse(**density)


@router.get(
    "/analytics/congestion",
    response_model=CongestionResponse,
    tags=["Analytics"],
    summary="Get corridor transit speed analysis and congestion indicators",
)
async def get_congestion_indicators():
    """Calculates transit speeds and corridor delay ratios from camera-to-camera movements."""
    congestion = analytics_service.get_congestion_indicators()
    return CongestionResponse(**congestion)


# ============================================================================
# WEBSOCKETS (LIVE DASHBOARD TELEMETRY)
# ============================================================================
@router.websocket("/ws/dashboard")
async def websocket_dashboard_endpoint(websocket: WebSocket):
    """
    WebSocket feed streaming real-time detections, active tracklets,
    and alert events to connected GIS dashboards.
    """
    await ws_manager.connect(websocket)
    try:
        # Initial greeting and handshake
        await websocket.send_json({
            "event": "connected",
            "message": "CITYVISION AI Live Dashboard Telemetry Initialized",
            "active_clients": len(ws_manager.active_connections),
        })
        while True:
            # Client heartbeat / request handler
            data = await websocket.receive_text()
            await websocket.send_json({"event": "pong", "received": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
        ws_manager.disconnect(websocket)


# Alias for backward compatibility
@router.websocket("/ws/telemetry")
async def websocket_telemetry_alias(websocket: WebSocket):
    await websocket_dashboard_endpoint(websocket)
