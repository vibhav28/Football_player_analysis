"""Camera motion estimation via Lucas-Kanade optical flow (PRD section 15).

Broadcast/sideline footage pans and zooms with play, which looks like
player movement if not corrected for. This tracks a handful of static
background features (frame edges, assumed to be advertising boards /
crowd rather than pitch) frame-to-frame and reports the camera's own
displacement so it can be subtracted from player positions before speed
and distance are calculated.
"""

import cv2
import numpy as np

LK_PARAMS = dict(
    winSize=(15, 15),
    maxLevel=2,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
)

FEATURE_PARAMS = dict(
    maxCorners=100,
    qualityLevel=0.3,
    minDistance=7,
    blockSize=7,
)

# Fraction of the frame height, from the top, assumed to be crowd/boards
# rather than pitch — a reasonable default for a raised sideline camera.
STATIC_REGION_HEIGHT_RATIO = 0.15


def _static_region_mask(frame_shape: tuple[int, int]) -> np.ndarray:
    height, width = frame_shape
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[: int(height * STATIC_REGION_HEIGHT_RATIO), :] = 255
    return mask


def estimate_camera_movement(frames: list) -> list[tuple[float, float]]:
    """Return per-frame (dx, dy) camera displacement, frame 0 = (0, 0)."""
    if not frames:
        return []

    movements: list[tuple[float, float]] = [(0.0, 0.0)]
    gray_prev = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    mask = _static_region_mask(gray_prev.shape)
    features_prev = cv2.goodFeaturesToTrack(gray_prev, mask=mask, **FEATURE_PARAMS)

    for i in range(1, len(frames)):
        gray_curr = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)

        if features_prev is None or len(features_prev) == 0:
            movements.append((0.0, 0.0))
            features_prev = cv2.goodFeaturesToTrack(gray_curr, mask=mask, **FEATURE_PARAMS)
            gray_prev = gray_curr
            continue

        features_curr, status, _ = cv2.calcOpticalFlowPyrLK(
            gray_prev, gray_curr, features_prev, None, **LK_PARAMS
        )

        good_prev = features_prev[status == 1]
        good_curr = features_curr[status == 1]

        if len(good_prev) == 0:
            movements.append((0.0, 0.0))
        else:
            displacement = (good_curr - good_prev).reshape(-1, 2)
            dx, dy = np.median(displacement, axis=0)
            movements.append((float(dx), float(dy)))

        gray_prev = gray_curr
        features_prev = cv2.goodFeaturesToTrack(gray_curr, mask=mask, **FEATURE_PARAMS)

    return movements


def compensate_position(
    position: tuple[float, float], cumulative_camera_movement: tuple[float, float]
) -> tuple[float, float]:
    """Subtract accumulated camera drift from a raw pixel position."""
    return (
        position[0] - cumulative_camera_movement[0],
        position[1] - cumulative_camera_movement[1],
    )
