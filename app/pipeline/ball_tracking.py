"""Ball detection + interpolation (PRD section 14).

The ball is small, fast, and frequently occluded, so raw YOLO detections
will have gaps. Missing frames are linearly interpolated between the
nearest known positions so the annotated video shows a continuous marker.
Ball data is for visualization only in the MVP — it does not feed
statistics.
"""

import pandas as pd

from .detection import Detection
from .utils import get_bbox_center


def extract_ball_positions(
    detections_per_frame: list[list[Detection]],
) -> dict[int, tuple[float, float]]:
    """Pick the highest-confidence ball detection per frame, if any."""
    positions: dict[int, tuple[float, float]] = {}
    for frame_index, frame_detections in enumerate(detections_per_frame):
        balls = [d for d in frame_detections if d.class_name == "ball"]
        if not balls:
            continue
        best = max(balls, key=lambda d: d.confidence)
        positions[frame_index] = get_bbox_center(best.bbox)
    return positions


def interpolate_ball_positions(
    positions: dict[int, tuple[float, float]], frame_count: int
) -> dict[int, tuple[float, float]]:
    """Fill gaps between known ball positions via linear interpolation.

    Frames before the first detection or after the last are back/forward
    filled rather than extrapolated.
    """
    df = pd.DataFrame(
        {
            "x": [positions.get(i, (None, None))[0] for i in range(frame_count)],
            "y": [positions.get(i, (None, None))[1] for i in range(frame_count)],
        }
    )
    df = df.interpolate(limit_direction="both")

    return {
        i: (row.x, row.y)
        for i, row in df.iterrows()
        if pd.notna(row.x) and pd.notna(row.y)
    }
