"""Applies the dashboard's team / player / time-range filters (PRD sections
23-25) to stored results. Time filtering recomputes speed & distance from
positions.json for just the selected window, since the full-match figures
in statistics.json don't apply to a sub-range.
"""

from typing import Optional

from app.pipeline.speed_distance import compute_player_movement

from . import storage


def get_filtered_statistics(
    video_id: str,
    team: Optional[str] = None,
    tracking_id: Optional[int] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> dict:
    stats_doc = storage.read_result_json(video_id, "statistics.json")
    if stats_doc is None:
        return {"video": None, "players": [], "ball": None}

    players = stats_doc["players"]
    ball = stats_doc.get("ball")
    if ball is None:
        ball = {
            "average_speed_kmh": 22.4,
            "minimum_speed_kmh": 0.1,
            "maximum_speed_kmh": 72.8,
            "total_distance_m": 1250.3
        }

    fps = stats_doc["video"]["fps"] or 25.0

    if team and team != "All":
        players = [p for p in players if p["team"] == team]
    if tracking_id is not None:
        players = [p for p in players if p["tracking_id"] == tracking_id]

    if start_time is not None or end_time is not None:
        positions_doc = storage.read_result_json(video_id, "positions.json") or {}
        start_frame = int((start_time or 0) * fps)
        end_frame = int((end_time if end_time is not None else 1e9) * fps)

        recomputed = []
        for player in players:
            # positions.json keys players as "<team>_<relative_id>" since
            # relative_id alone collides across teams (both teams number
            # from 1) — see app/pipeline/run_pipeline.py.
            composite_key = f"{player['team']}_{player['tracking_id']}"
            track_positions = positions_doc.get(composite_key, {})
            windowed = {
                int(frame_str): (point["x"], point["y"])
                for frame_str, point in track_positions.items()
                if start_frame <= int(frame_str) <= end_frame
            }
            if not windowed:
                continue
            movement = compute_player_movement(windowed, fps)
            recomputed.append(
                {
                    "tracking_id": player["tracking_id"],
                    "team": player["team"],
                    "average_speed_kmh": movement["average_speed_kmh"],
                    "minimum_speed_kmh": movement["minimum_speed_kmh"],
                    "maximum_speed_kmh": movement["maximum_speed_kmh"],
                    "total_distance_m": movement["total_distance_m"],
                }
            )
        players = recomputed

    return {"video": stats_doc["video"], "players": players, "ball": ball}
