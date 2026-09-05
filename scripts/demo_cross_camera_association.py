"""
Demonstration Script for Cross-Camera Vehicle Association Engine
Problem Statement ID: SIH26127

Demonstrates explainable multi-evidence fusion across cameras:
1. Strong plate match (HIGH CONFIDENCE)
2. Partial OCR + strong Re-ID (HIGH / MEDIUM CONFIDENCE)
3. Conflicting plate / Re-ID (UNMATCHED - Plate conflict veto)
4. Impossible temporal transition (UNMATCHED - Temporal veto)
5. No evidence (UNMATCHED - Insufficient evidence)
6. Visual similarity alone does NOT create Global ID
"""
import sys
import os
import numpy as np

# Ensure root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.matching.base import VehicleObservation, ConfidenceTier
from ai.matching.engine import ExplainableCrossCameraMatcher
from backend.app.services.cross_camera import CrossCameraAssociationService


def make_embedding(seed: int, dim: int = 256) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def make_similar_embedding(base: np.ndarray, similarity: float = 0.95) -> np.ndarray:
    rng = np.random.RandomState(777)
    noise = rng.randn(len(base)).astype(np.float32)
    noise = noise - (np.dot(noise, base) * base)
    noise = noise / np.linalg.norm(noise)
    combined = (similarity * base) + (np.sqrt(max(0.0, 1.0 - similarity**2)) * noise)
    return combined / np.linalg.norm(combined)


def print_match_record(title: str, record):
    print("=" * 75)
    print(f"SCENARIO: {title}")
    print("=" * 75)
    print(f"Camera Transition:   {record.observation_a.camera_id} -> {record.observation_b.camera_id}")
    print(f"Elapsed Time:        {record.evidence_breakdown.get('time_delta_sec')} seconds")
    print(f"Implied Speed:       {record.evidence_breakdown.get('implied_speed_kmh')} km/h")
    print(f"Plate A:             '{record.observation_a.normalized_plate}' (conf: {record.observation_a.ocr_confidence:.2f})")
    print(f"Plate B:             '{record.observation_b.normalized_plate}' (conf: {record.observation_b.ocr_confidence:.2f})")
    print(f"Plate Edit Distance: {record.evidence_breakdown.get('plate_edit_distance')}")
    print(f"Re-ID Similarity:    {record.evidence_breakdown.get('reid_similarity_score')}")
    print(f"Veto Applied:        {record.evidence_breakdown.get('veto_applied')}")
    print(f"Composite Score:     {record.match_score:.4f}")
    print(f"Confidence Tier:     {record.confidence_tier.value}")
    print(f"Association Verdict: {'MATCHED (Merged Global ID)' if record.is_matched else 'UNMATCHED (Distinct Global ID)'}")
    print(f"Explanation:\n  \"{record.explanation}\"")
    print()


