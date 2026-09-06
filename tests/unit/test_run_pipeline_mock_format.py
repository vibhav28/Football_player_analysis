"""app/pipeline/run_pipeline.py's mock mode (mock=True) — used for
backend/frontend dev without a trained model. Confirms players_per_team
threads through to the fabricated statistics the same way it will for the
real pipeline path (run_pipeline.run's players_per_team param), and that
the dev-only default (MOCK_DEFAULT_PLAYERS_PER_TEAM) stays pinned so a
future edit has to consciously change this test too, not silently drift."""

import json

import cv2
import numpy as np
import pytest

from app.pipeline import run_pipeline


@pytest.fixture
def tiny_video(tmp_path):
    path = tmp_path / "tiny.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 5.0, (64, 48))
    for _ in range(10):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    return path


def _players_per_team(statistics_path):
    with open(statistics_path) as f:
        players = json.load(f)["players"]
    counts = {}
    for p in players:
        counts[p["team"]] = counts.get(p["team"], 0) + 1
    return counts


def test_mock_pipeline_respects_explicit_players_per_team(tiny_video, tmp_path):
    result_dir = tmp_path / "result"
    run_pipeline.run(str(tiny_video), str(result_dir), mock=True, players_per_team=11)

    counts = _players_per_team(result_dir / "statistics.json")
    assert counts == {"Team A": 11, "Team B": 11}


def test_mock_pipeline_default_players_per_team_is_seven(tiny_video, tmp_path):
    result_dir = tmp_path / "result"
    run_pipeline.run(str(tiny_video), str(result_dir), mock=True)

    counts = _players_per_team(result_dir / "statistics.json")
    assert counts == {"Team A": 7, "Team B": 7}
    assert run_pipeline.MOCK_DEFAULT_PLAYERS_PER_TEAM == 7
