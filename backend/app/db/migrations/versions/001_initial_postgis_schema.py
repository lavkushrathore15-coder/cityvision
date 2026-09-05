"""Initial PostgreSQL and PostGIS Schema for CITYVISION AI

Revision ID: 001_postgis_init
Revises: 
Create Date: 2026-09-04 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = "001_postgis_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Table: cameras
    op.create_table(
        "cameras",
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("camera_name", sa.String(length=128), nullable=False),
        sa.Column("location_name", sa.String(length=256), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("heading_deg", sa.Float(), server_default=sa.text("0.0"), nullable=True),
        sa.Column("fps", sa.Integer(), server_default=sa.text("15"), nullable=True),
        sa.Column("source_type", sa.String(length=32), server_default=sa.text("'file'"), nullable=True),
        sa.Column("stream_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'configured'"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("camera_id"),
    )
    op.create_index("idx_cameras_status", "cameras", ["status"])

    # 3. Table: vehicles
    op.create_table(
        "vehicles",
        sa.Column("global_vehicle_id", sa.String(length=64), nullable=False),
        sa.Column("primary_plate", sa.String(length=32), nullable=True),
        sa.Column("vehicle_class", sa.String(length=32), server_default=sa.text("'car'"), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_observations", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("total_cameras_visited", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_flagged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("flag_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("global_vehicle_id"),
    )
    op.create_index("idx_vehicles_primary_plate", "vehicles", ["primary_plate"])
    op.create_index("idx_vehicles_class", "vehicles", ["vehicle_class"])
    op.create_index("idx_vehicles_is_flagged", "vehicles", ["is_flagged"])
    op.create_index("idx_vehicles_last_seen", "vehicles", [sa.text("last_seen DESC")])

    # 4. Table: tracks
    op.create_table(
        "tracks",
        sa.Column("track_id", sa.String(length=96), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("local_track_id", sa.Integer(), nullable=False),
        sa.Column("global_vehicle_id", sa.String(length=64), nullable=True),
        sa.Column("vehicle_class", sa.String(length=32), server_default=sa.text("'car'"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detection_confidence", sa.Float(), nullable=False),
        sa.Column("total_frames", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["global_vehicle_id"], ["vehicles.global_vehicle_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("track_id"),
    )
    op.create_index("idx_tracks_camera_local", "tracks", ["camera_id", "local_track_id"])
    op.create_index("idx_tracks_global_vehicle", "tracks", ["global_vehicle_id"])
    op.create_index("idx_tracks_time", "tracks", ["start_time", "end_time"])

    # 5. Table: observations
    op.create_table(
        "observations",
        sa.Column("observation_id", sa.String(length=96), nullable=False),
        sa.Column("global_vehicle_id", sa.String(length=64), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("local_track_id", sa.Integer(), nullable=False),
        sa.Column("frame_number", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("bbox_x1", sa.Float(), nullable=False),
        sa.Column("bbox_y1", sa.Float(), nullable=False),
        sa.Column("bbox_x2", sa.Float(), nullable=False),
        sa.Column("bbox_y2", sa.Float(), nullable=False),
        sa.Column("detection_confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("source_frame_uri", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["global_vehicle_id"], ["vehicles.global_vehicle_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("observation_id"),
    )
    op.create_index("idx_observations_camera_time", "observations", ["camera_id", sa.text("timestamp DESC")])
    op.create_index("idx_observations_global_time", "observations", ["global_vehicle_id", sa.text("timestamp ASC")])
    op.create_index("idx_observations_timestamp", "observations", ["timestamp"])

    # 6. Table: ocr_observations
    op.create_table(
        "ocr_observations",
        sa.Column("ocr_id", sa.String(length=96), nullable=False),
        sa.Column("observation_id", sa.String(length=96), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("local_track_id", sa.Integer(), nullable=False),
        sa.Column("frame_number", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_text", sa.String(length=64), nullable=False),
        sa.Column("normalized_text", sa.String(length=64), nullable=False),
        sa.Column("ocr_confidence", sa.Float(), nullable=False),
        sa.Column("plate_bbox_x1", sa.Float(), nullable=True),
        sa.Column("plate_bbox_y1", sa.Float(), nullable=True),
        sa.Column("plate_bbox_x2", sa.Float(), nullable=True),
        sa.Column("plate_bbox_y2", sa.Float(), nullable=True),
        sa.Column("is_blurry", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.observation_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ocr_id"),
    )
    op.create_index("idx_ocr_normalized_plate", "ocr_observations", ["normalized_text"])
    op.create_index("idx_ocr_observation_id", "ocr_observations", ["observation_id"])
    op.create_index("idx_ocr_camera_id", "ocr_observations", ["camera_id"])
    op.create_index("idx_ocr_timestamp", "ocr_observations", ["timestamp"])

    # 7. Table: reid_embeddings
    op.create_table(
        "reid_embeddings",
        sa.Column("embedding_id", sa.String(length=96), nullable=False),
        sa.Column("observation_id", sa.String(length=96), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("local_track_id", sa.Integer(), nullable=False),
        sa.Column("frame_number", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_identifier", sa.String(length=64), nullable=False),
        sa.Column("dimension", sa.Integer(), server_default=sa.text("256"), nullable=False),
        sa.Column("distance_metric", sa.String(length=32), server_default=sa.text("'cosine'"), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column("embedding_preview", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.observation_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("embedding_id"),
    )
    op.create_index("idx_reid_obs_id", "reid_embeddings", ["observation_id"])
    op.create_index("idx_reid_camera_track", "reid_embeddings", ["camera_id", "local_track_id"])
    op.create_index("idx_reid_timestamp", "reid_embeddings", ["timestamp"])

    # 8. Table: vehicle_matches
    op.create_table(
        "vehicle_matches",
        sa.Column("match_id", sa.String(length=96), nullable=False),
        sa.Column("global_vehicle_id", sa.String(length=64), nullable=False),
        sa.Column("source_observation_id", sa.String(length=96), nullable=False),
        sa.Column("target_observation_id", sa.String(length=96), nullable=False),
        sa.Column("source_camera_id", sa.String(length=64), nullable=False),
        sa.Column("target_camera_id", sa.String(length=64), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("confidence_tier", sa.String(length=32), nullable=False),
        sa.Column("plate_score", sa.Float(), nullable=True),
        sa.Column("reid_score", sa.Float(), nullable=True),
        sa.Column("spatial_score", sa.Float(), nullable=True),
        sa.Column("temporal_score", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["global_vehicle_id"], ["vehicles.global_vehicle_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_observation_id"], ["observations.observation_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_observation_id"], ["observations.observation_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id"),
    )
    op.create_index("idx_matches_global_vehicle", "vehicle_matches", ["global_vehicle_id"])
    op.create_index("idx_matches_confidence_tier", "vehicle_matches", ["confidence_tier"])
    op.create_index("idx_matches_pair", "vehicle_matches", ["source_camera_id", "target_camera_id", "matched_at"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_matches_evidence ON vehicle_matches USING GIN (evidence_breakdown);")

    # 9. Table: trajectories
    op.create_table(
        "trajectories",
        sa.Column("trajectory_id", sa.String(length=96), nullable=False),
        sa.Column("global_vehicle_id", sa.String(length=64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_distance_km", sa.Float(), nullable=True),
        sa.Column("avg_speed_kmh", sa.Float(), nullable=True),
        sa.Column("visited_cameras_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "geom_path",
            geoalchemy2.types.Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("waypoints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_spatial_available", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["global_vehicle_id"], ["vehicles.global_vehicle_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trajectory_id"),
    )
    op.create_index("idx_trajectories_global_vehicle", "trajectories", ["global_vehicle_id"])
    op.create_index("idx_trajectories_time_range", "trajectories", ["start_time", "end_time"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_trajectories_waypoints ON trajectories USING GIN (waypoints);")

    # 10. Table: alerts
    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.String(length=96), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("global_vehicle_id", sa.String(length=64), nullable=True),
        sa.Column("plate_text", sa.String(length=32), nullable=True),
        sa.Column("camera_id", sa.String(length=64), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'NEW'"), nullable=False),
        sa.Column("acknowledged_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["global_vehicle_id"], ["vehicles.global_vehicle_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("alert_id"),
    )
    op.create_index("idx_alerts_status_severity", "alerts", ["status", "severity", sa.text("timestamp DESC")])
    op.create_index("idx_alerts_type", "alerts", ["alert_type"])
    op.create_index("idx_alerts_plate", "alerts", ["plate_text"])
    op.create_index("idx_alerts_timestamp", "alerts", [sa.text("timestamp DESC")])
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_details ON alerts USING GIN (details);")


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("trajectories")
    op.drop_table("vehicle_matches")
    op.drop_table("reid_embeddings")
    op.drop_table("ocr_observations")
    op.drop_table("observations")
    op.drop_table("tracks")
    op.drop_table("vehicles")
    op.drop_table("cameras")
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")
