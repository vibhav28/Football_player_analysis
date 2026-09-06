"""Ball possession assignment.

For each frame, the player whose foot position is closest to the ball is
considered to have possession, provided they're within
POSSESSION_THRESHOLD_PX — otherwise the ball is treated as loose (in the
air, between players, a pass in flight) and no one gets possession that
frame. Referees aren't eligible. This is the same closest-player-within-
threshold heuristic as the reference implementation this pipeline was
built from (training/football-players-detection/main.py,
estimate_ball_possession), threshold value included.
"""

from .utils import get_foot_position, measure_distance

POSSESSION_THRESHOLD_PX = 70.0


def assign_ball_possession(
    tracks: dict[int, dict[int, dict]],
    ball_positions: dict[int, tuple[float, float]],
    threshold_px: float = POSSESSION_THRESHOLD_PX,
) -> dict[int, int]:
    """Returns {frame_index: raw_track_id} of the possessing player for
    every frame where one is within threshold_px of the ball. Frames with
    no ball position, or no player close enough, are omitted rather than
    given a fabricated possessor."""
    possession: dict[int, int] = {}

    for frame_index, ball_pos in ball_positions.items():
        closest_id, closest_dist = None, float("inf")
        for tracking_id, track in tracks.items():
            frame_data = track.get(frame_index)
            if frame_data is None or frame_data["class_name"] != "player":
                continue
            foot = get_foot_position(frame_data["bbox"])
            dist = measure_distance(foot, ball_pos)
            if dist < closest_dist:
                closest_id, closest_dist = tracking_id, dist

        if closest_id is not None and closest_dist < threshold_px:
            possession[frame_index] = closest_id

    return possession


def team_possession_percentages(
    possession_by_frame: dict[int, int], team_by_id: dict[int, str]
) -> dict[str, float]:
    """Aggregates per-frame possession into each team's share of total
    possessed frames (not total video frames — frames where the ball is
    loose don't count toward either team, matching how 'possession %' is
    reported in real match stats)."""
    frames_by_team: dict[str, int] = {}
    for raw_id in possession_by_frame.values():
        team = team_by_id.get(raw_id)
        if team is None:
            continue
        frames_by_team[team] = frames_by_team.get(team, 0) + 1

    total = sum(frames_by_team.values())
    if not total:
        return {}
    return {team: round(100 * count / total, 1) for team, count in frames_by_team.items()}


def cumulative_possession_by_frame(
    possession_by_frame: dict[int, int], team_by_id: dict[int, str], frame_count: int
) -> dict[int, dict[str, float]]:
    """Running possession % through frame N (not the single final match
    figure team_possession_percentages returns) — for the annotated
    video's possession banner, which should read like a live broadcast
    graphic updating as the match plays, the same way the reference
    implementation's does (training/football-players-detection/
    trackers/tracker.py, draw_team_ball_control). statistics.json and the
    frontend panel still use the final, match-wide percentage; this is
    only for what gets baked into the video."""
    running_frames_by_team: dict[str, int] = {}
    result: dict[int, dict[str, float]] = {}

    for frame_index in range(frame_count):
        raw_id = possession_by_frame.get(frame_index)
        if raw_id is not None:
            team = team_by_id.get(raw_id)
            if team is not None:
                running_frames_by_team[team] = running_frames_by_team.get(team, 0) + 1

        total = sum(running_frames_by_team.values())
        if total:
            result[frame_index] = {
                team: round(100 * count / total, 2) for team, count in running_frames_by_team.items()
            }

    return result
