"""Draws tracking overlays onto video frames (PRD sections 19 & 21).

Produces the annotated.mp4 output. Overlay style mirrors the toggles the
frontend exposes: player markers + IDs, team indicators (color AND shape,
per PRD section 13 — never color alone), a ball marker, and a referee
marker.
"""

import cv2
import numpy as np

TEAM_COLORS = {
    "Team A": (255, 60, 60),   # BGR
    "Team B": (60, 200, 255),
    "Referee": (0, 220, 0),
}


def draw_player_ellipse(
    frame: np.ndarray,
    bbox: tuple[float, float, float, float],
    color: tuple[int, int, int],
    tracking_id: int,
) -> np.ndarray:
    x1, _, x2, y2 = (int(v) for v in bbox)
    center_x = (x1 + x2) // 2
    width = x2 - x1

    cv2.ellipse(
        frame,
        center=(center_x, y2),
        axes=(int(width * 0.6), int(width * 0.2)),
        angle=0.0,
        startAngle=-45,
        endAngle=235,
        color=color,
        thickness=2,
        lineType=cv2.LINE_4,
    )

    label = str(tracking_id)
    label_width = max(20, len(label) * 8 + 10)
    rect_x1 = center_x - label_width // 2
    rect_y1 = y2 + 5
    cv2.rectangle(frame, (rect_x1, rect_y1), (rect_x1 + label_width, rect_y1 + 16), color, cv2.FILLED)
    cv2.putText(
        frame, label, (rect_x1 + 4, rect_y1 + 13),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1,
    )
    return frame


def draw_ball_marker(frame: np.ndarray, position: tuple[float, float]) -> np.ndarray:
    x, y = (int(v) for v in position)
    triangle = np.array([[x, y - 12], [x - 8, y + 4], [x + 8, y + 4]])
    cv2.drawContours(frame, [triangle], 0, (0, 0, 255), cv2.FILLED)
    cv2.drawContours(frame, [triangle], 0, (0, 0, 0), 1)
    return frame


