"""
Typed Request and Response Schemas for CITYVISION AI FastAPI Endpoints
Problem Statement ID: SIH26127
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.schemas.trajectory import (
    VehicleObservationEntity,
    CameraVisitSchema,
    CameraMovementSchema,
    TrajectoryWaypoint,
    ReconstructedTrajectorySchema,
)


class ErrorResponse(BaseModel):
    """Standardized structured error response."""
    error: str = Field(..., description="Short error name or HTTP error title")
    detail: str = Field(..., description="Detailed explanatory error message")
    code: str = Field(..., description="Internal error code identifier")
    timestamp: str = Field(..., description="ISO-8601 error generation timestamp")


class ObservationDetailResponse(BaseModel):
    """Detailed observation representation returned by GET /api/v1/observations/{id}."""
    observation_id: str
    global_vehicle_id: str
    camera_id: str
    camera_name: Optional[str] = None
    local_track_id: int
    frame_number: int = 0
    timestamp: float
    timestamp_iso: str
    location: Optional[Dict[str, float]] = None
    bounding_box: Dict[str, float]
    detection_confidence: float
    plate_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    reid_preview: Optional[str] = None
    source_frame_uri: Optional[str] = None


class VehicleHistoryResponse(BaseModel):
    """Chronological event history for a vehicle across the city network."""
    global_vehicle_id: str
    primary_plate: Optional[str] = None
    vehicle_class: str
    first_seen: str
    last_seen: str
    total_cameras_visited: int
    total_observations: int
    is_flagged: bool
    flag_reason: Optional[str] = None
    camera_visits: List[CameraVisitSchema]
    movements: List[CameraMovementSchema]


class AlertUpdateSchema(BaseModel):
    """Payload for PATCH /api/v1/alerts/{id}/status."""
    status: str = Field(..., description="New status: ACKNOWLEDGED, RESOLVED, DISMISSED, or NEW")
    acknowledged_by: Optional[str] = Field(None, description="Operator or subsystem identifier")


class AlertResponse(BaseModel):
    """Detailed alert schema."""
    alert_id: str
    alert_type: str
    severity: str
    global_vehicle_id: Optional[str] = None
    plate_text: Optional[str] = None
    camera_id: Optional[str] = None
    camera_name: Optional[str] = None
    location: Optional[Dict[str, float]] = None
    timestamp: str
    details: Dict[str, Any]
    status: str
    acknowledged_by: Optional[str] = None


class TrafficCountsResponse(BaseModel):
    """Real-time and aggregated traffic volume statistics."""
    total_tracked_vehicles: int
    active_camera_count: int
    hourly_vehicle_counts: List[int]
    total_observations_recorded: int
    time_window_start_iso: str
    time_window_end_iso: str


class CameraActivityItem(BaseModel):
    """Activity breakdown for an individual CCTV node."""
    camera_id: str
    camera_name: str
    total_observations: int
    unique_vehicles_observed: int
    last_observation_timestamp: Optional[str] = None
    status: str


class CameraActivityResponse(BaseModel):
    """Response containing activity metrics across all registered cameras."""
    cameras: List[CameraActivityItem]
    most_active_camera_id: Optional[str] = None


class ZoneDensityItem(BaseModel):
    """Spatial density indicator for a specific camera zone."""
    camera_id: str
    zone_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    active_vehicle_density: int
    density_level: str  # "LOW", "MODERATE", "HIGH", "SEVERE"


class ZoneDensityResponse(BaseModel):
    """Collection of zone density indicators."""
    zones: List[ZoneDensityItem]
    city_average_density: float


class CongestionIndicatorItem(BaseModel):
    """Corridor congestion metrics based on actual transit travel times."""
    from_camera_id: str
    to_camera_id: str
    corridor_name: str
    distance_meters: Optional[float] = None
    recorded_transits: int
    average_transit_speed_kmh: Optional[float] = None
    free_flow_speed_kmh: float = 50.0
    congestion_level: str  # "FREE_FLOW", "MODERATE", "CONGESTED", "HEAVY_CONGESTION"
    delay_ratio: float = 1.0


class CongestionResponse(BaseModel):
    """Citywide corridor congestion analysis."""
    corridors: List[CongestionIndicatorItem]
    citywide_congestion_index_percent: float


class GisSummaryResponse(BaseModel):
    """Aggregated GIS spatial intelligence payload."""
    cameras: List[Dict[str, Any]]
    trajectories: List[Dict[str, Any]]
    corridors: List[CongestionIndicatorItem]
    zones: List[ZoneDensityItem]
    alerts: List[Dict[str, Any]]
    unconfigured_camera_count: int
    total_cameras: int
    filter_applied: Dict[str, Any]

