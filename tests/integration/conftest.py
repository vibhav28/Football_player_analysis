import cv2
import numpy as np
import pytest

from app.backend.services import storage


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Redirect upload/result storage to a temp dir so the API tests never
    read or write the project's real uploads/ or results/ directories."""
    upload_dir = tmp_path / "uploads"
    results_dir = tmp_path / "results"
    upload_dir.mkdir()
    results_dir.mkdir()
    monkeypatch.setattr(storage, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(storage, "RESULTS_DIR", str(results_dir))
    return {"upload_dir": upload_dir, "results_dir": results_dir}


@pytest.fixture
def tiny_video(tmp_path):
    """A minimal, genuinely readable mp4 (a few solid-color frames) for
    exercising the real cv2.VideoCapture validation path in
    video_validation.py without needing a real football clip."""
    path = tmp_path / "tiny.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 5.0, (64, 48))
    for _ in range(10):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    return path
