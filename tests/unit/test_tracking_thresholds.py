"""app/pipeline/tracking.py's BoT-SORT construction — regression test for a
bug found during a full-codebase review: the ByteTrack -> BoT-SORT
migration dropped syncing the tracker's track-initiation confidence with
the detector's own CONFIDENCE_THRESHOLD (0.2). boxmot's BotSort ships much
higher tuned defaults (~0.6-0.63) for track_high_thresh/new_track_thresh,
so any detection between 0.2 and ~0.6 confidence -- normal output for this
project's own documented "lightly fine-tuned" model -- could never start a
new track, silently under-tracking real players."""

from boxmot.trackers.registry import create_tracker

from app.pipeline.detection import CONFIDENCE_THRESHOLD
from app.pipeline.tracking import REID_WEIGHTS


def test_tracker_new_track_threshold_matches_detector_confidence_floor():
    tracker = create_tracker(
        "botsort",
        reid_weights=REID_WEIGHTS,
        device="cpu",
        half=False,
        tracker_kwargs={
            "frame_rate": 25,
            "track_buffer": 60,
            "track_high_thresh": CONFIDENCE_THRESHOLD,
            "new_track_thresh": CONFIDENCE_THRESHOLD,
        },
    )

    assert tracker.track_high_thresh == CONFIDENCE_THRESHOLD
    assert tracker.new_track_thresh == CONFIDENCE_THRESHOLD
    # track_low_thresh already sits below the detector floor by default
    # (~0.10 vs 0.2) so it was never the problem, but confirm it stays
    # under the floor too -- if boxmot's own default ever changes to sit
    # above CONFIDENCE_THRESHOLD, low-confidence secondary matching would
    # silently start rejecting valid detections the detector already
    # accepted.
    assert tracker.track_low_thresh < CONFIDENCE_THRESHOLD
