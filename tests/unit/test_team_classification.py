"""app/pipeline/team_classification.py — regression coverage for the two
concrete bugs this module already had and was fixed for (see its own
docstrings): "larger cluster = jersey" picking background instead of
jersey color, and a real 68/4 broken split before the torso-crop +
lowest-variance fix. These tests pin the fixed behavior down so it can't
silently regress again."""

import numpy as np

from app.pipeline.team_classification import _kmeans_fit, assign_teams, get_player_color

RED = np.array([200, 20, 20], dtype=np.uint8)
BLUE = np.array([20, 20, 200], dtype=np.uint8)
GREEN_PITCH = np.array([40, 120, 40], dtype=np.uint8)  # stand-in for grass/background


def _solid_frame(height=100, width=100, color=GREEN_PITCH):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = color
    return frame


def _paint_bbox(frame, bbox, color):
    x1, y1, x2, y2 = (int(v) for v in bbox)
    frame[y1:y2, x1:x2] = color
    return frame


def test_kmeans_separates_two_distinct_clusters():
    rng = np.random.default_rng(0)
    cluster_a = rng.normal(loc=[0, 0, 0], scale=1.0, size=(50, 3))
    cluster_b = rng.normal(loc=[100, 100, 100], scale=1.0, size=(50, 3))
    data = np.vstack([cluster_a, cluster_b])

    labels, centers = _kmeans_fit(data, n_clusters=2)

    # The 50 points from each cluster must all end up under the same label.
    assert len(set(labels[:50])) == 1
    assert len(set(labels[50:])) == 1
    assert labels[0] != labels[50]


def test_player_color_picks_jersey_even_when_background_dominates_bbox():
    # Regression test for the exact bug described in team_classification.py:
    # a small jersey patch surrounded by more background pixels than
    # jersey pixels within the naive full-bbox crop. get_player_color
    # narrows to the torso band specifically to avoid this.
    frame = _solid_frame(200, 200, color=GREEN_PITCH)
    bbox = (50, 50, 80, 150)  # 30x100 player box
    # Paint the torso band (per get_player_color: x 20%-80%, y 15%-55% of bbox)
    torso_color = RED
    frame = _paint_bbox(frame, (56, 65, 74, 105), torso_color)

    sampled = get_player_color(frame, bbox)

    # Sampled color should be much closer to the jersey (red) than to the
    # green background that still dominates the bbox as a whole.
    assert np.linalg.norm(sampled - RED) < np.linalg.norm(sampled - GREEN_PITCH)


def test_assign_teams_splits_two_visually_distinct_kits():
    frame = _solid_frame(200, 200, color=GREEN_PITCH)
    frame = _paint_bbox(frame, (10, 10, 30, 60), RED)
    frame = _paint_bbox(frame, (100, 10, 120, 60), BLUE)
    frames = [frame]

    tracks = {
        1: {0: {"bbox": (10, 10, 30, 60), "class_name": "player"}},
        2: {0: {"bbox": (100, 10, 120, 60), "class_name": "player"}},
    }

    team_by_id = assign_teams(frames, tracks)

    assert team_by_id[1] != team_by_id[2]


def test_assign_teams_single_player_defaults_to_team_a():
    frame = _solid_frame()
    tracks = {1: {0: {"bbox": (10, 10, 30, 60), "class_name": "player"}}}

    team_by_id = assign_teams([frame], tracks)

    assert team_by_id == {1: "Team A"}
