"""Video upload validation (PRD section 9.2)."""

import os

import cv2

from ..config import ALLOWED_EXTENSIONS, MAX_DURATION_SECONDS, MAX_UPLOAD_SIZE_BYTES, MIN_DURATION_SECONDS


class VideoValidationError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_extension(filename: str) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise VideoValidationError(
            f"Unsupported file format '{ext}'. Supported formats: "
            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )


def validate_file_size(size_bytes: int) -> None:
    if size_bytes <= 0:
        raise VideoValidationError("Uploaded file is empty.")
    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise VideoValidationError(f"File exceeds the maximum upload size of {max_mb} MB.")


def validate_readable(video_path: str) -> dict:
    """Checks readability, frame rate, resolution, and duration in one pass
    (PRD section 9.2) — reopening the file per-check would be wasteful."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        raise VideoValidationError("Unsupported or corrupted video file.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ok, _ = cap.read()
    cap.release()

    if not ok:
        raise VideoValidationError("Unsupported or corrupted video file.")
    if not fps or width <= 0 or height <= 0:
        raise VideoValidationError("Unable to read video frame rate or resolution.")

    duration_seconds = frame_count / fps
    if duration_seconds < MIN_DURATION_SECONDS:
        raise VideoValidationError("Video is too short to analyze.")
    if duration_seconds > MAX_DURATION_SECONDS:
        raise VideoValidationError("Video exceeds the maximum supported duration.")

    return {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": duration_seconds,
    }
