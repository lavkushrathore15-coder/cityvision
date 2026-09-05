"""
Schema definition for CCTV Camera Nodes
"""
from typing import Optional
from dataclasses import dataclass, asdict

try:
    from pydantic import BaseModel, Field

    class CameraBase(BaseModel):
        id: str
        name: str
        latitude: Optional[float] = None
        longitude: Optional[float] = None
        heading_deg: float = 0.0
        fps: int = 15
        source_type: str = "file"  # "file", "rtsp", "webcam"
        stream_uri: str
        status: str = "configured"  # "configured", "streaming", "offline", "error"

    class CameraLocationUpdateSchema(BaseModel):
        latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="WGS-84 Latitude")
        longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="WGS-84 Longitude")
        heading_deg: Optional[float] = Field(None, ge=0.0, le=360.0, description="Heading degrees")
        description: Optional[str] = None

    class CameraCreate(CameraBase):
        pass

    class CameraResponse(CameraBase):
        active_track_count: Optional[int] = 0

    class CameraResolution(BaseModel):
        width: int
        height: int

    class CameraLocationSchema(BaseModel):
        latitude: Optional[float] = None
        longitude: Optional[float] = None
        description: str
        is_gps_available: bool
        source: str

    class CameraStatusResponse(BaseModel):
        camera_id: str
        camera_name: str
        source_uri: str
        source_type: str
        is_connected: bool
        processing_status: str
        total_frames: int
        frames_read: int
        frames_sampled: int
        fps: float
        resolution: CameraResolution
        location: CameraLocationSchema
        error_message: Optional[str] = None

except ImportError:
    @dataclass
    class CameraBase:
        id: str
        name: str
        latitude: Optional[float] = None
        longitude: Optional[float] = None
        heading_deg: float = 0.0
        fps: int = 15
        source_type: str = "file"
        stream_uri: str = ""
        status: str = "configured"

    @dataclass
    class CameraLocationUpdateSchema:
        latitude: Optional[float] = None
        longitude: Optional[float] = None
        heading_deg: Optional[float] = None
        description: Optional[str] = None

    @dataclass
    class CameraCreate(CameraBase):
        pass

    @dataclass
    class CameraResponse(CameraBase):
        active_track_count: Optional[int] = 0
