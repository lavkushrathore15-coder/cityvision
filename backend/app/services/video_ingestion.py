"""
CITYVISION AI - Video Ingestion Subsystem
Supports local video files representing virtual CCTV cameras with clean abstractions
for future RTSP and live camera streams.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Generator, Iterator, Optional, Tuple
import time
import cv2
import numpy as np


class StreamState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class CameraLocation:
    """
    Explicit representation of camera spatial coordinates.
    If GPS coordinates are not explicitly configured or known, they are marked
    as unavailable rather than fabricated.
    """
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    is_gps_available: bool = False
    source: str = "unconfigured"  # "config", "gps_sensor", "unconfigured"

    @classmethod
    def from_config(
        cls,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        description: Optional[str] = None,
    ) -> "CameraLocation":
        has_coords = (latitude is not None) and (longitude is not None)
        return cls(
            latitude=latitude if has_coords else None,
            longitude=longitude if has_coords else None,
            description=description,
            is_gps_available=has_coords,
            source="config" if has_coords else "unconfigured",
        )


@dataclass
class FramePacket:
    """
    Standard container for an ingested video frame and its telemetry.
    """
    camera_id: str
    frame_index: int           # Sequential index of sampled frame emitted
    source_frame_index: int    # Original frame index from video stream
    timestamp_ms: float        # Video playback timestamp in milliseconds
    frame: np.ndarray          # OpenCV BGR image matrix
    capture_time_epoch: float = field(default_factory=time.time)


@dataclass
class StreamStatus:
    """
    Current status and technical telemetry of a camera video stream.
    """
    camera_id: str
    camera_name: str
    source_uri: str
    source_type: str
    is_connected: bool
    processing_status: StreamState
    total_frames: int          # Total frames in file (-1 for live streams)
    frames_read: int           # Total physical frames read by decoder
    frames_sampled: int        # Frames passed after sampling policy
    fps: float                 # Stream native FPS (0.0 if unknown)
    resolution: Tuple[int, int]  # (width, height) in pixels
    location: CameraLocation
    error_message: Optional[str] = None


class BaseCameraSource(ABC):
    """
    Abstract interface for video ingestion sources (Local File, RTSP, HTTP-FLV, etc.).
    Enables future plug-and-play addition of live CCTV camera streams.
    """

    def __init__(
        self,
        camera_id: str,
        camera_name: str,
        source_uri: str,
        location: Optional[CameraLocation] = None,
        sample_stride: int = 1,
    ):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.source_uri = source_uri
        self.location = location or CameraLocation.from_config()
        self.sample_stride = max(1, sample_stride)

        self._state: StreamState = StreamState.IDLE
        self._error_message: Optional[str] = None
        self._frames_read: int = 0
        self._frames_sampled: int = 0

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Returns the type identifier (e.g. 'file', 'rtsp', 'stream')."""
        pass

    @abstractmethod
    def open(self) -> bool:
        """Establishes connection or opens the video source."""
        pass

    @abstractmethod
    def read_frame(self) -> Optional[FramePacket]:
        """Fetches the next sampled frame from the source."""
        pass

    @abstractmethod
    def get_status(self) -> StreamStatus:
        """Returns real-time status and telemetry of the camera source."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Closes the connection and releases resources."""
        pass


