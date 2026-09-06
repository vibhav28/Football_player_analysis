"""app/pipeline/detection.py's NMS handling — regression coverage for a
real bug found via a review of an actual annotated video: agnostic_nms=True
suppressed a real player's detection because its box overlapped a nearby
referee's box, treating two different real people as if one were a
duplicate detection of the other. The fix switches to per-class NMS
(agnostic_nms=False) plus a narrower second pass that still merges
player/goalkeeper duplicates on the same body (the original problem
agnostic NMS was meant to solve) without ever touching referee/ball."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from app.pipeline.detection import detect_frames


def _make_result(boxes_data):
    """boxes_data: list of (class_id, confidence, x1, y1, x2, y2)."""
    class_ids = torch.tensor([b[0] for b in boxes_data], dtype=torch.float32)
    confs = torch.tensor([b[1] for b in boxes_data], dtype=torch.float32)
    xyxy = torch.tensor([b[2:] for b in boxes_data], dtype=torch.float32)

    boxes = MagicMock()
    boxes.cls = class_ids
    boxes.conf = confs
    boxes.xyxy = xyxy
    boxes.__len__ = lambda self: len(boxes_data)

    result = MagicMock()
    result.names = {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}
    result.boxes = boxes
    return result


def _run_with_fake_predict(boxes_data):
    fake_result = _make_result(boxes_data)
    fake_model = MagicMock()
    fake_model.predict.return_value = [fake_result]

    with patch("app.pipeline.detection.load_model", return_value=fake_model):
        detections = detect_frames([np.zeros((10, 10, 3), dtype=np.uint8)], "fake_model_path")

    return detections[0], fake_model


def test_agnostic_nms_is_disabled_so_per_class_suppression_applies():
    _, fake_model = _run_with_fake_predict([(2, 0.9, 0, 0, 10, 10)])
    _, kwargs = fake_model.predict.call_args
    assert kwargs["agnostic_nms"] is False


def test_referee_overlapping_a_player_is_not_suppressed():
    """The actual bug: a referee (class 3) and a player (class 2) with
    heavily overlapping boxes -- two different real people -- must both
    survive, not have one suppressed as if it were a duplicate of the other."""
    detections = _run_with_fake_predict(
        [
            (2, 0.85, 100, 100, 150, 200),  # player
            (3, 0.90, 102, 100, 152, 200),  # referee, nearly identical box
        ]
    )[0]

    class_names = sorted(d.class_name for d in detections)
    assert class_names == ["player", "referee"]


def test_player_and_goalkeeper_duplicate_boxes_are_still_merged():
    """The original problem agnostic_nms was meant to fix: a player-class
    box and a goalkeeper-class box on the SAME real body (aliased to one
    class downstream) should still collapse to one detection."""
    detections = _run_with_fake_predict(
        [
            (2, 0.80, 100, 100, 150, 200),  # player
            (1, 0.85, 101, 100, 151, 200),  # goalkeeper, near-identical box
        ]
    )[0]

    assert len(detections) == 1
    assert detections[0].class_name == "player"  # goalkeeper aliases to player
    assert detections[0].confidence == pytest.approx(0.85)  # the higher-confidence box survives


def test_non_overlapping_player_and_goalkeeper_boxes_both_kept():
    detections = _run_with_fake_predict(
        [
            (2, 0.80, 0, 0, 20, 20),        # player, far away
            (1, 0.85, 500, 500, 520, 520),  # goalkeeper, unrelated location
        ]
    )[0]

    assert len(detections) == 2
