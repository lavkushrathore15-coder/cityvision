"""
SQLAlchemy and PostGIS Database Models for CITYVISION AI
Problem Statement ID: SIH26127

Defines relational and spatial entities:
1. Camera (POINT geometry, CCTV stream metadata)
2. Vehicle (Global vehicle identity & metadata)
3. Track (Intra-camera tracker state)
4. Observation (Frame detections, POINT geometry, bounding boxes)
5. OCRObservation (License plate text & confidence)
6. ReIDEmbedding (256-dim feature vectors & distance metrics)
7. VehicleMatch (Cross-camera association evidence)
8. Trajectory (LINESTRING geometry, chronological path & speed)
9. Alert (Spatial alerts, watchlist hits, violations)
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    LargeBinary,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geometry

Base = declarative_base()


class Camera(Base):
    """CCTV Camera node registered in the city sensor network."""
    __tablename__ = "cameras"

    camera_id = Column(String(64), primary_key=True)
    camera_name = Column(String(128), nullable=False)
    location_name = Column(String(256), nullable=True)
    
    # PostGIS Spatial Point (Longitude, Latitude) in WGS-84 (SRID 4326)
    geom = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    heading_deg = Column(Float, default=0.0)
    fps = Column(Integer, default=15)
    source_type = Column(String(32), default="file")  # "file", "rtsp", "webcam"
    
    # Reference to video stream/source location; video files are NOT stored in PostgreSQL
    stream_uri = Column(Text, nullable=True)
    status = Column(String(32), default="configured")  # "configured", "streaming", "offline", "error"
    
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tracks = relationship("Track", back_populates="camera", cascade="all, delete-orphan")
    observations = relationship("Observation", back_populates="camera", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="camera")

    def __repr__(self) -> str:
        return f"<Camera(id='{self.camera_id}', name='{self.camera_name}', status='{self.status}')>"


class Vehicle(Base):
    """Global unique vehicle identity correlated across multiple cameras."""
    __tablename__ = "vehicles"

    global_vehicle_id = Column(String(64), primary_key=True)
    primary_plate = Column(String(32), index=True, nullable=True)
    vehicle_class = Column(String(32), nullable=False, default="car")
    first_seen = Column(DateTime(timezone=True), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=False)
    total_observations = Column(Integer, default=1, nullable=False)
    total_cameras_visited = Column(Integer, default=1, nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False, index=True)
    flag_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    observations = relationship("Observation", back_populates="vehicle", cascade="all, delete-orphan")
    tracks = relationship("Track", back_populates="vehicle")
    trajectories = relationship("Trajectory", back_populates="vehicle", cascade="all, delete-orphan")
    matches = relationship("VehicleMatch", back_populates="vehicle", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="vehicle")

    def __repr__(self) -> str:
        return f"<Vehicle(id='{self.global_vehicle_id}', plate='{self.primary_plate}', class='{self.vehicle_class}')>"


class Track(Base):
    """Intra-camera continuous multi-object track."""
    __tablename__ = "tracks"

    track_id = Column(String(96), primary_key=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    local_track_id = Column(Integer, nullable=False, index=True)
    global_vehicle_id = Column(String(64), ForeignKey("vehicles.global_vehicle_id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_class = Column(String(32), nullable=False, default="car")
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    detection_confidence = Column(Float, nullable=False)
    total_frames = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relationships
    camera = relationship("Camera", back_populates="tracks")
    vehicle = relationship("Vehicle", back_populates="tracks")

    __table_args__ = (
        Index("idx_tracks_camera_local", "camera_id", "local_track_id"),
    )


class Observation(Base):
    """Frame-level vehicle bounding box observation with spatial camera binding."""
    __tablename__ = "observations"

    observation_id = Column(String(96), primary_key=True)
    global_vehicle_id = Column(String(64), ForeignKey("vehicles.global_vehicle_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    local_track_id = Column(Integer, nullable=False)
    frame_number = Column(Integer, default=0, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # PostGIS Point location where observation occurred
    geom = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Vehicle Bounding Box coordinates
    bbox_x1 = Column(Float, nullable=False)
    bbox_y1 = Column(Float, nullable=False)
    bbox_x2 = Column(Float, nullable=False)
    bbox_y2 = Column(Float, nullable=False)
    detection_confidence = Column(Float, default=1.0, nullable=False)
    
    # External reference to stored crop; image binary not in DB
    source_frame_uri = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="observations")
    camera = relationship("Camera", back_populates="observations")
    ocr_reads = relationship("OCRObservation", back_populates="observation", cascade="all, delete-orphan")
    reid_embeddings = relationship("ReIDEmbedding", back_populates="observation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_observations_camera_time", "camera_id", "timestamp"),
        Index("idx_observations_global_time", "global_vehicle_id", "timestamp"),
    )


class OCRObservation(Base):
    """License plate detection and recognition result for an observation."""
    __tablename__ = "ocr_observations"

    ocr_id = Column(String(96), primary_key=True)
    observation_id = Column(String(96), ForeignKey("observations.observation_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    local_track_id = Column(Integer, nullable=False)
    frame_number = Column(Integer, default=0, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    raw_text = Column(String(64), nullable=False)
    normalized_text = Column(String(64), nullable=False, index=True)
    ocr_confidence = Column(Float, nullable=False)
    
    plate_bbox_x1 = Column(Float, nullable=True)
    plate_bbox_y1 = Column(Float, nullable=True)
    plate_bbox_x2 = Column(Float, nullable=True)
    plate_bbox_y2 = Column(Float, nullable=True)
    is_blurry = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relationship
    observation = relationship("Observation", back_populates="ocr_reads")


class ReIDEmbedding(Base):
    """Vehicle visual appearance embedding vector for cross-camera re-identification."""
    __tablename__ = "reid_embeddings"

    embedding_id = Column(String(96), primary_key=True)
    observation_id = Column(String(96), ForeignKey("observations.observation_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    local_track_id = Column(Integer, nullable=False)
    frame_number = Column(Integer, default=0, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    model_identifier = Column(String(64), nullable=False)
    dimension = Column(Integer, default=256, nullable=False)
    distance_metric = Column(String(32), default="cosine", nullable=False)
    
    # Binary packed float32 vector (256 * 4 = 1024 bytes)
    embedding = Column(LargeBinary, nullable=False)
    embedding_preview = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relationship
    observation = relationship("Observation", back_populates="reid_embeddings")


class VehicleMatch(Base):
    """Explainable cross-camera vehicle association record."""
    __tablename__ = "vehicle_matches"

    match_id = Column(String(96), primary_key=True)
    global_vehicle_id = Column(String(64), ForeignKey("vehicles.global_vehicle_id", ondelete="CASCADE"), nullable=False, index=True)
    source_observation_id = Column(String(96), ForeignKey("observations.observation_id", ondelete="CASCADE"), nullable=False)
    target_observation_id = Column(String(96), ForeignKey("observations.observation_id", ondelete="CASCADE"), nullable=False)
    source_camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False)
    target_camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False)
    
    match_score = Column(Float, nullable=False)
    confidence_tier = Column(String(32), nullable=False, index=True)  # "HIGH", "MEDIUM", "LOW", "UNMATCHED"
    plate_score = Column(Float, nullable=True)
    reid_score = Column(Float, nullable=True)
    spatial_score = Column(Float, nullable=True)
    temporal_score = Column(Float, nullable=True)
    
    explanation = Column(Text, nullable=False)
    evidence_breakdown = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    matched_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

    # Relationship
    vehicle = relationship("Vehicle", back_populates="matches")

    __table_args__ = (
        Index("idx_matches_pair", "source_camera_id", "target_camera_id", "matched_at"),
    )


class Trajectory(Base):
    """Reconstructed cross-camera vehicle trajectory with PostGIS LineString path."""
    __tablename__ = "trajectories"

    trajectory_id = Column(String(96), primary_key=True)
    global_vehicle_id = Column(String(64), ForeignKey("vehicles.global_vehicle_id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    total_distance_km = Column(Float, nullable=True)
    avg_speed_kmh = Column(Float, nullable=True)
    visited_cameras_count = Column(Integer, default=1, nullable=False)
    
    # PostGIS LineString geometry connecting visited cameras in sequence
    geom_path = Column(Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True), nullable=True)
    
    # Detailed ordered waypoints with timestamps and camera metadata
    waypoints = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    is_spatial_available = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    vehicle = relationship("Vehicle", back_populates="trajectories")

    __table_args__ = (
        Index("idx_trajectories_time_range", "start_time", "end_time"),
    )


class Alert(Base):
    """Urban surveillance and traffic alert entity."""
    __tablename__ = "alerts"

    alert_id = Column(String(96), primary_key=True)
    alert_type = Column(String(64), nullable=False, index=True)  # "WATCHLIST_HIT", "SPEED_VIOLATION", "UNUSUAL_TRANSIT", "RESTRICTED_ZONE"
    severity = Column(String(32), nullable=False, index=True)    # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    
    global_vehicle_id = Column(String(64), ForeignKey("vehicles.global_vehicle_id", ondelete="SET NULL"), nullable=True, index=True)
    plate_text = Column(String(32), nullable=True, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="SET NULL"), nullable=True, index=True)
    
    # PostGIS Point location where alert was triggered
    geom = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    details = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    
    status = Column(String(32), default="NEW", nullable=False, index=True)  # "NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"
    acknowledged_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relationships
    camera = relationship("Camera", back_populates="alerts")
    vehicle = relationship("Vehicle", back_populates="alerts")

    __table_args__ = (
        Index("idx_alerts_status_severity", "status", "severity", "timestamp"),
    )
