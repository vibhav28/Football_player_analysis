# PitchTrack — Session Capsule

## Executive Summary
PitchTrack is a football video analytics web app (upload → CV pipeline → player tracking/stats dashboard), built from a PRD to a working MVP in this session. The core pipeline now runs on a real trained YOLOv8 model — not mock data — after root-causing and fixing 10+ concrete bugs (a process-crashing OpenMP conflict, broken team classification, an unplayable video codec, missing calibration, and more), each verified by direct re-testing, not assumption. Biggest remaining gap: speed/distance always read 0 because pitch calibration was never implemented. Git version control is now in place (it wasn't for most of the session — was the top risk).

---

## 1. Project Scope
- **What**: Upload a pre-recorded football video → get player detection, tracking, team classification, speed/distance, and an annotated video with overlays.
- **Stack**: FastAPI backend (Python 3.13) · React+Vite frontend (JS, no TS) · CV pipeline: YOLOv8 (Ultralytics) + ByteTrack (`supervision`) + OpenCV + custom NumPy K-Means for team color.
- **Storage**: File-based only, no database — deliberate MVP-scope PRD decision (DB deferred until defined scale criteria are met).
- **Users**: Coaches, analysts, students, football enthusiasts. Single-operator, no auth/multi-user.
- **Owner**: Vibhav Thakur (solo).

## 2. Current Status
**Completed**: full backend/frontend/pipeline scaffold · real trained model deployed (`app/pipeline/models/best.pt`, run `train_full2`, 100 epochs, imgsz=1000) · team-relative player ID scheme · on-field boundary filtering · min-track-duration filtering · H.264 video output · fixed team-color classification · fake overlay/fake ball-stats removed · "not calibrated" UI notice · Recent Videos list on Home · git commits in place.

**In progress / not started**: pitch calibration UI (blocks real speed/distance) · automated tests (zero coverage) · ball-detection accuracy improvement (needs more data, not more epochs — plateaued).

## 3. Known Issues & Failures (root cause → fix)
- **Backend crashed (SIGSEGV) on real video processing** → two conflicting OpenMP runtimes (torch's bundled `libomp` + scikit-learn's Homebrew-linked one). Fixed: pipeline now runs in an isolated spawned process (crash can't take down the server; job fails gracefully instead of hanging), and scikit-learn's KMeans was replaced with a dependency-free NumPy implementation, removing the conflict entirely.
- **Real pipeline always failed** → `pitch_pixel_corners` was required but never passed in. Fixed: calibration is now optional; pipeline degrades gracefully (tracking/video work, speed/distance = 0 + `pitch_calibrated: false` flag).
- **Detection ran at wrong resolution** (640 default vs. training res) → fixed via explicit `IMG_SIZE`, kept in sync with whichever model is deployed.
- **`goalkeeper` class silently dropped from stats** → merged via `CLASS_NAME_ALIASES`.
- **72 spurious "players" on one 30s clip** → field-boundary margin too narrow (6% vs. real ~22% crowd bleed) + no min-track-duration filter. Fixed both; count → ~37.
- **Team classification badly broken (68/4 split)** → custom K-Means picked "larger cluster = jersey," but background pixels outnumber jersey pixels at small player sizes. Fixed: tighter torso sampling + pick lowest-variance cluster. Verified visually correct (~24/13 split).
- **Annotated video never played in any browser** → OpenCV wrote `mp4v`, which browsers can't decode. Fixed: `avc1` (H.264).
- **Confusing double overlay on screen** → leftover fake procedural placeholder overlay drawn over the real one. Removed.
- **Fake ball-speed numbers shown as real** (22.4/72.8 km/h hardcoded fallback) → now returns `null`, frontend hides the panel.
- **Training CLI confusion**: stale `cd` path after a folder reorg, and Ultralytics' *global* (not per-project) `runs_dir` setting kept redirecting output outside the project. Both fixed (`data.yaml` given explicit `path:`; global setting repointed).
- **No git history for most of the session** → now has real, meaningful commits.

## 4. Achievements
- Full MVP delivered from PRD to working app in one session.
- Real model verified working end-to-end via direct API testing (not assumed).
- Every major fix empirically re-verified after the change, not just applied and assumed correct.
- Model quality quantified: precision ≈0.89, recall ≈0.80, mAP50 ≈0.81–0.82 aggregate; per-class: player/goalkeeper/referee mAP50 0.95–0.99 (strong), **ball mAP50 0.36 (weak — known limiter)**.
- Player-count accuracy: 72 (broken) → ~37 (functional) on a real test clip; team split: 68/4 (broken) → ~24/13 (correct, visually confirmed).
- Delivered `PROJECT_AUDIT.txt` (codebase health, model status, UI roadmap, milestones).

## 5. Next Steps & Blockers
- **Biggest lever, not started**: pitch calibration UI (click 4 reference points → wire `pitch_pixel_corners` through upload/processing) — unlocks real speed/distance, the PRD's core feature. Needs explicit go-ahead; meaningful scope.
- **Test coverage**: still zero — two regressions this session (goalkeeper class, missing calibration param) were exactly the class of bug tests would catch.
- **Ball detection**: plateaued on current 372-image dataset; needs more/varied data, not more epochs.
- **ID churn** (~37 vs. true ~22-23 players): bounded by detection/tracking confidence, not a config fix — ties to training data.
- **Blocker**: any further model training must run on the user's machine (Mac M4 Air, MPS) — commands can be provided, execution and results reporting is on the user.
- **Decision needed**: prioritize calibration UI vs. test coverage vs. more training data — not yet ranked against each other.

## 6. Assumptions & Constraints
- **Environment**: macOS, Apple Silicon (M4 Air — fanless, thermal-throttles, shared unified memory), Python 3.13 venv, Node/Vite.
- **No DB, no auth** — deliberate PRD scope; all state is file-based JSON under the project dir.
- **Training data**: Roboflow "football-players-detection" (`roboflow-jvuqo`), 4 classes, 372 images total — small by CV standards.
- **Model/config coupling**: `IMG_SIZE` in `detection.py` must stay in sync with whatever checkpoint is at `app/pipeline/models/best.pt`.
- **Privacy**: test footage was real broadcast video with identifiable people; PRD requires anonymous tracking IDs only (no face/jersey-number ID), which the implementation respects — user is responsible for rights/permission on any uploaded footage.
- **Tooling gotcha**: Ultralytics' `runs_dir` setting is machine-global, not per-project — now pointed at this project; relevant if the user starts another CV project later.
- **Coordination risk**: a separate AI tool ("Antigravity") also edited this codebase directly during the session (frontend ID scheme, `TRAINING.md` rewrite) — worth watching if multiple tools continue touching the same repo without shared context.
