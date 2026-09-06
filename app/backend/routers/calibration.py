"""POST /api/videos/{video_id}/calibrate (PRD section 35, Perspective
Calibration) — the step between Upload and Processing. The user supplies
four pixel corners of a known rectangular pitch region (or skips), which
is what actually kicks off the CV pipeline; upload alone no longer does."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..schemas import MATCH_FORMAT_PRESETS, CalibrationRequest
from ..services import processing_manager, storage

router = APIRouter(prefix="/api/videos", tags=["calibration"])


def _resolve_match_format(body: CalibrationRequest) -> tuple[int | None, float | None, float | None]:
    """Explicit players_per_team/pitch_width_m/pitch_length_m values win
    over the selected preset's individual fields (permissive, not mutually
    exclusive) -- covers e.g. "9v9 but I measured a slightly different
    pitch" without forcing an all-or-nothing choice."""
    players_per_team = body.players_per_team
    pitch_width_m = body.pitch_width_m
    pitch_length_m = body.pitch_length_m

    if body.match_format and body.match_format != "custom":
        preset_players, preset_width, preset_length = MATCH_FORMAT_PRESETS[body.match_format]
        players_per_team = preset_players if players_per_team is None else players_per_team
        pitch_width_m = preset_width if pitch_width_m is None else pitch_width_m
        pitch_length_m = preset_length if pitch_length_m is None else pitch_length_m

    return players_per_team, pitch_width_m, pitch_length_m


@router.post("/{video_id}/calibrate")
async def calibrate_video(video_id: str, body: CalibrationRequest, background_tasks: BackgroundTasks):
    job = storage.read_job(video_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    if job["status"] != "Uploaded":
        raise HTTPException(
            status_code=409,
            detail=f"Video is not awaiting calibration (status: {job['status']}).",
        )

    corners = body.pitch_pixel_corners
    if corners is not None and len(corners) != 4:
        raise HTTPException(
            status_code=400,
            detail="pitch_pixel_corners must contain exactly 4 points, or be omitted to skip calibration.",
        )

    players_per_team, pitch_width_m, pitch_length_m = _resolve_match_format(body)

    # Caught here, at the API boundary, rather than deep in the pipeline —
    # same pattern as the corner-count check above.
    if players_per_team is not None and not (1 <= players_per_team <= 30):
        raise HTTPException(status_code=400, detail="players_per_team must be between 1 and 30.")
    if pitch_width_m is not None and not (10.0 <= pitch_width_m <= 100.0):
        raise HTTPException(status_code=400, detail="pitch_width_m must be between 10 and 100 meters.")
    if pitch_length_m is not None and not (15.0 <= pitch_length_m <= 130.0):
        raise HTTPException(status_code=400, detail="pitch_length_m must be between 15 and 130 meters.")

    video_path = storage.find_upload_path(video_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Uploaded video file not found.")

    corner_tuples = [(p.x, p.y, p.time_seconds) for p in corners] if corners else None

    # Synchronous, not left to the background task: see
    # processing_manager.mark_processing's own docstring for why the
    # response below and job.json must not be able to disagree.
    processing_manager.mark_processing(video_id)

    background_tasks.add_task(
        processing_manager.run_processing,
        video_id,
        video_path,
        pitch_pixel_corners=corner_tuples,
        players_per_team=players_per_team,
        pitch_width_m=pitch_width_m,
        pitch_length_m=pitch_length_m,
    )
    return {"video_id": video_id, "status": "Processing"}
