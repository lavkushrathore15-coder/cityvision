"""
Database Persistence Layer for CITYVISION AI
Problem Statement ID: SIH26127

Dual-engine persistence manager supporting:
1. PostgreSQL + PostGIS (via SQLAlchemy 2.0 & GeoAlchemy2)
2. SQLite (via sqlite3 for local development and in-memory test suites)
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from backend.app.core.config import settings
from backend.app.db.models import Base


class DatabaseManager:
    """
    Database Manager for CITYVISION AI persistence.
    Supports PostgreSQL/PostGIS with SQLAlchemy ORM and fallback SQLite connection mode.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.raw_url = db_url or settings.DATABASE_URL
        self.is_postgres = (
            self.raw_url.startswith("postgresql://")
            or self.raw_url.startswith("postgresql+psycopg://")
        )

        self._engine: Optional[Engine] = None
        self._sessionmaker: Optional[sessionmaker] = None
        self._shared_conn: Optional[sqlite3.Connection] = None
        self.db_path: str = ""

        if self.is_postgres:
            # Normalize to psycopg 3 driver for SQLAlchemy
            sync_url = self.raw_url
            if sync_url.startswith("postgresql://"):
                sync_url = sync_url.replace("postgresql://", "postgresql+psycopg://", 1)
            
            self._engine = create_engine(
                sync_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            self._sessionmaker = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self._engine,
            )
        else:
            # SQLite configuration
            if self.raw_url.startswith("sqlite:///"):
                self.db_path = self.raw_url.replace("sqlite:///", "")
            elif self.raw_url == ":memory:" or self.raw_url.startswith("sqlite:///:memory:"):
                self.db_path = ":memory:"
            else:
                self.db_path = self.raw_url

            if self.db_path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
                self._shared_conn = None
            else:
                self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._shared_conn.row_factory = sqlite3.Row
                self._shared_conn.execute("PRAGMA foreign_keys = ON")

            self._init_sqlite_schema()

    def get_engine(self) -> Optional[Engine]:
        """Returns the active SQLAlchemy engine (if PostgreSQL is enabled)."""
        return self._engine

    def get_session(self) -> Session:
        """Yields or returns a new SQLAlchemy Session (for PostgreSQL/ORM usage)."""
        if not self._sessionmaker:
            raise RuntimeError("SQLAlchemy sessionmaker is only active when configured with a database URL (e.g. PostgreSQL).")
        return self._sessionmaker()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Context manager for transactional SQLAlchemy sessions."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with row factory (legacy/fallback mode)."""
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_sqlite_schema(self) -> None:
        """Initializes legacy SQLite database tables and performance indices."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Global Vehicles Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_vehicles (
                    global_vehicle_id TEXT PRIMARY KEY,
                    primary_plate TEXT,
                    vehicle_class TEXT NOT NULL,
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    total_observations INTEGER DEFAULT 1,
                    total_cameras_visited INTEGER DEFAULT 1,
                    is_flagged INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # Vehicle Observations Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_observations (
                    observation_id TEXT PRIMARY KEY,
                    global_vehicle_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    local_track_id INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    plate_text TEXT,
                    ocr_confidence REAL,
                    reid_embedding_preview TEXT,
                    confidence REAL DEFAULT 1.0,
                    source_frame INTEGER DEFAULT 0,
                    FOREIGN KEY (global_vehicle_id) REFERENCES global_vehicles (global_vehicle_id) ON DELETE CASCADE
                )
            """)

            # Query Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_global_id ON vehicle_observations (global_vehicle_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_camera_time ON vehicle_observations (camera_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON vehicle_observations (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_plate ON vehicle_observations (plate_text)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_veh_plate ON global_vehicles (primary_plate)")

            conn.commit()


# Default global database instance
db_manager = DatabaseManager()
