# Using PitchTrack

This walks through setting up and running the PitchTrack MVP, using the
sample clip included in this folder (`08fd33_4.mp4` — 1920×1080, 25fps,
30s) to test the full upload → processing → dashboard → export flow.

For the product spec, see [`PRD.md`](PRD.md). For the file/folder layout,
see [`README.md`](README.md).

---

## 1. Prerequisites

* **Python 3.11–3.13** — recommended over 3.14. This machine's default
  `python3` resolves to 3.14, which is new enough that some CV packages
  (`opencv-python`, `ultralytics`) may not yet publish prebuilt wheels for
  it, forcing a slow from-source build or failing outright. Use
  `python3.13` explicitly when creating the virtual environment (installed
  at `/opt/homebrew/bin/python3.13` on this machine).
* **Node.js 18+** (this machine has v25, which is fine) and npm.
* A modern browser.

---

## 2. One-time setup

### Backend

Run from the **project root** — the backend imports the CV pipeline as
`app.pipeline`, so it must run as part of the `app` package.

```bash
cd "/Users/vibhavthakur/College/coding/projects/pitchtrack"
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If a `.venv` already exists but was created with Python 3.14 and
`pip install` fails on `opencv-python` or `ultralytics`, delete it and
recreate with `python3.13` as above:

```bash
rm -rf .venv
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend

```bash
cd "/Users/vibhavthakur/College/coding/projects/pitchtrack/app/frontend"
npm install
```

---

## 3. Running the app

Two terminals, both left running:

**Terminal 1 — backend** (from the project root):

```bash
source .venv/bin/activate
uvicorn app.backend.main:app --reload --port 8000
```

**Terminal 2 — frontend**:

```bash
cd app/frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 4. Try it with the sample video

1. On the Home screen, click **Upload Video**.
2. Drag in `08fd33_4.mp4` from the project root (or click to browse to it).
3. Click **Start Analysis**. You'll be moved to the Processing screen,
   which polls the backend every 2 seconds until it reports `Completed`.
4. You'll land on the **Analysis Workspace**:
   * Left: the annotated video with tracking overlays.
   * Right: the player stats table (tracking ID, team, avg/min/max speed,
     distance).
   * Top: team filter, player-ID search, overlay toggles.
   * Bottom: a time-window filter that recalculates stats for just that
     range.
5. Click **Export** (top right) to download the results as CSV, JSON, or
   the annotated video. CSV/JSON respect whatever filters were set on the
   Analysis screen.

### About the numbers you'll see

The pipeline currently runs in **mock mode** (`USE_MOCK_PIPELINE = True` in
[`app/backend/config.py`](app/backend/config.py)) — it generates
plausible-looking placeholder stats for ~14 players instead of running
real detection, because no trained YOLOv8 weights exist yet. This lets you
exercise the whole upload → dashboard → export flow before Phase 1 (the
actual CV pipeline) is finished. The annotated video download will be
missing in mock mode, since no frames are actually processed.

To switch to real processing once you have a model:

1. Train or acquire a YOLOv8 checkpoint that detects players/ball/referee,
   and place it at `app/pipeline/models/best.pt`.
2. Provide four pitch reference points (pixel coordinates of a known
   rectangular area, e.g. a penalty box) for perspective calibration —
   `run_pipeline.run()` currently expects these via `pitch_pixel_corners`;
   wiring a calibration UI/step is the next piece of work.
3. Set `USE_MOCK_PIPELINE = False` in `app/backend/config.py`.

---

## 5. Where things land on disk

```
uploads/<video_id>.mp4          the original upload
results/<video_id>/job.json     processing status (Uploaded/Processing/Completed/Failed)
results/<video_id>/statistics.json
results/<video_id>/positions.json
results/<video_id>/players.json
results/<video_id>/annotated.mp4
```

There's no database — this is the whole persistence layer (PRD section 27).
Deleting a video via the UI (or `DELETE /api/videos/{video_id}`) removes
all of the above for that ID.

---

## 6. API quick reference

All endpoints are under `http://localhost:8000`.

| Method | Path                                  | Purpose                                  |
|--------|----------------------------------------|-------------------------------------------|
| POST   | `/api/videos/upload`                   | Upload a video, kicks off processing      |
| GET    | `/api/videos`                          | List all processed videos                 |
| GET    | `/api/videos/{id}/status`              | Job status + processing step checklist    |
| GET    | `/api/videos/{id}/results`             | Player stats (supports `team`, `tracking_id`, `start_time`, `end_time` query params) |
| GET    | `/api/videos/{id}/positions`           | Raw per-player position data              |
| GET    | `/api/videos/{id}/video`               | Original uploaded video                   |
| GET    | `/api/videos/{id}/annotated`           | Annotated video with overlays             |
| GET    | `/api/videos/{id}/export/csv`          | CSV export (same filters as `/results`)   |
| GET    | `/api/videos/{id}/export/json`         | JSON export                               |
| GET    | `/api/videos/{id}/export/annotated-video` | Download annotated video               |
| DELETE | `/api/videos/{id}`                     | Cascade-delete video + all results        |

Interactive docs (Swagger UI) are available at
`http://localhost:8000/docs` whenever the backend is running.

---

## 7. Troubleshooting

* **Upload fails immediately with a format error** — only `.mp4`, `.mov`,
  `.avi` are accepted (PRD section 9.1).
* **Frontend can't reach the backend / CORS errors** — make sure the
  backend is running on port 8000 and the frontend on 5173; CORS is
  hardcoded to allow `http://localhost:5173` in `app/backend/main.py`.
* **`pip install` hangs or fails building `opencv-python`/`ultralytics`
  from source** — you're likely on Python 3.14; recreate the venv with
  `python3.13` (see Setup above).
* **Analysis page shows "Video is not ready"** — processing hasn't
  finished yet; wait for the Processing screen to redirect you, or check
  `GET /api/videos/{id}/status`.
* **Annotated video 404s in mock mode** — expected; mock mode skips frame
  rendering entirely (see section 4).
