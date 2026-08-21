"""File-based storage helpers (PRD section 27) — the stand-in for a videos
table. Each uploaded video gets a video_id; everything about it lives at
uploads/<video_id><ext> and results/<video_id>/.
"""

import json
import os
import shutil
import uuid
from typing import Optional

from ..config import RESULTS_DIR, UPLOAD_DIR

JOB_FILENAME = "job.json"


def new_video_id() -> str:
    return uuid.uuid4().hex[:12]


def upload_path(video_id: str, ext: str) -> str:
    return os.path.join(UPLOAD_DIR, f"{video_id}{ext}")


def result_dir(video_id: str) -> str:
    return os.path.join(RESULTS_DIR, video_id)


def find_upload_path(video_id: str) -> Optional[str]:
    for entry in os.listdir(UPLOAD_DIR):
        name, _ = os.path.splitext(entry)
        if name == video_id:
            return os.path.join(UPLOAD_DIR, entry)
    return None


def save_upload(video_id: str, ext: str, file_obj) -> str:
    dest_path = upload_path(video_id, ext)
    with open(dest_path, "wb") as out:
        shutil.copyfileobj(file_obj, out)
    return dest_path


def write_job(video_id: str, job_data: dict) -> None:
    os.makedirs(result_dir(video_id), exist_ok=True)
    with open(os.path.join(result_dir(video_id), JOB_FILENAME), "w") as f:
        json.dump(job_data, f, indent=2)


def read_job(video_id: str) -> Optional[dict]:
    path = os.path.join(result_dir(video_id), JOB_FILENAME)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def read_result_json(video_id: str, filename: str) -> Optional[dict]:
    path = os.path.join(result_dir(video_id), filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_videos() -> list[dict]:
    """Scan results/ for job files — the file-based equivalent of `SELECT *
    FROM videos`, acceptable at MVP scale (PRD section 30)."""
    videos = []
    if not os.path.isdir(RESULTS_DIR):
        return videos
    for video_id in os.listdir(RESULTS_DIR):
        job = read_job(video_id)
        if job:
            videos.append(job)
    return videos


def delete_video(video_id: str) -> bool:
    """Cascade delete: original video, JSON results, annotated video
    (PRD section 39)."""
    deleted_something = False

    upload = find_upload_path(video_id)
    if upload and os.path.exists(upload):
        os.remove(upload)
        deleted_something = True

    result_path = result_dir(video_id)
    if os.path.isdir(result_path):
        shutil.rmtree(result_path)
        deleted_something = True

    return deleted_something
