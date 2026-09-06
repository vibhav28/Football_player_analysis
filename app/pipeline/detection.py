"""YOLOv8 object detection stage (PRD section 11).

Detects players, the ball, and referees in each frame. Requires a trained
or fine-tuned weights file placed at app/pipeline/models/<name>.pt — a
stock/generic YOLOv8 checkpoint will not reliably separate players from
referees; see PRD section 42 (Phase 1) for training notes.
"""

from dataclasses import dataclass

import numpy as np
from torchvision.ops import nms

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

# Raw model class ids (see load_model's YOLO().names — verified against the
# deployed checkpoint: {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"})
# that can both fire on the SAME real body, per CLASS_NAME_ALIASES above.
# Used to scope the cross-class duplicate-box suppression below to ONLY
# this pair, never to referee/ball.
_DUPLICATE_BODY_CLASS_IDS = (1, 2)  # goalkeeper, player
# Same IoU bar Ultralytics' own NMS uses by default — near-duplicate boxes
# on one real body (the actual problem this exists for) overlap far above
# this regardless of the exact value; kept in line with Ultralytics' own
# default rather than invented separately.
DUPLICATE_BODY_IOU_THRESHOLD = 0.7


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
        # agnostic_nms=False (was True): class-agnostic NMS suppresses ANY
        # sufficiently-overlapping boxes regardless of class, which was
        # meant to catch a "player" box and a "goalkeeper" box on the same
        # real person (aliased to one class downstream anyway — see
        # CLASS_NAME_ALIASES) — but it applies the exact same suppression
        # between a referee and a player standing/overlapping close
        # together, two DIFFERENT real people, not a duplicate detection
        # of one. Verified on real footage: a player directly next to a
        # referee never got a box at all, while the referee did — the
        # player's detection was being suppressed as if it were a
        # duplicate of the referee's. Per-class NMS (agnostic_nms=False)
        # never does this, since referee and player are different classes;
        # the narrower fix for the original goalkeeper/player duplicate
        # problem is applied separately below, scoped to only that pair.
        results = model.predict(
            batch, conf=CONFIDENCE_THRESHOLD, imgsz=IMG_SIZE, agnostic_nms=False, verbose=False
        )

        for offset, result in enumerate(results):
            frame_index = start + offset
            frame_detections = []
            names = result.names
            boxes = result.boxes
            class_ids = boxes.cls.cpu().numpy().astype(int)

            # Ultralytics' own per-class NMS above already suppressed
            # same-class duplicates. This second, narrower pass additionally
            # suppresses cross-class duplicates ONLY between player and
            # goalkeeper boxes (the one pair of classes documented as being
            # the same aliased real body, see CLASS_NAME_ALIASES) — never
            # against referee or ball, so a referee genuinely standing close
            # to a player is never mistaken for a duplicate box on that
            # player's body.
            keep = np.ones(len(class_ids), dtype=bool)
            dup_mask = np.isin(class_ids, _DUPLICATE_BODY_CLASS_IDS)
            if dup_mask.sum() >= 2:
                dup_idx = np.where(dup_mask)[0]
                kept_dup = nms(boxes.xyxy[dup_idx], boxes.conf[dup_idx], DUPLICATE_BODY_IOU_THRESHOLD)
                kept_dup_set = set(kept_dup.cpu().tolist())
                for position, box_idx in enumerate(dup_idx):
                    if position not in kept_dup_set:
                        keep[box_idx] = False

            for i in range(len(class_ids)):
                if not keep[i]:
                    continue
                class_name = CLASS_NAME_ALIASES.get(names[class_ids[i]], names[class_ids[i]])
                frame_detections.append(
                    Detection(
                        frame_index=frame_index,
                        bbox=tuple(boxes.xyxy[i].tolist()),
                        confidence=float(boxes.conf[i]),
                        class_name=class_name,
                    )
                )
            all_detections.append(frame_detections)

    return all_detections
