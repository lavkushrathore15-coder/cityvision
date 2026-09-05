"""
Schema definitions for Global Vehicle Trajectories, Observations, and Movements
Problem Statement ID: SIH26127
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    from pydantic import BaseModel, Field

    class VehicleObservationEntity(BaseModel):
        """Persistent representation of a single vehicle observation."""
        observation_id: str
        global_vehicle_id: str
        camera_id: str
        local_track_id: int
        timestamp: float
        timestamp_iso: str
        location: Optional[Dict[str, float]] = None  # None if camera has unconfigured GPS
        plate_text: Optional[str] = None
        ocr_confidence: Optional[float] = None
        reid_info: Optional[str] = None
        confidence: float = 1.0
        source_frame: int = 0

    class CameraVisitSchema(BaseModel):
        """Cluster of continuous observations of a vehicle at a single camera."""
        camera_id: str
        camera_name: str
        arrival_time: float
        departure_time: float
        arrival_iso: str
        departure_iso: str
        duration_sec: float
        observation_count: int
        plate_reads: List[str] = Field(default_factory=list)
        location: Optional[Dict[str, float]] = None

    class CameraMovementSchema(BaseModel):
        """Movement hop between two consecutive camera visits."""
        from_camera_id: str
        to_camera_id: str
        departure_time: float
        arrival_time: float
        elapsed_time_sec: float
        distance_meters: Optional[float] = None
        speed_kmh: Optional[float] = None
        is_feasible: bool = True

    class ReconstructedTrajectorySchema(BaseModel):
        """Full chronologically reconstructed vehicle trajectory."""
        global_vehicle_id: str
        primary_plate: Optional[str] = None
        vehicle_class: str = "car"
        first_seen_iso: str
        last_seen_iso: str
        first_seen_timestamp: float
        last_seen_timestamp: float
        is_spatial_available: bool  # False if any camera waypoint lacks GPS coordinates
        visited_cameras: List[str]
        total_distance_meters: Optional[float] = None
        observations: List[VehicleObservationEntity] = Field(default_factory=list)
        camera_visits: List[CameraVisitSchema] = Field(default_factory=list)
        movements: List[CameraMovementSchema] = Field(default_factory=list)

    # Legacy schemas for backward compatibility
    class TrajectoryWaypoint(BaseModel):
        camera_id: str
        camera_name: str
        latitude: float
        longitude: float
        timestamp_iso: str
        speed_estimate_kmh: Optional[float] = None
        confidence: float

    class GlobalVehicleRecord(BaseModel):
        global_id: str
        primary_plate: Optional[str] = None
        vehicle_class: str = "car"
        first_seen: str
        last_seen: str
        total_cameras_passed: int = 1
        waypoints: List[TrajectoryWaypoint] = Field(default_factory=list)
        is_flagged: bool = False

    class AlertSchema(BaseModel):
        id: str = ""
        alert_id: Optional[str] = None
        type: Optional[str] = None
        alert_type: Optional[str] = None
        severity: str = "MEDIUM"  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
        camera_id: str
        global_vehicle_id: Optional[str] = None
        plate_text: Optional[str] = None
        message: str = ""
        timestamp: Optional[float] = None
        timestamp_iso: Optional[str] = None
        status: str = "NEW"  # "NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"
        acknowledged_by: Optional[str] = None
        evidence: Optional[Dict[str, Any]] = None
        details: Optional[Dict[str, Any]] = None

        def model_post_init(self, __context: Any) -> None:
            if not self.alert_id and self.id:
                self.alert_id = self.id
            elif not self.id and self.alert_id:
                self.id = self.alert_id

            if not self.type and self.alert_type:
                self.type = self.alert_type
            elif not self.alert_type and self.type:
                self.alert_type = self.type
            elif not self.type and not self.alert_type:
                self.type = "ANOMALY"
                self.alert_type = "ANOMALY"

            if not self.evidence and self.details:
                self.evidence = self.details
            elif not self.details and self.evidence:
                self.details = self.evidence
            elif self.evidence is None:
                self.evidence = {}
                self.details = {}

            if not self.timestamp_iso:
                import datetime
                if self.timestamp:
                    self.timestamp_iso = datetime.datetime.fromtimestamp(
                        self.timestamp, tz=datetime.timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    now = datetime.datetime.now(datetime.timezone.utc)
                    self.timestamp = now.timestamp()
                    self.timestamp_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            elif not self.timestamp:
                try:
                    import datetime
                    dt = datetime.datetime.fromisoformat(self.timestamp_iso.replace("Z", "+00:00"))
                    self.timestamp = dt.timestamp()
                except Exception:
                    pass

            if not self.message:
                self.message = f"{self.type} alert on camera {self.camera_id}"

    class TrafficAnalyticsSchema(BaseModel):
        active_camera_count: int
        total_tracked_vehicles: int
        average_speed_kmh: float
        hourly_vehicle_counts: List[int]
        congestion_index_percent: float

except ImportError:
    @dataclass
    class VehicleObservationEntity:
        observation_id: str
        global_vehicle_id: str
        camera_id: str
        local_track_id: int
        timestamp: float
        timestamp_iso: str
        location: Optional[Dict[str, float]] = None
        plate_text: Optional[str] = None
        ocr_confidence: Optional[float] = None
        reid_info: Optional[str] = None
        confidence: float = 1.0
        source_frame: int = 0

    @dataclass
    class CameraVisitSchema:
        camera_id: str
        camera_name: str
        arrival_time: float
        departure_time: float
        arrival_iso: str
        departure_iso: str
        duration_sec: float
        observation_count: int
        plate_reads: List[str] = field(default_factory=list)
        location: Optional[Dict[str, float]] = None

    @dataclass
    class CameraMovementSchema:
        from_camera_id: str
        to_camera_id: str
        departure_time: float
        arrival_time: float
        elapsed_time_sec: float
        distance_meters: Optional[float] = None
        speed_kmh: Optional[float] = None
        is_feasible: bool = True

    @dataclass
    class ReconstructedTrajectorySchema:
        global_vehicle_id: str
        first_seen_iso: str
        last_seen_iso: str
        first_seen_timestamp: float
        last_seen_timestamp: float
        is_spatial_available: bool
        visited_cameras: List[str]
        primary_plate: Optional[str] = None
        vehicle_class: str = "car"
        total_distance_meters: Optional[float] = None
        observations: List[VehicleObservationEntity] = field(default_factory=list)
        camera_visits: List[CameraVisitSchema] = field(default_factory=list)
        movements: List[CameraMovementSchema] = field(default_factory=list)

    @dataclass
    class TrajectoryWaypoint:
        camera_id: str
        camera_name: str
        latitude: float
        longitude: float
        timestamp_iso: str
        speed_estimate_kmh: Optional[float]
        confidence: float

    @dataclass
    class GlobalVehicleRecord:
        global_id: str
        primary_plate: Optional[str]
        vehicle_class: str
        first_seen: str
        last_seen: str
        total_cameras_passed: int
        waypoints: List[TrajectoryWaypoint]
        is_flagged: bool = False

    @dataclass
    class AlertSchema:
        id: str
        alert_type: str
        severity: str
        camera_id: str
        global_vehicle_id: Optional[str] = None
        plate_text: Optional[str] = None
        message: str = ""
        timestamp: Optional[float] = None
        timestamp_iso: str = ""
        status: str = "NEW"
        alert_id: Optional[str] = None
        type: Optional[str] = None
        evidence: Optional[Dict[str, Any]] = None
        details: Optional[Dict[str, Any]] = None
        acknowledged_by: Optional[str] = None

    @dataclass
    class TrafficAnalyticsSchema:
        active_camera_count: int
        total_tracked_vehicles: int
        average_speed_kmh: float
        hourly_vehicle_counts: List[int]
        congestion_index_percent: float
