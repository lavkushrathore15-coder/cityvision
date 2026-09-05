"""
Unit tests for configuration and paths
"""
from pathlib import Path
from backend.app.core.config import settings


def test_settings_loaded():
    assert settings.PROJECT_NAME == "CITYVISION AI"
    assert settings.INFERENCE_DEVICE in ("cpu", "cuda")
    assert settings.PORT == 8000


def test_camera_configuration_file_exists():
    path = Path("config/cameras.yaml")
    assert path.is_file(), "config/cameras.yaml must exist"


def test_watchlist_file_exists():
    path = Path("data/watchlist/stolen_vehicles.json")
    assert path.is_file(), "data/watchlist/stolen_vehicles.json must exist"
