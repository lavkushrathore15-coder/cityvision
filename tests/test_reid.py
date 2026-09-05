"""
Unit and Integration Tests for Vehicle Re-Identification (Re-ID) Subsystem
Problem Statement ID: SIH26127
"""
import pytest
import numpy as np
import cv2

from ai.reid.base import BaseVehicleReID, VehicleEmbeddingRecord, SimilarityResult
from ai.reid.extractor import YOLOVehicleReID
from ai.reid.similarity import (
    compute_cosine_similarity,
    compute_cosine_distance,
    compute_euclidean_distance,
    compare_embeddings,
)
from backend.app.services.reid import ReIDService


# Helper to generate synthetic vehicle crops with controllable appearance
def create_synthetic_vehicle_crop(
    color: str = "red",
    width: int = 120,
    height: int = 120,
    noise_level: float = 0.0,
) -> np.ndarray:
    """Generate a realistic vehicle-like image crop with specific dominant colors."""
    img = np.zeros((height, width, 3), dtype=np.uint8)

    color_map = {
        "red": (30, 30, 200),
        "blue": (200, 50, 30),
        "white": (230, 230, 230),
        "black": (25, 25, 25),
        "yellow": (20, 210, 220),
    }
    base_bgr = color_map.get(color.lower(), (100, 100, 100))

    # Vehicle body
    cv2.rectangle(img, (10, 30), (width - 10, height - 10), base_bgr, -1)
    # Windshield (darker)
    cv2.rectangle(img, (25, 10), (width - 25, 45), (40, 40, 40), -1)
    # Wheels / tires
    cv2.circle(img, (25, height - 12), 10, (15, 15, 15), -1)
    cv2.circle(img, (width - 25, height - 12), 10, (15, 15, 15), -1)

    if noise_level > 0.0:
        noise = np.random.normal(0, noise_level * 255, img.shape).astype(np.int16)
        noisy = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return noisy

    return img


# =====================================================================
# Unit Tests: Similarity & Distance Functions
# =====================================================================

def test_cosine_similarity_identical_vectors():
    v = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    sim = compute_cosine_similarity(v, v)
    dist = compute_cosine_distance(v, v)
    assert pytest.approx(sim, abs=1e-5) == 1.0
    assert pytest.approx(dist, abs=1e-5) == 0.0


def test_cosine_similarity_orthogonal_vectors():
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    sim = compute_cosine_similarity(v1, v2)
    dist = compute_cosine_distance(v1, v2)
    assert pytest.approx(sim, abs=1e-5) == 0.0
    assert pytest.approx(dist, abs=1e-5) == 1.0


def test_cosine_similarity_opposite_vectors():
    v1 = np.array([1.0, 0.0], dtype=np.float32)
    v2 = np.array([-1.0, 0.0], dtype=np.float32)
    sim = compute_cosine_similarity(v1, v2)
    dist = compute_cosine_distance(v1, v2)
    assert pytest.approx(sim, abs=1e-5) == -1.0
    assert pytest.approx(dist, abs=1e-5) == 2.0


def test_euclidean_distance_identical_and_different():
    v1 = np.array([0.6, 0.8], dtype=np.float32)
    dist_zero = compute_euclidean_distance(v1, v1)
    assert pytest.approx(dist_zero, abs=1e-5) == 0.0

    v2 = np.array([0.0, 0.0], dtype=np.float32)
    dist_unit = compute_euclidean_distance(v1, v2)
    assert pytest.approx(dist_unit, abs=1e-5) == 1.0


def test_compare_embeddings_returns_proper_structure_and_disclaimer():
    v1 = np.random.randn(256).astype(np.float32)
    v1 /= np.linalg.norm(v1)
    v2 = v1.copy()

    res = compare_embeddings(v1, v2, metric="cosine", model_identifier="test-model")
    assert isinstance(res, SimilarityResult)
    assert pytest.approx(res.similarity_score, abs=1e-4) == 1.0
    assert pytest.approx(res.distance, abs=1e-4) == 0.0
    assert res.distance_metric == "cosine"
    assert res.model_identifier == "test-model"
    # Crucial requirement: similarity is NOT proof of identity
    assert res.is_same_vehicle_proof is False
    assert "NOT constitute proof" in res.disclaimer


# =====================================================================
# Unit Tests: Feature Extractor (YOLOVehicleReID)
# =====================================================================

def test_extractor_l2_normalization():
    extractor = YOLOVehicleReID()
    crop = create_synthetic_vehicle_crop("blue")
    emb = extractor.extract_embedding(crop)

    assert emb is not None
    assert isinstance(emb, np.ndarray)
    assert emb.ndim == 1
    # Check L2 normalization: norm must be exactly 1.0
    norm = float(np.linalg.norm(emb))
    assert pytest.approx(norm, abs=1e-4) == 1.0


