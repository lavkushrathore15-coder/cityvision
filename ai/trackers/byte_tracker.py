"""
ByteTrack: Multi-Object Vehicle Tracker for Single Camera Feeds
Implements two-stage association (high-confidence and low-confidence detections),
Kalman filter motion modeling, and explicit track lifecycle state transitions:
Creation -> Updates -> Disappearance -> Termination.
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import linear_sum_assignment

from ai.detectors.base import BoundingBox, DetectionResult
from ai.trackers.base import BaseTracker, TrackState, TrackedVehicle


def box_iou_batch(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """
    Computes pairwise Intersection over Union (IoU) between two sets of bounding boxes.
    boxes_a: (N, 4) in [x1, y1, x2, y2]
    boxes_b: (M, 4) in [x1, y1, x2, y2]
    Returns: (N, M) matrix of IoU scores in [0, 1].
    """
    if boxes_a.size == 0 or boxes_b.size == 0:
        return np.empty((len(boxes_a), len(boxes_b)), dtype=np.float32)

    x1 = np.maximum(boxes_a[:, 0:1], boxes_b[:, 0:1].T)
    y1 = np.maximum(boxes_a[:, 1:2], boxes_b[:, 1:2].T)
    x2 = np.minimum(boxes_a[:, 2:3], boxes_b[:, 2:3].T)
    y2 = np.minimum(boxes_a[:, 3:4], boxes_b[:, 3:4].T)

    intersection = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    area_a = (boxes_a[:, 2] - boxes_a[:, 0]) * (boxes_a[:, 3] - boxes_a[:, 1])
    area_b = (boxes_b[:, 2] - boxes_b[:, 0]) * (boxes_b[:, 3] - boxes_b[:, 1])
    union = area_a[:, None] + area_b[None, :] - intersection

    iou = np.zeros_like(intersection)
    valid = union > 0
    iou[valid] = intersection[valid] / union[valid]
    return iou


class KalmanBoxTracker:
    """
    Constant-velocity Kalman filter tracking bounding box state in:
    [x_center, y_center, area, aspect_ratio, dx, dy, d_area, d_aspect_ratio]
    """

    def __init__(self, bbox: BoundingBox):
        # State dimension: 8, Measurement dimension: 4
        self.dim_x = 8
        self.dim_z = 4

        # State transition matrix F
        self.F = np.eye(self.dim_x, dtype=np.float32)
        for i in range(4):
            self.F[i, i + 4] = 1.0  # position += velocity

        # Measurement matrix H
        self.H = np.zeros((self.dim_z, self.dim_x), dtype=np.float32)
        for i in range(4):
            self.H[i, i] = 1.0

        # State vector x
        self.x = np.zeros((self.dim_x, 1), dtype=np.float32)
        self.x[:4] = self._bbox_to_z(bbox)

        # Covariance matrix P
        self.P = np.eye(self.dim_x, dtype=np.float32) * 10.0
        self.P[4:, 4:] *= 100.0  # High uncertainty in initial velocity

        # Process noise Q
        self.Q = np.eye(self.dim_x, dtype=np.float32)
        self.Q[:4, :4] *= 1.0
        self.Q[4:, 4:] *= 0.01

        # Measurement noise R
        self.R = np.eye(self.dim_z, dtype=np.float32) * 1.0

    @staticmethod
    def _bbox_to_z(bbox: BoundingBox) -> np.ndarray:
        w = max(1.0, bbox.x2 - bbox.x1)
        h = max(1.0, bbox.y2 - bbox.y1)
        xc = bbox.x1 + w / 2.0
        yc = bbox.y1 + h / 2.0
        s = w * h
        r = w / float(h)
        return np.array([[xc], [yc], [s], [r]], dtype=np.float32)

    def predict(self) -> None:
        """Projects state and error covariance ahead by 1 time step."""
        if self.x[6, 0] + self.x[2, 0] <= 0:
            self.x[6, 0] = 0.0
        self.x = np.dot(self.F, self.x)
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q

    def update(self, bbox: BoundingBox) -> None:
        """Corrects state projection with new bounding box measurement."""
        z = self._bbox_to_z(bbox)
        y = z - np.dot(self.H, self.x)
        S = np.dot(np.dot(self.H, self.P), self.H.T) + self.R
        K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))
        self.x = self.x + np.dot(K, y)
        I = np.eye(self.dim_x, dtype=np.float32)
        self.P = np.dot(np.dot(I - np.dot(K, self.H), self.P), (I - np.dot(K, self.H)).T) + np.dot(np.dot(K, self.R), K.T)

    def get_state(self) -> BoundingBox:
        """Converts internal Kalman state back into bounding box coordinates."""
        xc = float(self.x[0, 0])
        yc = float(self.x[1, 0])
        s = max(1.0, float(self.x[2, 0]))
        r = max(0.01, float(self.x[3, 0]))

        w = np.sqrt(s * r)
        h = s / max(1e-5, w)

        x1 = xc - w / 2.0
        y1 = yc - h / 2.0
        x2 = xc + w / 2.0
        y2 = yc + h / 2.0
        return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


class STrack:
    """
    Internal single-camera track representation tracking lifecycle and trajectory.
    """

    def __init__(
        self,
        local_track_id: int,
        camera_id: str,
        class_name: str,
        detection: DetectionResult,
        frame_number: int,
        timestamp: float,
    ):
        self.local_track_id = local_track_id
        self.camera_id = camera_id
        self.class_name = class_name
        self.confidence = detection.confidence
        self.frame_number = frame_number
        self.timestamp = timestamp

        self.kalman = KalmanBoxTracker(detection.bbox)
        self.state = TrackState.NEW
        self.hits = 1
        self.lost_frames = 0
        self.trajectory_history: List[Tuple[float, float]] = []

        # Store centroid
        cx = (detection.bbox.x1 + detection.bbox.x2) / 2.0
        cy = (detection.bbox.y1 + detection.bbox.y2) / 2.0
        self.trajectory_history.append((cx, cy))

    def predict(self) -> None:
        self.kalman.predict()

    def update(self, detection: DetectionResult, frame_number: int, timestamp: float) -> None:
        self.kalman.update(detection.bbox)
        self.confidence = detection.confidence
        self.frame_number = frame_number
        self.timestamp = timestamp
        self.hits += 1
        self.lost_frames = 0
        self.state = TrackState.TRACKED

        bbox = self.kalman.get_state()
        cx = (bbox.x1 + bbox.x2) / 2.0
        cy = (bbox.y1 + bbox.y2) / 2.0
        self.trajectory_history.append((cx, cy))

    def mark_lost(self) -> None:
        """Transitions track into LOST (temporary disappearance)."""
        self.state = TrackState.LOST
        self.lost_frames += 1

    def mark_removed(self) -> None:
        """Transitions track into REMOVED (permanent termination)."""
        self.state = TrackState.REMOVED

    def to_tracked_vehicle(self) -> TrackedVehicle:
        bbox = self.kalman.get_state()
        return TrackedVehicle(
            local_track_id=self.local_track_id,
            camera_id=self.camera_id,
            bounding_box=bbox,
            class_name=self.class_name,
            detection_confidence=self.confidence,
            frame_number=self.frame_number,
            timestamp=self.timestamp,
            state=self.state,
            hits=self.hits,
            lost_frames=self.lost_frames,
            trajectory_history=list(self.trajectory_history),
        )


class SingleCameraByteTracker(BaseTracker):
    """
    ByteTrack implementation for a single CCTV camera feed.
    Maintains independent track IDs strictly within this camera's viewpoint.
    """

    def __init__(
        self,
        camera_id: str,
        track_high_thresh: float = 0.5,
        track_low_thresh: float = 0.1,
        match_thresh: float = 0.8,      # Maximum cost (1 - IoU threshold, 0.8 means min IoU 0.2)
        max_lost_frames: int = 30,     # Termination limit for missing tracks
        min_hits: int = 2,             # Frames required to confirm track
    ):
        self.camera_id = camera_id
        self.track_high_thresh = track_high_thresh
        self.track_low_thresh = track_low_thresh
        self.match_thresh = match_thresh
        self.max_lost_frames = max_lost_frames
        self.min_hits = min_hits

        self._next_id: int = 1
        self._tracked_tracks: List[STrack] = []
        self._lost_tracks: List[STrack] = []
        self._removed_tracks: List[STrack] = []

        # Operational metrics
        self.total_created: int = 0
        self.total_terminated: int = 0

    def reset(self) -> None:
        """Resets tracker state, pools, and local track ID counter."""
        self._next_id = 1
        self._tracked_tracks.clear()
        self._lost_tracks.clear()
        self._removed_tracks.clear()
        self.total_created = 0
        self.total_terminated = 0

    def _get_next_id(self) -> int:
        tid = self._next_id
        self._next_id += 1
        return tid

    @staticmethod
    def _linear_assignment(
        cost_matrix: np.ndarray,
        threshold: float,
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Solves the bipartite matching problem using Hungarian linear assignment.
        Returns: (matched_indices, unmatched_a, unmatched_b)
        """
        if cost_matrix.size == 0:
            return [], list(range(cost_matrix.shape[0])), list(range(cost_matrix.shape[1]))

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matches: List[Tuple[int, int]] = []
        unmatched_a = set(range(cost_matrix.shape[0]))
        unmatched_b = set(range(cost_matrix.shape[1]))

        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] <= threshold:
                matches.append((r, c))
                unmatched_a.discard(r)
                unmatched_b.discard(c)

        return matches, sorted(list(unmatched_a)), sorted(list(unmatched_b))

    def update(
        self,
        detections: List[DetectionResult],
        frame: Optional[np.ndarray],
        camera_id: str,
        frame_index: int,
        timestamp_ms: float,
    ) -> List[TrackedVehicle]:
        """
        Executes ByteTrack two-stage data association on incoming frame detections.
        """
        # Ensure camera_id aligns with tracker's assigned camera
        assert camera_id == self.camera_id, (
            f"Cross-camera violation: Tracker initialized for '{self.camera_id}' "
            f"received detections from '{camera_id}'."
        )

        # 1. Partition detections into high-confidence and low-confidence
        det_high: List[DetectionResult] = []
        det_low: List[DetectionResult] = []

        for d in detections:
            if d.confidence >= self.track_high_thresh:
                det_high.append(d)
            elif d.confidence >= self.track_low_thresh:
                det_low.append(d)

        # 2. Predict next positions for all active tracks via Kalman filter
        all_active_tracks = self._tracked_tracks + self._lost_tracks
        for trk in all_active_tracks:
            trk.predict()

        # -------------------------------------------------------------
        # 3. First Association: High-confidence detections with active tracks
        # -------------------------------------------------------------
        activated_tracks: List[STrack] = []
        refind_tracks: List[STrack] = []

        if len(all_active_tracks) > 0 and len(det_high) > 0:
            track_boxes = np.array(
                [[b.x1, b.y1, b.x2, b.y2] for b in [t.kalman.get_state() for t in all_active_tracks]],
                dtype=np.float32,
            )
            det_high_boxes = np.array(
                [[d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2] for d in det_high],
                dtype=np.float32,
            )
            cost_matrix = 1.0 - box_iou_batch(track_boxes, det_high_boxes)
            matches_1, unmatched_tracks_1_idx, unmatched_det_high_idx = self._linear_assignment(
                cost_matrix, threshold=self.match_thresh
            )

            for t_idx, d_idx in matches_1:
                trk = all_active_tracks[t_idx]
                trk.update(det_high[d_idx], frame_index, timestamp_ms)
                if trk in self._lost_tracks:
                    refind_tracks.append(trk)
                else:
                    activated_tracks.append(trk)

            unmatched_tracks_1 = [all_active_tracks[i] for i in unmatched_tracks_1_idx]
            unmatched_det_high = [det_high[i] for i in unmatched_det_high_idx]
        else:
            unmatched_tracks_1 = all_active_tracks
            unmatched_det_high = det_high

        # -------------------------------------------------------------
        # 4. Second Association: Low-confidence detections with remaining tracks
        # -------------------------------------------------------------
        # Only associate remaining tracks that were previously TRACKED (not recently lost)
        unmatched_tracked_1 = [t for t in unmatched_tracks_1 if t.state == TrackState.TRACKED]

        if len(unmatched_tracked_1) > 0 and len(det_low) > 0:
            track_boxes_2 = np.array(
                [[b.x1, b.y1, b.x2, b.y2] for b in [t.kalman.get_state() for t in unmatched_tracked_1]],
                dtype=np.float32,
            )
            det_low_boxes = np.array(
                [[d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2] for d in det_low],
                dtype=np.float32,
            )
            cost_matrix_2 = 1.0 - box_iou_batch(track_boxes_2, det_low_boxes)
            matches_2, unmatched_tracks_2_idx, _ = self._linear_assignment(
                cost_matrix_2, threshold=self.match_thresh
            )

            for t_idx, d_idx in matches_2:
                trk = unmatched_tracked_1[t_idx]
                trk.update(det_low[d_idx], frame_index, timestamp_ms)
                activated_tracks.append(trk)

            still_unmatched_tracks = [unmatched_tracked_1[i] for i in unmatched_tracks_2_idx]
        else:
            still_unmatched_tracks = unmatched_tracked_1

        # Tracks that were already LOST and not matched in stage 1 stay unmatched
        already_lost_unmatched = [t for t in unmatched_tracks_1 if t.state == TrackState.LOST]
        unmatched_tracks = still_unmatched_tracks + already_lost_unmatched

        # -------------------------------------------------------------
        # 5. Track Disappearance & Termination
        # -------------------------------------------------------------
        current_lost: List[STrack] = []
        for trk in unmatched_tracks:
            # Mark disappearance
            trk.mark_lost()
            if trk.lost_frames > self.max_lost_frames:
                # Mark termination
                trk.mark_removed()
                self._removed_tracks.append(trk)
                self.total_terminated += 1
            else:
                current_lost.append(trk)

        # -------------------------------------------------------------
        # 6. Track Creation from Unmatched High-Confidence Detections
        # -------------------------------------------------------------
        new_tracks: List[STrack] = []
        for det in unmatched_det_high:
            tid = self._get_next_id()
            trk = STrack(
                local_track_id=tid,
                camera_id=self.camera_id,
                class_name=det.class_name,
                detection=det,
                frame_number=frame_index,
                timestamp=timestamp_ms,
            )
            # Immediate confirmation for high-confidence detections
            trk.state = TrackState.TRACKED
            new_tracks.append(trk)
            self.total_created += 1

        # -------------------------------------------------------------
        # 7. Update Track Pools
        # -------------------------------------------------------------
        self._tracked_tracks = [t for t in (activated_tracks + refind_tracks + new_tracks) if t.state == TrackState.TRACKED]
        self._lost_tracks = current_lost

        # Filter active tracks to return
        output_vehicles: List[TrackedVehicle] = []
        for trk in self._tracked_tracks:
            if trk.hits >= self.min_hits or trk.confidence >= self.track_high_thresh:
                output_vehicles.append(trk.to_tracked_vehicle())

        return output_vehicles
