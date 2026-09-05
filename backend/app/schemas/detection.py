"""
Schema definition for Vehicle Detections and Tracks
"""
from typing import Optional, List, Tuple
from dataclasses import dataclass

try:
    from pydantic import BaseModel

    class BoundingBoxSchema(BaseModel):
        x1: float
        y1: float
        x2: float
        y2: float

    class DetectionSchema(BaseModel):
        camera_id: str
        frame_id: int
        timestamp_ms: float
        bbox: BoundingBoxSchema
        confidence: float
        class_name: str

    class TrackletSchema(BaseModel):
        track_id: int
        camera_id: str
        class_name: str
        start_time_ms: float
        end_time_ms: float
        trajectory_points: List[Tuple[float, float]]  # [(x, y), ...]
        is_active: bool = True

except ImportError:
    @dataclass
    class BoundingBoxSchema:
        x1: float
        y1: float
        x2: float
        y2: float

    @dataclass
    class DetectionSchema:
        camera_id: str
        frame_id: int
        timestamp_ms: float
        bbox: BoundingBoxSchema
        confidence: float
        class_name: str

    @dataclass
    class TrackletSchema:
        track_id: int
        camera_id: str
        class_name: str
        start_time_ms: float
        end_time_ms: float
        trajectory_points: List[Tuple[float, float]]
        is_active: bool = True
