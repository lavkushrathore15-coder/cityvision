"""
Vehicle Detection Service
Coordinates YOLO model inference, frame sampling, telemetry packaging,
and debug visualization.
"""
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple
import cv2
import numpy as np

from ai.detectors.base import BaseVehicleDetector, BoundingBox, DetectionResult
from backend.app.services.video_ingestion import FramePacket


@dataclass
class VehicleDetectionPacket:
    """
    Standard output packet containing detected vehicle metadata,
    exact bounding box, frame index, source timestamp, and camera identifier.
    """
    class_name: str
    confidence: float
    bbox: BoundingBox
    frame_number: int
    timestamp_ms: float
    camera_id: str


class VehicleDetectionService:
    """
    Service managing vehicle detection across video streams with configurable
    confidence thresholds, frame sampling, and debug overlay rendering.
    """

    def __init__(
        self,
        detector: Optional[BaseVehicleDetector] = None,
        confidence_threshold: float = 0.35,
        sample_stride: int = 1,
    ):
        self.detector = detector
        self.confidence_threshold = confidence_threshold
        self.sample_stride = max(1, sample_stride)

        # Distinct color palette per vehicle class for debug overlays (BGR format)
        self.class_colors: Dict[str, Tuple[int, int, int]] = {
            "car": (0, 200, 255),        # Amber/Yellow
            "motorcycle": (255, 100, 0), # Blue
            "bus": (0, 255, 100),        # Green
            "truck": (200, 0, 200),      # Magenta
        }
        self.default_color: Tuple[int, int, int] = (0, 255, 0)

    def detect_in_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int,
        timestamp_ms: float,
    ) -> List[VehicleDetectionPacket]:
        """
        Executes vehicle detection on a single frame.
        Applies frame sampling policy: if frame_number is not on the sampling stride,
        returns an empty list without spending inference compute.
        Preserves original frame dimensions.
        """
        if self.detector is None:
            return []

        # Apply frame sampling if configured
        if frame_number % self.sample_stride != 0:
            return []

        raw_detections: List[DetectionResult] = self.detector.detect(
            frame=frame,
            confidence_threshold=self.confidence_threshold,
        )

        output_packets: List[VehicleDetectionPacket] = []
        for det in raw_detections:
            output_packets.append(
                VehicleDetectionPacket(
                    class_name=det.class_name,
                    confidence=det.confidence,
                    bbox=det.bbox,
                    frame_number=frame_number,
                    timestamp_ms=timestamp_ms,
                    camera_id=camera_id,
                )
            )

        return output_packets

    def process_frame_packet(
        self,
        packet: FramePacket,
    ) -> List[VehicleDetectionPacket]:
        """
        Helper method processing a FramePacket from the Video Ingestion subsystem.
        """
        return self.detect_in_frame(
            frame=packet.frame,
            camera_id=packet.camera_id,
            frame_number=packet.frame_index,
            timestamp_ms=packet.timestamp_ms,
        )

    def draw_debug_overlays(
        self,
        frame: np.ndarray,
        detections: List[VehicleDetectionPacket],
        draw_hud: bool = True,
    ) -> np.ndarray:
        """
        Renders bounding boxes, classification tags, confidence scores,
        and telemetry HUD onto a copy of the input frame.
        Preserves original frame dimensions.
        """
        if frame is None or frame.size == 0:
            return frame

        debug_frame = frame.copy()
        h, w = debug_frame.shape[:2]

        for det in detections:
            bbox = det.bbox
            x1 = max(0, min(w - 1, int(round(bbox.x1))))
            y1 = max(0, min(h - 1, int(round(bbox.y1))))
            x2 = max(0, min(w - 1, int(round(bbox.x2))))
            y2 = max(0, min(h - 1, int(round(bbox.y2))))

            color = self.class_colors.get(det.class_name, self.default_color)

            # Draw bounding box rectangle
            cv2.rectangle(debug_frame, (x1, y1), (x2, y2), color, 2)

            # Draw label banner
            label = f"{det.class_name.upper()} {det.confidence:.2f}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            # Ensure label doesn't render outside image boundary
            label_y1 = max(0, y1 - label_h - baseline - 4)
            label_y2 = label_y1 + label_h + baseline + 4

            cv2.rectangle(
                debug_frame,
                (x1, label_y1),
                (x1 + label_w + 6, label_y2),
                color,
                -1,
            )
            cv2.putText(
                debug_frame,
                label,
                (x1 + 3, label_y2 - baseline - 2),
                font,
                font_scale,
                (0, 0, 0),
                thickness,
                cv2.LINE_AA,
            )

        if draw_hud and detections:
            # Stamp telemetry HUD on top-left
            first = detections[0]
            hud_text = (
                f"CAM: {first.camera_id} | FRAME: {first.frame_number} | "
                f"TIME: {first.timestamp_ms:.1f}ms | VEHICLES: {len(detections)}"
            )
            cv2.putText(
                debug_frame,
                hud_text,
                (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        return debug_frame
