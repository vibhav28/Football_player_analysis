"""ByteTrack player/referee tracking stage (PRD section 12).

Associates per-frame detections into consistent tracks across frames so
each player keeps the same tracking_id for as long as the tracker can
maintain identity (PRD section 41, Tracking acceptance criteria).
"""

from collections import defaultdict

import numpy as np
import supervision as sv

from .detection import CONFIDENCE_THRESHOLD, Detection


def track_players(
    detections_per_frame: list[list[Detection]],
    fps: float = 25.0,
    lost_track_buffer: int = 60,
) -> dict[int, dict[int, dict]]:
    """Track players (and referees) across frames with ByteTrack.

    Returns: { tracking_id: { frame_index: {"bbox": (...), "class_name": str} } }
    Ball detections are excluded here — see ball_tracking.py, since the ball
    is tracked/interpolated differently rather than assigned a stable ID.

    ByteTrack's defaults (lost_track_buffer=30, frame_rate=30) assume a
    reasonably confident, consistent detector. A lightly fine-tuned model
    (few epochs / a small dataset) tends to drop a player for a handful of
    frames at a time rather than never seeing them — with the default
    30-frame buffer (~1s), that's enough to kill the track and hand out a
    new ID when they reappear, which is what "boxes/IDs keep changing"
    usually is. Doubling the buffer trades a bit of ID-reuse precision for
    a lot more continuity; tighten it back down once detections are
    consistently confident (i.e. once the model is trained further).
    """
    tracker = sv.ByteTrack(
        track_activation_threshold=CONFIDENCE_THRESHOLD,
        lost_track_buffer=lost_track_buffer,
        frame_rate=round(fps) or 25,
    )
    tracks: dict[int, dict[int, dict]] = defaultdict(dict)

    for frame_index, frame_detections in enumerate(detections_per_frame):
        trackable = [d for d in frame_detections if d.class_name != "ball"]
        if not trackable:
            tracker.update_with_detections(sv.Detections.empty())
            continue

        # Encode class_name as class_id so it survives ByteTrack's internal
        # filtering/reordering, then decode it back below.
        name_to_id = {"player": 0, "referee": 1}
        sv_detections = sv.Detections(
            xyxy=np.array([d.bbox for d in trackable], dtype=np.float32),
            confidence=np.array([d.confidence for d in trackable], dtype=np.float32),
            class_id=np.array(
                [name_to_id.get(d.class_name, 0) for d in trackable], dtype=int
            ),
        )
        id_to_name = {v: k for k, v in name_to_id.items()}

        tracked = tracker.update_with_detections(sv_detections)

        for i, tracker_id in enumerate(tracked.tracker_id):
            tracks[int(tracker_id)][frame_index] = {
                "bbox": tuple(tracked.xyxy[i].tolist()),
                "class_name": id_to_name.get(int(tracked.class_id[i]), "player"),
            }

    return dict(tracks)
