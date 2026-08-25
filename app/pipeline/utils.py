"""Video I/O and geometry helpers shared across pipeline stages."""

import cv2
import numpy as np


def read_video(video_path: str) -> list[np.ndarray]:
    """Read an entire video into memory as a list of BGR frames.

    Fine for short clips during development; for long matches prefer
    streaming frame-by-frame instead of loading everything at once.
    """
    cap = cv2.VideoCapture(video_path)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames


def get_video_properties(video_path: str) -> dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    props = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    props["duration_seconds"] = (
        props["frame_count"] / props["fps"] if props["fps"] else 0
    )
    return props


def save_video(frames: list[np.ndarray], output_path: str, fps: float) -> None:
    if not frames:
        raise ValueError("No frames to write")
    height, width = frames[0].shape[:2]
    # H.264 (avc1), not mp4v (MPEG-4 Part 2): browsers' <video> element
    # cannot decode mp4v even though a .mp4 container is otherwise valid,
    # so the file downloads fine but nothing ever renders — silently
    # "black forever" rather than an error. avc1 is what this OpenCV/
    # FFmpeg build actually supports writing for MP4; H264/X264 fourcc
    # strings aren't valid MP4 tags and fall back to avc1 anyway.
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()


def get_bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def get_bbox_width(bbox: tuple[float, float, float, float]) -> float:
    x1, _, x2, _ = bbox
    return x2 - x1


def get_foot_position(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    """Point where the player touches the ground — better than the bbox
    center for perspective transform, since it sits on the pitch plane."""
    x1, _, x2, y2 = bbox
    return (x1 + x2) / 2, y2


def measure_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return float(np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))
