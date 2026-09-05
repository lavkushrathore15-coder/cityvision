"""
Similarity and Distance Metrics for Vehicle Re-ID Embeddings
Problem Statement ID: SIH26127

Calculates pairwise similarity scores and explicit distances between
appearance embeddings.
"""
from typing import Union
import numpy as np

from ai.reid.base import SimilarityResult


def compute_cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Computes cosine similarity between two 1D vectors in range [-1.0, 1.0].
    Values closer to 1.0 indicate high directional alignment in feature space.
    """
    if v1 is None or v2 is None:
        raise ValueError("Cannot compute similarity on None vectors.")
    if v1.shape != v2.shape:
        raise ValueError(f"Vector shapes must match: {v1.shape} vs {v2.shape}")

    dot = float(np.dot(v1, v2))
    norm1 = float(np.linalg.norm(v1))
    norm2 = float(np.linalg.norm(v2))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    sim = dot / (norm1 * norm2)
    return float(np.clip(sim, -1.0, 1.0))


def compute_cosine_distance(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Computes cosine distance: 1.0 - cosine_similarity.
    Range [0.0, 2.0], where 0.0 indicates identical orientation.
    """
    sim = compute_cosine_similarity(v1, v2)
    return float(max(0.0, 1.0 - sim))


def compute_euclidean_distance(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Computes Euclidean (L2) distance between two 1D vectors.
    """
    if v1 is None or v2 is None:
        raise ValueError("Cannot compute distance on None vectors.")
    if v1.shape != v2.shape:
        raise ValueError(f"Vector shapes must match: {v1.shape} vs {v2.shape}")

    diff = v1 - v2
    return float(np.linalg.norm(diff))


def compare_embeddings(
    v1: np.ndarray,
    v2: np.ndarray,
    metric: str = "cosine",
    model_identifier: str = "yolov8n-backbone",
) -> SimilarityResult:
    """
    Compares two vehicle appearance embeddings using an explicit distance metric.

    Returns SimilarityResult with:
    - similarity_score: float
    - distance: float
    - distance_metric: str ('cosine' or 'euclidean')
    - model_identifier: str
    - is_same_vehicle_proof: False (explicit reminder that similarity != proof of identity)
    """
    metric_clean = metric.lower().strip()

    if metric_clean == "cosine":
        sim = compute_cosine_similarity(v1, v2)
        dist = compute_cosine_distance(v1, v2)
        return SimilarityResult(
            similarity_score=sim,
            distance=dist,
            distance_metric="cosine",
            model_identifier=model_identifier,
            is_same_vehicle_proof=False,
        )
    elif metric_clean in ("euclidean", "l2"):
        dist = compute_euclidean_distance(v1, v2)
        # Convert Euclidean distance on unit vectors into an intuitive [0, 1] similarity
        # For unit vectors, max dist is 2.0 (opposite vectors)
        sim = float(max(0.0, 1.0 - (dist / 2.0)))
        return SimilarityResult(
            similarity_score=sim,
            distance=dist,
            distance_metric="euclidean",
            model_identifier=model_identifier,
            is_same_vehicle_proof=False,
        )
    else:
        raise ValueError(f"Unsupported distance metric: '{metric}'. Supported: 'cosine', 'euclidean'")
