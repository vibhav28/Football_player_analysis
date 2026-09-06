"""app/backend/services/filtering.py's time-window filter — the seam where
a real bug was found during a full-codebase review: recomputing speed from
positions.json without checking whether the video was pitch-calibrated.
positions.json holds raw pixel foot-coordinates (not meters) for an
uncalibrated video, so treating them as meters silently fabricates
non-zero-looking speed/distance numbers instead of the honest 0 the
full-match statistics.json already reports for the same video."""

import json

import pytest

from app.backend.services import filtering, storage


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    monkeypatch.setattr(storage, "RESULTS_DIR", str(results_dir))
    monkeypatch.setattr(storage, "UPLOAD_DIR", str(tmp_path / "uploads"))
    return results_dir


def _write_result(video_id, results_dir, *, pitch_calibrated, positions):
    video_dir = results_dir / video_id
    video_dir.mkdir()
    statistics = {
        "video": {"filename": f"{video_id}.mp4", "duration": 10.0, "fps": 25.0, "pitch_calibrated": pitch_calibrated},
        "players": [{"tracking_id": 1, "team": "Team A", "average_speed_kmh": 0.0, "minimum_speed_kmh": 0.0, "maximum_speed_kmh": 0.0, "total_distance_m": 0.0}],
        "ball": None,
        "possession": None,
    }
    (video_dir / "statistics.json").write_text(json.dumps(statistics))
    (video_dir / "positions.json").write_text(json.dumps(positions))


def test_time_window_reports_zero_speed_when_not_pitch_calibrated(isolated_storage):
    # A large, fast-looking pixel jump — if ever mistaken for meters, this
    # would compute as an obviously-fabricated high speed instead of 0.
    positions = {"Team A_1": {"0": {"x": 0.0, "y": 0.0}, "5": {"x": 500.0, "y": 0.0}}}
    _write_result("vid1", isolated_storage, pitch_calibrated=False, positions=positions)

    result = filtering.get_filtered_statistics("vid1", start_time=0, end_time=1)

    assert result["players"][0]["average_speed_kmh"] == 0.0
    assert result["players"][0]["maximum_speed_kmh"] == 0.0
    assert result["players"][0]["total_distance_m"] == 0.0


def test_time_window_computes_real_speed_when_pitch_calibrated(isolated_storage):
    # Same shape of data, but now legitimately in meters (pitch_calibrated
    # True): 0.2m over 5 frames @ 25fps (0.2s) = 1 m/s = 3.6 km/h, a
    # plausible human walking speed well under the plausibility ceiling —
    # confirming the fix computes a real value here, not just zeroing out
    # everything regardless of calibration state.
    positions = {"Team A_1": {"0": {"x": 0.0, "y": 0.0}, "5": {"x": 0.2, "y": 0.0}}}
    _write_result("vid2", isolated_storage, pitch_calibrated=True, positions=positions)

    result = filtering.get_filtered_statistics("vid2", start_time=0, end_time=1)

    assert result["players"][0]["average_speed_kmh"] == pytest.approx(3.6, abs=0.05)
