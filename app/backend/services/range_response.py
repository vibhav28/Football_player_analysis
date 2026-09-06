"""HTTP Range support for serving video files (RFC 7233).

Starlette's FileResponse (as pinned in this project) always sends the whole
file with a 200, ignoring any Range header — verified directly: a
`curl -H "Range: bytes=0-1023"` against /video still came back 200 with the
full content-length, no Accept-Ranges/206 at all. Browsers rely on Range
support to seek a <video> element without downloading the entire file first;
without it, scrubbing (e.g. the pitch calibration page, PRD section 35)
either has to wait for a full download or behaves unreliably once a partial
fetch gets interrupted by navigation. This implements the single-range
subset that browsers actually send for video seeking.
"""

import os
import re

import anyio
from fastapi import Request
from starlette.responses import Response, StreamingResponse

CHUNK_SIZE = 1024 * 1024
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


async def _file_chunks(path: str, start: int, end: int):
    # Reads run via anyio.to_thread.run_sync rather than a plain blocking
    # f.read() — this generator runs on FastAPI's single asyncio event
    # loop, and a synchronous disk read of up to CHUNK_SIZE would stall
    # every other in-flight request (status polls, other uploads) for its
    # duration. Verified this matters here specifically: uploads can be up
    # to 2GB (PRD section 9.2) and the calibration page now has users
    # interactively scrubbing the raw video, not just watching an
    # already-finished clip, so this path sees real concurrent traffic.
    def _open_and_seek():
        f = open(path, "rb")
        f.seek(start)
        return f

    f = await anyio.to_thread.run_sync(_open_and_seek)
    try:
        remaining = end - start + 1
        while remaining > 0:
            chunk = await anyio.to_thread.run_sync(f.read, min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        f.close()


def range_file_response(request: Request, path: str, media_type: str = "video/mp4") -> Response:
    file_size = os.path.getsize(path)
    range_header = request.headers.get("range")

    if range_header is None:
        headers = {"content-length": str(file_size), "accept-ranges": "bytes"}
        # No Range header: stream the whole file (uploads can be up to 2GB —
        # PRD section 9.2 — so this must not read it all into memory at
        # once), but advertise Range support so the browser knows it can
        # ask for a byte range on the next request (e.g. once it seeks).
        return StreamingResponse(
            _file_chunks(path, 0, file_size - 1), media_type=media_type, headers=headers
        )

    match = RANGE_RE.match(range_header)
    if not match or (not match.group(1) and not match.group(2)):
        return Response(status_code=416, headers={"content-range": f"bytes */{file_size}"})

    start_str, end_str = match.groups()
    if start_str == "":
        # Suffix-range form (RFC 7233): "bytes=-500" means "the last 500
        # bytes of the file", NOT "byte 0 through byte 500" — treating an
        # empty start as 0 silently served the wrong 500 bytes (the start
        # of the file instead of the end) with a 206 the client reads as
        # success. Some MP4 parsers/players probe the tail of the file
        # this way (looking for a trailing moov atom on non-faststart
        # files), so this isn't just a theoretical RFC nuance here.
        suffix_length = int(end_str)
        start = max(0, file_size - suffix_length)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
    end = min(end, file_size - 1)

    if start > end or start >= file_size:
        return Response(status_code=416, headers={"content-range": f"bytes */{file_size}"})

    content_length = end - start + 1
    headers = {
        "content-range": f"bytes {start}-{end}/{file_size}",
        "content-length": str(content_length),
        "accept-ranges": "bytes",
    }
    return StreamingResponse(
        _file_chunks(path, start, end), status_code=206, media_type=media_type, headers=headers
    )
