"""PitchTrack backend (PRD section 33) — FastAPI, no database.

Run from the project root (needed so `app.pipeline` imports resolve):
    uvicorn app.backend.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import export, processing, results, upload

app = FastAPI(title="PitchTrack API", version="0.1.0")

# Vite's default dev server port; adjust/add origins for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(processing.router)
app.include_router(results.router)
app.include_router(export.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
