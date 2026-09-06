"""PitchTrack backend (PRD section 33) — FastAPI, no database.

Run from the project root (needed so `app.pipeline` imports resolve):
    uvicorn app.backend.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import calibration, export, processing, results, upload

app = FastAPI(title="PitchTrack API", version="0.1.0")

# Vite's dev server picks whatever port is free (5173 by default, but
# auto-increments if that's already taken by an unrelated process on the
# machine — see .claude/launch.json's "autoPort") rather than a single
# fixed port, so this matches any localhost dev-server port instead of
# hardcoding 5173. Tighten this to a specific origin allowlist for
# production.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(calibration.router)
app.include_router(processing.router)
app.include_router(results.router)
app.include_router(export.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
