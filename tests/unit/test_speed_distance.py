"""app/pipeline/speed_distance.py — sliding-window speed + accumulated
distance from a per-frame position track already in meters."""

import pytest

from app.pipeline.speed_distance import compute_player_movement


def test_stationary_player_has_zero_speed_and_distance():
    positions = {f: (10.0, 10.0) for f in range(10)}
    result = compute_player_movement(positions, fps=25.0)

    assert result["average_speed_kmh"] == 0.0
    assert result["total_distance_m"] == 0.0


def test_constant_velocity_gives_expected_speed():
    # 1 m/s along x, 25fps -> 0.04m per frame. 1 m/s = 3.6 km/h.
    fps = 25.0
    positions = {f: (f * (1.0 / fps), 0.0) for f in range(50)}

    result = compute_player_movement(positions, fps=fps)

    assert result["average_speed_kmh"] == pytest.approx(3.6, abs=0.05)
    assert result["maximum_speed_kmh"] == pytest.approx(3.6, abs=0.05)
    assert result["minimum_speed_kmh"] == pytest.approx(3.6, abs=0.05)


def test_total_distance_accumulates_frame_to_frame_not_window_to_window():
    # 3 points forming a right triangle: (0,0) -> (3,0) -> (3,4).
    # Frame-to-frame distance sums to 3 + 4 = 7, not the window-spanning
    # straight-line distance (0,0)->(3,4) = 5.
    positions = {0: (0.0, 0.0), 1: (3.0, 0.0), 2: (3.0, 4.0)}

    result = compute_player_movement(positions, fps=25.0)

    assert result["total_distance_m"] == pytest.approx(7.0, abs=1e-6)


def test_single_position_has_no_speed_data():
    result = compute_player_movement({0: (0.0, 0.0)}, fps=25.0)

    assert result["average_speed_kmh"] == 0.0
    assert result["per_frame_speed_kmh"] == {}


def test_implausible_speed_is_excluded_not_clamped_to_the_ceiling():
    """Regression test: max_plausible_speed_kmh used to CLAMP an
    implausible reading down to the ceiling value, so a noisy jump and a
    genuine near-ceiling sprint both silently reported as the exact same
    number. It should instead exclude the implausible sample, so
    maximum_speed_kmh reflects only readings actually trusted as real."""
    fps = 25.0
    # Frame 0->1: a real, plausible 5 m/s (18 km/h) walk/jog.
    # Frame 1->2: an impossible 500m jump in one frame (noise) -> ~4500 km/h
    # implied speed, far past any plausible human ceiling.
    positions = {
        0: (0.0, 0.0),
        1: (5.0 / fps, 0.0),
        2: (5.0 / fps + 500.0, 0.0),
    }

    result = compute_player_movement(positions, fps=fps, max_plausible_speed_kmh=40.0)

    # The noisy frame must not appear as a flat 40.0 (the old clamp
    # behavior) or contribute its 500m to distance.
    assert 2 not in result["per_frame_speed_kmh"] or result["per_frame_speed_kmh"][2] != pytest.approx(
        40.0
    )
    assert all(v <= 40.0 for v in result["per_frame_speed_kmh"].values())
    assert result["total_distance_m"] < 10.0


def test_plausible_near_ceiling_speed_is_reported_as_measured():
    """A genuine sprint just under the ceiling must be reported at its real
    value, not silently pinned to the ceiling like every other capped
    reading would have been under the old clamp-based behavior."""
    fps = 25.0
    # 10 m/s = 36 km/h, comfortably real (see MAX_PLAUSIBLE_PLAYER_SPEED_KMH's
    # own comment: the real-world football record sits at ~38 km/h) and
    # under the 40 km/h ceiling.
    positions = {f: (f * (10.0 / fps), 0.0) for f in range(10)}

    result = compute_player_movement(positions, fps=fps, max_plausible_speed_kmh=40.0)

    assert result["maximum_speed_kmh"] == pytest.approx(36.0, abs=0.05)
