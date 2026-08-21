"""GET /api/videos/{video_id}/status (PRD section 9.3 + Screen 3)."""

from fastapi import APIRouter, HTTPException

from ..services import storage

router = APIRouter(prefix="/api/videos", tags=["processing"])


@router.get("/{video_id}/status")
async def get_status(video_id: str):
    job = storage.read_job(video_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return job