def run_demo():
    matcher = ExplainableCrossCameraMatcher()

    # -------------------------------------------------------------
    # 1. Strong Plate Match
    # -------------------------------------------------------------
    emb1 = make_embedding(10)
    emb2 = make_similar_embedding(emb1, 0.93)
    rec1 = matcher.match_pair(
        VehicleObservation(camera_id="CAM-001", local_track_id=1, timestamp=100.0, normalized_plate="DL01AB1234", ocr_confidence=0.92, embedding=emb1),
        VehicleObservation(camera_id="CAM-002", local_track_id=12, timestamp=180.0, normalized_plate="DL01AB1234", ocr_confidence=0.90, embedding=emb2),
    )
    print_match_record("1. Strong Plate Match (Exact Plate + Corroborating Re-ID + Feasible Time)", rec1)

    # -------------------------------------------------------------
    # 2. Partial OCR + Strong Re-ID
    # -------------------------------------------------------------
    emb_a2 = make_embedding(20)
    emb_b2 = make_similar_embedding(emb_a2, 0.96)
    rec2 = matcher.match_pair(
        VehicleObservation(camera_id="CAM-001", local_track_id=5, timestamp=200.0, normalized_plate="DL01AB1234", ocr_confidence=0.88, embedding=emb_a2),
        VehicleObservation(camera_id="CAM-002", local_track_id=18, timestamp=275.0, normalized_plate="DL01AB123", ocr_confidence=0.82, embedding=emb_b2),
    )
    print_match_record("2. Partial OCR + Strong Re-ID (1 Edit Distance + High Visual Similarity)", rec2)

    # -------------------------------------------------------------
    # 3. Conflicting Plate / Re-ID
    # -------------------------------------------------------------
    emb_a3 = make_embedding(30)
    emb_b3 = make_similar_embedding(emb_a3, 0.94)  # High visual similarity!
    rec3 = matcher.match_pair(
        VehicleObservation(camera_id="CAM-001", local_track_id=2, timestamp=300.0, normalized_plate="DL01AB1234", ocr_confidence=0.91, embedding=emb_a3),
        VehicleObservation(camera_id="CAM-002", local_track_id=22, timestamp=375.0, normalized_plate="HR26DK8337", ocr_confidence=0.89, embedding=emb_b3),
    )
    print_match_record("3. Conflicting Plate / Re-ID (High Visual Similarity BUT Verified Plate Mismatch)", rec3)

    # -------------------------------------------------------------
    # 4. Impossible Temporal Transition
    # -------------------------------------------------------------
    rec4 = matcher.match_pair(
        VehicleObservation(camera_id="CAM-001", local_track_id=8, timestamp=500.0, normalized_plate="KA03MG7788", ocr_confidence=0.95, embedding=emb1),
        VehicleObservation(camera_id="CAM-005", local_track_id=35, timestamp=503.0, normalized_plate="KA03MG7788", ocr_confidence=0.95, embedding=emb1),
    )
    print_match_record("4. Impossible Temporal Transition (Distant Nodes in 3 Seconds)", rec4)

    # -------------------------------------------------------------
    # 5. No Evidence
    # -------------------------------------------------------------
    rec5 = matcher.match_pair(
        VehicleObservation(camera_id="CAM-001", local_track_id=9, timestamp=600.0, normalized_plate=None, embedding=None),
        VehicleObservation(camera_id="CAM-002", local_track_id=40, timestamp=680.0, normalized_plate=None, embedding=None),
    )
    print_match_record("5. No Evidence (Missing License Plate and Missing Appearance Embedding)", rec5)

    # -------------------------------------------------------------
    # 6. Visual Similarity Alone Does NOT Create Global ID
    # -------------------------------------------------------------
    emb_a6 = make_embedding(60)
    emb_b6 = make_similar_embedding(emb_a6, 0.88)
    rec6 = matcher.match_pair(
        VehicleObservation(camera_id="CAM-001", local_track_id=14, timestamp=700.0, normalized_plate=None, embedding=emb_a6),
        VehicleObservation(camera_id="CAM-002", local_track_id=52, timestamp=770.0, normalized_plate=None, embedding=emb_b6),
    )
    print_match_record("6. Visual Similarity Alone (Missing Plates -> Capped at LOW CONFIDENCE)", rec6)

    # -------------------------------------------------------------
    # 7. Global Trajectory Reconstruction
    # -------------------------------------------------------------
    print("=" * 75)
    print("TRAJECTORY RECONSTRUCTION: CrossCameraAssociationService")
    print("=" * 75)
    service = CrossCameraAssociationService()

    # Step 1: Vehicle 1 sighted at CAM-001
    g1, _ = service.process_observation(
        VehicleObservation(camera_id="CAM-001", local_track_id=101, timestamp=1000.0, normalized_plate="MH12DE1433", ocr_confidence=0.91, embedding=emb1)
    )
    print(f"Observation 1 (CAM-001): Assigned Global ID -> {g1}")

    # Step 2: Same vehicle sighted at CAM-002 (80s later)
    g2, match2 = service.process_observation(
        VehicleObservation(camera_id="CAM-002", local_track_id=202, timestamp=1080.0, normalized_plate="MH12DE1433", ocr_confidence=0.93, embedding=emb2)
    )
    print(f"Observation 2 (CAM-002): Associated Global ID -> {g2} (Match Tier: {match2.confidence_tier.value})")

    # Step 3: Different vehicle sighted at CAM-002
    g3, match3 = service.process_observation(
        VehicleObservation(camera_id="CAM-002", local_track_id=203, timestamp=1100.0, normalized_plate="UP16BT4004", ocr_confidence=0.90, embedding=make_embedding(999))
    )
    print(f"Observation 3 (CAM-002): Assigned Global ID -> {g3} (New Identity)")

    print(f"\nActive Global Vehicles in Registry: {service.get_all_global_ids()}")
    print(f"Trajectory Waypoints for {g1}: {[obs.camera_id for obs in service.get_global_vehicle(g1)]}")
    print("=" * 75)


if __name__ == "__main__":
    run_demo()
