"""
Deterministic Tests for Cross-Camera Vehicle Association Engine
Problem Statement ID: SIH26127

Verifies multi-evidence fusion:
1. Strong plate match
2. Partial OCR + strong Re-ID
3. Conflicting plate / Re-ID
4. Impossible temporal transition
5. No evidence
6. Visual similarity alone does NOT create global ID
7. Global vehicle trajectory aggregation and audit trails
"""
import pytest
import numpy as np

from ai.matching.base import (
    VehicleObservation,
    CrossCameraMatchRecord,
    ConfidenceTier,
)
from ai.matching.spatial_temporal import SpatioTemporalTopology
from ai.matching.engine import ExplainableCrossCameraMatcher, levenshtein_distance
from backend.app.services.cross_camera import CrossCameraAssociationService


# Helper to generate a normalized unit feature embedding
def make_unit_embedding(seed: int = 42, dim: int = 256) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def make_similar_embedding(base: np.ndarray, similarity: float = 0.95) -> np.ndarray:
    """Generate an embedding with exact desired cosine similarity to base."""
    rng = np.random.RandomState(999)
    noise = rng.randn(len(base)).astype(np.float32)
    # Orthogonalize noise relative to base
    noise = noise - (np.dot(noise, base) * base)
    noise = noise / np.linalg.norm(noise)
    # Linear combination
    combined = (similarity * base) + (np.sqrt(max(0.0, 1.0 - similarity**2)) * noise)
    return combined / np.linalg.norm(combined)


@pytest.fixture
def topology():
    """Topology fixture with configured urban CCTV locations."""
    topo = SpatioTemporalTopology()
    # CAM-001 (lat: 28.6139, lon: 77.2090)
    # CAM-002 (lat: 28.6180, lon: 77.2150) -> ~740m away
    # CAM-005 (lat: 28.6220, lon: 77.2185) -> ~1280m away from CAM-001
    return topo


@pytest.fixture
def matcher(topology):
    return ExplainableCrossCameraMatcher(topology=topology)


# =====================================================================
# Test 1: Strong Plate Match
# =====================================================================

def test_strong_plate_match(matcher):
    """
    Scenario: Exact plate match with high OCR confidence across a feasible travel time.
    Expected: HIGH CONFIDENCE, is_matched=True, score >= 0.82.
    """
    emb_a = make_unit_embedding(seed=10)
    emb_b = make_similar_embedding(emb_a, similarity=0.92)

    # CAM-001 to CAM-002 distance ~740m.
    # At 40 km/h (~11.1 m/s), transit takes ~67 seconds.
    obs_a = VehicleObservation(
        camera_id="CAM-001",
        local_track_id=1,
        timestamp=100.0,
        normalized_plate="DL01AB1234",
        ocr_confidence=0.92,
        embedding=emb_a,
        vehicle_class="car",
    )
    obs_b = VehicleObservation(
        camera_id="CAM-002",
        local_track_id=12,
        timestamp=175.0,  # 75s later -> ~35.5 km/h (very feasible)
        normalized_plate="DL01AB1234",
        ocr_confidence=0.89,
        embedding=emb_b,
        vehicle_class="car",
    )

    record = matcher.match_pair(obs_a, obs_b)

    assert record.confidence_tier == ConfidenceTier.HIGH
    assert record.is_matched is True
    assert record.match_score >= 0.82
    assert record.evidence_breakdown["plate_edit_distance"] == 0
    assert record.evidence_breakdown["temporal_feasible"] is True
    assert "Exact license plate match" in record.explanation


# =====================================================================
# Test 2: Partial OCR + Strong Re-ID
# =====================================================================

