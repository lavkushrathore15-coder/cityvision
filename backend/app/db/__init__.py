"""Database module for CITYVISION AI"""
from backend.app.db.database import db_manager, DatabaseManager
from backend.app.db.models import (
    Base,
    Camera,
    Vehicle,
    Track,
    Observation,
    OCRObservation,
    ReIDEmbedding,
    VehicleMatch,
    Trajectory,
    Alert,
)

__all__ = [
    "db_manager",
    "DatabaseManager",
    "Base",
    "Camera",
    "Vehicle",
    "Track",
    "Observation",
    "OCRObservation",
    "ReIDEmbedding",
    "VehicleMatch",
    "Trajectory",
    "Alert",
]
