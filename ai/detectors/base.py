"""
Abstract Base Classes for Vehicle Detection
STATUS: INTERFACE DEFINITION ONLY (Model inference will be implemented in subsequent AI phase)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
import numpy as np


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class DetectionResult:
    bbox: BoundingBox
    confidence: float
    class_id: int
    class_name: str  # e.g., 'car', 'motorcycle', 'bus', 'truck'


class BaseVehicleDetector(ABC):
    """
    Contract for vehicle detection models (e.g., YOLOv8, YOLO11, ONNX Runtime).
    """

    @abstractmethod
    def load_model(self, weights_path: str, device: str = "cpu") -> None:
        """Loads model weights into memory and prepares inference engine."""
        pass

    @abstractmethod
    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.35) -> List[DetectionResult]:
        """
        Executes inference on a single video frame (BGR format from OpenCV).
        Returns a list of DetectionResult objects.
        """
        pass
