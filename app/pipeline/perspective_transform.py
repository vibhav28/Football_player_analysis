"""Pixel-to-meter perspective transform (PRD section 16).

Maps pixel coordinates on the broadcast/sideline image to approximate
real-world pitch coordinates in meters, via a homography fit from four
known pitch reference points (e.g. penalty box corners) to their real
FIFA-standard positions.

The four pixel corners below are placeholders — they must be set per
video, since camera angle/zoom differs per match. A calibration step
(user clicks the four points, or a fixed camera preset) is expected
before this is usable; see PRD section 35, "Perspective Calibration
Failure" for the corresponding error case.
"""

import cv2
import numpy as np

# Standard football pitch dimensions in meters.
PITCH_WIDTH_M = 68.0
PITCH_LENGTH_M = 105.0


class PerspectiveTransformer:
    def __init__(
        self,
        pixel_corners: list[tuple[float, float]],
        target_width_m: float = PITCH_WIDTH_M,
        target_length_m: float = PITCH_LENGTH_M,
    ):
        """pixel_corners: 4 points in the source frame, ordered
        top-left, top-right, bottom-right, bottom-left, corresponding to
        a known rectangular region of the pitch (e.g. penalty area)."""
        if len(pixel_corners) != 4:
            raise ValueError("Perspective transform requires exactly 4 reference points")

        self.target_corners = np.array(
            [
                [0, 0],
                [target_width_m, 0],
                [target_width_m, target_length_m],
                [0, target_length_m],
            ],
            dtype=np.float32,
        )
        self.pixel_corners = np.array(pixel_corners, dtype=np.float32)
        self.matrix = cv2.getPerspectiveTransform(self.pixel_corners, self.target_corners)

    def transform_point(self, point: tuple[float, float]) -> tuple[float, float] | None:
        point_array = np.array([[point]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(point_array, self.matrix)
        x, y = transformed[0][0]

        # Reject points that fall outside a reasonable margin of the
        # calibrated region — perspective extrapolation gets unreliable
        # far from the reference points.
        margin = 5.0
        if not (-margin <= x <= PITCH_WIDTH_M + margin and -margin <= y <= PITCH_LENGTH_M + margin):
            return None

        return float(x), float(y)
