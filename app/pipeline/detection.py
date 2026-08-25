"""YOLOv8 object detection stage (PRD section 11).

Detects players, the ball, and referees in each frame. Requires a trained
or fine-tuned weights file placed at app/pipeline/models/<name>.pt — a
stock/generic YOLOv8 checkpoint will not reliably separate players from
referees; see PRD section 42 (Phase 1) for training notes.
"""

from dataclasses import dataclass

import numpy as np

CONFIDENCE_THRESHOLD = 0.2
BATCH_SIZE = 8
# Must match (or be close to) the imgsz used at training time — passing
# none of this to model.predict() silently falls back to Ultralytics'
# default of 640, which quietly resizes every frame to a different
# resolution than the model was trained on and hurts small/fast objects
# (the ball especially) the most. Lower BATCH_SIZE if this causes an
# out-of-memory error on CPU/modest GPUs.
# Current app/pipeline/models/best.pt is training/runs/detect/train_full2
# (100 epochs, trained at imgsz=1000 — see that run's args.yaml). Update
# this value together with the model whenever you swap in a new checkpoint.
IMG_SIZE = 1000

# Some Roboflow football datasets (including the one this project's
# TRAINING.md recommends) ship a separate "goalkeeper" class rather than
# folding it into "player". Everything downstream (tracking, team-color
# classification, statistics) only recognizes "player"/"ball"/"referee" —
# without this alias, goalkeepers get detected and tracked but then
# silently dropped before they ever reach positions.json/statistics.json.
CLASS_NAME_ALIASES = {"goalkeeper": "player"}


@dataclass
class Detection:
    frame_index: int
    bbox: tuple[float, float, float, float]
    confidence: float
    class_name: str  # "player" | "ball" | "referee"


def load_model(model_path: str):
    from ultralytics import YOLO

    return YOLO(model_path)


def detect_frames(frames: list[np.ndarray], model_path: str) -> list[list[Detection]]:
    """Run YOLOv8 detection across all frames, batched for throughput.

    Returns one list of Detection per input frame.
    """
    model = load_model(model_path)
    all_detections: list[list[Detection]] = []

    for start in range(0, len(frames), BATCH_SIZE):
        batch = frames[start : start + BATCH_SIZE]
        # agnostic_nms=True: without it, Ultralytics' NMS only suppresses
        # overlapping boxes of the SAME class, so a "player" box and a
        # "goalkeeper" box on the same real person (a class the model is
        # visibly unsure between, given they're aliased to one class
        # downstream anyway — see CLASS_NAME_ALIASES) both survive as
        # separate detections, becoming two separate tracked "players"
        # for one real athlete. Verified on real footage: near-duplicate
        # boxes (~same coordinates, different confidence) were present
        # per-frame before this. Class-agnostic NMS suppresses those
        # regardless of which class they were assigned.
        results = model.predict(
            batch, conf=CONFIDENCE_THRESHOLD, imgsz=IMG_SIZE, agnostic_nms=True, verbose=False
        )

        for offset, result in enumerate(results):
            frame_index = start + offset
            frame_detections = []
            names = result.names
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = names[class_id]
                class_name = CLASS_NAME_ALIASES.get(class_name, class_name)
                frame_detections.append(
                    Detection(
                        frame_index=frame_index,
                        bbox=tuple(box.xyxy[0].tolist()),
                        confidence=float(box.conf[0]),
                        class_name=class_name,
                    )
                )
            all_detections.append(frame_detections)

    return all_detections
