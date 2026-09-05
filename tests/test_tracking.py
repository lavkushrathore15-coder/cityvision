"""
Unit and Integration Tests for Multi-Object Vehicle Tracking Subsystem
Tests ByteTrack single-camera tracking:
- Track creation
- Track continuity / updates
- Track disappearance (temporary occlusion / loss)
- Track termination (aging out beyond max_lost_frames)
- Strict camera isolation (local_track_id is camera-local, not global)
"""
import numpy as np
import pytest

from ai.detectors.base import BoundingBox, DetectionResult
from ai.trackers.base import TrackState, TrackedVehicle
from ai.trackers.byte_tracker import SingleCameraByteTracker, STrack
from backend.app.services.tracking import TrackingService


# ---------------------------------------------------------------------------
# 1. Track Creation Tests
# ---------------------------------------------------------------------------

def test_track_creation():
    tracker = SingleCameraByteTracker(camera_id="CAM-001", track_high_thresh=0.5)

    det1 = DetectionResult(
        bbox=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=180.0),
        confidence=0.88,
        class_id=2,
        class_name="car",
    )
    det2 = DetectionResult(
        bbox=BoundingBox(x1=400.0, y1=200.0, x2=550.0, y2=320.0),
        confidence=0.75,
        class_id=5,
        class_name="bus",
    )

    tracks = tracker.update(
        detections=[det1, det2],
        frame=None,
        camera_id="CAM-001",
        frame_index=1,
        timestamp_ms=0.0,
    )

    assert len(tracks) == 2
    assert tracker.total_created == 2

    # Verify track fields
    t1, t2 = tracks[0], tracks[1]
    assert t1.camera_id == "CAM-001"
    assert t1.local_track_id == 1
    assert t1.class_name == "car"
    assert t1.frame_number == 1
    assert t1.detection_confidence == 0.88
    assert isinstance(t1.bounding_box, BoundingBox)

    assert t2.camera_id == "CAM-001"
    assert t2.local_track_id == 2
    assert t2.class_name == "bus"


# ---------------------------------------------------------------------------
# 2. Track Continuity / Updates
# ---------------------------------------------------------------------------

def test_track_continuity_across_consecutive_frames():
    """
    Simulates a car driving smoothly across 10 frames.
    The vehicle must retain the exact same local_track_id throughout.
    """
    tracker = SingleCameraByteTracker(camera_id="CAM-001", track_high_thresh=0.5)

    for i in range(10):
        # Translate vehicle 10 pixels right each frame
        x1 = 50.0 + i * 10.0
        y1 = 120.0
        x2 = x1 + 80.0
        y2 = y1 + 50.0

        det = DetectionResult(
            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
            confidence=0.90,
            class_id=2,
            class_name="car",
        )

        tracks = tracker.update(
            detections=[det],
            frame=None,
            camera_id="CAM-001",
            frame_index=i + 1,
            timestamp_ms=i * 66.6,
        )

        assert len(tracks) == 1
        curr_track = tracks[0]

        # Crucial requirement: retains the exact same local_track_id
        assert curr_track.local_track_id == 1
        assert curr_track.hits == i + 1
        assert curr_track.lost_frames == 0
        assert len(curr_track.trajectory_history) == i + 1


# ---------------------------------------------------------------------------
# 3. Track Disappearance & Re-Identification Recovery
# ---------------------------------------------------------------------------

def test_track_disappearance_and_recovery():
    """
    Vehicle is tracked -> disappears for 2 frames (occlusion) -> reappears.
    Tracker should recover the track and keep the same local_track_id.
    """
    tracker = SingleCameraByteTracker(
        camera_id="CAM-001",
        track_high_thresh=0.5,
        max_lost_frames=5,
    )

    # Frame 1: Vehicle appears
    det = DetectionResult(
        bbox=BoundingBox(x1=100.0, y1=100.0, x2=180.0, y2=150.0),
        confidence=0.85,
        class_id=2,
        class_name="car",
    )
    t1 = tracker.update([det], None, "CAM-001", frame_index=1, timestamp_ms=0.0)
    assert len(t1) == 1
    assert t1[0].local_track_id == 1

    # Frames 2 & 3: Occluded (0 detections)
    t2 = tracker.update([], None, "CAM-001", frame_index=2, timestamp_ms=66.6)
    t3 = tracker.update([], None, "CAM-001", frame_index=3, timestamp_ms=133.2)
    assert len(t2) == 0, "No active tracks should be returned during occlusion"
    assert len(t3) == 0

    # Verify track entered LOST state in tracker pool
    assert len(tracker._lost_tracks) == 1
    assert tracker._lost_tracks[0].local_track_id == 1
    assert tracker._lost_tracks[0].lost_frames == 2

    # Frame 4: Vehicle reappears near predicted location
    det_reappear = DetectionResult(
        bbox=BoundingBox(x1=105.0, y1=100.0, x2=185.0, y2=150.0),
        confidence=0.82,
        class_id=2,
        class_name="car",
    )
    t4 = tracker.update([det_reappear], None, "CAM-001", frame_index=4, timestamp_ms=199.8)

    assert len(t4) == 1
    # Successfully recovered: retains local_track_id = 1
    assert t4[0].local_track_id == 1
    assert t4[0].lost_frames == 0


# ---------------------------------------------------------------------------
# 4. Track Termination
# ---------------------------------------------------------------------------

