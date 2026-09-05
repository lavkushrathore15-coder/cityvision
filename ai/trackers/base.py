"""
Abstract Base Classes and Data Structures for Multi-Object Tracking
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
import numpy as np

from ai.detectors.base import BoundingBox, DetectionResult


class TrackState(str, Enum):
    NEW = "new"              # Track newly created, awaiting confirmation
    TRACKED = "tracked"      # Actively tracked and confirmed
    LOST = "lost"            # Temporarily occluded / missing detection
    REMOVED = "removed"      # Terminated / aged out


@dataclass
class TrackedVehicle:
    """
    Representation of a single vehicle tracked within a single camera feed.
    NOTE: local_track_id is strictly local to this camera_id and does NOT represent
    a global vehicle identity across different cameras.
    """
    local_track_id: int
    camera_id: str
    bounding_box: BoundingBox
    class_name: str
    detection_confidence: float
    frame_number: int
    timestamp: float         # Milliseconds or epoch seconds
    state: TrackState = TrackState.TRACKED
    hits: int = 1            # Total frames this track was matched
    lost_frames: int = 0     # Consecutive frames track has been missing
    trajectory_history: List[Tuple[float, float]] = field(default_factory=list)  # [(cx, cy), ...]

    # Compatibility aliases for legacy/existing interfaces
    @property
    def track_id(self) -> int:
        return self.local_track_id

    @property
    def bbox(self) -> BoundingBox:
        return self.bounding_box

    @property
    def confidence(self) -> float:
        return self.detection_confidence

    @property
    def frame_index(self) -> int:
        return self.frame_number

    @property
    def timestamp_ms(self) -> float:
        return self.timestamp

    @property
    def is_active(self) -> bool:
        return self.state == TrackState.TRACKED


class BaseTracker(ABC):
    """
    Contract for single-camera multi-object tracking (e.g. ByteTrack, BoT-SORT).
    """

    @abstractmethod
    def reset(self) -> None:
        """Resets all internal Kalman filter states and track ID counters."""
        pass

    @abstractmethod
    def update(
        self,
        detections: List[DetectionResult],
        frame: Optional[np.ndarray],
        camera_id: str,
        frame_index: int,
        timestamp_ms: float,
    ) -> List[TrackedVehicle]:
        """
        Updates the tracker with frame detections.
        Handles track creation, updates, disappearance, and termination.
        Returns currently active tracked vehicles.
        """
        pass
