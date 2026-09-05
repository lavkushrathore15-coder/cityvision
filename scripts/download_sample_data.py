"""
Sample Data Acquisition & Synthetic CCTV Stream Generator
Provides reproducible test video feeds for cameras CAM-001 through CAM-005.
Uses OpenCV to generate synthetic traffic streams with simulated vehicle motion,
timestamps, and camera watermarks for reliable offline testing.
"""
from pathlib import Path
import cv2
import numpy as np


def generate_synthetic_cctv_clip(
    output_path: Path,
    camera_id: str,
    camera_name: str,
    duration_sec: int = 10,
    fps: int = 15,
    width: int = 640,
    height: int = 360,
):
    """
    Creates a valid MP4 video clip depicting simulated road traffic
    with bounding boxes and camera watermarks for pipeline testing.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    total_frames = duration_sec * fps

    for f in range(total_frames):
        # Dark asphalt road background
        frame = np.full((height, width, 3), (40, 40, 40), dtype=np.uint8)
        
        # Road lane markings (dashed center lines)
        cv2.line(frame, (0, height // 2), (width, height // 2), (180, 180, 180), 2)
        
        # Simulated moving vehicles
        # Vehicle 1: Moving left to right
        x1 = int((f * 8) % (width + 100)) - 80
        y1 = int(height * 0.3)
        if 0 <= x1 < width - 60:
            cv2.rectangle(frame, (x1, y1), (x1 + 60, y1 + 35), (200, 50, 50), -1)
            cv2.putText(frame, "CAR-01", (x1 + 5, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Vehicle 2: Moving right to left
        x2 = width - int((f * 6) % (width + 120))
        y2 = int(height * 0.65)
        if 0 <= x2 < width - 70:
            cv2.rectangle(frame, (x2, y2), (x2 + 70, y2 + 40), (50, 150, 220), -1)
            cv2.putText(frame, "SUV-02", (x2 + 5, y2 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Camera watermark & timestamp
        timestamp_str = f"2026-09-04 12:00:{f // fps:02d}.{int((f % fps) * (1000 / fps)):03d}"
        cv2.putText(frame, f"{camera_id} | {camera_name}", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(frame, f"TIME: {timestamp_str} | FPS: {fps}", (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        out.write(frame)

    out.release()
    print(f"Generated synthetic stream: {output_path} ({total_frames} frames)")


def main():
    cameras = [
        ("CAM-001", "North Gateway Intersection", "cam_01.mp4"),
        ("CAM-002", "Central Ring Road Eastbound", "cam_02.mp4"),
        ("CAM-003", "South Metro Junction", "cam_03.mp4"),
        ("CAM-004", "West Tech Park Avenue", "cam_04.mp4"),
        ("CAM-005", "City Terminal Outer Exit", "cam_05.mp4"),
    ]
    base_dir = Path("data/sample_videos")
    for cam_id, name, filename in cameras:
        generate_synthetic_cctv_clip(base_dir / filename, cam_id, name)


if __name__ == "__main__":
    main()