def test_partial_ocr_plus_strong_reid(matcher):
    """
    Scenario: Plate has 1 edit distance (e.g. optical misread 'DL01AB1234' vs 'DL01AB123'),
    corroborated by high Re-ID appearance similarity (0.95) and feasible transition.
    Expected: HIGH or qualified MEDIUM CONFIDENCE, is_matched=True.
    """
    emb_a = make_unit_embedding(seed=20)
    emb_b = make_similar_embedding(emb_a, similarity=0.96)

    obs_a = VehicleObservation(
        camera_id="CAM-001",
        local_track_id=5,
        timestamp=200.0,
        normalized_plate="DL01AB1234",
        ocr_confidence=0.88,
        embedding=emb_a,
    )
    obs_b = VehicleObservation(
        camera_id="CAM-002",
        local_track_id=18,
        timestamp=280.0,  # 80s later
        normalized_plate="DL01AB123",  # 1 deletion edit
        ocr_confidence=0.82,
        embedding=emb_b,
    )

    record = matcher.match_pair(obs_a, obs_b)

    assert record.confidence_tier in (ConfidenceTier.HIGH, ConfidenceTier.MEDIUM)
    assert record.is_matched is True
    assert record.match_score >= 0.65
    assert record.evidence_breakdown["plate_edit_distance"] == 1
    assert record.evidence_breakdown["reid_similarity_score"] >= 0.90
    assert "1 edit" in record.explanation or "corroborated" in record.explanation.lower()


# =====================================================================
# Test 3: Conflicting Plate / Re-ID
# =====================================================================

def test_conflicting_plate_reid(matcher):
    """
    Scenario: High Re-ID similarity (two white cars look almost identical),
    BUT both have verified high-confidence plates that completely disagree.
    Expected: UNMATCHED, is_matched=False, PLATE_CONFLICT veto applied.
    """
    emb_a = make_unit_embedding(seed=30)
    # Visually very similar: 0.94 cosine similarity
    emb_b = make_similar_embedding(emb_a, similarity=0.94)

    obs_a = VehicleObservation(
        camera_id="CAM-001",
        local_track_id=2,
        timestamp=300.0,
        normalized_plate="DL01AB1234",
        ocr_confidence=0.88,
        embedding=emb_a,
    )
    obs_b = VehicleObservation(
        camera_id="CAM-002",
        local_track_id=22,
        timestamp=370.0,
        normalized_plate="HR26DK8337",  # Totally different plate
        ocr_confidence=0.90,
        embedding=emb_b,
    )

    record = matcher.match_pair(obs_a, obs_b)

    assert record.confidence_tier == ConfidenceTier.UNMATCHED
    assert record.is_matched is False
    assert record.match_score <= 0.20
    assert record.evidence_breakdown["veto_applied"] == "PLATE_CONFLICT"
    assert "Plate Conflict Veto" in record.explanation


# =====================================================================
# Test 4: Impossible Temporal Transition
# =====================================================================

def test_impossible_temporal_transition(matcher):
    """
    Scenario: Two observations across distant cameras (CAM-001 to CAM-005, ~1.28 km)
    occurring only 4 seconds apart (implied speed > 1100 km/h).
    Expected: UNMATCHED, is_matched=False, TEMPORAL_IMPOSSIBLE veto applied.
    """
    emb_a = make_unit_embedding(seed=40)
    emb_b = emb_a.copy()

    obs_a = VehicleObservation(
        camera_id="CAM-001",
        local_track_id=8,
        timestamp=500.0,
        normalized_plate="KA03MG7788",
        ocr_confidence=0.95,
        embedding=emb_a,
    )
    obs_b = VehicleObservation(
        camera_id="CAM-005",
        local_track_id=35,
        timestamp=504.0,  # 4 seconds later for 1.28 km!
        normalized_plate="KA03MG7788",
        ocr_confidence=0.95,
        embedding=emb_b,
    )

    record = matcher.match_pair(obs_a, obs_b)

    assert record.confidence_tier == ConfidenceTier.UNMATCHED
    assert record.is_matched is False
    assert record.match_score == 0.0
    assert record.evidence_breakdown["veto_applied"] == "TEMPORAL_IMPOSSIBLE"
    assert "Temporal Feasibility Veto" in record.explanation


# =====================================================================
# Test 5: No Evidence
# =====================================================================

