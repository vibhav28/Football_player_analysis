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


def annotate_frame(
    frame: np.ndarray,
    frame_index: int,
    tracks: dict[int, dict[int, dict]],
    team_by_id: dict[int, str],
    ball_positions: dict[int, tuple[float, float]],
    overlay_flags: dict[str, bool] | None = None,
    id_labels: dict[int, int] | None = None,
) -> np.ndarray:
    """overlay_flags mirrors the frontend's overlay toggles (PRD section 21):
    {"players": bool, "player_ids": bool, "ball": bool, "referee": bool}

    id_labels maps raw tracker IDs to the team-relative IDs (1-N per team)
    shown everywhere else in the app — statistics table, charts, JSON
    export — so the video overlay matches instead of showing raw ByteTrack
    IDs. Referees aren't in id_labels and fall back to their raw ID.
    """
    flags = overlay_flags or {"players": True, "player_ids": True, "ball": True, "referee": True}
    id_labels = id_labels or {}
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

    if flags.get("ball", True) and frame_index in ball_positions:
        annotated = draw_ball_marker(annotated, ball_positions[frame_index])

    return annotated
