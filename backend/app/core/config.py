"""
Application Configuration Settings
Loads settings from environment variables and config files.
"""
import os
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings:
    PROJECT_NAME: str = os.getenv("APP_NAME", "CITYVISION AI")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1")
    
    # Server
    HOST: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/cityvision.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql://") or self.DATABASE_URL.startswith("postgresql+psycopg://")

    @property
    def sync_database_url(self) -> str:
        """Returns SQLAlchemy-compatible connection string."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    
    # Paths
    CAMERAS_CONFIG_PATH: str = os.getenv(
        "VIDEO_SOURCES_CONFIG", str(BASE_DIR / "config" / "cameras.yaml")
    )
    WATCHLIST_PATH: str = os.getenv(
        "WATCHLIST_FILE", str(BASE_DIR / "data" / "watchlist" / "stolen_vehicles.json")
    )
    
    # Inference Hardware & Models
    INFERENCE_DEVICE: str = os.getenv("INFERENCE_DEVICE", "cpu")
    DETECTION_MODEL_PATH: str = os.getenv(
        "DETECTION_MODEL_PATH", str(BASE_DIR / "models" / "weights" / "yolov8n.pt")
    )
    REID_MODEL_PATH: str = os.getenv(
        "REID_MODEL_PATH", str(BASE_DIR / "models" / "weights" / "yolov8n.pt")
    )

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "cityvision-dev-insecure-change-in-production")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


settings = Settings()
