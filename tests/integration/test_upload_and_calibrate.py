"""API-level regression coverage for the upload -> calibrate -> processing
handoff (see app/backend/routers/upload.py and calibration.py). This is
exactly the seam where a real bug shipped earlier in this project
(pitch_pixel_corners required but never passed in, which made every real
video processing run fail) - these tests exist so that class of bug fails
a test run instead of only turning up when someone uploads a real video.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.backend.main import app

client = TestClient(app)


def _upload(tiny_video):
    with open(tiny_video, "rb") as f:
        return client.post("/api/videos/upload", files={"file": ("clip.mp4", f, "video/mp4")})


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_rejects_unsupported_extension(isolated_storage):
    resp = client.post(
        "/api/videos/upload", files={"file": ("clip.txt", b"not a video", "text/plain")}
    )
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_upload_rejects_empty_file(isolated_storage, tmp_path):
    resp = client.post("/api/videos/upload", files={"file": ("clip.mp4", b"", "video/mp4")})
    assert resp.status_code == 400


def test_upload_accepts_valid_video_and_stays_in_uploaded_status(isolated_storage, tiny_video):
    resp = _upload(tiny_video)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Uploaded"

    status_resp = client.get(f"/api/videos/{body['video_id']}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "Uploaded"


def test_upload_no_longer_auto_starts_processing(isolated_storage, tiny_video):
    """Regression guard: upload used to kick off processing immediately;
    calibration is now the step that does that (see calibration.py). If
    this regresses, users would skip the calibration prompt again."""
    with patch("app.backend.routers.upload.processing_manager.run_processing") as mock_run:
        _upload(tiny_video)
        mock_run.assert_not_called()


def test_calibrate_unknown_video_returns_404(isolated_storage):
    resp = client.post("/api/videos/doesnotexist/calibrate", json={"pitch_pixel_corners": None})
    assert resp.status_code == 404


def test_calibrate_rejects_wrong_corner_count(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]

    resp = client.post(
        f"/api/videos/{video_id}/calibrate",
        json={
            "pitch_pixel_corners": [
                {"x": 0, "y": 0, "time_seconds": 0},
                {"x": 1, "y": 1, "time_seconds": 0},
            ]
        },
    )
    assert resp.status_code == 400


def test_calibrate_starts_processing_with_corners_passed_through(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]
    corners = [
        {"x": 10, "y": 10, "time_seconds": 0},
        {"x": 100, "y": 10, "time_seconds": 0},
        {"x": 100, "y": 100, "time_seconds": 0},
        {"x": 10, "y": 100, "time_seconds": 0},
    ]

    with patch("app.backend.routers.calibration.processing_manager.run_processing") as mock_run:
        resp = client.post(f"/api/videos/{video_id}/calibrate", json={"pitch_pixel_corners": corners})

        assert resp.status_code == 200
        mock_run.assert_called_once()
        called_video_id, _called_path = mock_run.call_args.args
        called_corners = mock_run.call_args.kwargs["pitch_pixel_corners"]
        assert called_video_id == video_id
        assert [list(pt) for pt in called_corners] == [
            [c["x"], c["y"], c["time_seconds"]] for c in corners
        ]


def test_calibrate_accepts_skip_with_no_corners(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]

    with patch("app.backend.routers.calibration.processing_manager.run_processing") as mock_run:
        resp = client.post(f"/api/videos/{video_id}/calibrate", json={"pitch_pixel_corners": None})

        assert resp.status_code == 200
        assert mock_run.call_args.kwargs["pitch_pixel_corners"] is None


def test_calibrate_forwards_match_format_and_dimensions(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]

    with patch("app.backend.routers.calibration.processing_manager.run_processing") as mock_run:
        resp = client.post(
            f"/api/videos/{video_id}/calibrate",
            json={"pitch_pixel_corners": None, "match_format": "7v7"},
        )

        assert resp.status_code == 200
        assert mock_run.call_args.kwargs["players_per_team"] == 7
        assert mock_run.call_args.kwargs["pitch_width_m"] == 40.0
        assert mock_run.call_args.kwargs["pitch_length_m"] == 60.0


def test_calibrate_custom_dimensions_override_preset(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]

    with patch("app.backend.routers.calibration.processing_manager.run_processing") as mock_run:
        resp = client.post(
            f"/api/videos/{video_id}/calibrate",
            json={"pitch_pixel_corners": None, "match_format": "9v9", "pitch_width_m": 55.0},
        )

        assert resp.status_code == 200
        assert mock_run.call_args.kwargs["players_per_team"] == 9
        assert mock_run.call_args.kwargs["pitch_width_m"] == 55.0
        assert mock_run.call_args.kwargs["pitch_length_m"] == 82.0


def test_calibrate_rejects_out_of_range_players_per_team(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]

    resp = client.post(
        f"/api/videos/{video_id}/calibrate",
        json={"pitch_pixel_corners": None, "players_per_team": 0},
    )
    assert resp.status_code == 400


def test_full_lifecycle_reaches_completed_and_rejects_second_calibration(
    isolated_storage, tiny_video, monkeypatch
):
    """End-to-end through the real background task (not mocked), using the
    mock CV pipeline so it stays fast and doesn't need a trained model.
    Confirms the job actually leaves 'Uploaded' status, and that
    calibration can't be submitted twice for the same video."""
    monkeypatch.setattr("app.backend.services.processing_manager.USE_MOCK_PIPELINE", True)

    video_id = _upload(tiny_video).json()["video_id"]

    first = client.post(f"/api/videos/{video_id}/calibrate", json={"pitch_pixel_corners": None})
    assert first.status_code == 200

    status_resp = client.get(f"/api/videos/{video_id}/status")
    assert status_resp.json()["status"] == "Completed"

    second = client.post(f"/api/videos/{video_id}/calibrate", json={"pitch_pixel_corners": None})
    assert second.status_code == 409
