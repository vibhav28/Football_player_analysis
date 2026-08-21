"""Pipeline orchestrator (PRD section 10).

    Input Video -> Frame Extraction -> YOLOv8 Detection -> ByteTrack Tracking
    -> Team Classification -> Ball Detection/Interpolation -> Optical Flow
    -> Camera Motion Compensation -> Perspective Transformation
    -> Pixel->Meter Conversion -> Speed Calculation -> Distance Calculation
    -> Statistics Generation -> Annotated Video

Writes players.json, positions.json, statistics.json, annotated.mp4 into
result_dir, matching the layout in PRD section 27/28.

Real detection needs a trained YOLOv8 weights file (app/pipeline/models/*.pt) —
doesn't exist in a fresh checkout. Call run(..., mock=True) to generate
structurally valid output for backend/frontend development in the meantime.

pitch_pixel_corners (four pixel corners for the perspective transform) is
optional: without it, detection/tracking/team classification/the annotated
video all still run, just with speed/distance reported as 0 and
video.pitch_calibrated=False in statistics.json, since meters-per-pixel is
unknowable without calibration.
"""

import json
import os
import random

from . import annotator, ball_tracking, camera_motion, detection, field_boundary, team_classification, tracking
from .perspective_transform import PerspectiveTransformer
from .speed_distance import compute_player_movement
from .utils import get_foot_position, get_video_properties, read_video, save_video


class PipelineError(Exception):
    """Raised for the failure cases in PRD section 35 (Processing Failure,
    Insufficient Detection, Perspective Calibration Failure)."""


def run(
    video_path: str,
    result_dir: str,
    model_path: str | None = None,
    pitch_pixel_corners: list[tuple[float, float]] | None = None,
    mock: bool = False,
) -> dict:
    os.makedirs(result_dir, exist_ok=True)

    if mock:
        return _run_mock(video_path, result_dir)

    if not model_path or not os.path.exists(model_path):
        raise PipelineError(
            "No YOLOv8 weights found. Place a trained model at "
            "app/pipeline/models/<name>.pt, or call run(mock=True)."
        )

    props = get_video_properties(video_path)
    frames = read_video(video_path)
    fps = props["fps"] or 25.0

    detections_per_frame = detection.detect_frames(frames, model_path)
    detections_per_frame = field_boundary.filter_detections_within_field(
        detections_per_frame, props["width"], props["height"]
    )

    has_players = any(
        d.class_name == "player" for frame in detections_per_frame for d in frame
    )
    if not has_players:
        raise PipelineError(
            "Unable to reliably detect players in this video. "
            "Try using a clearer video with better lighting and visibility."
        )

    tracks = tracking.track_players(detections_per_frame, fps=fps)
    team_by_id = team_classification.assign_teams(frames, tracks)

    ball_positions_raw = ball_tracking.extract_ball_positions(detections_per_frame)
    ball_positions = ball_tracking.interpolate_ball_positions(
        ball_positions_raw, len(frames)
    )

    camera_movement = camera_motion.estimate_camera_movement(frames)
    cumulative = [(0.0, 0.0)]
    for dx, dy in camera_movement[1:]:
        prev_x, prev_y = cumulative[-1]
        cumulative.append((prev_x + dx, prev_y + dy))

    # Meter-based speed/distance need pitch calibration (four known pixel
    # corners), which nothing currently supplies — there's no calibration
    # UI yet. Rather than hard-failing the whole run (which used to mean
    # detection/tracking/annotated video were thrown away even though they
    # succeeded), degrade gracefully: skip meter conversion and report
    # speed/distance as 0 with pitch_calibrated=False, but still produce
    # tracking, team classification, and the annotated video.
    pitch_calibrated = bool(pitch_pixel_corners)
    transformer = PerspectiveTransformer(pitch_pixel_corners) if pitch_calibrated else None

    # Map raw ByteTrack IDs to team-relative IDs (1, 2, 3... per team) so
    # each team is numbered from 1 instead of sharing one continuous
    # sequence across both teams (e.g. Team A: 1-7, Team B: 1-7, not 1-14).
    player_ids_by_team: dict[str, list[int]] = {}
    for raw_id, track in tracks.items():
        if not any(f["class_name"] == "player" for f in track.values()):
            continue  # referees aren't numbered as players
        player_ids_by_team.setdefault(team_by_id.get(raw_id, "Team A"), []).append(raw_id)

    relative_id_by_raw: dict[int, int] = {
        raw_id: relative_id
        for raw_ids in player_ids_by_team.values()
        for relative_id, raw_id in enumerate(sorted(raw_ids), start=1)
    }

    positions_json = {}
    statistics = []

    for raw_id, track in tracks.items():
        if raw_id not in relative_id_by_raw:
            continue  # skip referees in player statistics

        team = team_by_id.get(raw_id, "Team A")
        relative_id = relative_id_by_raw[raw_id]

        if transformer is not None:
            positions_m: dict[int, tuple[float, float]] = {}
            for frame_index, frame_data in track.items():
                pixel_point = get_foot_position(frame_data["bbox"])
                compensated = camera_motion.compensate_position(
                    pixel_point, cumulative[frame_index]
                )
                meters = transformer.transform_point(compensated)
                if meters is not None:
                    positions_m[frame_index] = meters

            if not positions_m:
                continue

            movement = compute_player_movement(positions_m, fps)
            # Composite key since relative_id alone collides across teams
            # (Team A's Player 3 and Team B's Player 3 both use relative_id=3).
            positions_json[f"{team}_{relative_id}"] = {
                str(frame_index): {"x": x, "y": y}
                for frame_index, (x, y) in positions_m.items()
            }
        else:
            # No pitch calibration — can't convert to meters, so
            # speed/distance are meaningless. Still record pixel positions
            # (for the overlay/positions endpoint) and report 0 rather
            # than a fabricated number; video_meta.pitch_calibrated tells
            # the caller why.
            movement = {
                "average_speed_kmh": 0.0,
                "minimum_speed_kmh": 0.0,
                "maximum_speed_kmh": 0.0,
                "total_distance_m": 0.0,
            }
            positions_json[f"{team}_{relative_id}"] = {
                str(frame_index): dict(zip(("x", "y"), get_foot_position(frame_data["bbox"])))
                for frame_index, frame_data in track.items()
            }

        statistics.append(
            {
                "tracking_id": relative_id,
                "team": team,
                "average_speed_kmh": movement["average_speed_kmh"],
                "minimum_speed_kmh": movement["minimum_speed_kmh"],
                "maximum_speed_kmh": movement["maximum_speed_kmh"],
                "total_distance_m": movement["total_distance_m"],
            }
        )

    annotated_frames = [
        annotator.annotate_frame(
            frame, i, tracks, team_by_id, ball_positions, id_labels=relative_id_by_raw
        )
        for i, frame in enumerate(frames)
    ]
    save_video(annotated_frames, os.path.join(result_dir, "annotated.mp4"), fps)

    # Calculate real ball movement from tracked ball positions if available
    ball_stats = None
    if transformer is not None:
        ball_positions_m = {}
        for frame_index, pixel_point in ball_positions.items():
            compensated = camera_motion.compensate_position(
                pixel_point, cumulative[frame_index]
            )
            meters = transformer.transform_point(compensated)
            if meters is not None:
                ball_positions_m[frame_index] = meters

        if ball_positions_m:
            ball_movement = compute_player_movement(ball_positions_m, fps)
            ball_stats = {
                "average_speed_kmh": ball_movement["average_speed_kmh"],
                "minimum_speed_kmh": ball_movement["minimum_speed_kmh"],
                "maximum_speed_kmh": ball_movement["maximum_speed_kmh"],
                "total_distance_m": ball_movement["total_distance_m"]
            }

    return _write_results(
        result_dir, video_path, props, statistics, positions_json, ball_stats,
        pitch_calibrated=pitch_calibrated,
    )


