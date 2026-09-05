"""
Multi-Object Tracking Service
Integrates SingleCameraByteTracker instances across individual camera feeds.
Enforces strict camera isolation: local_track_id is unique only within a camera.
"""
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from ai.detectors.base import DetectionResult
from ai.trackers.base import BaseTracker, TrackedVehicle
from ai.trackers.byte_tracker import SingleCameraByteTracker


class TrackingService:
    """
    Maintains independent tracker instances for each active camera feed.
    """

    def __init__(
        self,
        track_high_thresh: float = 0.5,
        track_low_thresh: float = 0.1,
        match_thresh: float = 0.8,
        max_lost_frames: int = 30,
    ):
        self.track_high_thresh = track_high_thresh
        self.track_low_thresh = track_low_thresh
        self.match_thresh = match_thresh
        self.max_lost_frames = max_lost_frames

        self._camera_trackers: Dict[str, BaseTracker] = {}

    def _get_or_create_tracker(self, camera_id: str) -> BaseTracker:
        """
        Retrieves or creates a dedicated single-camera tracker instance.
        Ensures strict camera isolation: track IDs are camera-local.
        """
        if camera_id not in self._camera_trackers:
            self._camera_trackers[camera_id] = SingleCameraByteTracker(
                camera_id=camera_id,
                track_high_thresh=self.track_high_thresh,
                track_low_thresh=self.track_low_thresh,
                match_thresh=self.match_thresh,
                max_lost_frames=self.max_lost_frames,
            )
        return self._camera_trackers[camera_id]

    def register_tracker(self, camera_id: str, tracker: BaseTracker) -> None:
        self._camera_trackers[camera_id] = tracker

    def get_tracker(self, camera_id: str) -> Optional[BaseTracker]:
        return self._camera_trackers.get(camera_id)

    def reset_tracker(self, camera_id: str) -> None:
        if camera_id in self._camera_trackers:
            self._camera_trackers[camera_id].reset()

    def reset_all(self) -> None:
        for tracker in self._camera_trackers.values():
            tracker.reset()

    def update_tracks(
        self,
        camera_id: str,
        detections: List[DetectionResult],
        frame: Optional[np.ndarray],
        frame_index: int,
        timestamp_ms: float,
    ) -> List[TrackedVehicle]:
        """
        Routes frame detections to the camera's dedicated tracker.
        Returns active tracked vehicles for this camera in this frame.
        """
        tracker = self._get_or_create_tracker(camera_id)
        return tracker.update(
            detections=detections,
            frame=frame,
            camera_id=camera_id,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
        )

    def draw_tracking_overlays(
        self,
        frame: np.ndarray,
        tracks: List[TrackedVehicle],
        draw_trails: bool = True,
    ) -> np.ndarray:
        """
        Visualizes tracking state: bounding boxes, local track IDs, category,
        and spatial motion trails (centroid trajectory).
        Preserves original frame dimensions.
        """
        if frame is None or frame.size == 0:
            return frame

        annotated = frame.copy()
        h, w = annotated.shape[:2]

        for trk in tracks:
            bbox = trk.bounding_box
            x1 = max(0, min(w - 1, int(round(bbox.x1))))
            y1 = max(0, min(h - 1, int(round(bbox.y1))))
            x2 = max(0, min(w - 1, int(round(bbox.x2))))
            y2 = max(0, min(h - 1, int(round(bbox.y2))))

            # Assign color pseudo-randomly but deterministically based on local_track_id
            color = (
                int((trk.local_track_id * 67) % 255),
                int((trk.local_track_id * 131) % 255),
                int((trk.local_track_id * 199) % 255),
            )

            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Draw Track ID & Class badge
            label = f"ID:{trk.local_track_id} {trk.class_name.upper()} {trk.detection_confidence:.2f}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            label_y1 = max(0, y1 - label_h - baseline - 4)
            label_y2 = label_y1 + label_h + baseline + 4

            cv2.rectangle(
                annotated,
                (x1, label_y1),
                (x1 + label_w + 6, label_y2),
                color,
                -1,
            )
            cv2.putText(
                annotated,
                label,
                (x1 + 3, label_y2 - baseline - 2),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )

            # Draw centroid trajectory trail
            if draw_trails and len(trk.trajectory_history) > 1:
                pts = np.array(
                    [[int(pt[0]), int(pt[1])] for pt in trk.trajectory_history[-20:]],
                    dtype=np.int32,
                )
                cv2.polylines(annotated, [pts], isClosed=False, color=color, thickness=2)

        return annotated
