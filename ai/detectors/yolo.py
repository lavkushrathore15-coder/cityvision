"""
YOLO Vehicle Detector Implementation using Ultralytics
Supports real inference on CPU or CUDA devices.
Filters for traffic vehicle classes (car, motorcycle, bus, truck) by default.
"""
from typing import Dict, List, Optional, Set
import numpy as np
from ultralytics import YOLO

from ai.detectors.base import BaseVehicleDetector, BoundingBox, DetectionResult

# Standard COCO class indices for motorized road traffic vehicles
DEFAULT_VEHICLE_CLASSES: Dict[int, str] = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


class YOLOVehicleDetector(BaseVehicleDetector):
    """
    Production detector wrapping Ultralytics YOLO models for vehicle identification.
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        device: str = "cpu",
        target_classes: Optional[Dict[int, str]] = None,
    ):
        self.device = device
        self.target_classes = target_classes or DEFAULT_VEHICLE_CLASSES
        self.model: Optional[YOLO] = None
        self.weights_path: Optional[str] = None

        if weights_path:
            self.load_model(weights_path, device=device)

    def load_model(self, weights_path: str, device: str = "cpu") -> None:
        """
        Loads pre-trained YOLO weights (.pt) and sets inference execution device.
        """
        self.device = device
        self.weights_path = weights_path
        self.model = YOLO(weights_path)
        # Verify model loaded
        if self.model is None:
            raise RuntimeError(f"Failed to initialize YOLO model from: {weights_path}")

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: float = 0.35,
    ) -> List[DetectionResult]:
        """
        Executes real YOLO inference on a single frame (BGR matrix).
        Filters predictions to include only configured vehicle categories exceeding
        the confidence threshold.
        Coordinates are preserved in the original input frame's pixel dimensions.
        """
        if self.model is None:
            raise RuntimeError("YOLO model has not been loaded. Call load_model() first.")

        if frame is None or frame.size == 0:
            return []

        # Run inference (verbose=False avoids polluting stdout per frame)
        results = self.model.predict(
            source=frame,
            device=self.device,
            conf=confidence_threshold,
            classes=list(self.target_classes.keys()),
            verbose=False,
        )

        detections: List[DetectionResult] = []

        if not results:
            return detections

        first_result = results[0]
        boxes = first_result.boxes

        if boxes is None or len(boxes) == 0:
            return detections

        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())

            # Verify category is within target vehicle classes
            if cls_id not in self.target_classes:
                continue

            # Extract coordinates (x1, y1, x2, y2)
            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

            detections.append(
                DetectionResult(
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    confidence=conf,
                    class_id=cls_id,
                    class_name=self.target_classes[cls_id],
                )
            )

        return detections
