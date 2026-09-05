"""
Base Classes and Data Structures for ANPR Subsystem (CITYVISION AI)
Problem Statement ID: SIH26127
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np

from ai.detectors.base import BoundingBox


@dataclass
class PlateDetectionResult:
    """Represents a localized license plate candidate within a vehicle image."""
    bbox: BoundingBox
    confidence: float
    plate_crop: np.ndarray
    aspect_ratio: float = 0.0
    area_ratio: float = 0.0


@dataclass
class LicensePlateRead:
    """Historical read container for plate recognition."""
    plate_text: str
    confidence: float
    normalized_text: str
    plate_bbox: Optional[BoundingBox] = None


@dataclass
class PlateObservationRecord:
    """
    Suggested record schema for an individual ANPR observation on a local track:
    camera_id, local_track_id, timestamp, raw_text, normalized_text,
    ocr_confidence, plate_bbox, frame_number
    """
    camera_id: str
    local_track_id: int
    timestamp: float
    raw_text: str
    normalized_text: str
    ocr_confidence: float
    plate_bbox: Optional[BoundingBox] = None
    frame_number: int = 0
    is_blurry: bool = False
    quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "local_track_id": self.local_track_id,
            "timestamp": self.timestamp,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "ocr_confidence": round(self.ocr_confidence, 4),
            "plate_bbox": {"x1": self.plate_bbox.x1, "y1": self.plate_bbox.y1, "x2": self.plate_bbox.x2, "y2": self.plate_bbox.y2} if self.plate_bbox else None,
            "frame_number": self.frame_number,
            "is_blurry": self.is_blurry,
            "quality_score": round(self.quality_score, 4),
        }


@dataclass
class PlateConsensusResult:
    """Represents the multi-frame consensus license plate for a local track."""
    camera_id: str
    local_track_id: int
    consensus_text: str
    average_confidence: float
    total_observations: int
    candidate_frequencies: Dict[str, float] = field(default_factory=dict)
    all_observations: List[PlateObservationRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "local_track_id": self.local_track_id,
            "consensus_text": self.consensus_text,
            "average_confidence": round(self.average_confidence, 4),
            "total_observations": self.total_observations,
            "candidate_frequencies": {k: round(v, 4) for k, v in self.candidate_frequencies.items()},
            "observation_count": len(self.all_observations),
        }


class BasePlateDetector(ABC):
    """Contract for localizing license plates within vehicle crops."""

    @abstractmethod
    def detect_plates(self, vehicle_crop: np.ndarray) -> List[PlateDetectionResult]:
        """Detect license plate candidate regions in vehicle frame crop."""
        pass


class BasePlateOCR(ABC):
    """Contract for optical character recognition of license plates."""

    @abstractmethod
    def recognize_text(self, plate_crop: np.ndarray) -> List[Dict[str, Any]]:
        """
        Recognize text in cropped plate image.
        Returns list of dicts with keys: 'raw_text', 'confidence', 'bbox'.
        """
        pass
