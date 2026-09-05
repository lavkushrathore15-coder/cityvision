"""
Comprehensive Tests for the Video Ingestion Subsystem
"""
import os
from pathlib import Path
import cv2
import numpy as np
import pytest

from backend.app.services.video_ingestion import (
    BaseCameraSource,
    CameraLocation,
    FileCameraSource,
    FramePacket,
    RTSPCameraSource,
    StreamState,
    StreamStatus,
    VideoIngestionEngine,
)


@pytest.fixture(scope="session")
def sample_video_path(tmp_path_factory) -> Path:
    """
    Creates a deterministic 30-frame test MP4 video using OpenCV.
    Ensures tests are completely self-contained and reproducible offline.
    """
    temp_dir = tmp_path_factory.mktemp("test_videos")
    video_file = temp_dir / "test_traffic_feed.mp4"

    fps = 15
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_file), fourcc, fps, (width, height))

    for i in range(30):
        # Create distinct test frame with frame number stamped
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)  # dark gray
        cv2.putText(
            frame,
            f"FRAME-{i:03d}",
            (40, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
        )
        out.write(frame)

    out.release()
    return video_file


# ---------------------------------------------------------------------------
# 1. Camera Location & Non-Fabrication Tests
# ---------------------------------------------------------------------------

def test_camera_location_with_valid_coordinates():
    loc = CameraLocation.from_config(latitude=28.6139, longitude=77.2090, description="Connaught Place")
    assert loc.is_gps_available is True
    assert loc.latitude == 28.6139
    assert loc.longitude == 77.2090
    assert loc.source == "config"
    assert loc.description == "Connaught Place"


def test_camera_location_without_coordinates_marks_unavailable():
    """Rule verification: If GPS is missing, do NOT invent coordinates."""
    loc = CameraLocation.from_config(latitude=None, longitude=None, description="Indoor Basement Cam")
    assert loc.is_gps_available is False
    assert loc.latitude is None
    assert loc.longitude is None
    assert loc.source == "unconfigured"


# ---------------------------------------------------------------------------
# 2. FileCameraSource Lifecycle & Metadata Tests
# ---------------------------------------------------------------------------

def test_file_camera_source_nonexistent_file():
    source = FileCameraSource(
        camera_id="CAM-ERR",
        camera_name="Ghost Camera",
        video_path="nonexistent_video_path.mp4",
    )
    opened = source.open()
    assert opened is False
    status = source.get_status()
    assert status.is_connected is False
    assert status.processing_status == StreamState.ERROR
    assert "does not exist" in status.error_message


def test_file_camera_source_open_and_metadata(sample_video_path):
    location = CameraLocation.from_config(28.6180, 77.2150, "Junction 4")
    source = FileCameraSource(
        camera_id="CAM-001",
        camera_name="North Approach",
        video_path=str(sample_video_path),
        location=location,
        sample_stride=1,
    )

    opened = source.open()
    assert opened is True

    status = source.get_status()
    assert status.is_connected is True
    assert status.processing_status == StreamState.STREAMING
    assert status.camera_id == "CAM-001"
    assert status.camera_name == "North Approach"
    assert status.source_type == "file"
    assert status.resolution == (320, 240)
    assert status.fps == 15.0
    assert status.total_frames == 30
    assert status.frames_read == 0
    assert status.frames_sampled == 0
    assert status.location.latitude == 28.6180

    source.close()
    assert source.get_status().processing_status == StreamState.CLOSED
    assert source.get_status().is_connected is False


# ---------------------------------------------------------------------------
# 3. Frame Reading & Telemetry Tests
# ---------------------------------------------------------------------------

def test_file_camera_read_frames(sample_video_path):
    source = FileCameraSource(
        camera_id="CAM-001",
        camera_name="North Approach",
        video_path=str(sample_video_path),
        sample_stride=1,
    )
    assert source.open() is True

    packet = source.read_frame()
    assert packet is not None
    assert isinstance(packet, FramePacket)
    assert packet.camera_id == "CAM-001"
    assert packet.frame_index == 1
    assert packet.source_frame_index == 1
    assert isinstance(packet.frame, np.ndarray)
    assert packet.frame.shape == (240, 320, 3)

    source.close()


# ---------------------------------------------------------------------------
# 4. Configurable Frame Sampling Tests
# ---------------------------------------------------------------------------

def test_configurable_frame_sampling_stride(sample_video_path):
    """
    Verifies that sample_stride=3 skips 2 frames and emits every 3rd frame.
    For a 30-frame clip, exactly 10 frames should be sampled.
    """
    source = FileCameraSource(
        camera_id="CAM-SAMPLER",
        camera_name="Sampling Test Cam",
        video_path=str(sample_video_path),
        sample_stride=3,
        loop=False,
    )
    assert source.open() is True

    sampled_packets = []
    while True:
        pkt = source.read_frame()
        if pkt is None:
            break
        sampled_packets.append(pkt)

    assert len(sampled_packets) == 10

    # Verify frame numbering and stride advancement
    assert sampled_packets[0].frame_index == 1
    assert sampled_packets[0].source_frame_index == 3

    assert sampled_packets[1].frame_index == 2
    assert sampled_packets[1].source_frame_index == 6

    assert sampled_packets[-1].frame_index == 10
    assert sampled_packets[-1].source_frame_index == 30

    status = source.get_status()
    assert status.frames_read == 30
    assert status.frames_sampled == 10
    assert status.processing_status == StreamState.COMPLETED

    source.close()


# ---------------------------------------------------------------------------
# 5. RTSP / Live Stream Abstraction Interface Test
# ---------------------------------------------------------------------------

def test_rtsp_camera_source_abstraction():
    rtsp_source = RTSPCameraSource(
        camera_id="CAM-RTSP-99",
        camera_name="Live Arterial RTSP",
        source_uri="rtsp://192.168.1.100:554/live",
    )
    assert rtsp_source.source_type == "rtsp"
    opened = rtsp_source.open()
    assert opened is False  # Stub correctly reports error / not yet connected

    status = rtsp_source.get_status()
    assert status.source_type == "rtsp"
    assert status.is_connected is False
    assert status.total_frames == -1  # Live stream marker


# ---------------------------------------------------------------------------
# 6. VideoIngestionEngine Multi-Camera Management Tests
# ---------------------------------------------------------------------------

def test_video_ingestion_engine_multi_camera(sample_video_path):
    engine = VideoIngestionEngine()

    # Register 2 virtual cameras
    cam1 = engine.register_camera(
        camera_id="CAM-001",
        camera_name="Gate 1",
        video_path=str(sample_video_path),
        location=CameraLocation.from_config(28.6139, 77.2090),
        sample_stride=2,
    )
    cam2 = engine.register_camera(
        camera_id="CAM-002",
        camera_name="Gate 2",
        video_path=str(sample_video_path),
        location=CameraLocation.from_config(28.6180, 77.2150),
        sample_stride=5,
    )

    assert engine.open_camera("CAM-001") is True
    assert engine.open_camera("CAM-002") is True

    # Test status reporting across cameras
    all_statuses = engine.get_all_statuses()
    assert len(all_statuses) == 2
    assert all_statuses["CAM-001"].is_connected is True
    assert all_statuses["CAM-002"].is_connected is True
    assert all_statuses["CAM-001"].resolution == (320, 240)

    # Stream frames generator test
    frames_cam2 = list(engine.stream_frames("CAM-002"))
    # 30 frames with sample_stride=5 -> 6 sampled frames
    assert len(frames_cam2) == 6
    assert frames_cam2[0].camera_id == "CAM-002"

    engine.close_all()
    assert engine.get_camera_status("CAM-001").is_connected is False
    assert engine.get_camera_status("CAM-002").is_connected is False
