"""Pipeline orchestrator (PRD section 10).

    Input Video -> Frame Extraction -> YOLOv8 Detection -> ByteTrack Tracking
    -> Team Classification -> Track Merging (ID-churn cleanup, appearance
    re-id, roster-size cap -- see tracking.py)
    -> Ball Detection/Interpolation -> Optical Flow
    -> Camera Motion Compensation -> Perspective Transformation
    -> Pixel->Meter Conversion -> Speed Calculation -> Distance Calculation
    -> Statistics Generation -> Annotated Video

Writes players.json, positions.json, statistics.json, annotated.mp4 into
result_dir, matching the layout in PRD section 27/28.

Real detection needs a trained YOLOv8 weights file (app/pipeline/models/*.pt) —
doesn't exist in a fresh checkout. Call run(..., mock=True) to generate
structurally valid output for backend/frontend development in the meantime.

pitch_pixel_corners (four (x, y, time_seconds) pixel corners for the
perspective transform) is optional: without it, detection/tracking/team
classification/the annotated video all still run, just with speed/distance
reported as 0 and video.pitch_calibrated=False in statistics.json, since
meters-per-pixel is unknowable without calibration.

Each corner carries its own timestamp because camera pan/zoom means no
single frame necessarily shows all four pitch corners — the calibration UI
lets each corner be picked from whichever frame the user scrubbed to. Each
corner is independently camera-motion-compensated back to frame 0's
coordinate system (the same compensation every player/ball position below
already gets), so all four end up in one consistent coordinate space
regardless of which frame each was read from.
"""

import json
import os
import random
from collections import defaultdict

from . import annotator, ball_possession, ball_tracking, camera_motion, detection, field_boundary, team_classification, tracking
from .perspective_transform import PITCH_LENGTH_M, PITCH_WIDTH_M, PerspectiveTransformer
from .speed_distance import (
    MAX_PLAUSIBLE_BALL_SPEED_KMH,
    MAX_PLAUSIBLE_PLAYER_SPEED_KMH,
    compute_player_movement,
)
from .utils import get_foot_position, get_video_properties, read_video, save_video


class PipelineError(Exception):
    """Raised for the failure cases in PRD section 35 (Processing Failure,
    Insufficient Detection, Perspective Calibration Failure)."""


