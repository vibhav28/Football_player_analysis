"""Central paths/limits, matching the file-based storage layout in PRD section 27."""

import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BACKEND_DIR)
PROJECT_ROOT = os.path.dirname(APP_DIR)

UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")
MODEL_PATH = os.path.join(APP_DIR, "pipeline", "models", "best.pt")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi"}
MAX_UPLOAD_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB, PRD section 9.2
MAX_DURATION_SECONDS = 3 * 60 * 60  # 3 hours, generous upper bound for a match/session
MIN_DURATION_SECONDS = 1

# False now that a trained model lives at MODEL_PATH (training/runs/ has
# the full history — see TRAINING.md). Flip back to True if you swap in a
# checkpoint that isn't ready yet. See run_pipeline.run(mock=...).
USE_MOCK_PIPELINE = False

for directory in (UPLOAD_DIR, RESULTS_DIR, TEMP_DIR):
    os.makedirs(directory, exist_ok=True)
