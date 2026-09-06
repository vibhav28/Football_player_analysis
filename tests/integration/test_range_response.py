"""app/backend/services/range_response.py — the custom Range/206 support
that replaced Starlette's FileResponse (which ignored Range entirely, see
that module's docstring). Regression coverage for a real bug found during a
full-codebase review: a suffix-range request (`bytes=-N`) served the wrong
end of the file. (A second fix in the same pass — offloading blocking file
reads to a thread so they don't stall the event loop — isn't directly
testable here; a routing-layer check confirmed this project's FastAPI
routes reject HEAD with 405 before reaching this module at all, so no
HEAD-specific handling was needed here despite an initial review finding
suggesting otherwise.)"""

from fastapi.testclient import TestClient

from app.backend.main import app

client = TestClient(app)


def _upload(tiny_video):
    with open(tiny_video, "rb") as f:
        return client.post("/api/videos/upload", files={"file": ("clip.mp4", f, "video/mp4")})


def test_full_request_returns_whole_file_with_accept_ranges(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]
    full_bytes = tiny_video.read_bytes()

    resp = client.get(f"/api/videos/{video_id}/video")

    assert resp.status_code == 200
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.content == full_bytes


def test_normal_byte_range_returns_206_with_requested_slice(isolated_storage, tiny_video):
    video_id = _upload(tiny_video).json()["video_id"]
    full_bytes = tiny_video.read_bytes()

    resp = client.get(f"/api/videos/{video_id}/video", headers={"Range": "bytes=0-9"})

    assert resp.status_code == 206
    assert resp.content == full_bytes[0:10]
    assert resp.headers["content-range"] == f"bytes 0-9/{len(full_bytes)}"


def test_suffix_range_returns_last_bytes_not_first(isolated_storage, tiny_video):
    """Regression test: `Range: bytes=-500` (RFC 7233 suffix-range syntax
    for "the last 500 bytes") used to be parsed as start=0, silently
    serving the FIRST 500 bytes with a 206 the client reads as success."""
    video_id = _upload(tiny_video).json()["video_id"]
    full_bytes = tiny_video.read_bytes()
    suffix_length = 10
    assert len(full_bytes) > suffix_length  # otherwise this test proves nothing

    resp = client.get(f"/api/videos/{video_id}/video", headers={"Range": f"bytes=-{suffix_length}"})

    assert resp.status_code == 206
    assert resp.content == full_bytes[-suffix_length:]
    assert resp.content != full_bytes[:suffix_length]