def test_extractor_similar_vs_different_vehicles():
    extractor = YOLOVehicleReID()

    # Base vehicle crop (e.g. car)
    car_1 = create_synthetic_vehicle_crop("red", width=140, height=140)
    # Slightly perturbed/cropped version of the same vehicle
    car_same = car_1[4:-4, 4:-4].copy()

    # Structurally distinct vehicle (different aspect ratio and silhouette, e.g. tall delivery van/truck)
    truck = np.zeros((180, 100, 3), dtype=np.uint8)
    cv2.rectangle(truck, (5, 10), (95, 140), (200, 180, 30), -1)  # Tall boxy body
    cv2.rectangle(truck, (15, 20), (85, 50), (40, 40, 40), -1)
    cv2.circle(truck, (25, 160), 12, (20, 20, 20), -1)
    cv2.circle(truck, (75, 160), 12, (20, 20, 20), -1)

    emb_car_1 = extractor.extract_embedding(car_1)
    emb_car_same = extractor.extract_embedding(car_same)
    emb_truck = extractor.extract_embedding(truck)

    assert emb_car_1 is not None
    assert emb_car_same is not None
    assert emb_truck is not None

    sim_same = compute_cosine_similarity(emb_car_1, emb_car_same)
    sim_different = compute_cosine_similarity(emb_car_1, emb_truck)

    # Re-ID embedding of same vehicle across slight perspective/crop shifts should be high
    assert sim_same > 0.95
    # Clearly different vehicle geometry should have lower similarity
    assert sim_same > sim_different


def test_extractor_missing_and_invalid_crops():
    """Requirement: Gracefully handle missing/invalid crops."""
    extractor = YOLOVehicleReID()

    # None crop
    assert extractor.extract_embedding(None) is None

    # Empty crop
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    assert extractor.extract_embedding(empty) is None

    # Sub-resolution / degenerate crop (< min_crop_size)
    tiny = np.full((12, 12, 3), 128, dtype=np.uint8)
    assert extractor.extract_embedding(tiny) is None

    # Pure solid blank color (standard deviation < 1.0)
    solid = np.full((64, 64, 3), 100, dtype=np.uint8)
    assert extractor.extract_embedding(solid) is None


def test_extractor_grayscale_conversion_support():
    extractor = YOLOVehicleReID()
    crop = create_synthetic_vehicle_crop("white")
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    emb = extractor.extract_embedding(gray)
    assert emb is not None
    assert pytest.approx(float(np.linalg.norm(emb)), abs=1e-4) == 1.0


# =====================================================================
# Integration Tests: ReIDService
# =====================================================================

def test_reid_service_full_workflow():
    service = ReIDService()

    crop = create_synthetic_vehicle_crop("yellow")
    record = service.process_vehicle_crop(
        camera_id="cam_01",
        local_track_id=15,
        vehicle_crop=crop,
        frame_number=42,
        timestamp=100.0,
    )

    assert record is not None
    assert isinstance(record, VehicleEmbeddingRecord)
    assert record.camera_id == "cam_01"
    assert record.local_track_id == 15
    assert record.frame_number == 42
    assert record.dimension == len(record.embedding)
    assert record.model_identifier == "yolov8n-backbone-embed"
    assert record.distance_metric == "cosine"

    # History retrieval
    history = service.get_track_embeddings("cam_01", 15)
    assert len(history) == 1
    assert service.get_latest_embedding("cam_01", 15) == record

    # Serialization
    as_dict = record.to_dict()
    assert as_dict["dimension"] == record.dimension
    assert len(as_dict["vector_preview"]) == 8


def test_reid_service_pairwise_comparison():
    service = ReIDService()

    crop1 = create_synthetic_vehicle_crop("red", noise_level=0.0)
    crop2 = create_synthetic_vehicle_crop("blue", noise_level=0.0)

    emb1 = service.extract_features(crop1)
    emb2 = service.extract_features(crop2)

    result_cosine = service.compare(emb1, emb2, metric="cosine")
    assert result_cosine.distance_metric == "cosine"
    assert result_cosine.similarity_score <= 1.0
    assert result_cosine.distance >= 0.0

    result_euclid = service.compare(emb1, emb2, metric="euclidean")
    assert result_euclid.distance_metric == "euclidean"
    assert result_euclid.distance > 0.0


def test_reid_independence_from_ocr():
    """Requirement: Keep Re-ID independent from license plate OCR."""
    service = ReIDService()
    crop = create_synthetic_vehicle_crop("black")
    record = service.process_vehicle_crop("cam_02", 9, crop)

    assert record is not None
    # Re-ID record contains only appearance embedding metadata, no OCR plate text fields
    assert hasattr(record, "embedding")
    assert not hasattr(record, "raw_text")
    assert not hasattr(record, "normalized_text")
