"""
Unit and Integration Tests for ANPR / OCR Subsystem
Problem Statement ID: SIH26127
"""
from typing import Tuple, Optional, List, Dict
import pytest
import numpy as np
import cv2

from ai.detectors.base import BoundingBox
from ai.anpr.base import (
    PlateDetectionResult,
    PlateObservationRecord,
    PlateConsensusResult,
    BasePlateOCR,
)
from ai.anpr.preprocessor import PlatePreprocessor
from ai.anpr.plate_detector import MorphologicalPlateDetector
from ai.anpr.normalizer import PlateTextNormalizer
from ai.anpr.consensus import TrackPlateConsensusManager
from ai.anpr.easy_ocr import EasyPlateOCR
from backend.app.services.anpr import ANPRService


# Helper to generate a realistic synthetic license plate image
def create_synthetic_plate(
    text: str = "DL01AB1234",
    width: int = 240,
    height: int = 70,
    blur: bool = False,
    noise: bool = False,
) -> np.ndarray:
    """Generate a clean synthetic plate crop image for testing."""
    # White background with black border
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (2, 2), (width - 3, height - 3), (0, 0, 0), 3)

    # Blue band on left side (standard IND/EU format)
    band_w = int(width * 0.12)
    cv2.rectangle(img, (2, 2), (band_w, height - 3), (200, 100, 0), -1)

    # Draw text
    font = cv2.FONT_HERSHEY_DUPLEX
    scale = 1.1
    thickness = 2
    size, _ = cv2.getTextSize(text, font, scale, thickness)
    tx = band_w + max(5, (width - band_w - size[0]) // 2)
    ty = (height + size[1]) // 2
    cv2.putText(img, text, (tx, ty), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)

    if blur:
        img = cv2.GaussianBlur(img, (15, 15), 5.0)

    if noise:
        noise_mat = np.random.randint(0, 50, (height, width, 3), dtype=np.uint8)
        img = cv2.add(img, noise_mat)

    return img


def create_synthetic_vehicle_with_plate(
    plate_text: str = "HR26DK8337",
    has_plate: bool = True,
) -> Tuple[np.ndarray, Optional[BoundingBox]]:
    """Generate a synthetic vehicle crop (e.g. car rear) optionally containing a plate."""
    veh_h, veh_w = 300, 400
    # Car body (dark gray/navy)
    veh = np.full((veh_h, veh_w, 3), 60, dtype=np.uint8)

    # Rear windshield (darker)
    cv2.rectangle(veh, (50, 20), (350, 120), (30, 30, 30), -1)

    # Taillights (red)
    cv2.rectangle(veh, (20, 140), (80, 180), (0, 0, 200), -1)
    cv2.rectangle(veh, (320, 140), (380, 180), (0, 0, 200), -1)

    # Bumper area
    cv2.rectangle(veh, (40, 210), (360, 280), (45, 45, 45), -1)

    if not has_plate:
        return veh, None

    # Embed plate in bumper
    pw, ph = 180, 50
    px = (veh_w - pw) // 2
    py = 220
    plate_img = create_synthetic_plate(plate_text, width=pw, height=ph)
    veh[py:py+ph, px:px+pw] = plate_img

    bbox = BoundingBox(x1=float(px), y1=float(py), x2=float(px+pw), y2=float(py+ph))
    return veh, bbox


# =====================================================================
# Unit Tests: Preprocessing & Blur Detection
# =====================================================================

def test_preprocessor_sharp_vs_blur():
    prep = PlatePreprocessor(blur_threshold=60.0)
    sharp = create_synthetic_plate("MH12DE1433", blur=False)
    blurry = create_synthetic_plate("MH12DE1433", blur=True)

    res_sharp = prep.preprocess(sharp)
    res_blurry = prep.preprocess(blurry)

    assert not res_sharp.is_blurry
    assert res_sharp.blur_score > res_blurry.blur_score
    assert res_blurry.is_blurry
    assert res_sharp.processed_image.shape[0] == prep.target_height


def test_preprocessor_empty_input():
    prep = PlatePreprocessor()
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    res = prep.preprocess(empty)
    assert not res.is_usable
    assert res.is_blurry


# =====================================================================
# Unit Tests: License Plate Region Detection
# =====================================================================

def test_detector_detects_plate_in_vehicle_crop():
    detector = MorphologicalPlateDetector()
    veh, expected_bbox = create_synthetic_vehicle_with_plate("DL3CAF1234", has_plate=True)
    candidates = detector.detect_plates(veh)

    assert len(candidates) >= 1
    best = candidates[0]
    assert best.plate_crop is not None
    assert best.plate_crop.shape[0] > 0 and best.plate_crop.shape[1] > 0
    assert best.confidence > 0.4
    # Check that candidate bbox overlaps the embedded plate region
    assert best.bbox.x2 > expected_bbox.x1
    assert best.bbox.x1 < expected_bbox.x2


def test_detector_no_plate_returns_empty():
    """Requirement 1 & 2: Plate not visible must return empty list; no fake detections."""
    detector = MorphologicalPlateDetector()
    # Uniform texture with no plate
    blank_car = np.full((300, 400, 3), 80, dtype=np.uint8)
    candidates = detector.detect_plates(blank_car)
    assert candidates == []


# =====================================================================
# Unit Tests: Text Normalizer & Raw Separation
# =====================================================================

def test_normalizer_preserves_raw_and_creates_sanitized():
    norm = PlateTextNormalizer(min_confidence=0.35)
    raw = "  ka-03-mg-7788! "
    res = norm.normalize(raw, confidence=0.88)

    assert res.raw_text == raw.strip()
    assert res.normalized_text == "KA03MG7788"
    assert res.is_valid
    assert not res.is_partial
    assert res.confidence == 0.88
    assert res.confidence_passed


def test_normalizer_handles_low_confidence():
    norm = PlateTextNormalizer(min_confidence=0.50)
    res = norm.normalize("DL10AB1234", confidence=0.25)
    assert not res.is_valid
    assert not res.confidence_passed
    assert res.rejection_reason == "LOW_CONFIDENCE"
    assert res.raw_text == "DL10AB1234"


def test_normalizer_handles_partial_plate():
    norm = PlateTextNormalizer(min_characters=6, partial_min_characters=3)
    res = norm.normalize("DL1", confidence=0.75)
    assert not res.is_valid
    assert res.is_partial
    assert res.normalized_text == "DL1"


def test_normalizer_rejects_empty():
    norm = PlateTextNormalizer()
    res = norm.normalize("   ", confidence=0.0)
    assert not res.is_valid
    assert res.rejection_reason == "EMPTY_TEXT"


# =====================================================================
# Unit Tests: Multi-Frame Consensus
# =====================================================================

def test_consensus_voting_across_multiple_frames():
    manager = TrackPlateConsensusManager(min_consensus_observations=2)
    cam_id = "cam_01"
    track_id = 101

    # Frame 1: Clear read
    manager.add_observation(
        PlateObservationRecord(
            camera_id=cam_id,
            local_track_id=track_id,
            timestamp=100.0,
            raw_text="KA05MH2020",
            normalized_text="KA05MH2020",
            ocr_confidence=0.92,
            frame_number=1,
            is_blurry=False,
        )
    )

    # Frame 2: Minor character glitch ('O' instead of '0', lower conf)
    manager.add_observation(
        PlateObservationRecord(
            camera_id=cam_id,
            local_track_id=track_id,
            timestamp=100.1,
            raw_text="KA05MH2O20",
            normalized_text="KA05MH2O20",
            ocr_confidence=0.50,
            frame_number=2,
            is_blurry=True,
        )
    )

    # Frame 3: Another clear read
    manager.add_observation(
        PlateObservationRecord(
            camera_id=cam_id,
            local_track_id=track_id,
            timestamp=100.2,
            raw_text="KA05MH2020",
            normalized_text="KA05MH2020",
            ocr_confidence=0.95,
            frame_number=3,
            is_blurry=False,
        )
    )

    consensus = manager.compute_consensus(cam_id, track_id)
    assert consensus is not None
    assert consensus.consensus_text == "KA05MH2020"
    assert consensus.total_observations == 3
    assert consensus.average_confidence > 0.90
    assert "KA05MH2020" in consensus.candidate_frequencies


def test_consensus_no_observations_returns_none():
    """No fake plates generated when observations are absent."""
    manager = TrackPlateConsensusManager()
    assert manager.compute_consensus("cam_99", 999) is None


# =====================================================================
# Integration Tests: Mock OCR & Full ANPRService Pipeline
# =====================================================================

class MockOCR(BasePlateOCR):
    """Deterministic mock OCR engine for unit pipeline isolation."""
    def __init__(self, mocked_text: str = "UP16BT4004", confidence: float = 0.91):
        self.mocked_text = mocked_text
        self.confidence = confidence

    def recognize_text(self, plate_crop: np.ndarray):
        if plate_crop is None or plate_crop.size == 0:
            return []
        return [{"raw_text": self.mocked_text, "confidence": self.confidence, "bbox": None}]


def test_anpr_service_full_pipeline():
    service = ANPRService(ocr_engine=MockOCR("MH01AX9999", 0.94))
    veh, bbox = create_synthetic_vehicle_with_plate("MH01AX9999", has_plate=True)

    record = service.process_vehicle_frame(
        camera_id="cam_test",
        local_track_id=7,
        vehicle_crop=veh,
        frame_number=42,
        known_plate_bbox=bbox,
    )

    assert record is not None
    assert record.camera_id == "cam_test"
    assert record.local_track_id == 7
    assert record.raw_text == "MH01AX9999"
    assert record.normalized_text == "MH01AX9999"
    assert record.ocr_confidence == 0.94
    assert record.frame_number == 42
    assert record.quality_score > 0.7


def test_anpr_service_missing_plate_returns_none():
    """Requirement: Do not generate a plate number when no plate is detected."""
    service = ANPRService(ocr_engine=MockOCR())
    blank_car = np.full((300, 400, 3), 50, dtype=np.uint8)

    record = service.process_vehicle_frame(
        camera_id="cam_test",
        local_track_id=8,
        vehicle_crop=blank_car,
        frame_number=1,
    )

    assert record is None
    assert service.get_track_consensus("cam_test", 8) is None


# =====================================================================
# Live Integration Test: EasyPlateOCR Real Inference
# =====================================================================

def test_easyocr_real_synthetic_plate():
    """Verify actual real EasyOCR inference on synthetic high-resolution plate."""
    easy_ocr = EasyPlateOCR(gpu=False)
    plate_crop = create_synthetic_plate("DL04CA1122", width=260, height=70)

    results = easy_ocr.recognize_text(plate_crop)
    assert len(results) >= 1
    # Check that EasyOCR found text containing the characters
    detected_raw = "".join(r["raw_text"] for r in results).replace(" ", "").upper()
    assert "DL" in detected_raw or "1122" in detected_raw
