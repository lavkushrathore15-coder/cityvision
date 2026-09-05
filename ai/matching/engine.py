"""
Explainable Cross-Camera Vehicle Association Engine
Problem Statement ID: SIH26127

Multi-evidence fusion engine for determining whether observations across
different cameras represent the same physical vehicle.
Strict rules:
- Do NOT use a single signal as absolute truth.
- Do NOT fabricate matches.
- Do NOT assume impossible travel times are valid (hard temporal veto).
- Do NOT create a global ID merely because two observations look visually similar.
- Provide explainable evidence breakdown for every decision.
"""
from typing import Optional, Dict, Any, List, Tuple
import time
import math
import numpy as np

from ai.matching.base import (
    BaseCrossCameraMatcher,
    VehicleObservation,
    CrossCameraMatchRecord,
    ConfidenceTier,
    MatchResult,
)
from ai.matching.spatial_temporal import SpatioTemporalTopology, SpatioTemporalEvaluation
from ai.reid.similarity import compute_cosine_similarity


def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes Levenshtein edit distance between two strings."""
    if not s1:
        return len(s2) if s2 else 0
    if not s2:
        return len(s1)
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # Deletion
                dp[i][j - 1] + 1,      # Insertion
                dp[i - 1][j - 1] + cost  # Substitution
            )
    return dp[m][n]


class ExplainableCrossCameraMatcher(BaseCrossCameraMatcher):
    """
    Explainable Association Matcher combining:
    1. License plate text agreement (exact & Levenshtein)
    2. OCR confidence weighting
    3. Re-ID appearance cosine similarity
    4. Spatio-temporal road feasibility and camera geometry
    """

    def __init__(
        self,
        topology: Optional[SpatioTemporalTopology] = None,
        high_threshold: float = 0.82,
        medium_threshold: float = 0.65,
        low_threshold: float = 0.45,
    ):
        self.topology = topology or SpatioTemporalTopology()
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.low_threshold = low_threshold

    def match_pair(
        self,
        obs_a: VehicleObservation,
        obs_b: VehicleObservation,
    ) -> CrossCameraMatchRecord:
        """
        Evaluate pair of observations for cross-camera identity association.
        Produces full explainable score, confidence tier, and reasoning trail.
        """
        current_time = time.time()
        plate_a = obs_a.normalized_plate.strip().upper() if obs_a.normalized_plate else None
        plate_b = obs_b.normalized_plate.strip().upper() if obs_b.normalized_plate else None

        conf_a = obs_a.ocr_confidence if plate_a else 0.0
        conf_b = obs_b.ocr_confidence if plate_b else 0.0

        emb_a = obs_a.embedding
        emb_b = obs_b.embedding

        # -------------------------------------------------------------
        # 1. Spatio-Temporal Feasibility Check (Hard Constraint)
        # -------------------------------------------------------------
        st_eval: SpatioTemporalEvaluation = self.topology.evaluate_transition(
            obs_a.camera_id, obs_a.timestamp, obs_b.camera_id, obs_b.timestamp
        )

        evidence: Dict[str, Any] = {
            "time_delta_sec": round(st_eval.time_delta_sec, 2),
            "distance_meters": round(st_eval.distance_meters, 1),
            "implied_speed_kmh": round(st_eval.implied_speed_kmh, 1) if not math.isinf(st_eval.implied_speed_kmh) else "inf",
            "temporal_feasible": st_eval.is_feasible,
            "temporal_score": round(st_eval.temporal_score, 4),
            "plate_agreement_score": 0.0,
            "reid_similarity_score": None,
            "plate_edit_distance": None,
            "veto_applied": None,
        }

        # Hard Veto: Physically impossible travel time
        if not st_eval.is_feasible:
            evidence["veto_applied"] = "TEMPORAL_IMPOSSIBLE"
            explanation = (
                f"Temporal Feasibility Veto: Physical transition is impossible between "
                f"{obs_a.camera_id} and {obs_b.camera_id}. {st_eval.rejection_reason}."
            )
            return CrossCameraMatchRecord(
                global_vehicle_id=None,
                observation_a=obs_a,
                observation_b=obs_b,
                match_score=0.0,
                confidence_tier=ConfidenceTier.UNMATCHED,
                is_matched=False,
                evidence_breakdown=evidence,
                explanation=explanation,
                timestamp=current_time,
            )

        # -------------------------------------------------------------
        # 2. Check for Absolute Absence of Evidence
        # -------------------------------------------------------------
        has_plate = bool(plate_a or plate_b)
        has_reid = bool(emb_a is not None and emb_b is not None)

        if not has_plate and not has_reid:
            evidence["veto_applied"] = "NO_EVIDENCE"
            explanation = (
                "Insufficient Evidence: Neither license plates nor visual embeddings "
                "are available to compare these observations."
            )
            return CrossCameraMatchRecord(
                global_vehicle_id=None,
                observation_a=obs_a,
                observation_b=obs_b,
                match_score=0.0,
                confidence_tier=ConfidenceTier.UNMATCHED,
                is_matched=False,
                evidence_breakdown=evidence,
                explanation=explanation,
                timestamp=current_time,
            )

        # -------------------------------------------------------------
        # 3. License Plate Evaluation
        # -------------------------------------------------------------
        plate_score = 0.0
        plate_edit_dist = None
        has_plate_conflict = False

        if plate_a and plate_b:
            plate_edit_dist = levenshtein_distance(plate_a, plate_b)
            evidence["plate_edit_distance"] = plate_edit_dist
            min_ocr_conf = min(conf_a, conf_b)

            if plate_edit_dist == 0:
                # Exact plate match: weighted by OCR confidence
                plate_score = min_ocr_conf * 1.0
            elif plate_edit_dist == 1:
                # 1 character difference (single character optical confusion, e.g. 0 vs O or 8 vs B)
                plate_score = min_ocr_conf * 0.70
            elif plate_edit_dist == 2 and min(len(plate_a), len(plate_b)) >= 8:
                # 2 character difference on long plate
                plate_score = min_ocr_conf * 0.35
            else:
                # Completely distinct plates
                plate_score = 0.0
                if conf_a >= 0.70 and conf_b >= 0.70:
                    has_plate_conflict = True

        elif plate_a or plate_b:
            # Only one observation had a plate read; plate evidence is neutral/unknown
            plate_score = 0.0

        evidence["plate_agreement_score"] = round(plate_score, 4)

        # Hard Veto: Conflicting high-confidence plates
        if has_plate_conflict:
            evidence["veto_applied"] = "PLATE_CONFLICT"
            explanation = (
                f"Plate Conflict Veto: Observations have mutually incompatible high-confidence "
                f"license plates ('{plate_a}' [conf: {conf_a:.2f}] vs '{plate_b}' [conf: {conf_b:.2f}]). "
                f"Visual appearance similarity alone cannot override verified plate mismatch."
            )
            return CrossCameraMatchRecord(
                global_vehicle_id=None,
                observation_a=obs_a,
                observation_b=obs_b,
                match_score=0.05,
                confidence_tier=ConfidenceTier.UNMATCHED,
                is_matched=False,
                evidence_breakdown=evidence,
                explanation=explanation,
                timestamp=current_time,
            )

        # -------------------------------------------------------------
        # 4. Vehicle Re-ID Appearance Evaluation
        # -------------------------------------------------------------
        reid_sim = None
        if emb_a is not None and emb_b is not None:
            reid_sim = compute_cosine_similarity(emb_a, emb_b)
            evidence["reid_similarity_score"] = round(reid_sim, 4)

        # -------------------------------------------------------------
        # 5. Multi-Signal Evidence Fusion
        # -------------------------------------------------------------
        # Dynamic weighting based on available signals
        if plate_a and plate_b and reid_sim is not None:
            # Full multi-modal evidence available
            # Plate: 0.50, Re-ID: 0.35, Spatio-temporal: 0.15
            match_score = (plate_score * 0.50) + (max(0.0, reid_sim) * 0.35) + (st_eval.temporal_score * 0.15)
        elif plate_a and plate_b:
            # Only plates available (no Re-ID)
            match_score = (plate_score * 0.80) + (st_eval.temporal_score * 0.20)
        elif reid_sim is not None:
            # Only Re-ID available (missing plate on one or both)
            # Rule: Re-ID alone cannot achieve HIGH or MEDIUM association without plate confirmation
            # Capped at 0.55 (LOW CONFIDENCE)
            raw_reid_score = (max(0.0, reid_sim) * 0.70) + (st_eval.temporal_score * 0.30)
            match_score = min(0.55, raw_reid_score)
        else:
            match_score = 0.0

        match_score = float(np.clip(match_score, 0.0, 1.0))
        evidence["composite_match_score"] = round(match_score, 4)

        # -------------------------------------------------------------
        # 6. Confidence Tier Classification & Explanation Generation
        # -------------------------------------------------------------
        # Strict Rule: If no plate agreement exists at all (both plates missing),
        # visual appearance alone CANNOT merge identities into a global ID.
        if not plate_a and not plate_b:
            tier = ConfidenceTier.LOW if match_score >= self.low_threshold else ConfidenceTier.UNMATCHED
            is_matched = False
            sim_str = f"{reid_sim:.3f}" if reid_sim is not None else "N/A"
            explanation = (
                f"Visual Appearance Only: Re-ID similarity ({sim_str}) detected across feasible transit "
                f"({st_eval.time_delta_sec:.1f}s), but neither observation has verified license plate evidence. "
                f"Per strict non-identity rules, visual similarity alone does NOT create a global vehicle identity."
            )

        elif match_score >= self.high_threshold:
            tier = ConfidenceTier.HIGH
            is_matched = True
            if plate_edit_dist == 0:
                explanation = (
                    f"Strong Agreement: Exact license plate match ('{plate_a}') with OCR confidence "
                    f"({conf_a:.2f}, {conf_b:.2f})"
                )
                if reid_sim is not None:
                    explanation += f" and corroborated by visual Re-ID similarity ({reid_sim:.3f})"
                explanation += f" across feasible transit ({st_eval.time_delta_sec:.1f}s, {st_eval.implied_speed_kmh:.1f} km/h)."
            else:
                explanation = (
                    f"Strong Corroboration: Near-exact plate match (1 edit: '{plate_a}' vs '{plate_b}') "
                    f"strongly corroborated by high visual Re-ID similarity ({reid_sim:.3f}) and "
                    f"feasible transit ({st_eval.time_delta_sec:.1f}s, {st_eval.implied_speed_kmh:.1f} km/h)."
                )

        elif match_score >= self.medium_threshold:
            tier = ConfidenceTier.MEDIUM
            is_matched = True
            if plate_edit_dist == 1:
                explanation = (
                    f"Probable Association: Minor plate divergence ('{plate_a}' vs '{plate_b}', 1 edit) "
                    f"with consistent visual appearance (Re-ID sim: {reid_sim or 'N/A'}) and feasible transit."
                )
            elif reid_sim is not None and reid_sim >= 0.90:
                explanation = (
                    f"Visual Candidate: Strong appearance correlation (Re-ID: {reid_sim:.3f}) and feasible "
                    f"transit, but plate unconfirmed. Flagged as medium confidence candidate."
                )
            else:
                explanation = (
                    f"Moderate Evidence: Composite score {match_score:.2f} satisfies medium threshold "
                    f"based on partial plate agreement and spatio-temporal transit."
                )

        elif match_score >= self.low_threshold:
            tier = ConfidenceTier.LOW
            is_matched = False
            explanation = (
                f"Weak Correlation: Score {match_score:.2f} indicates insufficient evidence to link "
                f"observations across cameras. Visual or plate agreement is too weak or unverified."
            )

        else:
            tier = ConfidenceTier.UNMATCHED
            is_matched = False
            explanation = (
                f"Unmatched: Composite evidence score ({match_score:.2f}) falls below association "
                f"threshold. Observations treated as distinct physical vehicles."
            )

        return CrossCameraMatchRecord(
            global_vehicle_id=None,
            observation_a=obs_a,
            observation_b=obs_b,
            match_score=match_score,
            confidence_tier=tier,
            is_matched=is_matched,
            evidence_breakdown=evidence,
            explanation=explanation,
            timestamp=current_time,
        )

    def associate(
        self,
        observation: VehicleObservation,
        active_gallery: List[VehicleObservation],
    ) -> MatchResult:
        """
        Legacy contract support: associates incoming observation with active gallery.
        """
        best_match: Optional[CrossCameraMatchRecord] = None

        for gallery_obs in active_gallery:
            # Only match across different cameras
            if gallery_obs.camera_id == observation.camera_id:
                continue

            record = self.match_pair(gallery_obs, observation)
            if record.is_matched:
                if best_match is None or record.match_score > best_match.match_score:
                    best_match = record

        if best_match and best_match.observation_a.global_vehicle_id:
            return MatchResult(
                global_vehicle_id=best_match.observation_a.global_vehicle_id,
                confidence=best_match.match_score,
                matched_by=best_match.confidence_tier.value,
                previous_camera_id=best_match.observation_a.camera_id,
                time_delta_sec=best_match.evidence_breakdown.get("time_delta_sec"),
            )

        # New global identity
        new_gid = f"GLOBAL-VEH-{int(time.time() * 1000) % 1000000:06d}"
        observation.global_vehicle_id = new_gid
        return MatchResult(
            global_vehicle_id=new_gid,
            confidence=1.0,
            matched_by="NEW_IDENTITY",
            previous_camera_id=None,
            time_delta_sec=None,
        )