def run(
    video_path: str,
    result_dir: str,
    model_path: str | None = None,
    pitch_pixel_corners: list[tuple[float, float, float]] | None = None,
    mock: bool = False,
    players_per_team: int | None = None,
    target_width_m: float | None = None,
    target_length_m: float | None = None,
) -> dict:
    os.makedirs(result_dir, exist_ok=True)

    if mock:
        return _run_mock(video_path, result_dir, players_per_team=players_per_team)

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

    tracks = tracking.track_players(detections_per_frame, frames, fps=fps)
    team_by_id = team_classification.assign_teams(frames, tracks)
    tracks, team_by_id = tracking.merge_broken_tracks(tracks, team_by_id, fps=fps)
    # Long-gap same-player reunification (appearance, not position) followed
    # by the fixed-squad-size guardrail -- see tracking.py's module comment
    # above merge_broken_tracks_by_appearance for why these are separate
    # passes from merge_broken_tracks and from BoT-SORT's own tracking-time
    # ReID matching.
    tracks, team_by_id = tracking.merge_broken_tracks_by_appearance(tracks, team_by_id, frames, fps=fps)
    # players_per_team=None here means "the caller/user didn't specify the
    # match's real per-team count" -- NOT "disable the roster cap". Those are
    # different things: passing None straight through to enforce_roster_size
    # would fully disable its guardrail (that's what None means to THAT
    # function, see its docstring), silently re-opening the door to
    # unbounded runaway noise. Resolving to a generous safety ceiling here
    # instead keeps a cap in place even when the format is unknown, while
    # still never trimming a genuine full-size roster (see
    # MAX_PLAYERS_PER_TEAM_SAFETY_CAP's own comment for why 13).
    effective_target_size = (
        players_per_team if players_per_team is not None else tracking.MAX_PLAYERS_PER_TEAM_SAFETY_CAP
    )
    teams_before_cap = defaultdict(list)
    for tid, track in tracks.items():
        if any(f["class_name"] == "player" for f in track.values()):
            teams_before_cap[team_by_id.get(tid, "Team A")].append(tid)

    tracks, team_by_id = tracking.enforce_roster_size(
        tracks, team_by_id, frames, fps=fps, target_size=effective_target_size
    )

    # Cheap diagnostic signal, not a behavior change: if a team had way more
    # candidate tracks than the resolved target before capping, that's worth
    # knowing about when tuning the safety cap or format selection against
    # real footage -- could be genuine ID churn, or a misclassified
    # referee/staff track that slipped past class-based filtering.
    for team, ids in teams_before_cap.items():
        if len(ids) > effective_target_size + 3:
            print(
                f"[pitchtrack] {team}: {len(ids)} tracked player candidates before roster cap "
                f"(target {effective_target_size}) -- check for misclassified referee/staff or ID churn."
            )

    ball_positions_raw = ball_tracking.extract_ball_positions(detections_per_frame)
    ball_positions = ball_tracking.interpolate_ball_positions(
        ball_positions_raw, len(frames)
    )

    # Ball possession works in raw pixel space (proximity, not meters), so
    # it doesn't depend on calibration and runs unconditionally — unlike
    # speed/distance below, team possession % is available even for an
    # uncalibrated video.
    possession_by_frame = ball_possession.assign_ball_possession(tracks, ball_positions)
    possession_pct = ball_possession.team_possession_percentages(possession_by_frame, team_by_id)
    # Running possession-so-far, keyed by frame — used only for the video
    # overlay banner, which should read like a live-updating broadcast
    # graphic rather than repeat the single final percentage on every frame.
    possession_running_by_frame = ball_possession.cumulative_possession_by_frame(
        possession_by_frame, team_by_id, len(frames)
    )

    camera_movement = camera_motion.estimate_camera_movement(frames)
    cumulative = [(0.0, 0.0)]
    for dx, dy in camera_movement[1:]:
        prev_x, prev_y = cumulative[-1]
        cumulative.append((prev_x + dx, prev_y + dy))

    def _frame_index_for_time(time_seconds: float) -> int:
        return min(len(frames) - 1, max(0, round(time_seconds * fps))) if frames else 0

    # Meter-based speed/distance need pitch calibration (four known pixel
    # corners); the calibration UI lets the user skip it (e.g. no frame
    # shows all four pitch corners). Rather than hard-failing the whole
    # run when that happens (which used to mean detection/tracking/
    # annotated video were thrown away even though they succeeded),
    # degrade gracefully: skip meter conversion and report speed/distance
    # as 0 with pitch_calibrated=False, but still produce tracking, team
    # classification, and the annotated video.
    pitch_calibrated = bool(pitch_pixel_corners)
    transformer = None
    if pitch_calibrated:
        # Each corner is compensated back to frame 0's coordinate system
        # using its OWN frame's camera drift, exactly like every player/
        # ball position below — so it doesn't matter that different
        # corners may have been picked from different frames (see the
        # module docstring).
        compensated_corners = [
            camera_motion.compensate_position(
                (x, y), cumulative[_frame_index_for_time(time_seconds)]
            )
            for x, y, time_seconds in pitch_pixel_corners
        ]
        transformer = PerspectiveTransformer(
            compensated_corners,
            target_width_m=target_width_m or PITCH_WIDTH_M,
            target_length_m=target_length_m or PITCH_LENGTH_M,
        )

    # Map raw ByteTrack IDs to team-relative IDs (1, 2, 3... per team) so
    # each team is numbered from 1 instead of sharing one continuous
    # sequence across both teams (e.g. for a 7-a-side match, Team A: 1-7,
    # Team B: 1-7, not 1-14 -- the exact range just depends on how many
    # real players that team has, whatever the match format).
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

    # Referees get their own small sequential label (1, 2, 3...) for the
    # video overlay, same reasoning as player numbering above -- without
    # this they fall back to BoT-SORT's raw track id, which climbs into
    # the hundreds over a longer clip (verified on real footage: a
    # referee showing as "302" next to players labeled 1-11 looks like a
    # stray bug, not a deliberately different numbering scheme). Kept
    # entirely separate from relative_id_by_raw, which the stats loop
    # below also uses to decide "is this raw_id a player" -- merging
    # referees into that same dict would make them incorrectly pass that
    # check and get counted in player statistics.
    referee_ids = sorted(
        raw_id
        for raw_id, track in tracks.items()
        if any(f["class_name"] == "referee" for f in track.values())
    )
    referee_id_by_raw = {raw_id: i for i, raw_id in enumerate(referee_ids, start=1)}
    annotator_id_labels = {**relative_id_by_raw, **referee_id_by_raw}

    positions_json = {}
    statistics = []
    # {raw_id: {frame_index: (speed_kmh, distance_m)}} — live per-player
    # readout for the annotated video overlay. Only populated when
    # calibrated; an uncalibrated video shows no live stats, consistent
    # with statistics.json reporting 0 rather than a fabricated number.
    live_stats: dict[int, dict[int, tuple[float, float]]] = {}
    total_player_tracks = 0
    fully_out_of_bounds_tracks = 0

    for raw_id, track in tracks.items():
        if raw_id not in relative_id_by_raw:
            continue  # skip referees in player statistics
        total_player_tracks += 1

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

            if positions_m:
                movement = compute_player_movement(
                    positions_m, fps, max_plausible_speed_kmh=MAX_PLAUSIBLE_PLAYER_SPEED_KMH
                )
                # Composite key since relative_id alone collides across teams
                # (Team A's Player 3 and Team B's Player 3 both use relative_id=3).
                positions_json[f"{team}_{relative_id}"] = {
                    str(frame_index): {"x": x, "y": y}
                    for frame_index, (x, y) in positions_m.items()
                }
                live_stats[raw_id] = {
                    frame_index: (
                        movement["per_frame_speed_kmh"].get(frame_index, 0.0),
                        movement["per_frame_distance_m"].get(frame_index, 0.0),
                    )
                    for frame_index in positions_m
                }
            else:
                fully_out_of_bounds_tracks += 1
                # Every single frame of THIS track's position fell outside
                # the calibrated pitch region + margin (PerspectiveTransformer's
                # transform_point returned None every time) -- in practice
                # this means the calibration itself is off for this track
                # (imprecise corner clicks, or a match-format pitch-size
                # preset that doesn't match this footage's real pitch), not
                # that the player was never really on the pitch. Used to
                # `continue` here, silently dropping the player from
                # players.json/statistics.json entirely -- verified on real
                # footage that a mismatched preset can make this happen to
                # every player but one, collapsing the whole dashboard down
                # to a single row with zero indication anything was wrong.
                # Degrade the same way a fully uncalibrated video already
                # does instead: report 0 (not fabricated) but keep the
                # player in the roster, since a user who tracked ~20 real
                # players should see ~20 rows, not however many happened to
                # land inside the calibrated box.
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

    # A cheap diagnostic signal, not a behavior change: if most of the
    # match's players never had a single position land inside the
    # calibrated pitch region, that's almost certainly the calibration
    # itself being off (imprecise corners, or a match-format preset whose
    # pitch size doesn't match this footage), not a coincidence -- worth
    # flagging loudly rather than only quietly degrading each player to 0.
    if pitch_calibrated and total_player_tracks and fully_out_of_bounds_tracks / total_player_tracks > 0.5:
        print(
            f"[pitchtrack] {fully_out_of_bounds_tracks}/{total_player_tracks} tracked players had "
            "every position fall outside the calibrated pitch region -- speed/distance for them "
            "reads 0. Check the 4 calibration corners and match-format pitch size against this "
            "video's actual pitch."
        )

    annotated_frames = [
        annotator.annotate_frame(
            frame, i, tracks, team_by_id, ball_positions,
            id_labels=annotator_id_labels, ball_possession=possession_by_frame,
            live_stats=live_stats, possession_pct=possession_running_by_frame.get(i),
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
            ball_movement = compute_player_movement(
                ball_positions_m, fps, max_plausible_speed_kmh=MAX_PLAUSIBLE_BALL_SPEED_KMH
            )
            ball_stats = {
                "average_speed_kmh": ball_movement["average_speed_kmh"],
                "minimum_speed_kmh": ball_movement["minimum_speed_kmh"],
                "maximum_speed_kmh": ball_movement["maximum_speed_kmh"],
                "total_distance_m": ball_movement["total_distance_m"]
            }

    return _write_results(
        result_dir, video_path, props, statistics, positions_json, ball_stats,
        pitch_calibrated=pitch_calibrated, possession_pct=possession_pct,
    )


# Arbitrary dev-only fabricated-data size, unrelated to
# tracking.MAX_PLAYERS_PER_TEAM_SAFETY_CAP's real-pipeline safety-net
# reasoning -- mock mode just needs *a* number of fake players to generate
# when the caller doesn't ask for a specific match format.
MOCK_DEFAULT_PLAYERS_PER_TEAM = 7


def _run_mock(video_path: str, result_dir: str, players_per_team: int | None = None) -> dict:
    """Generate structurally valid results without running any CV model,
    so the backend/frontend can be built and tested end-to-end first."""
    props = get_video_properties(video_path)
    rng = random.Random(42)
    team_size = players_per_team or MOCK_DEFAULT_PLAYERS_PER_TEAM

    statistics = []
    positions_json = {}
    for team in ("Team A", "Team B"):
        for relative_id in range(1, team_size + 1):
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
    possession_pct = {"Team A": 54.3, "Team B": 45.7}

    # annotated.mp4 intentionally omitted in mock mode — no frames processed.
    return _write_results(
        result_dir, video_path, props, statistics, positions_json, ball_stats,
        possession_pct=possession_pct,
    )


def _write_results(
    result_dir, video_path, props, statistics, positions_json, ball_stats=None,
    pitch_calibrated=True, possession_pct=None,
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
        json.dump(
            {
                "video": video_meta,
                "players": statistics,
                "ball": ball_stats,
                "possession": possession_pct or None,
            },
            f,
            indent=2,
        )

    with open(os.path.join(result_dir, "positions.json"), "w") as f:
        json.dump(positions_json, f, indent=2)

    with open(os.path.join(result_dir, "players.json"), "w") as f:
        json.dump(
            [{"tracking_id": s["tracking_id"], "team": s["team"]} for s in statistics],
            f,
            indent=2,
        )

    return {"video": video_meta, "players": statistics, "ball": ball_stats, "possession": possession_pct or None}
