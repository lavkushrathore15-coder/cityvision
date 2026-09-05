"""
ANPR Service Orchestration Subsystem
Problem Statement ID: SIH26127

Coordinates the complete license plate recognition pipeline:
vehicle frame
  -> license plate region detection
  -> image preprocessing
  -> OCR
  -> text normalization
  -> confidence evaluation
  -> multi-frame track consensus
"""
from typing import Optional, List, Dict, Any, Tuple
import time
import cv2
import numpy as np

from ai.detectors.base import BoundingBox
from ai.anpr.base import (
    BasePlateDetector,
    BasePlateOCR,
    PlateDetectionResult,
    PlateObservationRecord,
    PlateConsensusResult,
)
from ai.anpr.plate_detector import MorphologicalPlateDetector
from ai.anpr.preprocessor import PlatePreprocessor
from ai.anpr.easy_ocr import EasyPlateOCR
from ai.anpr.normalizer import PlateTextNormalizer, NormalizedPlateResult
from ai.anpr.consensus import TrackPlateConsensusManager


class ANPRService:
    """
    Production ANPR Subsystem for CITYVISION AI.
    Features:
    - Rejects frames without plates (strictly no synthetic fake number generation)
    - Separates raw OCR output from normalized plate text
    - Preserves individual OCR confidence scores
    - Supports multiple observations for local vehicle tracks
    - Multi-frame consensus voting
    - Handles blur, partial plates, low confidence, and noisy OCR
    """

    def __init__(
        self,
        plate_detector: Optional[BasePlateDetector] = None,
        preprocessor: Optional[PlatePreprocessor] = None,
        ocr_engine: Optional[BasePlateOCR] = None,
        normalizer: Optional[PlateTextNormalizer] = None,
        consensus_manager: Optional[TrackPlateConsensusManager] = None,
        lazy_ocr: bool = True,
    ):
        self.detector = plate_detector or MorphologicalPlateDetector()
        self.preprocessor = preprocessor or PlatePreprocessor()
        self._ocr_engine = ocr_engine
        self.lazy_ocr = lazy_ocr
        self.normalizer = normalizer or PlateTextNormalizer(min_confidence=0.35)
        self.consensus_manager = consensus_manager or TrackPlateConsensusManager()

    @property
    def ocr(self) -> BasePlateOCR:
        """Get or lazily initialize OCR engine."""
        if self._ocr_engine is None:
            self._ocr_engine = EasyPlateOCR(gpu=False)
        return self._ocr_engine

    def process_vehicle_frame(
        self,
        camera_id: str,
        local_track_id: int,
        vehicle_crop: np.ndarray,
        frame_number: int = 0,
        timestamp: Optional[float] = None,
        known_plate_bbox: Optional[BoundingBox] = None,
    ) -> Optional[PlateObservationRecord]:
        """
        Process a single vehicle crop frame through the ANPR pipeline.

        Returns PlateObservationRecord if a valid plate is detected and recognized,
        or None if no plate is visible, blurred beyond recognition, or rejected.
        Never fabricates a plate number.
        """
        if vehicle_crop is None or vehicle_crop.size == 0:
            return None

        current_time = timestamp if timestamp is not None else time.time()

        # Step 1: License Plate Region Detection
        candidate_crop: Optional[np.ndarray] = None
        detected_bbox: Optional[BoundingBox] = None

        if known_plate_bbox is not None:
            # Explicit plate bounding box provided
            x1 = max(0, int(known_plate_bbox.x1))
            y1 = max(0, int(known_plate_bbox.y1))
            x2 = min(vehicle_crop.shape[1], int(known_plate_bbox.x2))
            y2 = min(vehicle_crop.shape[0], int(known_plate_bbox.y2))
            candidate_crop = vehicle_crop[y1:y2, x1:x2]
            detected_bbox = known_plate_bbox
        else:
            candidates = self.detector.detect_plates(vehicle_crop)
            if not candidates:
                # Requirement 1 & 2: Do not assume plate is visible, do not generate fake plate
                return None
            best_candidate = candidates[0]
            candidate_crop = best_candidate.plate_crop
            detected_bbox = best_candidate.bbox

        if candidate_crop is None or candidate_crop.size == 0:
            return None

        # Step 2: Image Preprocessing
        prep = self.preprocessor.preprocess(candidate_crop)
        if not prep.is_usable:
            # Low contrast or degenerate region
            return None

        # Step 3: OCR
        ocr_results = self.ocr.recognize_text(prep.processed_image)
        if not ocr_results:
            # Fall back to trying the original color crop if preprocessed didn't catch it
            ocr_results = self.ocr.recognize_text(candidate_crop)
            if not ocr_results:
                return None

        # Step 4: Text Normalization and Confidence Evaluation
        # Select best text candidate from OCR output
        best_norm: Optional[NormalizedPlateResult] = None
        best_raw: str = ""
        best_conf: float = 0.0

        for item in ocr_results:
            raw_text = item.get("raw_text", "")
            conf = float(item.get("confidence", 0.0))
            norm = self.normalizer.normalize(raw_text, conf, is_blurry=prep.is_blurry)

            if norm.is_valid or (norm.is_partial and conf > 0.60):
                if best_norm is None or conf > best_conf:
                    best_norm = norm
                    best_raw = raw_text
                    best_conf = conf

        if best_norm is None or not best_norm.normalized_text:
            return None

        # Step 5: Construct Observation Record
        quality_score = float(np.clip(
            (best_conf * 0.7) + ((0.3 if not prep.is_blurry else 0.1) * (min(prep.blur_score, 200.0) / 200.0)),
            0.0,
            1.0,
        ))

        record = PlateObservationRecord(
            camera_id=camera_id,
            local_track_id=local_track_id,
            timestamp=current_time,
            raw_text=best_raw,
            normalized_text=best_norm.normalized_text,
            ocr_confidence=best_conf,
            plate_bbox=detected_bbox,
            frame_number=frame_number,
            is_blurry=prep.is_blurry,
            quality_score=quality_score,
        )

        # Step 6: Accumulate for Multi-Frame Track Consensus
        self.consensus_manager.add_observation(record)

        return record

    def get_track_consensus(self, camera_id: str, local_track_id: int) -> Optional[PlateConsensusResult]:
        """Compute multi-frame consensus license plate for a track."""
        return self.consensus_manager.compute_consensus(camera_id, local_track_id)

    def get_track_observations(self, camera_id: str, local_track_id: int) -> List[PlateObservationRecord]:
        """Retrieve all observations for a track."""
        return self.consensus_manager.get_observations(camera_id, local_track_id)

    def clear_track(self, camera_id: str, local_track_id: int) -> None:
        """Clear cached observations when track ends."""
        self.consensus_manager.clear_track(camera_id, local_track_id)

    def draw_anpr_overlay(
        self,
        vehicle_image: np.ndarray,
        record: PlateObservationRecord,
    ) -> np.ndarray:
        """Draw bounding box and plate text annotation on image for debugging/visuals."""
        annotated = vehicle_image.copy()
        if record.plate_bbox is not None:
            x1 = int(record.plate_bbox.x1)
            y1 = int(record.plate_bbox.y1)
            x2 = int(record.plate_bbox.x2)
            y2 = int(record.plate_bbox.y2)
            # Yellow bounding box for plate
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 255), 2)

            label = f"{record.normalized_text} ({record.ocr_confidence:.2f})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            size, _ = cv2.getTextSize(label, font, font_scale, thickness)
            tw, th = size

            # Background rectangle for readable text
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, max(0, y1)), (0, 0, 0), -1)
            cv2.putText(annotated, label, (x1 + 2, max(th, y1 - 2)), font, font_scale, (0, 255, 255), thickness)

        return annotated