def test_track_termination():
    """
    Vehicle disappears and remains missing for > max_lost_frames.
    Track must be permanently terminated and removed from the active pool.
    """
    max_lost = 3
    tracker = SingleCameraByteTracker(
        camera_id="CAM-001",
        track_high_thresh=0.5,
        max_lost_frames=max_lost,
    )

    # Frame 1: Vehicle appears
    det = DetectionResult(
        bbox=BoundingBox(x1=200.0, y1=200.0, x2=300.0, y2=260.0),
        confidence=0.90,
        class_id=2,
        class_name="car",
    )
    tracker.update([det], None, "CAM-001", frame_index=1, timestamp_ms=0.0)

    # Frames 2, 3, 4: Lost (within grace period)
    for f in range(2, 2 + max_lost):
        tracker.update([], None, "CAM-001", frame_index=f, timestamp_ms=f * 66.6)
        assert len(tracker._lost_tracks) == 1

    # Frame 5: Exceeds max_lost_frames -> Terminated
    tracker.update([], None, "CAM-001", frame_index=5, timestamp_ms=5 * 66.6)
    assert len(tracker._lost_tracks) == 0, "Terminated track must be purged from lost pool"
    assert len(tracker._removed_tracks) == 1
    assert tracker.total_terminated == 1
    assert tracker._removed_tracks[0].state == TrackState.REMOVED


# ---------------------------------------------------------------------------
# 5. Camera Isolation (Local Track IDs are strictly Camera-Local)
# ---------------------------------------------------------------------------

def test_camera_isolation():
    """
    Verifies that CAM-001 and CAM-002 maintain strictly separate local_track_ids.
    They must not merge or be considered the same vehicle across cameras.
    """
    service = TrackingService()

    det_cam1 = DetectionResult(
        bbox=BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=120.0),
        confidence=0.85,
        class_id=2,
        class_name="car",
    )
    det_cam2 = DetectionResult(
        bbox=BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=120.0),
        confidence=0.85,
        class_id=2,
        class_name="car",
    )

    tracks_cam1 = service.update_tracks("CAM-001", [det_cam1], None, frame_index=1, timestamp_ms=0.0)
    tracks_cam2 = service.update_tracks("CAM-002", [det_cam2], None, frame_index=1, timestamp_ms=0.0)

    assert len(tracks_cam1) == 1
    assert len(tracks_cam2) == 1

    # Each camera starts its own sequence at local_track_id=1
    assert tracks_cam1[0].camera_id == "CAM-001"
    assert tracks_cam1[0].local_track_id == 1

    assert tracks_cam2[0].camera_id == "CAM-002"
    assert tracks_cam2[0].local_track_id == 1

    # Trackers must be completely distinct instances
    assert service.get_tracker("CAM-001") is not service.get_tracker("CAM-002")


# ---------------------------------------------------------------------------
# 6. Visualization Overlays
# ---------------------------------------------------------------------------

def test_draw_tracking_overlays():
    service = TrackingService()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    det = DetectionResult(
        bbox=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=180.0),
        confidence=0.88,
        class_id=2,
        class_name="car",
    )
    tracks = service.update_tracks("CAM-001", [det], frame, frame_index=1, timestamp_ms=0.0)

    annotated = service.draw_tracking_overlays(frame, tracks, draw_trails=True)
    assert annotated is not None
    assert annotated.shape == frame.shape
    assert annotated.dtype == frame.dtype
    assert not np.array_equal(annotated, frame)


# ---------------------------------------------------------------------------
# 7. End-to-End YOLO Detection -> ByteTrack Integration
# ---------------------------------------------------------------------------

def test_yolo_detection_to_bytetrack_integration():
    """
    Feeds real YOLO model detections directly into the TrackingService across
    multiple simulated frames of a vehicle translating across the camera field.
    """
    from pathlib import Path
    import cv2
    from ai.detectors.yolo import YOLOVehicleDetector

    weights_path = Path("models/weights/yolov8n.pt")
    image_path = Path("data/sample_images/bus.jpg")
    if not weights_path.is_file() or not image_path.is_file():
        pytest.skip("Model weights or test image missing")

    detector = YOLOVehicleDetector(weights_path=str(weights_path), device="cpu")
    tracking_service = TrackingService()

    base_frame = cv2.imread(str(image_path))
    assert base_frame is not None

    # Step 1: Detect on base frame
    detections = detector.detect(base_frame, confidence_threshold=0.35)
    assert len(detections) > 0

    # Step 2: Feed detections into TrackingService
    tracks_f1 = tracking_service.update_tracks(
        camera_id="CAM-001",
        detections=detections,
        frame=base_frame,
        frame_index=1,
        timestamp_ms=0.0,
    )
    assert len(tracks_f1) > 0
    assigned_local_id = tracks_f1[0].local_track_id
    assert tracks_f1[0].camera_id == "CAM-001"
    assert tracks_f1[0].class_name == "bus"

    # Step 3: Frame 2 with slight translation simulates motion
    translated_detections = [
        DetectionResult(
            bbox=BoundingBox(
                x1=d.bbox.x1 + 5.0,
                y1=d.bbox.y1 + 2.0,
                x2=d.bbox.x2 + 5.0,
                y2=d.bbox.y2 + 2.0,
            ),
            confidence=d.confidence,
            class_id=d.class_id,
            class_name=d.class_name,
        )
        for d in detections
    ]

    tracks_f2 = tracking_service.update_tracks(
        camera_id="CAM-001",
        detections=translated_detections,
        frame=base_frame,
        frame_index=2,
        timestamp_ms=66.6,
    )
    assert len(tracks_f2) > 0
    # Must retain identical local_track_id!
    assert tracks_f2[0].local_track_id == assigned_local_id
    assert tracks_f2[0].hits == 2
