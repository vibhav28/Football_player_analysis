"""Drives the Uploaded -> Processing -> Completed/Failed state machine
(PRD section 9.3) and the step checklist shown on the Processing screen
(PRD section 40, Screen 3).
"""

import multiprocessing

from ..config import MODEL_PATH, USE_MOCK_PIPELINE
from . import storage

STEP_NAMES = ["Player Detection", "Player Tracking", "Team Classification", "Speed Calculation"]


def _steps(status: str = "waiting") -> list[dict]:
    return [{"name": name, "status": status} for name in STEP_NAMES]


def mark_uploaded(video_id: str, original_filename: str) -> None:
    storage.write_job(
        video_id,
        {
            "video_id": video_id,
            "original_filename": original_filename,
            "status": "Uploaded",
            "error_message": None,
            "steps": _steps("waiting"),
        },
    )


def mark_processing(video_id: str) -> dict:
    """Flips job.json to "Processing" and returns the updated job dict.

    Called synchronously from the calibrate route BEFORE scheduling the
    background task — not just from inside run_processing() below — so
    that the HTTP response (which already says {"status": "Processing"})
    and job.json can never disagree. run_processing() used to be the only
    place this write happened, but that runs as a FastAPI BackgroundTask,
    which executes AFTER the response is already sent: a client polling
    GET /status immediately upon receiving the "Processing" response could
    still read the stale "Uploaded" job.json underneath it.
    """
    job = storage.read_job(video_id) or {}
    job["status"] = "Processing"
    job["steps"] = _steps("running")
    storage.write_job(video_id, job)
    return job


def _run_pipeline_in_subprocess(
    video_path: str,
    result_dir: str,
    model_path: str,
    mock: bool,
    pitch_pixel_corners: list[tuple[float, float, float]] | None,
    players_per_team: int | None,
    pitch_width_m: float | None,
    pitch_length_m: float | None,
    result_queue,
) -> None:
    """Runs in a fresh, spawned OS process, not a thread of the FastAPI
    server. Real video processing was found to reliably SIGSEGV the whole
    backend when run in-process: torch (via ultralytics) and scikit-learn
    each bring their own native OpenMP thread pool, and spinning those up
    from a background thread inside a multi-threaded ASGI server process
    is unsafe on macOS regardless of the KMP_DUPLICATE_LIB_OK mitigation
    in app/pipeline/__init__.py (which still applies here too — belt and
    suspenders). A genuinely separate process means torch/sklearn's native
    threading never has to coexist with uvicorn's own threads/event loop.
    """
    try:
        from app.pipeline import run_pipeline

        run_pipeline.run(
            video_path=video_path,
            result_dir=result_dir,
            model_path=model_path,
            mock=mock,
            pitch_pixel_corners=pitch_pixel_corners,
            players_per_team=players_per_team,
            target_width_m=pitch_width_m,
            target_length_m=pitch_length_m,
        )
        result_queue.put(("ok", None))
    except Exception as exc:  # noqa: BLE001 - message relayed to the parent process
        result_queue.put(("error", str(exc)))


def run_processing(
    video_id: str,
    video_path: str,
    pitch_pixel_corners: list[tuple[float, float, float]] | None = None,
    players_per_team: int | None = None,
    pitch_width_m: float | None = None,
    pitch_length_m: float | None = None,
) -> None:
    """Called from a FastAPI BackgroundTask (itself a background thread).
    Blocks that thread on the subprocess's completion — fine, since it
    isn't the thread serving HTTP requests. For longer videos this is the
    natural place to swap in a real job queue later (PRD section 34)
    without changing the CV pipeline itself.
    """
    job = mark_processing(video_id)

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_run_pipeline_in_subprocess,
        args=(
            video_path,
            storage.result_dir(video_id),
            MODEL_PATH,
            USE_MOCK_PIPELINE,
            pitch_pixel_corners,
            players_per_team,
            pitch_width_m,
            pitch_length_m,
            result_queue,
        ),
    )
    process.start()
    process.join()

    if not result_queue.empty():
        outcome, error_message = result_queue.get()
    elif process.exitcode != 0:
        # The subprocess died without reporting anything (crash, killed,
        # OOM) — a prior version of this crash used to leave the job stuck
        # on "Processing" forever with no explanation. Fail loudly instead.
        outcome, error_message = (
            "error",
            f"Processing stopped unexpectedly (exit code {process.exitcode}). "
            "This usually means the process crashed rather than raised a normal error.",
        )
    else:
        outcome, error_message = "ok", None

    if outcome == "ok":
        job["status"] = "Completed"
        job["steps"] = _steps("done")
        job["error_message"] = None
    else:
        job["status"] = "Failed"
        job["steps"] = _steps("failed")
        job["error_message"] = error_message

    storage.write_job(video_id, job)