def draw_possession_marker(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Small filled triangle above a player's head, marking them as
    currently having the ball (closest player within
    ball_possession.POSSESSION_THRESHOLD_PX)."""
    x1, y1, x2, _ = (int(v) for v in bbox)
    center_x = (x1 + x2) // 2
    triangle = np.array([[center_x, y1 - 4], [center_x - 8, y1 - 18], [center_x + 8, y1 - 18]])
    cv2.drawContours(frame, [triangle], 0, (0, 220, 255), cv2.FILLED)
    cv2.drawContours(frame, [triangle], 0, (0, 0, 0), 1)
    return frame


def draw_live_stats(
    frame: np.ndarray,
    bbox: tuple[float, float, float, float],
    speed_kmh: float,
    distance_m: float,
) -> np.ndarray:
    """Live per-frame speed + cumulative distance above a player's head —
    only meaningful once the video is pitch-calibrated (see
    run_pipeline.py's live_stats, built from
    speed_distance.compute_player_movement's per-frame fields).

    Drawn above the bounding box (not below the feet, where the team/ID
    ellipse already sits) so it reads like an above-head broadcast-graphic
    label instead of competing for space with the ID marker, and stays
    clear of a crowded penalty box where several players' feet are close
    together but their heads usually aren't."""
    x1, y1, x2, _ = (int(v) for v in bbox)
    center_x = (x1 + x2) // 2
    # Clears draw_possession_marker's triangle (drawn from y1-4 to y1-18
    # when this player has the ball) so the two never overlap regardless
    # of possession state.
    base_y = y1 - 24

    # Speed sits closest to the head, distance stacks above that — climbing
    # upward from base_y so neither line overlaps the player's box.
    for offset, text in enumerate((f"{speed_kmh:.2f} km/h", f"{distance_m:.2f} m")):
        (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
        text_y = base_y - offset * 14
        # Small dark backing box so white text stays legible against a
        # bright pitch/crowd background, same reasoning as the ID label's
        # filled rectangle below the feet.
        cv2.rectangle(
            frame,
            (center_x - text_w // 2 - 2, text_y - text_h - 2),
            (center_x + text_w // 2 + 2, text_y + 2),
            (0, 0, 0),
            cv2.FILLED,
        )
        cv2.putText(
            frame, text, (center_x - text_w // 2, text_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA,
        )
    return frame


def draw_possession_banner(frame: np.ndarray, possession_pct: dict[str, float] | None) -> np.ndarray:
    """Semi-transparent 'Team A/B Ball Control: XX.XX%' box baked into the
    bottom-right of the frame, same style as the reference implementation
    this pipeline was built from (training/football-players-detection,
    trackers/tracker.py draw_team_ball_control). The caller passes the
    running percentage through this frame, not the final match-wide
    figure, so the number updates as the video plays like a live
    broadcast graphic — see run_pipeline.py's possession_running_by_frame."""
    if not possession_pct:
        return frame

    height, width = frame.shape[:2]
    box_w, box_h = min(430, width - 40), 90
    x1, y1 = width - box_w - 20, height - box_h - 20

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x1 + box_w, y1 + box_h), (0, 0, 0), cv2.FILLED)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

    cv2.putText(
        frame, f"Team A Ball Control: {possession_pct.get('Team A', 0.0):.2f}%",
        (x1 + 15, y1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA,
    )
    cv2.putText(
        frame, f"Team B Ball Control: {possession_pct.get('Team B', 0.0):.2f}%",
        (x1 + 15, y1 + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA,
    )
    return frame


def annotate_frame(
    frame: np.ndarray,
    frame_index: int,
    tracks: dict[int, dict[int, dict]],
    team_by_id: dict[int, str],
    ball_positions: dict[int, tuple[float, float]],
    overlay_flags: dict[str, bool] | None = None,
    id_labels: dict[int, int] | None = None,
    ball_possession: dict[int, int] | None = None,
    live_stats: dict[int, dict[int, tuple[float, float]]] | None = None,
    possession_pct: dict[str, float] | None = None,
) -> np.ndarray:
    """overlay_flags mirrors the frontend's overlay toggles (PRD section 21):
    {"players": bool, "player_ids": bool, "ball": bool, "referee": bool}

    id_labels maps raw tracker IDs to display IDs: for players, the
    team-relative ID (1-N per team) shown everywhere else in the app —
    statistics table, charts, JSON export; for referees, their own
    separate small sequential number (1, 2, 3...), since referees aren't
    numbered in player statistics at all but still need a clean label
    here rather than falling back to BoT-SORT's raw track id (which can
    run into the hundreds over a longer clip). A raw tracker ID not in
    id_labels at all (shouldn't normally happen) falls back to itself.

    ball_possession maps frame_index -> raw tracking_id of whichever player
    is currently closest to the ball (see ball_possession.py); that player
    gets a small marker above their head.

    live_stats maps raw tracking_id -> {frame_index: (speed_kmh, distance_m)}
    (see run_pipeline.py) for a live per-player readout; empty/omitted when
    the video isn't pitch-calibrated, same as statistics.json's players.

    possession_pct is {"Team A": pct, "Team B": pct} shown as a banner
    (unlike the per-player overlays, not gated by overlay_flags — it isn't
    tied to any one player). The caller decides whether this is the
    running possession-so-far for this specific frame or the final
    match-wide figure; run_pipeline.py passes the running one so the video
    reads like a live broadcast graphic.
    """
    flags = overlay_flags or {"players": True, "player_ids": True, "ball": True, "referee": True}
    id_labels = id_labels or {}
    ball_possession = ball_possession or {}
    live_stats = live_stats or {}
    possessor_id = ball_possession.get(frame_index)
    annotated = frame.copy()

    for tracking_id, track in tracks.items():
        frame_data = track.get(frame_index)
        if frame_data is None:
            continue

        class_name = frame_data["class_name"]
        if class_name == "referee":
            if not flags.get("referee", True):
                continue
            color = TEAM_COLORS["Referee"]
        else:
            if not flags.get("players", True):
                continue
            team = team_by_id.get(tracking_id, "Team A")
            color = TEAM_COLORS.get(team, TEAM_COLORS["Team A"])

        display_id = id_labels.get(tracking_id, tracking_id)
        label = display_id if flags.get("player_ids", True) else ""
        annotated = draw_player_ellipse(annotated, frame_data["bbox"], color, label)
        if flags.get("players", True) and tracking_id == possessor_id:
            annotated = draw_possession_marker(annotated, frame_data["bbox"])

        player_stats = live_stats.get(tracking_id, {}).get(frame_index)
        if class_name != "referee" and player_stats is not None:
            speed_kmh, distance_m = player_stats
            annotated = draw_live_stats(annotated, frame_data["bbox"], speed_kmh, distance_m)

    if flags.get("ball", True) and frame_index in ball_positions:
        annotated = draw_ball_marker(annotated, ball_positions[frame_index])

    annotated = draw_possession_banner(annotated, possession_pct)

    return annotated
