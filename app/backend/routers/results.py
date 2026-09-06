"""Results endpoints backing the Analysis Workspace (PRD section 19) and
video library/delete (PRD section 39)."""

import os

from fastapi import APIRouter, HTTPException, Query, Request

from ..services import filtering, storage
from ..services.range_response import range_file_response

router = APIRouter(prefix="/api/videos", tags=["results"])


@router.get("")
async def list_videos():
    """Not explicitly in the PRD's screen list, but needed since there is
    no login/DB — this is how a returning user finds past analyses."""
    return storage.list_videos()


@router.get("/{video_id}/results")
async def get_results(
    video_id: str,
    team: str | None = Query(default=None),
    tracking_id: int | None = Query(default=None),
    start_time: float | None = Query(default=None),
    end_time: float | None = Query(default=None),
):
    job = storage.read_job(video_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    if job["status"] != "Completed":
        raise HTTPException(status_code=409, detail=f"Video is not ready (status: {job['status']}).")

    return filtering.get_filtered_statistics(video_id, team, tracking_id, start_time, end_time)


@router.get("/{video_id}/positions")
async def get_positions(video_id: str):
    positions = storage.read_result_json(video_id, "positions.json")
    if positions is None:
        raise HTTPException(status_code=404, detail="Positions not found.")
    return positions


@router.get("/{video_id}/video")
async def get_original_video(video_id: str, request: Request):
    path = storage.find_upload_path(video_id)
    if path is None or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video not found.")
    return range_file_response(request, path, media_type="video/mp4")


@router.get("/{video_id}/annotated")
async def get_annotated_video(video_id: str, request: Request):
    path = os.path.join(storage.result_dir(video_id), "annotated.mp4")
    if not os.path.exists(path):
        path = storage.find_upload_path(video_id)
        if path is None or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Annotated video not found.")
    return range_file_response(request, path, media_type="video/mp4")


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """Cascade delete: original + JSON results + annotated video (PRD
    section 39, Privacy)."""
    deleted = storage.delete_video(video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Video not found.")
    return {"deleted": True, "video_id": video_id}
