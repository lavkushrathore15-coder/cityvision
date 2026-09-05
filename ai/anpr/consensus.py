"""
Multi-Frame License Plate Consensus Aggregator
Problem Statement ID: SIH26127

Maintains multiple OCR observations per (camera_id, local_track_id)
and resolves OCR inconsistencies using confidence-weighted voting.
"""
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from ai.anpr.base import PlateObservationRecord, PlateConsensusResult


class TrackPlateConsensusManager:
    """
    Manages license plate observations across frames for local vehicle tracks.
    Provides multi-frame consensus resolution without fabricating missing plates.
    """

    def __init__(self, min_consensus_observations: int = 1):
        self.min_consensus_observations = min_consensus_observations
        # Key: (camera_id, local_track_id) -> List[PlateObservationRecord]
        self._track_observations: Dict[Tuple[str, int], List[PlateObservationRecord]] = defaultdict(list)

    def add_observation(self, record: PlateObservationRecord) -> None:
        """Record an individual OCR observation for a tracked vehicle."""
        key = (record.camera_id, record.local_track_id)
        self._track_observations[key].append(record)

    def get_observations(self, camera_id: str, local_track_id: int) -> List[PlateObservationRecord]:
        """Retrieve all recorded OCR observations for a given local track."""
        return self._track_observations.get((camera_id, local_track_id), [])

    def compute_consensus(self, camera_id: str, local_track_id: int) -> Optional[PlateConsensusResult]:
        """
        Compute the consensus license plate text for a local track across all seen frames.
        Returns None if no observations or no valid plate candidates are available.
        Does NOT invent fake numbers.
        """
        observations = self.get_observations(camera_id, local_track_id)
        if not observations:
            return None

        # Filter candidates that have non-empty normalized text
        valid_obs = [obs for obs in observations if obs.normalized_text]
        if not valid_obs:
            return None

        if len(valid_obs) < self.min_consensus_observations:
            return None

        # Confidence- and quality-weighted voting for each candidate string
        scores: Dict[str, float] = defaultdict(float)
        confidences_by_text: Dict[str, List[float]] = defaultdict(list)

        for obs in valid_obs:
            # Blur penalty: down-weight blurry reads
            weight = 0.5 if obs.is_blurry else 1.0
            score = obs.ocr_confidence * weight
            scores[obs.normalized_text] += score
            confidences_by_text[obs.normalized_text].append(obs.ocr_confidence)

        # Find candidate with highest accumulated weighted score
        best_text = max(scores.keys(), key=lambda t: scores[t])
        winning_confidences = confidences_by_text[best_text]
        avg_conf = sum(winning_confidences) / float(len(winning_confidences))

        # Normalize score distribution for reporting
        total_score = sum(scores.values()) or 1.0
        candidate_freqs = {text: sc / total_score for text, sc in scores.items()}

        return PlateConsensusResult(
            camera_id=camera_id,
            local_track_id=local_track_id,
            consensus_text=best_text,
            average_confidence=avg_conf,
            total_observations=len(observations),
            candidate_frequencies=candidate_freqs,
            all_observations=observations,
        )

    def clear_track(self, camera_id: str, local_track_id: int) -> None:
        """Clear observations when track is terminated."""
        key = (camera_id, local_track_id)
        self._track_observations.pop(key, None)

    def get_all_active_tracks(self) -> List[Tuple[str, int]]:
        """List all tracks currently holding observations."""
        return list(self._track_observations.keys())
