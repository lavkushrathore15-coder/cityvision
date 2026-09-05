"""
Base Classes and Data Structures for Cross-Camera Vehicle Association
Problem Statement ID: SIH26127

Defines vehicle observation packages, match records, confidence tiers,
and abstract matcher contracts.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import numpy as np


class ConfidenceTier(str, Enum):
    """Confidence tier classification for cross-camera associations."""
    HIGH = "HIGH CONFIDENCE"
    MEDIUM = "MEDIUM CONFIDENCE"
    LOW = "LOW CONFIDENCE"
    UNMATCHED = "UNMATCHED"


@dataclass
class VehicleObservation:
    """
    Standard multi-modal observation of a vehicle at a specific camera location.
    Integrates ANPR/OCR, Appearance Re-ID, Camera Metadata, and Timestamps.
    """
    camera_id: str
    local_track_id: int
    timestamp: float  # In seconds (epoch)
    normalized_plate: Optional[str] = None
    raw_plate: Optional[str] = None
    ocr_confidence: float = 0.0
    embedding: Optional[np.ndarray] = None  # 1D L2-normalized vector
    vehicle_class: str = "car"
    bbox_coords: Optional[tuple] = None
    timestamp_ms: Optional[float] = None
    global_vehicle_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp_ms is None:
            self.timestamp_ms = self.timestamp * 1000.0
        # Backward compatibility for plate_text
        if hasattr(self, "plate_text") and self.plate_text and not self.normalized_plate:
            self.normalized_plate = self.plate_text

    @property
    def plate_text(self) -> Optional[str]:
        return self.normalized_plate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "local_track_id": self.local_track_id,
            "timestamp": round(self.timestamp, 3),
            "timestamp_ms": round(self.timestamp_ms, 1) if self.timestamp_ms else None,
            "normalized_plate": self.normalized_plate,
            "raw_plate": self.raw_plate,
            "ocr_confidence": round(self.ocr_confidence, 4),
            "has_embedding": self.embedding is not None,
            "vehicle_class": self.vehicle_class,
            "global_vehicle_id": self.global_vehicle_id,
        }


@dataclass
class CrossCameraMatchRecord:
    """
    Explainable match record evaluating whether two observations from different
    cameras represent the same physical vehicle.
    """
    global_vehicle_id: Optional[str]
    observation_a: VehicleObservation
    observation_b: VehicleObservation
    match_score: float  # Composite explainable score: 0.0 to 1.0
    confidence_tier: ConfidenceTier
    is_matched: bool  # True only if confidence tier is HIGH or qualified MEDIUM
    evidence_breakdown: Dict[str, Any]
    explanation: str  # Human-readable reasoning trail
    timestamp: float  # Decision epoch timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global_vehicle_id": self.global_vehicle_id,
            "camera_a": self.observation_a.camera_id,
            "camera_b": self.observation_b.camera_id,
            "track_id_a": self.observation_a.local_track_id,
            "track_id_b": self.observation_b.local_track_id,
            "match_score": round(self.match_score, 4),
            "confidence_tier": self.confidence_tier.value,
            "is_matched": self.is_matched,
            "evidence_breakdown": self.evidence_breakdown,
            "explanation": self.explanation,
            "timestamp": round(self.timestamp, 3),
        }


@dataclass
class MatchResult:
    """Legacy contract compatibility container."""
    global_vehicle_id: str
    confidence: float
    matched_by: str
    previous_camera_id: Optional[str] = None
    time_delta_sec: Optional[float] = None


class BaseCrossCameraMatcher(ABC):
    """
    Contract for matching vehicle observations across cameras without overlapping views.
    Fuses:
    1. License plate text agreement (exact & Levenshtein)
    2. OCR confidence evaluation
    3. Re-ID visual appearance similarity
    4. Spatio-temporal road topology feasibility (speed & travel time constraints)
    """

    @abstractmethod
    def match_pair(
        self,
        obs_a: VehicleObservation,
        obs_b: VehicleObservation,
    ) -> CrossCameraMatchRecord:
        """Evaluate a pair of observations across different cameras."""
        pass

    @abstractmethod
    def associate(
        self,
        observation: VehicleObservation,
        active_gallery: List[VehicleObservation],
    ) -> MatchResult:
        """Determines whether observation belongs to an existing Global Vehicle ID."""
        pass
