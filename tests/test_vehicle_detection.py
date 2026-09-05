"""
Unit and Integration Tests for the Vehicle Detection Subsystem
Tests real YOLO inference using downloaded pre-trained weights on test imagery.
"""
from pathlib import Path
import cv2
import numpy as np
import pytest

from ai.detectors.base import BoundingBox, DetectionResult
from ai.detectors.yolo import YOLOVehicleDetector, DEFAULT_VEHICLE_CLASSES
from backend.app.services.detection import (
    VehicleDetectionPacket,
    VehicleDetectionService,
)
from backend.app.services.video_ingestion import FramePacket, FileCameraSource


WEIGHTS_PATH = Path("models/weights/yolov8n.pt")
TEST_IMAGE_PATH = Path("data/sample_images/bus.jpg")


@pytest.fixture(scope="session")
def detector() -> YOLOVehicleDetector:
    """Loads the real YOLO detector fixture once per test session."""
    assert WEIGHTS_PATH.is_file(), f"Model weights missing: {WEIGHTS_PATH}"
    return YOLOVehicleDetector(weights_path=str(WEIGHTS_PATH), device="cpu")


@pytest.fixture(scope="session")
def test_frame() -> np.ndarray:
    """Loads a real test image containing vehicles."""
    assert TEST_IMAGE_PATH.is_file(), f"Test image missing: {TEST_IMAGE_PATH}"
    img = cv2.imread(str(TEST_IMAGE_PATH))
    assert img is not None and img.size > 0
    return img


# ---------------------------------------------------------------------------
# 1. Detector Loading & Model Verification
# ---------------------------------------------------------------------------

def test_yolo_detector_loads_successfully(detector):
    assert detector.is_loaded is True
    assert detector.device == "cpu"
    assert "car" in detector.target_classes.values()
    assert "bus" in detector.target_classes.values()
    assert "truck" in detector.target_classes.values()
    assert "motorcycle" in detector.target_classes.values()


def test_yolo_detector_empty_frame_handling(detector):
    empty_frame = np.zeros((0, 0, 3), dtype=np.uint8)
    results = detector.detect(empty_frame)
    assert results == []


# ---------------------------------------------------------------------------
# 2. Real Inference & Class Filtering
# ---------------------------------------------------------------------------

def test_real_vehicle_detection_on_image(detector, test_frame):
    """
    Executes actual YOLOv8n inference on bus.jpg.
    Verifies that the bus is identified and non-vehicle classes (pedestrians)
    are filtered out.
    """
    results = detector.detect(test_frame, confidence_threshold=0.35)
    assert len(results) > 0

    class_names = [r.class_name for r in results]
    assert "bus" in class_names
    # Verify non-vehicle classes (like person) are not returned
    assert "person" not in class_names

    # Check bounding box validity and scale
    h, w = test_frame.shape[:2]
    for r in results:
        assert isinstance(r, DetectionResult)
        assert 0.0 <= r.confidence <= 1.0
        assert 0.0 <= r.bbox.x1 < r.bbox.x2 <= w
        assert 0.0 <= r.bbox.y1 < r.bbox.y2 <= h


# ---------------------------------------------------------------------------
# 3. Configurable Confidence Threshold
# ---------------------------------------------------------------------------

def test_configurable_confidence_threshold(detector, test_frame):
    # Low threshold: detects detections
    low_conf_results = detector.detect(test_frame, confidence_threshold=0.20)
    # Extremely high threshold: filters out lower-confidence detections
    high_conf_results = detector.detect(test_frame, confidence_threshold=0.98)

    assert len(low_conf_results) >= len(high_conf_results)


# ---------------------------------------------------------------------------
# 4. Vehicle Detection Service & Telemetry Schema
# ---------------------------------------------------------------------------

def test_vehicle_detection_service_packet_fields(detector, test_frame):
    service = VehicleDetectionService(detector=detector, confidence_threshold=0.35)

    packets = service.detect_in_frame(
        frame=test_frame,
        camera_id="CAM-001",
        frame_number=42,
        timestamp_ms=2800.0,
    )

    assert len(packets) > 0
    first = packets[0]
    assert isinstance(first, VehicleDetectionPacket)
    assert first.camera_id == "CAM-001"
    assert first.frame_number == 42
    assert first.timestamp_ms == 2800.0
    assert first.class_name == "bus"
    assert isinstance(first.confidence, float)
    assert isinstance(first.bbox, BoundingBox)


# ---------------------------------------------------------------------------
# 5. Configurable Frame Sampling
# ---------------------------------------------------------------------------

def test_detection_frame_sampling(detector, test_frame):
    # Process only every 3rd frame
    service = VehicleDetectionService(detector=detector, sample_stride=3)

    # Frame 1: skipped by sampling policy
    pkts_f1 = service.detect_in_frame(test_frame, "CAM-001", frame_number=1, timestamp_ms=66.6)
    assert pkts_f1 == []

    # Frame 2: skipped
    pkts_f2 = service.detect_in_frame(test_frame, "CAM-001", frame_number=2, timestamp_ms=133.3)
    assert pkts_f2 == []

    # Frame 3: processed (3 % 3 == 0)
    pkts_f3 = service.detect_in_frame(test_frame, "CAM-001", frame_number=3, timestamp_ms=200.0)
    assert len(pkts_f3) > 0


# ---------------------------------------------------------------------------
# 6. Preservation of Original Frame Dimensions
# ---------------------------------------------------------------------------

def test_preservation_of_frame_dimensions(detector, test_frame):
    service = VehicleDetectionService(detector=detector)
    original_shape = test_frame.shape

    packets = service.detect_in_frame(test_frame, "CAM-001", frame_number=1, timestamp_ms=0.0)
    debug_image = service.draw_debug_overlays(test_frame, packets)

    assert debug_image.shape == original_shape, "Debug visualization must preserve original dimensions"
    assert debug_image.dtype == test_frame.dtype


# ---------------------------------------------------------------------------
# 7. Debug Visualization Overlays
# ---------------------------------------------------------------------------

def test_draw_debug_overlays(detector, test_frame):
    service = VehicleDetectionService(detector=detector)
    packets = service.detect_in_frame(test_frame, "CAM-001", frame_number=10, timestamp_ms=666.0)
    assert len(packets) > 0

    annotated = service.draw_debug_overlays(test_frame, packets, draw_hud=True)
    assert annotated is not None
    assert annotated.shape == test_frame.shape
    # Ensure drawing modified pixels (drawing bounding box changes image content)
    assert not np.array_equal(annotated, test_frame)


# ---------------------------------------------------------------------------
# 8. Integration with Video Ingestion FramePacket
# ---------------------------------------------------------------------------

def test_integration_with_ingestion_frame_packet(detector, test_frame):
    service = VehicleDetectionService(detector=detector)

    packet = FramePacket(
        camera_id="CAM-TEST",
        frame_index=5,
        source_frame_index=15,
        timestamp_ms=1000.0,
        frame=test_frame,
    )

    results = service.process_frame_packet(packet)
    assert len(results) > 0
    assert results[0].camera_id == "CAM-TEST"
    assert results[0].frame_number == 5
    assert results[0].timestamp_ms == 1000.0
