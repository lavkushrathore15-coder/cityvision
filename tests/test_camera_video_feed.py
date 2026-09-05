"""
Tests for Camera Video Streaming, Demo Video Serving, and Fallback Resolution.
Problem Statement ID: SIH26127
"""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_list_demo_videos():
    """Verify demo-videos endpoint returns 5 demo video assets."""
    response = client.get("/api/v1/demo-videos")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total"] == 5
    assert len(data["videos"]) == 5
    assert data["videos"][0]["filename"] == "cam_01.mp4"
    assert data["videos"][0]["camera_id"] == "CAM-001"


def test_get_camera_video_endpoints():
    """Verify camera video endpoints return MP4 bytes with 200 OK."""
    for cam_id in ["CAM-001", "CAM-002", "CAM-003", "CAM-004", "CAM-005"]:
        res = client.get(f"/api/v1/cameras/{cam_id}/video")
        assert res.status_code == 200
        assert "video/mp4" in res.headers.get("content-type", "")
        assert len(res.content) > 100000


def test_static_demo_videos_mount():
    """Verify static mount /demo_videos/ serves the sample mp4 files directly."""
    res = client.get("/demo_videos/cam_01.mp4")
    assert res.status_code == 200
    assert len(res.content) > 100000