def _run_mock(video_path: str, result_dir: str) -> dict:
    """Generate structurally valid results without running any CV model,
    so the backend/frontend can be built and tested end-to-end first."""
    props = get_video_properties(video_path)
    rng = random.Random(42)

    statistics = []
    positions_json = {}
    for team in ("Team A", "Team B"):
        for relative_id in range(1, 8):
            avg = round(rng.uniform(6.0, 9.5), 2)
            statistics.append(
                {
                    "tracking_id": relative_id,
                    "team": team,
                    "average_speed_kmh": avg,
                    "minimum_speed_kmh": round(rng.uniform(0.0, 0.5), 2),
                    "maximum_speed_kmh": round(avg + rng.uniform(10, 20), 2),
                    "total_distance_m": round(rng.uniform(6000, 10500), 1),
                }
            )
            positions_json[f"{team}_{relative_id}"] = {}

    ball_stats = {
        "average_speed_kmh": 22.4,
        "minimum_speed_kmh": 0.1,
        "maximum_speed_kmh": 72.8,
        "total_distance_m": 1250.3
    }

    # annotated.mp4 intentionally omitted in mock mode — no frames processed.
    return _write_results(result_dir, video_path, props, statistics, positions_json, ball_stats)


def _write_results(
    result_dir, video_path, props, statistics, positions_json, ball_stats=None,
    pitch_calibrated=True,
) -> dict:
    video_meta = {
        "filename": os.path.basename(video_path),
        "duration": props["duration_seconds"],
        "fps": props["fps"],
        # False means speed/distance above are 0 (not measured) because no
        # pitch calibration was supplied — see run(pitch_pixel_corners=...).
        "pitch_calibrated": pitch_calibrated,
    }

    with open(os.path.join(result_dir, "statistics.json"), "w") as f:
        json.dump({"video": video_meta, "players": statistics, "ball": ball_stats}, f, indent=2)

    with open(os.path.join(result_dir, "positions.json"), "w") as f:
        json.dump(positions_json, f, indent=2)

    with open(os.path.join(result_dir, "players.json"), "w") as f:
        json.dump(
            [{"tracking_id": s["tracking_id"], "team": s["team"]} for s in statistics],
            f,
            indent=2,
        )

    return {"video": video_meta, "players": statistics, "ball": ball_stats}
