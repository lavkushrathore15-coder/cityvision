"""
Base Classes and Data Structures for Vehicle Re-Identification (Re-ID)
Problem Statement ID: SIH26127

Generates appearance embeddings for detected/tracked vehicles.
Note: Re-ID similarity is NOT proof that two observations are the same vehicle.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np


@dataclass
class VehicleEmbedding:
    """Historical container for vehicle appearance embedding."""
    track_id: int
    camera_id: str
    feature_vector: np.ndarray  # L2-normalized vector
    dimension: int
    timestamp_ms: float
    confidence: float


@dataclass
class VehicleEmbeddingRecord:
    """
    Standard record for a single vehicle crop appearance embedding:
    - embedding: L2-normalized 1D feature vector
    - model_identifier: Model name/architecture
    - model_version: Model checkpoint or library version
    - distance_metric: Default distance metric used with this embedding
    """
    camera_id: str
    local_track_id: int
    embedding: np.ndarray
    dimension: int
    model_identifier: str
    model_version: str
    distance_metric: str = "cosine"
    frame_number: int = 0
    timestamp: float = 0.0
    quality_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "local_track_id": self.local_track_id,
            "dimension": self.dimension,
            "model_identifier": self.model_identifier,
            "model_version": self.model_version,
            "distance_metric": self.distance_metric,
            "frame_number": self.frame_number,
            "timestamp": self.timestamp,
            "quality_score": round(self.quality_score, 4),
            "vector_preview": [round(float(x), 4) for x in self.embedding[:8]],
        }


@dataclass
class SimilarityResult:
    """
    Pairwise similarity comparison between two vehicle appearance embeddings.
    Strictly documents that visual similarity is NOT proof of vehicle identity.
    """
    similarity_score: float  # Higher means more visually similar (e.g. cosine sim in [-1.0, 1.0])
    distance: float  # Lower means closer
    distance_metric: str  # e.g., 'cosine', 'euclidean'
    model_identifier: str
    is_same_vehicle_proof: bool = False  # Explicit invariant: appearance similarity != proof of identity
    disclaimer: str = (
        "Re-ID similarity indicates visual appearance correlation only. "
        "It does NOT constitute proof that two observations represent the same physical vehicle."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "similarity_score": round(self.similarity_score, 4),
            "distance": round(self.distance, 4),
            "distance_metric": self.distance_metric,
            "model_identifier": self.model_identifier,
            "is_same_vehicle_proof": self.is_same_vehicle_proof,
            "disclaimer": self.disclaimer,
        }


class BaseVehicleReID(ABC):
    """Contract for extracting deep visual appearance embeddings from vehicle crops."""

    @abstractmethod
    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads feature extraction model weights into memory."""
        pass

    @abstractmethod
    def extract_embedding(self, vehicle_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Processes cropped vehicle image and returns normalized 1D feature vector.
        Returns None if vehicle crop is invalid, empty, or degenerate.
        """
        pass

    @abstractmethod
    def batch_extract_embeddings(self, vehicle_crops: List[np.ndarray]) -> List[Optional[np.ndarray]]:
        """Batch extraction of feature vectors for inference efficiency."""
        pass
