"""POST /api/videos/upload (PRD section 9.1) — validates, stores, and
kicks off processing in the background so the response returns immediately
and the frontend can poll /status (Screen 2 -> Screen 3 transition)."""

import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from ..services import processing_manager, storage
from ..services.video_validation import VideoValidationError, validate_extension, validate_file_size, validate_readable

router = APIRouter(prefix="/api/videos", tags=["upload"])


@router.post("/upload")
async def upload_video(file: UploadFile, background_tasks: BackgroundTasks):
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
    background_tasks.add_task(processing_manager.run_processing, video_id, dest_path)

    return {"video_id": video_id, "status": "Uploaded"}
