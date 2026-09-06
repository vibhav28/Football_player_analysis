"""POST /api/videos/upload (PRD section 9.1) — validates and stores the
video. Processing doesn't start here: the frontend takes the user to
pitch calibration next (routers/calibration.py), which is what actually
kicks off the CV pipeline (Screen 2 -> calibration -> Screen 3)."""

import os

from fastapi import APIRouter, HTTPException, UploadFile

from ..services import processing_manager, storage
from ..services.video_validation import VideoValidationError, validate_extension, validate_file_size, validate_readable

router = APIRouter(prefix="/api/videos", tags=["upload"])


@router.post("/upload")
async def upload_video(file: UploadFile):
    try:
        validate_extension(file.filename)
    except VideoValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.reason) from exc

    video_id = storage.new_video_id()
    ext = os.path.splitext(file.filename)[1].lower()
    dest_path = storage.upload_path(video_id, ext)

    size_bytes = 0
    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            out.write(chunk)

    try:
        validate_file_size(size_bytes)
        validate_readable(dest_path)
    except VideoValidationError as exc:
        os.remove(dest_path)
        raise HTTPException(status_code=400, detail=exc.reason) from exc

    processing_manager.mark_uploaded(video_id, file.filename)

    return {"video_id": video_id, "status": "Uploaded"}
