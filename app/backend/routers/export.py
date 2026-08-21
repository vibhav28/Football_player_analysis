"""Export endpoints (PRD section 26). CSV/JSON honor the same team/player/
time filters as the dashboard, per the "Export values must correspond to
the selected analysis scope" acceptance criterion (PRD section 41)."""

import csv
import io
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from ..services import filtering, storage

router = APIRouter(prefix="/api/videos", tags=["export"])


@router.get("/{video_id}/export/csv")
async def export_csv(
    video_id: str,
    team: str | None = Query(default=None),
    tracking_id: int | None = Query(default=None),
    start_time: float | None = Query(default=None),
    end_time: float | None = Query(default=None),
):
    data = filtering.get_filtered_statistics(video_id, team, tracking_id, start_time, end_time)
    if data["video"] is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Player", "Team", "Average Speed", "Min Speed", "Max Speed", "Distance"])
    for player in data["players"]:
        writer.writerow(
            [
                f"Player {player['tracking_id']}",
                player["team"],
                player["average_speed_kmh"],
                player["minimum_speed_kmh"],
                player["maximum_speed_kmh"],
                player["total_distance_m"],
            ]
        )
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={video_id}_statistics.csv"},
    )


@router.get("/{video_id}/export/json")
async def export_json(
    video_id: str,
    team: str | None = Query(default=None),
    tracking_id: int | None = Query(default=None),
    start_time: float | None = Query(default=None),
    end_time: float | None = Query(default=None),
):
    data = filtering.get_filtered_statistics(video_id, team, tracking_id, start_time, end_time)
    if data["video"] is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return data


@router.get("/{video_id}/export/annotated-video")
async def export_annotated_video(video_id: str):
    path = os.path.join(storage.result_dir(video_id), "annotated.mp4")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Annotated video not found.")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{video_id}_annotated.mp4",
    )
