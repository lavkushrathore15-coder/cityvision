# Sample Videos Directory

This directory stores CCTV / traffic video streams used by the video ingestion service (`cam_01.mp4` through `cam_05.mp4`).

### Expected Video Criteria
- **Format**: MP4 / H.264
- **Resolution**: 1280x720 (720p) or 1920x1080 (1080p)
- **Target Frame Rate**: 15 - 30 FPS
- **Content**: Urban traffic junction, highway, or arterial road footage with distinct vehicles transitioning between viewpoints.

To download open sample feeds, run:
```bash
python scripts/download_sample_data.py
```
