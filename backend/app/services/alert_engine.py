"""
CITYVISION AI - Urban Surveillance & Traffic Alert Engine
Problem Statement ID: SIH26127

Evaluates real-time observations and trajectory metrics against municipal security rules:
1. BLACKLIST: Law enforcement watchlist evaluation with strict false-positive prevention on low-confidence OCR.
2. ANOMALY: Spatio-temporal trajectory movement analysis (excessive velocity, impossible transit times).
3. CONGESTION: Zone vehicle density and corridor travel delay evaluation.
"""
import json
import logging
import time
import uuid
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from backend.app.schemas.trajectory import AlertSchema, CameraMovementSchema

logger = logging.getLogger("cityvision.alert_engine")


@dataclass
class AlertEngineConfig:
    """Configurable thresholds and operational parameters for the Alert Engine."""
    min_plate_confidence: float = 0.80
    max_feasible_speed_kmh: float = 120.0
    min_transit_time_sec: float = 3.0
    congestion_density_threshold: int = 15
    congestion_speed_threshold_kmh: float = 25.0
    congestion_delay_ratio_threshold: float = 1.75
    demo_mode: bool = False
    watchlist_path: Optional[str] = None


class AlertEngine:
    """
    Production-grade Alert Evaluation Engine.
    Strictly prevents false positives and never manufactures alerts unless in DEMO MODE.
    """

    def __init__(self, config: Optional[AlertEngineConfig] = None):
        self.config = config or AlertEngineConfig()
        self._watchlist: List[Dict[str, Any]] = []
        self._active_alerts: Dict[str, AlertSchema] = {}
        self._load_watchlist()

        if self.config.demo_mode:
            self._seed_demo_alerts()

    def _load_watchlist(self) -> None:
        """Loads configured plate blacklist records."""
        path = self.config.watchlist_path
        if not path:
            candidate = Path("data/watchlist/stolen_vehicles.json")
            if candidate.is_file():
                path = str(candidate)

        if path and Path(path).is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._watchlist = json.load(f)
                logger.info(f"Loaded {len(self._watchlist)} blacklist records from {path}")
            except Exception as e:
                logger.error(f"Failed to load watchlist from {path}: {e}")
                self._watchlist = []
        else:
            self._watchlist = []

    def _seed_demo_alerts(self) -> None:
        """Seeds demo alert incidents across multiple categories, severities, and statuses."""
        now = time.time()

        alerts_data = [
            {
                "id": "ALT-SEC-001",
                "alert_id": "ALT-SEC-001",
                "type": "BLACKLIST",
                "alert_type": "WATCHLIST_HIT",
                "severity": "CRITICAL",
                "camera_id": "CAM-001",
                "global_vehicle_id": "GV-NCR-1001",
                "plate_text": "DL01AB1234",
                "message": "Wanted Stolen Honda City detected on CAM-001 (FIR #84920 Crime Branch Alert)",
                "timestamp": now - 240,
                "status": "NEW",
                "evidence": {
                    "plate_number": "DL01AB1234",
                    "ocr_confidence": 0.96,
                    "confidence_threshold": self.config.min_plate_confidence,
                    "rule": "RELIABLE_PLATE_MATCH",
                    "reason": "Wanted - Stolen Honda City (FIR #84920 Crime Branch)",
                },
            },
            {
                "id": "ALT-SEC-002",
                "alert_id": "ALT-SEC-002",
                "type": "BLACKLIST",
                "alert_type": "WATCHLIST_HIT",
                "severity": "CRITICAL",
                "camera_id": "CAM-004",
                "global_vehicle_id": "GV-NCR-1004",
                "plate_text": "HR26DK9988",
                "message": "Hit and run investigation suspect vehicle identified on CAM-004",
                "timestamp": now - 720,
                "status": "NEW",
                "evidence": {
                    "plate_number": "HR26DK9988",
                    "ocr_confidence": 0.94,
                    "confidence_threshold": self.config.min_plate_confidence,
                    "rule": "RELIABLE_PLATE_MATCH",
                    "reason": "Hit and run investigation suspect - NCR Traffic Notice",
                },
            },
            {
                "id": "ALT-TRAF-003",
                "alert_id": "ALT-TRAF-003",
                "type": "ANOMALY",
                "alert_type": "SPEED_VIOLATION",
                "severity": "HIGH",
                "camera_id": "CAM-002",
                "global_vehicle_id": "GV-NCR-1002",
                "plate_text": "HR26DQ8890",
                "message": "Excessive Speed Violation: Black Mahindra Scorpio at 94.5 km/h in 50 km/h zone on CAM-002",
                "timestamp": now - 1420,
                "status": "NEW",
                "evidence": {
                    "measured_speed_kmh": 94.5,
                    "speed_limit_kmh": 50.0,
                    "excess_speed_kmh": 44.5,
                    "rule": "CORRIDOR_SPEED_RADAR",
                },
            },
            {
                "id": "ALT-SEC-004",
                "alert_id": "ALT-SEC-004",
                "type": "BLACKLIST",
                "alert_type": "WATCHLIST_HIT",
                "severity": "HIGH",
                "camera_id": "CAM-003",
                "global_vehicle_id": "GV-NCR-1005",
                "plate_text": "UP16XY5544",
                "message": "Unpaid commercial toll evasion / Impound notice intercept on CAM-003",
                "timestamp": now - 2700,
                "status": "ACKNOWLEDGED",
                "acknowledged_by": "Insp. R. Sharma (HQ Command Desk)",
                "evidence": {
                    "plate_number": "UP16XY5544",
                    "ocr_confidence": 0.91,
                    "outstanding_notices": 4,
                    "rule": "COMMERCIAL_TOLL_ENFORCEMENT",
                },
            },
            {
                "id": "ALT-ANOM-005",
                "alert_id": "ALT-ANOM-005",
                "type": "ANOMALY",
                "alert_type": "TRANSIT_ANOMALY",
                "severity": "HIGH",
                "camera_id": "CAM-005",
                "global_vehicle_id": "GV-NCR-1007",
                "plate_text": "DL04EA9011",
                "message": "ROUTE ANOMALY: Impossible transit time (4.2s across 1400m) between CAM-002 and CAM-005",
                "timestamp": now - 4100,
                "status": "NEW",
                "evidence": {
                    "from_camera": "CAM-002",
                    "to_camera": "CAM-005",
                    "elapsed_time_sec": 4.2,
                    "distance_meters": 1400.0,
                    "rule": "PHYSICAL_CONTINUITY_VIOLATION",
                },
            },
            {
                "id": "ALT-CONG-006",
                "alert_id": "ALT-CONG-006",
                "type": "CONGESTION",
                "alert_type": "CONGESTION_DENSITY",
                "severity": "MEDIUM",
                "camera_id": "CAM-002",
                "global_vehicle_id": None,
                "plate_text": None,
                "message": "TRAFFIC CONGESTION: Central Ring Road Eastbound active density (19 vehicles) exceeds threshold (15)",
                "timestamp": now - 5600,
                "status": "NEW",
                "evidence": {
                    "zone_name": "Central Ring Road Sector 4",
                    "camera_id": "CAM-002",
                    "active_density": 19,
                    "density_threshold": 15,
                    "rule": "ZONE_CAPACITY_EXCEEDED",
                },
            },
            {
                "id": "ALT-CONG-007",
                "alert_id": "ALT-CONG-007",
                "type": "CONGESTION",
                "alert_type": "CORRIDOR_CONGESTION",
                "severity": "MEDIUM",
                "camera_id": "CAM-001",
                "global_vehicle_id": None,
                "plate_text": None,
                "message": "CORRIDOR BOTTLENECK: North Gateway Corridor delay ratio (2.10x) exceeds normal baseline",
                "timestamp": now - 7800,
                "status": "RESOLVED",
                "acknowledged_by": "Auto-cleared (Corridor Flow Normalized)",
                "evidence": {
                    "corridor_name": "North Gateway Corridor",
                    "delay_ratio": 2.10,
                    "average_transit_speed_kmh": 14.2,
                    "delay_threshold": 1.75,
                    "rule": "CORRIDOR_BOTTLENECK_DETECTED",
                },
            },
            {
                "id": "ALT-DEMO-101",
                "alert_id": "ALT-DEMO-101",
                "type": "BLACKLIST",
                "alert_type": "WATCHLIST_HIT",
                "severity": "CRITICAL",
                "camera_id": "CAM-005",
                "global_vehicle_id": "GLOBAL-DEMO-9901",
                "plate_text": "RJ14AB1234",
                "message": "Stolen vehicle watchlist hit on CAM-005",
                "timestamp": now - 9600,
                "status": "NEW",
                "evidence": {
                    "plate_number": "RJ14AB1234",
                    "ocr_confidence": 0.94,
                    "confidence_threshold": self.config.min_plate_confidence,
                    "rule": "RELIABLE_PLATE_MATCH",
                    "reason": "Demonstration seed incident",
                },
            },
        ]

        for item in alerts_data:
            ts = item["timestamp"]
            ts_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            alert = AlertSchema(
                id=item["id"],
                alert_id=item["alert_id"],
                type=item["type"],
                alert_type=item["alert_type"],
                severity=item["severity"],
                camera_id=item["camera_id"],
                global_vehicle_id=item.get("global_vehicle_id"),
                plate_text=item.get("plate_text"),
                message=item["message"],
                timestamp=ts,
                timestamp_iso=ts_iso,
                evidence=item["evidence"],
                details=item["evidence"],
                status=item["status"],
                acknowledged_by=item.get("acknowledged_by"),
            )
            self._active_alerts[alert.id] = alert

    # =========================================================================
    # 1. BLACKLIST EVALUATION
    # =========================================================================

    def evaluate_plate_blacklist(
        self,
        plate_text: Optional[str],
        ocr_confidence: Optional[float],
        camera_id: str,
        global_vehicle_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Optional[AlertSchema]:
        """
        Compares recognized plate against configured blacklist.
        Strict Rule: DOES NOT trigger a blacklist alert if OCR confidence is low
        or if plate text is missing.
        """
        # Guard 1: Missing plate text
        if not plate_text or not plate_text.strip():
            logger.debug("Blacklist check skipped: missing or empty plate text.")
            return None

        # Guard 2: Low-confidence OCR threshold enforcement
        if ocr_confidence is None:
            logger.debug(f"Blacklist check suppressed for '{plate_text}': OCR confidence is None.")
            return None

        if ocr_confidence < self.config.min_plate_confidence:
            logger.debug(
                f"Blacklist check suppressed for '{plate_text}': OCR confidence {ocr_confidence:.2f} "
                f"below required threshold {self.config.min_plate_confidence:.2f}."
            )
            return None

        # Normalize plate text for matching (uppercase, alphanumeric only)
        clean_input = "".join(c for c in plate_text.upper() if c.isalnum())
        matched_entry = None

        for item in self._watchlist:
            clean_item = "".join(c for c in item.get("plate_number", "").upper() if c.isalnum())
            if clean_item and clean_item == clean_input:
                matched_entry = item
                break

        if not matched_entry:
            return None

        # Create BLACKLIST Alert
        now = timestamp or time.time()
        now_iso = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        alert_id = f"ALT-BLK-{uuid.uuid4().hex[:8].upper()}"
        severity = matched_entry.get("alert_level", "CRITICAL").upper()

        evidence = {
            "plate_number": plate_text,
            "matched_plate": matched_entry.get("plate_number"),
            "ocr_confidence": round(ocr_confidence, 4),
            "confidence_threshold": self.config.min_plate_confidence,
            "rule": "RELIABLE_PLATE_MATCH",
            "reason": matched_entry.get("reason", "Watchlist match"),
            "vehicle_type": matched_entry.get("vehicle_type"),
            "reported_date": matched_entry.get("reported_date"),
        }

        alert = AlertSchema(
            id=alert_id,
            alert_id=alert_id,
            type="BLACKLIST",
            alert_type="BLACKLIST",
            severity=severity,
            camera_id=camera_id,
            global_vehicle_id=global_vehicle_id,
            plate_text=plate_text,
            message=f"BLACKLIST MATCH: Vehicle [{plate_text}] on {camera_id} — {matched_entry.get('reason', 'Watchlist match')}",
            timestamp=now,
            timestamp_iso=now_iso,
            evidence=evidence,
            details=evidence,
            status="NEW",
        )

        self._active_alerts[alert_id] = alert
        logger.warning(f"BLACKLIST ALERT GENERATED: {alert_id} for {plate_text} on {camera_id}")
        return alert

    # =========================================================================
    # 2. ANOMALY EVALUATION
    # =========================================================================

    def evaluate_movement_anomaly(
        self,
        movement: CameraMovementSchema,
        global_vehicle_id: str,
        plate_text: Optional[str] = None,
    ) -> Optional[AlertSchema]:
        """
        Evaluates inter-camera movement against spatio-temporal physics:
        - Excessive transit velocity exceeding speed limit threshold
        - Physically impossible transit times between distant cameras
        """
        # Guard: Missing transit metrics
        if movement.speed_kmh is None and movement.elapsed_time_sec <= 0:
            return None

        now = movement.arrival_time or time.time()
        now_iso = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Excessive Speed Anomaly
        if movement.speed_kmh is not None and movement.speed_kmh > self.config.max_feasible_speed_kmh:
            alert_id = f"ALT-ANOM-{uuid.uuid4().hex[:8].upper()}"
            evidence = {
                "anomaly_type": "EXCESSIVE_TRANSIT_SPEED",
                "speed_kmh": round(movement.speed_kmh, 1),
                "speed_threshold_kmh": self.config.max_feasible_speed_kmh,
                "from_camera": movement.from_camera_id,
                "to_camera": movement.to_camera_id,
                "distance_meters": movement.distance_meters,
                "elapsed_time_sec": round(movement.elapsed_time_sec, 1),
                "rule": "TRANSIT_SPEED_VIOLATION",
            }
            alert = AlertSchema(
                id=alert_id,
                alert_id=alert_id,
                type="ANOMALY",
                alert_type="ANOMALY",
                severity="HIGH",
                camera_id=movement.to_camera_id,
                global_vehicle_id=global_vehicle_id,
                plate_text=plate_text,
                message=(
                    f"SPEED ANOMALY: Vehicle {global_vehicle_id} clocked at {movement.speed_kmh:.1f} km/h "
                    f"between {movement.from_camera_id} and {movement.to_camera_id} "
                    f"(limit: {self.config.max_feasible_speed_kmh:.0f} km/h)"
                ),
                timestamp=now,
                timestamp_iso=now_iso,
                evidence=evidence,
                details=evidence,
                status="NEW",
            )
            self._active_alerts[alert_id] = alert
            return alert

        # 2. Impossible Travel Time (Physical Discontinuity)
        if (
            movement.from_camera_id != movement.to_camera_id
            and movement.distance_meters is not None
            and movement.distance_meters > 200.0
            and movement.elapsed_time_sec < self.config.min_transit_time_sec
        ):
            alert_id = f"ALT-ANOM-{uuid.uuid4().hex[:8].upper()}"
            evidence = {
                "anomaly_type": "IMPOSSIBLE_TRANSIT_TIME",
                "distance_meters": movement.distance_meters,
                "elapsed_time_sec": round(movement.elapsed_time_sec, 2),
                "min_expected_time_sec": self.config.min_transit_time_sec,
                "from_camera": movement.from_camera_id,
                "to_camera": movement.to_camera_id,
                "rule": "PHYSICAL_CONTINUITY_VIOLATION",
            }
            alert = AlertSchema(
                id=alert_id,
                alert_id=alert_id,
                type="ANOMALY",
                alert_type="ANOMALY",
                severity="CRITICAL",
                camera_id=movement.to_camera_id,
                global_vehicle_id=global_vehicle_id,
                plate_text=plate_text,
                message=(
                    f"ROUTE ANOMALY: Impossible transit time ({movement.elapsed_time_sec:.1f}s across {movement.distance_meters:.0f}m) "
                    f"for vehicle {global_vehicle_id} between {movement.from_camera_id} and {movement.to_camera_id}"
                ),
                timestamp=now,
                timestamp_iso=now_iso,
                evidence=evidence,
                details=evidence,
                status="NEW",
            )
            self._active_alerts[alert_id] = alert
            return alert

        return None

    # =========================================================================
    # 3. CONGESTION EVALUATION
    # =========================================================================

    def evaluate_congestion(
        self,
        camera_id: str,
        active_density: int,
        zone_name: Optional[str] = None,
        corridor_info: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> Optional[AlertSchema]:
        """
        Evaluates active traffic density or corridor transit delay:
        - Density exceeding sector capacity threshold
        - Corridor travel delay ratio exceeding congestion threshold
        """
        now = timestamp or time.time()
        now_iso = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Zone Density Threshold Trigger
        if active_density >= self.config.congestion_density_threshold:
            is_severe = active_density >= (self.config.congestion_density_threshold * 1.5)
            severity = "CRITICAL" if is_severe else "MEDIUM"
            alert_id = f"ALT-CONG-{uuid.uuid4().hex[:8].upper()}"

            evidence = {
                "zone_name": zone_name or camera_id,
                "camera_id": camera_id,
                "active_density": active_density,
                "density_threshold": self.config.congestion_density_threshold,
                "severity_level": "SEVERE" if is_severe else "MODERATE",
                "rule": "ZONE_CAPACITY_EXCEEDED",
            }

            alert = AlertSchema(
                id=alert_id,
                alert_id=alert_id,
                type="CONGESTION",
                alert_type="CONGESTION",
                severity=severity,
                camera_id=camera_id,
                global_vehicle_id=None,
                plate_text=None,
                message=(
                    f"TRAFFIC CONGESTION: {zone_name or camera_id} active density "
                    f"({active_density} vehicles) exceeds threshold ({self.config.congestion_density_threshold})"
                ),
                timestamp=now,
                timestamp_iso=now_iso,
                evidence=evidence,
                details=evidence,
                status="NEW",
            )
            self._active_alerts[alert_id] = alert
            return alert

        # 2. Corridor Transit Delay Trigger
        if corridor_info:
            delay_ratio = corridor_info.get("delay_ratio", 1.0)
            avg_speed = corridor_info.get("average_transit_speed_kmh")

            if (
                delay_ratio >= self.config.congestion_delay_ratio_threshold
                or (avg_speed is not None and avg_speed < self.config.congestion_speed_threshold_kmh)
            ):
                alert_id = f"ALT-CONG-{uuid.uuid4().hex[:8].upper()}"
                evidence = {
                    "corridor_name": corridor_info.get("corridor_name", "Transit Corridor"),
                    "from_camera": corridor_info.get("from_camera_id"),
                    "to_camera": corridor_info.get("to_camera_id"),
                    "average_transit_speed_kmh": avg_speed,
                    "delay_ratio": delay_ratio,
                    "delay_threshold": self.config.congestion_delay_ratio_threshold,
                    "rule": "CORRIDOR_BOTTLENECK_DETECTED",
                }

                alert = AlertSchema(
                    id=alert_id,
                    alert_id=alert_id,
                    type="CONGESTION",
                    alert_type="CONGESTION",
                    severity="MEDIUM",
                    camera_id=corridor_info.get("to_camera_id") or camera_id,
                    global_vehicle_id=None,
                    plate_text=None,
                    message=(
                        f"CORRIDOR BOTTLENECK: {corridor_info.get('corridor_name', 'Corridor')} delay ratio "
                        f"({delay_ratio:.2f}x) exceeds threshold ({self.config.congestion_delay_ratio_threshold:.2f}x)"
                    ),
                    timestamp=now,
                    timestamp_iso=now_iso,
                    evidence=evidence,
                    details=evidence,
                    status="NEW",
                )
                self._active_alerts[alert_id] = alert
                return alert

        return None

    # =========================================================================
    # ALERT MANAGEMENT
    # =========================================================================

    def get_alert(self, alert_id: str) -> Optional[AlertSchema]:
        """Retrieves an alert by ID."""
        if alert_id in self._active_alerts:
            return self._active_alerts[alert_id]
        for a in self._active_alerts.values():
            if a.id == alert_id or a.alert_id == alert_id:
                return a
        return None

    def update_alert_status(
        self,
        alert_id: str,
        status: str,
        acknowledged_by: Optional[str] = None,
    ) -> Optional[AlertSchema]:
        """Updates lifecycle status (NEW, ACKNOWLEDGED, RESOLVED, DISMISSED)."""
        alert = self.get_alert(alert_id)
        if not alert:
            return None

        clean_status = status.strip().upper()
        valid = {"NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"}
        if clean_status in valid:
            alert.status = clean_status
        if acknowledged_by:
            alert.acknowledged_by = acknowledged_by
        return alert

    def list_alerts(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> List[AlertSchema]:
        """Returns sorted alerts list with multi-filtering."""
        alerts = list(self._active_alerts.values())

        if status:
            alerts = [a for a in alerts if a.status.upper() == status.upper()]
        if severity:
            alerts = [a for a in alerts if a.severity.upper() == severity.upper()]
        if alert_type:
            alerts = [a for a in alerts if (a.type and a.type.upper() == alert_type.upper()) or (a.alert_type and a.alert_type.upper() == alert_type.upper())]

        # Sort by timestamp descending (newest first)
        alerts.sort(key=lambda a: a.timestamp or 0.0, reverse=True)
        return alerts[:limit]

    def clear_alerts(self) -> None:
        """Clears active in-memory alerts (useful for isolated tests)."""
        self._active_alerts.clear()
