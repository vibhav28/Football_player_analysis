"""app/pipeline/perspective_transform.py — the homography math that real
speed/distance depends on entirely. If this is wrong, every number
downstream (speed_distance.py) is silently wrong too, so it's worth
pinning down exactly with a case where the right answer is obvious."""

import pytest

from app.pipeline.perspective_transform import PITCH_LENGTH_M, PITCH_WIDTH_M, PerspectiveTransformer


def test_requires_exactly_four_corners():
    with pytest.raises(ValueError):
        PerspectiveTransformer([(0, 0), (1, 1), (2, 2)])


def test_corners_map_to_pitch_corners():
    # A simple axis-aligned 100x100 pixel square standing in for the pitch.
    pixel_corners = [(0, 0), (100, 0), (100, 100), (0, 100)]
    transformer = PerspectiveTransformer(pixel_corners)

    top_left = transformer.transform_point((0, 0))
    bottom_right = transformer.transform_point((100, 100))

    assert top_left == pytest.approx((0.0, 0.0), abs=1e-3)
    assert bottom_right == pytest.approx((PITCH_WIDTH_M, PITCH_LENGTH_M), abs=1e-3)


def test_center_point_maps_to_pitch_center():
    pixel_corners = [(0, 0), (100, 0), (100, 100), (0, 100)]
    transformer = PerspectiveTransformer(pixel_corners)

    center = transformer.transform_point((50, 50))

    assert center == pytest.approx((PITCH_WIDTH_M / 2, PITCH_LENGTH_M / 2), abs=1e-3)


def test_point_far_outside_calibrated_region_is_rejected():
    pixel_corners = [(0, 0), (100, 0), (100, 100), (0, 100)]
    transformer = PerspectiveTransformer(pixel_corners)

    # Wildly outside the 0-100 calibrated square -> maps far outside the
    # pitch + margin, per the docstring's stated extrapolation limit.
    assert transformer.transform_point((100_000, 100_000)) is None


def test_custom_target_dimensions_are_respected():
    # A calibration against a smaller known rectangle (e.g. some other
    # reference region) should scale to that region's real dimensions,
    # not the default full-pitch ones.
    pixel_corners = [(0, 0), (10, 0), (10, 10), (0, 10)]
    transformer = PerspectiveTransformer(pixel_corners, target_width_m=5.0, target_length_m=5.0)

    assert transformer.transform_point((10, 10)) == pytest.approx((5.0, 5.0), abs=1e-3)


def test_margin_check_uses_instance_target_dimensions_not_global_default():
    # Regression test: transform_point's out-of-bounds margin check used to
    # validate against the module-level PITCH_WIDTH_M/PITCH_LENGTH_M globals
    # (68/105) regardless of what target_width_m/target_length_m were
    # actually passed to this instance, so a point far outside a smaller
    # custom pitch (e.g. a real 7-a-side pitch) was silently accepted as
    # long as it fell within the much larger 11-a-side default.
    pixel_corners = [(0, 0), (10, 0), (10, 10), (0, 10)]
    transformer = PerspectiveTransformer(pixel_corners, target_width_m=20.0, target_length_m=40.0)

    # Maps to (30, 20): outside this 20m-wide pitch + 5m margin (bound
    # -5..25), but well inside the old global 68m bound (-5..73) the bug
    # would have checked against instead.
    assert transformer.transform_point((15, 5)) is None
