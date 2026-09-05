"""
Schema definition for ANPR and Re-ID
Problem Statement ID: SIH26127
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    from pydantic import BaseModel, Field

    class PlateObservationSchema(BaseModel):
        camera_id: str
        local_track_id: int
        timestamp: float
        raw_text: str
        normalized_text: str
        ocr_confidence: float
        plate_bbox: Optional[Dict[str, float]] = None
        frame_number: int = 0
        is_blurry: bool = False
        quality_score: float = 0.0

    class PlateConsensusSchema(BaseModel):
        camera_id: str
        local_track_id: int
        consensus_text: str
        average_confidence: float
        total_observations: int
        candidate_frequencies: Dict[str, float] = Field(default_factory=dict)

    class PlateReadSchema(BaseModel):
        camera_id: str
        track_id: int
        plate_text: str
        confidence: float
        timestamp_ms: float
        is_watchlist_match: bool = False

    class ReIdFeatureSchema(BaseModel):
        camera_id: str
        track_id: int
        feature_dim: int = 256
        vector_preview: List[float]  # First few dimensions for telemetry
        timestamp_ms: float
        model_identifier: str = "yolov8n-backbone-embed"
        distance_metric: str = "cosine"

    class ReIdSimilaritySchema(BaseModel):
        similarity_score: float
        distance: float
        distance_metric: str
        model_identifier: str
        is_same_vehicle_proof: bool = False
        disclaimer: str

except ImportError:
    @dataclass
    class PlateObservationSchema:
        camera_id: str
        local_track_id: int
        timestamp: float
        raw_text: str
        normalized_text: str
        ocr_confidence: float
        plate_bbox: Optional[Dict[str, float]] = None
        frame_number: int = 0
        is_blurry: bool = False
        quality_score: float = 0.0

    @dataclass
    class PlateConsensusSchema:
        camera_id: str
        local_track_id: int
        consensus_text: str
        average_confidence: float
        total_observations: int
        candidate_frequencies: Dict[str, float] = field(default_factory=dict)

    @dataclass
    class PlateReadSchema:
        camera_id: str
        track_id: int
        plate_text: str
        confidence: float
        timestamp_ms: float
        is_watchlist_match: bool = False

    @dataclass
    class ReIdFeatureSchema:
        camera_id: str
        track_id: int
        feature_dim: int
        vector_preview: List[float]
        timestamp_ms: float
        model_identifier: str = "yolov8n-backbone-embed"
        distance_metric: str = "cosine"

    @dataclass
    class ReIdSimilaritySchema:
        similarity_score: float
        distance: float
        distance_metric: str
        model_identifier: str
        is_same_vehicle_proof: bool = False
        disclaimer: str = ""
