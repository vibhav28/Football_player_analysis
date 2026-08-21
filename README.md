# PitchTrack

Turn an ordinary pre-recorded football video into player movement analytics using
Computer Vision — no wearables, no GPS trackers, no database (yet).

Full requirements: see `PRD.md`. This README covers what's scaffolded.
For step-by-step setup and a walkthrough with the included sample video, see [`USAGE.md`](USAGE.md).
To train the YOLOv8 model real detection needs, see [`TRAINING.md`](TRAINING.md).

## Status

MVP with a trained model wired in (`app/pipeline/models/best.pt`, `USE_MOCK_PIPELINE = False`
in `app/backend/config.py`) — real YOLOv8 detection + ByteTrack + K-Means team
classification, not mock data. No database — local filesystem + JSON, per PRD section 27.
A database (Django + ORM) is only introduced if criteria in PRD section 30 are met.

Speed/distance are 0 until the video is pitch-calibrated (no calibration UI yet — see
`TRAINING.md` §7); tracking, team classification, and the annotated video work without it.

## Layout

```
pitchtrack/
├── app/
│   ├── frontend/     React + Vite dashboard
│   ├── backend/      FastAPI upload/processing/results/export API
│   └── pipeline/     CV pipeline: YOLOv8 + ByteTrack + K-Means + optical flow
├── training/         Dataset + yolo run history (gitignored — see TRAINING.md)
├── uploads/          Raw uploaded videos
├── results/          Per-video output: players.json, positions.json, statistics.json, annotated.mp4
└── temp/             Scratch files during processing
```

## Setup

### Backend

Run from the **project root** (not `app/backend`) — the backend imports the
CV pipeline as `app.pipeline`, so it needs to run as part of the `app` package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.backend.main:app --reload --port 8000
```

### Frontend

```bash
cd app/frontend
npm install
npm run dev
```

Frontend expects the backend at `http://localhost:8000` (see `app/frontend/src/api/client.js`).

### CV Pipeline — model weights

`app/pipeline/models/best.pt` holds the trained YOLOv8 weights (player/ball/referee +
goalkeeper, aliased to player — see `TRAINING.md` §3). Training history and the dataset
live in `training/` — see `TRAINING.md` for how that model was produced and how to
retrain or swap it.

To fall back to mock output (no model needed) for backend/frontend work unrelated to the
CV pipeline itself, set `USE_MOCK_PIPELINE = True` in `app/backend/config.py` — this
produces a structurally valid `statistics.json` / `positions.json` / `players.json`
without running any CV.

## Development order (per PRD section 50)

1. Make the CV pipeline work on a single test video (`app/pipeline/`)
2. Produce `statistics.json` + `annotated.mp4`
3. Backend endpoints (`app/backend/`) — done as scaffold, wire up to real pipeline output
4. Frontend upload → processing → dashboard flow (`app/frontend/`) — scaffolded
5. Filters, export, error handling
6. Evaluate whether a database is actually needed (PRD section 30) before adding one

## Explicitly out of scope for v1

No live video/webcam/RTMP, no face/jersey-number identity recognition, no tactical event
detection (passes/shots/goals/offside), no multi-camera support, no login/accounts. See
PRD section 6.