def test_no_evidence(matcher):
    """
    Scenario: Neither observation has a license plate or visual embedding.
    Expected: UNMATCHED, is_matched=False, NO_EVIDENCE veto applied.
    """
    obs_a = VehicleObservation(
        camera_id="CAM-001",
        local_track_id=9,
        timestamp=600.0,
        normalized_plate=None,
        embedding=None,
    )
    obs_b = VehicleObservation(
        camera_id="CAM-002",
        local_track_id=40,
        timestamp=680.0,
        normalized_plate=None,
        embedding=None,
    )

    record = matcher.match_pair(obs_a, obs_b)

    assert record.confidence_tier == ConfidenceTier.UNMATCHED
    assert record.is_matched is False
    assert record.match_score == 0.0
    assert record.evidence_breakdown["veto_applied"] == "NO_EVIDENCE"
    assert "Insufficient Evidence" in record.explanation


# =====================================================================
# Test 6: Visual Similarity Alone Does NOT Create Global ID
# =====================================================================

def test_visual_similarity_alone_does_not_create_high_confidence(matcher):
    """
    Requirement: Do NOT create a global ID merely because two observations look visually similar.
    Scenario: Plates are missing/unreadable. Re-ID visual similarity is good (0.88).
    Expected: Confidence is capped at MEDIUM/LOW and does NOT qualify as HIGH CONFIDENCE.
    """
    emb_a = make_unit_embedding(seed=50)
    emb_b = make_similar_embedding(emb_a, similarity=0.88)

    obs_a = VehicleObservation(
        camera_id="CAM-001",
        local_track_id=14,
        timestamp=700.0,
        normalized_plate=None,
        embedding=emb_a,
    )
    obs_b = VehicleObservation(
        camera_id="CAM-002",
        local_track_id=52,
        timestamp=770.0,
        normalized_plate=None,
        embedding=emb_b,
    )

    record = matcher.match_pair(obs_a, obs_b)

    # Must NOT achieve HIGH confidence
    assert record.confidence_tier != ConfidenceTier.HIGH
    assert record.match_score < matcher.high_threshold


# =====================================================================
# Test 7: End-to-End Association Service Trajectory Management
# =====================================================================

def test_association_service_manages_global_identities():
    service = CrossCameraAssociationService()

    emb1 = make_unit_embedding(seed=100)
    emb2 = make_similar_embedding(emb1, similarity=0.96)
    emb3 = make_unit_embedding(seed=200)

    # Observation 1: Car at CAM-001
    obs1 = VehicleObservation(
        camera_id="CAM-001",
        local_track_id=101,
        timestamp=1000.0,
        normalized_plate="MH12DE1433",
        ocr_confidence=0.91,
        embedding=emb1,
    )
    gid1, rec1 = service.process_observation(obs1)
    assert gid1.startswith("GLOBAL-VEH-")
    assert rec1 is None  # First sighting, no prior gallery candidates

    # Observation 2: Same car arrives at CAM-002 after 80 seconds
    obs2 = VehicleObservation(
        camera_id="CAM-002",
        local_track_id=202,
        timestamp=1080.0,
        normalized_plate="MH12DE1433",
        ocr_confidence=0.93,
        embedding=emb2,
    )
    gid2, rec2 = service.process_observation(obs2)

    # Must be associated to the SAME global vehicle ID!
    assert gid2 == gid1
    assert rec2 is not None
    assert rec2.is_matched is True
    assert rec2.confidence_tier == ConfidenceTier.HIGH

    # Observation 3: Completely different vehicle arrives at CAM-002
    obs3 = VehicleObservation(
        camera_id="CAM-002",
        local_track_id=203,
        timestamp=1100.0,
        normalized_plate="UP16BT4004",
        ocr_confidence=0.90,
        embedding=emb3,
    )
    gid3, rec3 = service.process_observation(obs3)

    # Must be assigned a NEW distinct global vehicle ID!
    assert gid3 != gid1

    # Verify trajectory registry
    traj_vehicle1 = service.get_global_vehicle(gid1)
    assert len(traj_vehicle1) == 2
    assert traj_vehicle1[0].camera_id == "CAM-001"
    assert traj_vehicle1[1].camera_id == "CAM-002"

    traj_vehicle2 = service.get_global_vehicle(gid3)
    assert len(traj_vehicle2) == 1
    assert traj_vehicle2[0].camera_id == "CAM-002"

    # Verify audit history
    history = service.get_match_history()
    assert len(history) >= 2
    for h in history:
        assert isinstance(h, CrossCameraMatchRecord)
        assert len(h.explanation) > 0
        assert "evidence_breakdown" in h.to_dict()
