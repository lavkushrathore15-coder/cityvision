"""
Vehicle Re-Identification (Re-ID) Service
Problem Statement ID: SIH26127

Extracts visual appearance embeddings from vehicle crops and provides
pairwise similarity comparisons. Strictly independent from license plate OCR.
Note: Visual similarity is NOT proof of vehicle identity.
"""
from typing import Optional, List, Dict, Tuple, Any
from collections import defaultdict
import time
import numpy as np

from ai.reid.base import (
    BaseVehicleReID,
    VehicleEmbeddingRecord,
    SimilarityResult,
)
from ai.reid.extractor import YOLOVehicleReID
from ai.reid.similarity import compare_embeddings
from ai.matching.base import BaseCrossCameraMatcher, VehicleObservation, MatchResult


class ReIDService:
    """
    Vehicle Appearance Re-Identification Service.
    - Extracts deep convolutional embeddings from detected/tracked vehicle crops
    - L2-normalizes vectors
    - Stores historical embeddings per (camera_id, local_track_id)
    - Computes pairwise appearance similarities and explicit distance metrics
    - Re-ID is strictly independent from license plate OCR
    """

    def __init__(
        self,
        extractor: Optional[BaseVehicleReID] = None,
        default_metric: str = "cosine",
    ):
        self.extractor = extractor or YOLOVehicleReID()
        self.default_metric = default_metric
        # Cache of embeddings: (camera_id, local_track_id) -> List[VehicleEmbeddingRecord]
        self._track_embeddings: Dict[Tuple[str, int], List[VehicleEmbeddingRecord]] = defaultdict(list)

    def extract_features(self, vehicle_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract L2-normalized appearance embedding from vehicle crop.
        Returns None if crop is invalid or unprocessable.
        """
        if self.extractor is None or vehicle_crop is None:
            return None
        return self.extractor.extract_embedding(vehicle_crop)

    def process_vehicle_crop(
        self,
        camera_id: str,
        local_track_id: int,
        vehicle_crop: np.ndarray,
        frame_number: int = 0,
        timestamp: Optional[float] = None,
    ) -> Optional[VehicleEmbeddingRecord]:
        """
        Extract appearance embedding for a tracked vehicle observation,
        record it in track history, and return the embedding record.
        """
        if vehicle_crop is None:
            return None

        emb = self.extract_features(vehicle_crop)
        if emb is None:
            return None

        current_time = timestamp if timestamp is not None else time.time()
        record = VehicleEmbeddingRecord(
            camera_id=camera_id,
            local_track_id=local_track_id,
            embedding=emb,
            dimension=len(emb),
            model_identifier=getattr(self.extractor, "MODEL_IDENTIFIER", "reid-extractor"),
            model_version=getattr(self.extractor, "MODEL_VERSION", "1.0.0"),
            distance_metric=self.default_metric,
            frame_number=frame_number,
            timestamp=current_time,
        )

        self._track_embeddings[(camera_id, local_track_id)].append(record)
        return record

    def compare(
        self,
        emb1: np.ndarray,
        emb2: np.ndarray,
        metric: Optional[str] = None,
    ) -> SimilarityResult:
        """
        Compare two appearance embeddings.
        Returns SimilarityResult with similarity score, distance, and disclaimer.
        """
        use_metric = metric or self.default_metric
        model_id = getattr(self.extractor, "MODEL_IDENTIFIER", "reid-extractor")
        return compare_embeddings(emb1, emb2, metric=use_metric, model_identifier=model_id)

    def get_track_embeddings(self, camera_id: str, local_track_id: int) -> List[VehicleEmbeddingRecord]:
        """Retrieve all recorded embeddings for a track."""
        return self._track_embeddings.get((camera_id, local_track_id), [])

    def get_latest_embedding(self, camera_id: str, local_track_id: int) -> Optional[VehicleEmbeddingRecord]:
        """Get the most recent embedding for a track."""
        records = self.get_track_embeddings(camera_id, local_track_id)
        return records[-1] if records else None

    def clear_track(self, camera_id: str, local_track_id: int) -> None:
        """Clear cached embeddings when a track terminates."""
        self._track_embeddings.pop((camera_id, local_track_id), None)


class CrossCameraMatchingService:
    """
    Cross-Camera Matching Service delegating to ExplainableCrossCameraMatcher.
    """
    def __init__(self, matcher: Optional[BaseCrossCameraMatcher] = None):
        if matcher is None:
            from ai.matching.engine import ExplainableCrossCameraMatcher
            self.matcher = ExplainableCrossCameraMatcher()
        else:
            self.matcher = matcher
        self._gallery: List[VehicleObservation] = []

    def process_observation(self, observation: VehicleObservation) -> Optional[MatchResult]:
        if self.matcher is None:
            return None
        result = self.matcher.associate(observation, self._gallery)
        self._gallery.append(observation)
        return result
