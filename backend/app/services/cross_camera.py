"""
Cross-Camera Vehicle Association Service
Problem Statement ID: SIH26127

Coordinates cross-camera association across urban CCTV feeds,
manages global vehicle identities, and records explainable audit logs.
"""
from typing import List, Dict, Optional, Tuple
import time
import threading

from ai.matching.base import (
    VehicleObservation,
    CrossCameraMatchRecord,
    ConfidenceTier,
)
from ai.matching.engine import ExplainableCrossCameraMatcher


class CrossCameraAssociationService:
    """
    Cross-Camera Vehicle Association Service for CITYVISION AI.
    - Fuses ANPR, Appearance Re-ID, Camera Topology, and Timestamps
    - Enforces hard spatio-temporal and plate conflict vetoes
    - Manages Global Vehicle IDs with full audit trails and explanations
    """

    def __init__(
        self,
        matcher: Optional[ExplainableCrossCameraMatcher] = None,
        max_gallery_size: int = 1000,
        temporal_window_sec: float = 7200.0,  # 2 hours
    ):
        self.matcher = matcher or ExplainableCrossCameraMatcher()
        self.max_gallery_size = max_gallery_size
        self.temporal_window_sec = temporal_window_sec
        self._lock = threading.Lock()

        # Registered observations in gallery
        self._gallery: List[VehicleObservation] = []
        # Mapping: global_vehicle_id -> List[VehicleObservation]
        self._global_trajectories: Dict[str, List[VehicleObservation]] = {}
        # Audit log of evaluated associations
        self._match_history: List[CrossCameraMatchRecord] = []
        self._id_counter: int = 1

    def _generate_global_id(self) -> str:
        gid = f"GLOBAL-VEH-{self._id_counter:04d}"
        self._id_counter += 1
        return gid

    def process_observation(
        self,
        observation: VehicleObservation,
    ) -> Tuple[str, Optional[CrossCameraMatchRecord]]:
        """
        Process incoming vehicle observation from a camera.
        Evaluates against candidate observations from other cameras.
        Returns (global_vehicle_id, best_match_record). Thread-safe.
        """
        with self._lock:
            best_record: Optional[CrossCameraMatchRecord] = None

            # Compare against gallery observations from different cameras within temporal window
            for cand in reversed(self._gallery):
                if cand.camera_id == observation.camera_id:
                    continue

                # Check search window
                if abs(observation.timestamp - cand.timestamp) > self.temporal_window_sec:
                    continue

                record = self.matcher.match_pair(cand, observation)
                self._match_history.append(record)

                if record.is_matched:
                    if best_record is None or record.match_score > best_record.match_score:
                        best_record = record
                        # If strong exact high-confidence match found, we can terminate candidate search
                        if record.confidence_tier == ConfidenceTier.HIGH and record.match_score >= 0.95:
                            break

            if best_record and best_record.is_matched:
                # Associate to existing global vehicle ID
                matched_gid = best_record.observation_a.global_vehicle_id
                if not matched_gid:
                    matched_gid = self._generate_global_id()
                    best_record.observation_a.global_vehicle_id = matched_gid

                observation.global_vehicle_id = matched_gid
                best_record.global_vehicle_id = matched_gid
                assigned_gid = matched_gid
            else:
                # Create a new distinct Global Vehicle ID
                assigned_gid = self._generate_global_id()
                observation.global_vehicle_id = assigned_gid

            # Update gallery and trajectories
            self._gallery.append(observation)
            if len(self._gallery) > self.max_gallery_size:
                self._gallery.pop(0)

            if assigned_gid not in self._global_trajectories:
                self._global_trajectories[assigned_gid] = []
            self._global_trajectories[assigned_gid].append(observation)

            return assigned_gid, best_record

    def get_global_vehicle(self, global_vehicle_id: str) -> List[VehicleObservation]:
        """Retrieve all sightings/observations associated with a global vehicle ID."""
        return self._global_trajectories.get(global_vehicle_id, [])

    def get_all_global_ids(self) -> List[str]:
        """List all active global vehicle IDs."""
        return list(self._global_trajectories.keys())

    def get_match_history(self) -> List[CrossCameraMatchRecord]:
        """Get complete audit history of all pairwise association evaluations."""
        return self._match_history

    def clear(self) -> None:
        """Reset service state."""
        self._gallery.clear()
        self._global_trajectories.clear()
        self._match_history.clear()
        self._id_counter = 1
