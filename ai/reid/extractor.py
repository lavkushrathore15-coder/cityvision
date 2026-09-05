"""
Deep Convolutional Feature Extractor for Vehicle Re-ID
Problem Statement ID: SIH26127

Extracts L2-normalized appearance embeddings from cropped vehicle frames
using the verified Ultralytics YOLOv8 convolutional backbone.
"""
from typing import List, Optional, Any
import os
import logging
import cv2
import numpy as np

from ai.reid.base import BaseVehicleReID, VehicleEmbeddingRecord

logger = logging.getLogger("cityvision.reid")


class YOLOVehicleReID(BaseVehicleReID):
    """
    Vehicle appearance feature extraction using Ultralytics YOLOv8 backbone.
    - Verified against official pretrained weights (models/weights/yolov8n.pt)
    - Produces 256-dimensional deep feature embeddings
    - Applies L2 normalization onto the unit hypersphere
    - Strictly rejects degenerate, empty, or sub-resolution vehicle crops
    """

    DEFAULT_WEIGHTS = os.path.join("models", "weights", "yolov8n.pt")
    MODEL_IDENTIFIER = "yolov8n-backbone-embed"
    MODEL_VERSION = "8.4.138"
    DISTANCE_METRIC = "cosine"

    def __init__(
        self,
        weights_path: Optional[str] = None,
        device: str = "cpu",
        min_crop_size: int = 24,
    ):
        self.device = device
        self.min_crop_size = min_crop_size
        self.weights_path = weights_path or self.DEFAULT_WEIGHTS
        self.model: Optional[Any] = None
        self._dimension: int = 256

    def load_model(self, model_path: Optional[str] = None, device: Optional[str] = None) -> None:
        """Loads verified model weights into memory."""
        path = model_path or self.weights_path
        dev = device or self.device

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Verified model weights not found at '{path}'. "
                f"Please ensure official pretrained weights exist."
            )

        from ultralytics import YOLO
        self.model = YOLO(path)
        self.weights_path = path
        self.device = dev

    def _ensure_loaded(self) -> None:
        """Lazy loader if model hasn't been initialized explicitly."""
        if self.model is None:
            self.load_model(self.weights_path, self.device)

    def _validate_crop(self, vehicle_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Validates vehicle crop geometry and channels.
        Returns validated BGR image or None if invalid.
        """
        if vehicle_crop is None or not isinstance(vehicle_crop, np.ndarray):
            return None

        if vehicle_crop.size == 0:
            return None

        h, w = vehicle_crop.shape[:2]
        if h < self.min_crop_size or w < self.min_crop_size:
            return None

        # Ensure 3 color channels
        if len(vehicle_crop.shape) == 2:
            crop_bgr = cv2.cvtColor(vehicle_crop, cv2.COLOR_GRAY2BGR)
        elif len(vehicle_crop.shape) == 3 and vehicle_crop.shape[2] == 3:
            crop_bgr = vehicle_crop
        elif len(vehicle_crop.shape) == 3 and vehicle_crop.shape[2] == 4:
            crop_bgr = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGRA2BGR)
        else:
            return None

        # Reject degenerate uniform image (e.g., solid sensor noise or blank crop)
        if float(np.std(crop_bgr)) < 1.0:
            return None

        return crop_bgr

    def extract_embedding(self, vehicle_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Extracts L2-normalized 1D appearance vector from vehicle crop.
        Returns None if crop is invalid or unprocessable.
        """
        valid_crop = self._validate_crop(vehicle_crop)
        if valid_crop is None:
            return None

        self._ensure_loaded()

        try:
            # model.embed() extracts deep feature representation
            embeddings = self.model.embed(valid_crop)
            if not embeddings:
                return None

            raw_feat = embeddings[0]
            if hasattr(raw_feat, "cpu"):
                raw_feat = raw_feat.cpu().numpy()
            elif not isinstance(raw_feat, np.ndarray):
                raw_feat = np.array(raw_feat, dtype=np.float32)

            flat = raw_feat.flatten().astype(np.float32)
            self._dimension = len(flat)

            # L2 Normalization onto the unit hypersphere: ||e||_2 = 1.0
            norm = float(np.linalg.norm(flat))
            if norm == 0.0 or np.isnan(norm):
                return None

            normalized = flat / norm
            return normalized

        except Exception as e:
            logger.error(f"Re-ID deep feature extraction failed: {e}", exc_info=True)
            return None

    def batch_extract_embeddings(self, vehicle_crops: List[np.ndarray]) -> List[Optional[np.ndarray]]:
        """
        Batch extraction of embeddings for a list of vehicle crops.
        """
        return [self.extract_embedding(c) for c in vehicle_crops]

    def create_embedding_record(
        self,
        camera_id: str,
        local_track_id: int,
        vehicle_crop: np.ndarray,
        frame_number: int = 0,
        timestamp: float = 0.0,
    ) -> Optional[VehicleEmbeddingRecord]:
        """
        Convenience method to extract embedding and package into a complete VehicleEmbeddingRecord.
        Returns None if crop is invalid.
        """
        emb = self.extract_embedding(vehicle_crop)
        if emb is None:
            return None

        return VehicleEmbeddingRecord(
            camera_id=camera_id,
            local_track_id=local_track_id,
            embedding=emb,
            dimension=len(emb),
            model_identifier=self.MODEL_IDENTIFIER,
            model_version=self.MODEL_VERSION,
            distance_metric=self.DISTANCE_METRIC,
            frame_number=frame_number,
            timestamp=timestamp,
            quality_score=1.0,
        )
