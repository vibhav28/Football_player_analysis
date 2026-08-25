"""Restricts tracking to the field of play, so people outside the pitch —
subs bench, crowd, staff, ball boys near the touchline — never get a
tracking ID in the first place, instead of being tracked and only
filtered out later (or not at all).

There's no pitch-line detection in this pipeline, so this is a rectangular
pixel-space inset rather than a true trapezoidal pitch outline — cheap,
requires no calibration, and catches the common case (crowd/scoreboard at
the top of the frame, advertising boards at the sides). Tune FIELD_MARGIN
per camera angle: a raised sideline camera typically has the most bleed at
the top of the frame and the least at the bottom (nearest touchline).

For a geometrically correct trapezoidal boundary, see
perspective_transform.py — once a video is calibrated with the pitch's own
corner points, PerspectiveTransformer.transform_point() already rejects
positions outside the pitch (+ a small margin) using the actual pitch
shape rather than a rectangle. This module is the cheap always-available
fallback for videos that aren't calibrated.
"""

from .detection import Detection
from .utils import get_foot_position

# Raised broadcast-style sideline cameras (crowd + stands + advertising
# boards above the pitch) were found to need a much larger top margin than
# a tight/pitch-side camera — a real match clip showed crowd/board content
# extending down to roughly 20-23% of frame height, not the ~6% originally
# assumed. Misdetections in that zone don't move, so they show up as
# suspiciously perfect full-video-length "phantom players" if not excluded.
# Still just a rectangular guess, not real pitch-line detection — re-tune
# per camera angle if false positives keep appearing near the top of frame.
FIELD_MARGIN = {
    "top": 0.22,
    "bottom": 0.0,
    "left": 0.02,
    "right": 0.02,
}


def field_boundary_box(
    frame_width: int, frame_height: int, margin: dict[str, float] | None = None
) -> tuple[float, float, float, float]:
    m = margin or FIELD_MARGIN
    x1 = frame_width * m["left"]
    x2 = frame_width * (1 - m["right"])
    y1 = frame_height * m["top"]
    y2 = frame_height * (1 - m["bottom"])
    return x1, y1, x2, y2


def is_within_field(
    point: tuple[float, float], boundary_box: tuple[float, float, float, float]
) -> bool:
    x, y = point
    x1, y1, x2, y2 = boundary_box
    return x1 <= x <= x2 and y1 <= y <= y2


def filter_detections_within_field(
    detections_per_frame: list[list[Detection]],
    frame_width: int,
    frame_height: int,
    margin: dict[str, float] | None = None,
) -> list[list[Detection]]:
    """Drop player/goalkeeper/referee detections whose foot position falls
    outside the field boundary. The ball is exempt — it legitimately
    reaches the touchline/goal line on corners, throw-ins, and goal kicks,
    and losing its track right when it goes out of play is worse than
    keeping a few boundary-adjacent detections.
    """
    boundary = field_boundary_box(frame_width, frame_height, margin)

    return [
        [
            d
            for d in frame_detections
            if d.class_name == "ball" or is_within_field(get_foot_position(d.bbox), boundary)
        ]
        for frame_detections in detections_per_frame
    ]
