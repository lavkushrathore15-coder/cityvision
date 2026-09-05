"""
Spatio-Temporal Feasibility and Camera Topology Module
Problem Statement ID: SIH26127

Evaluates physical feasibility of vehicle transitions between camera nodes
based on geospatial distances, elapsed time, and implied transit speeds.
"""
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import math
import os
import yaml


@dataclass
class CameraNode:
    """Geospatial metadata for a camera installation."""
    camera_id: str
    name: str
    latitude: float
    longitude: float
    heading_deg: float = 0.0


@dataclass
class SpatioTemporalEvaluation:
    """Result of temporal and spatial feasibility check."""
    is_feasible: bool
    time_delta_sec: float
    distance_meters: float
    implied_speed_kmh: float
    temporal_score: float  # 0.0 (impossible) to 1.0 (ideal urban transit)
    rejection_reason: Optional[str] = None


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in meters
    using the Haversine formula.
    """
    earth_radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return earth_radius_m * c


class SpatioTemporalTopology:
    """
    Manages camera network coordinates and validates travel time feasibility.
    Enforces the rule: "Do NOT assume impossible travel times are valid."
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        max_speed_kmh: float = 160.0,
        min_expected_speed_kmh: float = 10.0,
        max_temporal_window_sec: float = 7200.0,  # 2 hours
    ):
        self.max_speed_kmh = max_speed_kmh
        self.min_expected_speed_kmh = min_expected_speed_kmh
        self.max_temporal_window_sec = max_temporal_window_sec
        self.cameras: Dict[str, CameraNode] = {}

        if config_path and os.path.exists(config_path):
            self.load_from_yaml(config_path)
        else:
            default_config = os.path.join("config", "cameras.yaml")
            if os.path.exists(default_config):
                self.load_from_yaml(default_config)

    def load_from_yaml(self, path: str) -> None:
        """Load camera coordinates from cameras.yaml configuration file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        for cam in data.get("cameras", []):
            cid = cam["id"]
            self.cameras[cid] = CameraNode(
                camera_id=cid,
                name=cam.get("name", cid),
                latitude=float(cam["latitude"]),
                longitude=float(cam["longitude"]),
                heading_deg=float(cam.get("heading_deg", 0.0)),
            )

    def add_camera(self, camera_id: str, latitude: float, longitude: float, name: str = "") -> None:
        """Dynamically add or register a camera node."""
        self.cameras[camera_id] = CameraNode(
            camera_id=camera_id,
            name=name or camera_id,
            latitude=latitude,
            longitude=longitude,
        )

    def get_distance_meters(self, cam_a: str, cam_b: str) -> float:
        """Returns distance between two cameras in meters."""
        if cam_a == cam_b:
            return 0.0

        node_a = self.cameras.get(cam_a)
        node_b = self.cameras.get(cam_b)

        if not node_a or not node_b:
            # Fallback default distance between arbitrary unconfigured city nodes (e.g. 500m)
            return 500.0

        return haversine_distance_meters(
            node_a.latitude, node_a.longitude, node_b.latitude, node_b.longitude
        )

    def evaluate_transition(
        self,
        camera_a: str,
        timestamp_a: float,
        camera_b: str,
        timestamp_b: float,
    ) -> SpatioTemporalEvaluation:
        """
        Evaluates the physical feasibility of travel between (camera_a, timestamp_a)
        and (camera_b, timestamp_b).
        """
        time_delta = abs(timestamp_b - timestamp_a)
        distance = self.get_distance_meters(camera_a, camera_b)

        # Case 1: Same camera
        if camera_a == camera_b:
            # Two observations from the same camera at the exact same moment cannot be the same vehicle
            # if they have different local track IDs.
            if time_delta < 0.1:
                return SpatioTemporalEvaluation(
                    is_feasible=False,
                    time_delta_sec=time_delta,
                    distance_meters=0.0,
                    implied_speed_kmh=0.0,
                    temporal_score=0.0,
                    rejection_reason="SIMULTANEOUS_SAME_CAMERA_OBSERVATION",
                )
            return SpatioTemporalEvaluation(
                is_feasible=True,
                time_delta_sec=time_delta,
                distance_meters=0.0,
                implied_speed_kmh=0.0,
                temporal_score=1.0,
            )

        # Case 2: Different cameras but simultaneous or near-simultaneous (within 1 second)
        if time_delta < 1.0 and distance > 30.0:
            return SpatioTemporalEvaluation(
                is_feasible=False,
                time_delta_sec=time_delta,
                distance_meters=distance,
                implied_speed_kmh=float("inf"),
                temporal_score=0.0,
                rejection_reason="SIMULTANEOUS_DISTANT_OBSERVATIONS",
            )

        # Case 3: Calculate implied speed
        # speed in m/s = distance / time_delta
        # speed in km/h = (distance / 1000) / (time_delta / 3600)
        implied_speed_kmh = (distance / 1000.0) / (time_delta / 3600.0) if time_delta > 0 else float("inf")

        # Hard Veto: Exceeds physical speed threshold
        if implied_speed_kmh > self.max_speed_kmh:
            return SpatioTemporalEvaluation(
                is_feasible=False,
                time_delta_sec=time_delta,
                distance_meters=distance,
                implied_speed_kmh=implied_speed_kmh,
                temporal_score=0.0,
                rejection_reason=f"IMPOSSIBLE_SPEED ({implied_speed_kmh:.1f} km/h > {self.max_speed_kmh} km/h)",
            )

        # Case 4: Excessive time window (e.g. over 2 hours)
        if time_delta > self.max_temporal_window_sec:
            decay = max(0.1, 1.0 - (time_delta - self.max_temporal_window_sec) / 3600.0)
            return SpatioTemporalEvaluation(
                is_feasible=True,
                time_delta_sec=time_delta,
                distance_meters=distance,
                implied_speed_kmh=implied_speed_kmh,
                temporal_score=float(decay),
                rejection_reason=None,
            )

        # Case 5: Feasible urban transit speed (typically 15 to 90 km/h)
        # Optimal temporal score is 1.0 for realistic urban transit speeds
        if 15.0 <= implied_speed_kmh <= 90.0:
            temp_score = 1.0
        elif implied_speed_kmh < 15.0:
            # Slower traffic, vehicle stopped at traffic light or parked
            temp_score = 0.85
        else:
            # Rapid transit (90 - 160 km/h)
            temp_score = max(0.5, 1.0 - (implied_speed_kmh - 90.0) / 100.0)

        return SpatioTemporalEvaluation(
            is_feasible=True,
            time_delta_sec=time_delta,
            distance_meters=distance,
            implied_speed_kmh=implied_speed_kmh,
            temporal_score=temp_score,
            rejection_reason=None,
        )