class FileCameraSource(BaseCameraSource):
    """
    Camera source implementation for local recorded video files.
    """

    def __init__(
        self,
        camera_id: str,
        camera_name: str,
        video_path: str,
        location: Optional[CameraLocation] = None,
        sample_stride: int = 1,
        loop: bool = False,
    ):
        super().__init__(
            camera_id=camera_id,
            camera_name=camera_name,
            source_uri=video_path,
            location=location,
            sample_stride=sample_stride,
        )
        self.video_path = Path(video_path)
        self.loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps: float = 0.0
        self._total_frames: int = 0
        self._width: int = 0
        self._height: int = 0

    @property
    def source_type(self) -> str:
        return "file"

    def open(self) -> bool:
        """
        Opens the local video file and reads stream metadata.
        """
        self._state = StreamState.CONNECTING
        self._error_message = None

        if not self.video_path.exists():
            self._state = StreamState.ERROR
            self._error_message = f"Video file does not exist: {self.video_path}"
            return False

        if not self.video_path.is_file():
            self._state = StreamState.ERROR
            self._error_message = f"Path is not a regular file: {self.video_path}"
            return False

        self._cap = cv2.VideoCapture(str(self.video_path))
        if not self._cap.isOpened():
            self._state = StreamState.ERROR
            self._error_message = f"OpenCV failed to open video codec for: {self.video_path}"
            return False

        # Read video metadata from container
        self._fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 0.0)
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        self._frames_read = 0
        self._frames_sampled = 0
        self._state = StreamState.STREAMING
        return True

    def read_frame(self) -> Optional[FramePacket]:
        """
        Reads frames from the video file with configurable sampling stride.
        For example, if sample_stride=2, advances 2 frames and emits the second.
        """
        if self._cap is None or not self._cap.isOpened():
            self._state = StreamState.ERROR
            self._error_message = "Stream is not open"
            return None

        # Apply configurable frame sampling
        step = 0
        while step < self.sample_stride:
            success, raw_frame = self._cap.read()
            if not success:
                if self.loop:
                    # Rewind to start
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    success, raw_frame = self._cap.read()
                    if not success:
                        self._state = StreamState.COMPLETED
                        return None
                else:
                    self._state = StreamState.COMPLETED
                    return None

            self._frames_read += 1
            step += 1

            if step == self.sample_stride:
                self._frames_sampled += 1
                pos_msec = float(self._cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                return FramePacket(
                    camera_id=self.camera_id,
                    frame_index=self._frames_sampled,
                    source_frame_index=self._frames_read,
                    timestamp_ms=pos_msec,
                    frame=raw_frame,
                )

        return None

    def get_status(self) -> StreamStatus:
        is_connected = self._cap is not None and self._cap.isOpened()
        return StreamStatus(
            camera_id=self.camera_id,
            camera_name=self.camera_name,
            source_uri=str(self.video_path),
            source_type=self.source_type,
            is_connected=is_connected,
            processing_status=self._state,
            total_frames=self._total_frames,
            frames_read=self._frames_read,
            frames_sampled=self._frames_sampled,
            fps=self._fps,
            resolution=(self._width, self._height),
            location=self.location,
            error_message=self._error_message,
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._state = StreamState.CLOSED


# Alias for compatibility with pipeline orchestrator
LocalFileCameraSource = FileCameraSource



class RTSPCameraSource(BaseCameraSource):
    """
    RTSP / Network CCTV camera stream source using OpenCV video capture.
    Supports real network video feeds, RTSP/HTTP/HLS streams.
    """

    def __init__(
        self,
        camera_id: str,
        camera_name: str,
        source_uri: str = "",
        rtsp_uri: Optional[str] = None,
        location: Optional[CameraLocation] = None,
        sample_stride: int = 1,
    ):
        resolved_uri = source_uri or rtsp_uri or ""
        super().__init__(
            camera_id=camera_id,
            camera_name=camera_name,
            source_uri=resolved_uri,
            location=location,
            sample_stride=sample_stride,
        )
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps: float = 0.0
        self._width: int = 0
        self._height: int = 0

    @property
    def source_type(self) -> str:
        return "rtsp"

    def open(self) -> bool:
        """Establishes connection to the RTSP / Network video stream."""
        self._state = StreamState.CONNECTING
        try:
            # Set short connection timeout for network streams to avoid hanging
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;1000000"
            self._cap = cv2.VideoCapture(self.source_uri)
            if not self._cap.isOpened():
                self._state = StreamState.ERROR
                self._error_message = f"Failed to connect to network RTSP stream: {self.source_uri}"
                return False
            self._fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 15.0)
            self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            self._state = StreamState.STREAMING
            self._error_message = None
            return True
        except Exception as e:
            self._state = StreamState.ERROR
            self._error_message = f"RTSP connection exception: {e}"
            return False

    def read_frame(self) -> Optional[FramePacket]:
        """Fetches the next frame packet from the RTSP stream."""
        if self._cap is None or not self._cap.isOpened():
            return None

        step = 0
        while step < self.sample_stride:
            ret, raw_frame = self._cap.read()
            if not ret or raw_frame is None:
                self._state = StreamState.ERROR
                self._error_message = "Stream read timeout or connection lost"
                return None

            self._frames_read += 1
            step += 1

            if step == self.sample_stride:
                self._frames_sampled += 1
                pos_msec = float(self._cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                return FramePacket(
                    camera_id=self.camera_id,
                    frame_index=self._frames_sampled,
                    source_frame_index=self._frames_read,
                    timestamp_ms=pos_msec,
                    frame=raw_frame,
                )
        return None

    def get_status(self) -> StreamStatus:
        is_connected = self._cap is not None and self._cap.isOpened()
        return StreamStatus(
            camera_id=self.camera_id,
            camera_name=self.camera_name,
            source_uri=self.source_uri,
            source_type=self.source_type,
            is_connected=is_connected,
            processing_status=self._state,
            total_frames=-1,
            frames_read=self._frames_read,
            frames_sampled=self._frames_sampled,
            fps=self._fps,
            resolution=(self._width, self._height),
            location=self.location,
            error_message=self._error_message,
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._state = StreamState.CLOSED


class VideoIngestionEngine:
    """
    Central manager for multiple camera sources across the city grid.
    Coordinates opening, status reporting, and frame ingestion.
    """

    def __init__(self):
        self._sources: Dict[str, BaseCameraSource] = {}

    def register_camera(
        self,
        camera_id: str,
        camera_name: str,
        video_path: str,
        location: Optional[CameraLocation] = None,
        sample_stride: int = 1,
        loop: bool = False,
    ) -> FileCameraSource:
        """Registers a local video file as a virtual CCTV camera."""
        source = FileCameraSource(
            camera_id=camera_id,
            camera_name=camera_name,
            video_path=video_path,
            location=location,
            sample_stride=sample_stride,
            loop=loop,
        )
        self._sources[camera_id] = source
        return source

    def register_source(self, source: BaseCameraSource) -> None:
        """Registers an arbitrary camera source conforming to BaseCameraSource."""
        self._sources[source.camera_id] = source

    def get_source(self, camera_id: str) -> Optional[BaseCameraSource]:
        return self._sources.get(camera_id)

    def open_camera(self, camera_id: str) -> bool:
        source = self._sources.get(camera_id)
        if source is None:
            return False
        return source.open()

    def get_camera_status(self, camera_id: str) -> Optional[StreamStatus]:
        source = self._sources.get(camera_id)
        if source is None:
            return None
        return source.get_status()

    def get_all_statuses(self) -> Dict[str, StreamStatus]:
        return {cam_id: src.get_status() for cam_id, src in self._sources.items()}

    def stream_frames(self, camera_id: str) -> Generator[FramePacket, None, None]:
        """
        Yields sampled FramePacket objects from the requested camera stream.
        """
        source = self._sources.get(camera_id)
        if source is None:
            return

        while True:
            packet = source.read_frame()
            if packet is None:
                break
            yield packet

    def close_all(self) -> None:
        for source in self._sources.values():
            source.close()
