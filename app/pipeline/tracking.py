"""BoT-SORT player/referee tracking stage (PRD section 12).

Associates per-frame detections into consistent tracks across frames so
each player keeps the same tracking_id for as long as the tracker can
maintain identity (PRD section 41, Tracking acceptance criteria).

Was plain ByteTrack (via `supervision`) — pure motion/IOU matching, no
concept of what a player looks like. Verified on real footage that this
was the direct cause of a chunk of the project's "37 players instead of
~22" problem: two players crossing paths (or one occluded a couple of
frames too long) reads identically to ByteTrack either way, so it would
kill a track and start a new ID, or swap which ID follows which physical
player, purely based on position. `supervision` doesn't offer anything
else (checked its source: `tracker/` contains only `byte_tracker/`).

BoT-SORT (via the `boxmot` package) keeps ByteTrack's association logic
but adds an appearance embedding (a small pretrained ReID network) to the
matching cost, so "does this box look like player #7" gets weighed
alongside "is this box near where #7 should be" — the only way to
actually disambiguate two overlapping players position-only matching
can't tell apart. It also folds camera-motion compensation directly into
its own matching decisions (separate from, and in addition to, this
project's own camera_motion.py compensation used later for the pitch
calibration/meters conversion — the two serve different purposes and
don't conflict). merge_broken_tracks below still runs on top of this: it
catches tracks broken for longer than BoT-SORT's own lost-track buffer,
which better association reduces the frequency of but doesn't eliminate.
"""

from collections import defaultdict

import numpy as np
import torch
from boxmot import ReIDModel
from boxmot.trackers.registry import create_tracker

from .detection import CONFIDENCE_THRESHOLD, Detection
from .utils import get_bbox_width, get_foot_position, measure_distance

# Generic person-ReID weights (not football-specific — trained on MSMT17,
# a pedestrian re-id dataset), auto-downloaded on first use (~3MB) and
# cached in the venv. Still meaningfully better than no appearance signal
# at all: jersey color/texture carries through even a generic embedding.
REID_WEIGHTS = "osnet_x0_25_msmt17.pt"


def _reid_device() -> str:
    """Apple Silicon's GPU cuts the ReID model's per-frame cost by ~6x
    over CPU (measured: ~332ms -> ~55ms for a 25-box frame) — a real
    difference given this runs on every player/referee box, every frame.
    Falls back to CPU where MPS isn't available (e.g. CI, non-Apple
    machines) rather than assuming this always runs on the dev Mac."""
    return "mps" if torch.backends.mps.is_available() else "cpu"

# Same reasoning as the old ByteTrack lost_track_buffer doubling this
# replaces: a lightly fine-tuned model on a small dataset drops a player
# for a handful of frames rather than never seeing them, so a longer
# buffer trades a bit of ID-reuse precision for a lot more continuity.
DEFAULT_TRACK_BUFFER = 60


def track_players(
    detections_per_frame: list[list[Detection]],
    frames: list[np.ndarray],
    fps: float = 25.0,
    lost_track_buffer: int = DEFAULT_TRACK_BUFFER,
) -> dict[int, dict[int, dict]]:
    """Track players (and referees) across frames with BoT-SORT + ReID.

    Returns: { tracking_id: { frame_index: {"bbox": (...), "class_name": str} } }
    Ball detections are excluded here — see ball_tracking.py, since the ball
    is tracked/interpolated differently rather than assigned a stable ID.

    frames is needed (unlike the old ByteTrack-only version) because
    BoT-SORT crops each detected box out of the actual frame to compute
    its appearance embedding — position alone isn't enough input anymore.
    """
    tracker = create_tracker(
        "botsort",
        reid_weights=REID_WEIGHTS,
        device=_reid_device(),
        half=False,
        tracker_kwargs={
            "frame_rate": round(fps) or 25,
            "track_buffer": lost_track_buffer,
            # boxmot's BotSort ships its own tuned defaults for these
            # (track_high_thresh/new_track_thresh ~0.62-0.63, verified
            # against the installed package) — both far above this
            # project's own detector confidence floor (CONFIDENCE_THRESHOLD
            # = 0.2, detection.py). Left unset, any detection between 0.2
            # and ~0.63 confidence — common output for the "lightly
            # fine-tuned" model this project documents elsewhere — could
            # never start a new track, silently under-tracking real
            # players regardless of how well merge_broken_tracks/
            # enforce_roster_size clean things up downstream, since a
            # player who's never tracked in the first place has nothing to
            # merge. The old ByteTrack setup this replaced explicitly
            # synced its own activation threshold to CONFIDENCE_THRESHOLD
            # (`track_activation_threshold=CONFIDENCE_THRESHOLD`) for the
            # same reason — this restores that same invariant for BoT-SORT.
            "track_high_thresh": CONFIDENCE_THRESHOLD,
            "new_track_thresh": CONFIDENCE_THRESHOLD,
        },
    )

    # Encode class_name as class_id so it survives the tracker's internal
    # filtering/reordering, then decode it back below.
    name_to_id = {"player": 0, "referee": 1}
    id_to_name = {v: k for k, v in name_to_id.items()}

    tracks: dict[int, dict[int, dict]] = defaultdict(dict)

    for frame_index, frame_detections in enumerate(detections_per_frame):
        trackable = [d for d in frame_detections if d.class_name != "ball"]

        if trackable:
            dets = np.array(
                [
                    [*d.bbox, d.confidence, name_to_id.get(d.class_name, 0)]
                    for d in trackable
                ],
                dtype=np.float32,
            )
        else:
            dets = np.empty((0, 6), dtype=np.float32)

        # BoT-SORT still needs an update() call on empty frames to advance
        # its internal frame counter / age out lost tracks, same as the
        # old tracker.update_with_detections(sv.Detections.empty()) call.
        result = tracker.update(dets, frames[frame_index])

        for x1, y1, x2, y2, track_id, _conf, cls, _det_ind in result:
            tracks[int(track_id)][frame_index] = {
                "bbox": (float(x1), float(y1), float(x2), float(y2)),
                "class_name": id_to_name.get(int(cls), "player"),
            }

    return _drop_short_tracks(dict(tracks), fps)


# A track that only exists for a fraction of a second is almost always
# noise, not a real player: a false-positive detection blinking on for a
# frame or two, or ByteTrack briefly losing and immediately reassigning a
# new ID to someone already tracked under a different ID. Left in, these
# both inflate the final player count (a 30s clip should show roughly as
# many players as were actually on the pitch, not 3-4x that) and pollute
# team-color classification, whose input is one color sample per track —
# a flood of short, often mis-cropped samples can swamp the real signal
# from the genuinely long-lived player tracks. This does NOT fix ID churn
# itself (a real player split across two long-ish tracks still counts
# twice) — it only removes the shortest, noisiest blips.
MIN_TRACK_SECONDS = 1.0


def _drop_short_tracks(
    tracks: dict[int, dict[int, dict]], fps: float, min_seconds: float = MIN_TRACK_SECONDS
) -> dict[int, dict[int, dict]]:
    min_frames = max(1, round(min_seconds * (fps or 25.0)))
    return {tid: track for tid, track in tracks.items() if len(track) >= min_frames}


# _drop_short_tracks removes noise but, as its own docstring says, does not
# fix ID churn itself: a real player split into two tracks by a gap
# ByteTrack's own lost_track_buffer (see track_players) didn't bridge — a
# camera pan or heavy occlusion that also shifts the bbox scale/position
# enough to break ByteTrack's own re-association — still counts as two
# players. merge_broken_tracks is the second half of that fix: greedily
# stitch track B into track A when B starts shortly after A ends, on the
# same team, near where A was last seen.
MERGE_MAX_GAP_SECONDS = 2.0
# There's no meters-per-pixel conversion available yet at this stage of the
# pipeline (perspective transform, if calibrated at all, runs later against
# already-merged tracks), so "near" is measured in bbox widths rather than
# meters: a player's own bbox width is a rough, self-scaling proxy for how
# large their real-world stride looks at that camera distance/zoom. 6
# widths/second is a deliberately generous upper bound (covers a full
# sprint) chosen to keep false merges of two different players rare, at
# the cost of missing some genuine reappearances that drift further than
# that.
MERGE_MAX_SPEED_BBOX_WIDTHS_PER_SEC = 6.0
# The speed-scaled budget above shrinks to 0 as gap -> 0, which silently
# made the single most common ID-churn pattern unmergeable: ByteTrack
# handing an object from an old ID straight to a new one in the very same
# frame (old track's last frame == new track's first frame, so gap == 0
# exactly — verified on real footage, e.g. a track ending at (545, 808)
# and a new one starting one frame later at (534, 808), 11px apart, never
# merged). A small fixed floor — independent of gap — covers that "same
# instant, near-identical box" case; the speed-scaled budget still governs
# every gap above 0.
MIN_MERGE_DISTANCE_BBOX_WIDTHS = 0.5


def merge_broken_tracks(
    tracks: dict[int, dict[int, dict]],
    team_by_id: dict[int, str],
    fps: float,
    max_gap_seconds: float = MERGE_MAX_GAP_SECONDS,
    max_speed_bbox_widths_per_sec: float = MERGE_MAX_SPEED_BBOX_WIDTHS_PER_SEC,
    min_merge_distance_bbox_widths: float = MIN_MERGE_DISTANCE_BBOX_WIDTHS,
) -> tuple[dict[int, dict[int, dict]], dict[int, str]]:
    """Merge player tracks that are almost certainly the same person split
    across two tracking IDs. Referees are left untouched (not team-numbered,
    and their identity doesn't feed into player statistics).

    Tracks are processed in start-frame order; each one either extends the
    most recent compatible still-open track (same team, gap within
    max_gap_seconds, reappearance position within the bbox-width-scaled
    distance budget) or becomes a new root. A root's "current end" updates
    every time something merges into it, so a chain of three-plus
    fragments for the same player stitches together correctly, not just
    pairs.
    """
    fps = fps or 25.0
    max_gap_frames = max(1, round(max_gap_seconds * fps))

    player_ids = [
        tid for tid, track in tracks.items()
        if any(f["class_name"] == "player" for f in track.values())
    ]
    player_ids.sort(key=lambda tid: min(tracks[tid].keys()))

    parent: dict[int, int] = {}
    # root_id -> {"end_frame": int, "end_bbox": tuple} for the merged
    # trajectory's most recently seen position so far.
    root_state: dict[int, dict] = {}

    for tid in player_ids:
        track = tracks[tid]
        start_frame = min(track.keys())
        end_frame = max(track.keys())
        start_pos = get_foot_position(track[start_frame]["bbox"])
        start_width = get_bbox_width(track[start_frame]["bbox"])

        best_root, best_gap = None, None
        for root, state in root_state.items():
            if team_by_id.get(root) != team_by_id.get(tid):
                continue
            gap = start_frame - state["end_frame"]
            if gap < 0 or gap > max_gap_frames:
                continue
            end_pos = get_foot_position(state["end_bbox"])
            end_width = get_bbox_width(state["end_bbox"])
            avg_width = (start_width + end_width) / 2 or 1.0
            distance = measure_distance(start_pos, end_pos)
            max_distance = max(
                min_merge_distance_bbox_widths * avg_width,
                max_speed_bbox_widths_per_sec * avg_width * (gap / fps),
            )
            if distance > max_distance:
                continue
            if best_gap is None or gap < best_gap:
                best_root, best_gap = root, gap

        root = best_root if best_root is not None else tid
        parent[tid] = root
        root_state[root] = {"end_frame": end_frame, "end_bbox": track[end_frame]["bbox"]}

    merged_tracks: dict[int, dict[int, dict]] = defaultdict(dict)
    merged_team: dict[int, str] = {}
    for tid in player_ids:
        root = parent[tid]
        merged_tracks[root].update(tracks[tid])
        merged_team[root] = team_by_id[root]

    for tid, track in tracks.items():
        if tid not in parent:  # referees and other non-player tracks
            merged_tracks[tid] = track

    return dict(merged_tracks), merged_team


# ---------------------------------------------------------------------------
# Appearance-based long-gap merging + fixed roster size enforcement.
#
# merge_broken_tracks above only bridges short gaps (MERGE_MAX_GAP_SECONDS),
# using position/bbox-width as its only signal, because that's genuinely all
# it has to work with. It still leaves two known-inflated-count patterns:
#
#   1. The SAME real player split into two tracks by a gap longer than a
#      couple of seconds (camera pan/cut, extended occlusion, briefly
#      leaving frame). BoT-SORT's own ReID gallery (see the module
#      docstring) can't bridge this either in practice: its first-association
#      cost gates appearance matching behind an IOU/proximity check against
#      the Kalman-predicted box, and that prediction degrades fast for a
#      moving player once several seconds pass -- so a plausible appearance
#      match still gets thrown out for "not being near enough."
#   2. A genuinely extra track that was never a real rostered player at all
#      -- a misclassified referee/staff/substitute, or a short false
#      detection that survived MIN_TRACK_SECONDS.
#
# merge_broken_tracks_by_appearance fixes (1) with a much longer time budget
# than the position-only pass, gated on a real per-player appearance
# embedding instead of jersey color -- color can't disambiguate two
# teammates, since a team's whole point is that they wear identical kit.
# enforce_roster_size then fixes (2): callers that know the match's real
# squad size (5-a-side, 7-a-side, 11-a-side, ...) can pass it as
# target_size, and anything still over that count after merging is treated
# as noise and either folded into the real player it best matches, or
# dropped -- never left inflating the count as a fabricated extra "player".
#
# target_size used to default to a hardcoded PLAYERS_PER_TEAM = 7 here,
# applied to every match regardless of its actual format -- silently
# discarding 4+ real players on anything bigger than 7-a-side (the direct
# cause of "11v11 gets miscounted as 7v7"). There is no longer a
# module-level default target size: callers must say what they know (see
# run_pipeline.run's players_per_team, and its own
# MAX_PLAYERS_PER_TEAM_SAFETY_CAP fallback for when they don't).
# ---------------------------------------------------------------------------

# Fallback target_size for run_pipeline.run() when the caller (ultimately,
# whatever the user selected at calibration time) doesn't specify the
# match's real per-team player count. A ceiling above the largest standard
# format (11-a-side, including keeper -- goalkeeper aliases to "player" in
# detection.py) so it never wrongly trims a full real roster, while still
# catching genuine runaway noise -- a misclassified referee/staff track, or
# unmerged false-positive spam -- that neither merge pass above caught.
# Deliberately not None (fully disabled): some upper bound is worth having
# even when the exact squad size isn't known.
MAX_PLAYERS_PER_TEAM_SAFETY_CAP = 13

# How many frames to crop+embed per track. A representative sample rather
# than every frame -- ReID inference cost scales with this, and a handful of
# samples spread across the track's lifetime already averages out pose/
# motion-blur/partial-occlusion noise in any single crop.
EMBEDDING_SAMPLE_FRAMES = 5

# Cosine similarity thresholds for the OSNet appearance embedding (1.0 =
# identical). The long-gap merge pass requires a confident match, since a
# false merge silently corrupts a real player's statistics (their track
# jumps to wherever the other fragment was). The roster-cap fallback is
# intentionally more permissive: by the time it runs, a leftover track is
# already known to be excess (the team is over PLAYERS_PER_TEAM), so the
# choice is between merging it into its best appearance match or discarding
# it outright -- a merge that's only "probably right" is still preferable to
# guaranteed lost data, whereas mid-track it wouldn't be worth the risk.
APPEARANCE_MERGE_MIN_SIMILARITY = 0.60
ROSTER_MERGE_MIN_SIMILARITY = 0.45

# Long-gap merge budget: generous (most of a short clip) rather than
# unlimited, so two genuinely different, similar-looking teammates who are
# each on screen for most of the video still can't be merged just because
# they never technically overlap.
APPEARANCE_MERGE_MAX_GAP_SECONDS = 20.0

_appearance_model_cache: dict[str, "ReIDModel"] = {}


def _get_appearance_model() -> "ReIDModel":
    """Standalone OSNet ReID model for track-level embeddings -- the same
    network/weights BoT-SORT already loads internally for per-frame
    matching (see REID_WEIGHTS above), reused here for a second pass that
    runs after tracking rather than during it."""
    device = _reid_device()
    model = _appearance_model_cache.get(device)
    if model is None:
        model = ReIDModel(REID_WEIGHTS, device=device, half=False)
        _appearance_model_cache[device] = model
    return model


def _track_embedding(
    track: dict[int, dict], frames: list[np.ndarray], appearance_model: "ReIDModel"
) -> np.ndarray | None:
    """Average OSNet embedding over a handful of frames spread across the
    track's lifetime. Returns None if no crop could be embedded (e.g. an
    empty/degenerate bbox) so callers can fall back to duration-only
    handling instead of crashing on bad input."""
    frame_indices = sorted(track.keys())
    if len(frame_indices) > EMBEDDING_SAMPLE_FRAMES:
        step = len(frame_indices) / EMBEDDING_SAMPLE_FRAMES
        sample_indices = [frame_indices[int(i * step)] for i in range(EMBEDDING_SAMPLE_FRAMES)]
    else:
        sample_indices = frame_indices

    embeddings = []
    for frame_index in sample_indices:
        bbox = track[frame_index]["bbox"]
        boxes = np.array([bbox], dtype=np.float32)
        try:
            feats = appearance_model.get_features(boxes, frames[frame_index])
        except Exception:
            continue
        if feats is None or len(feats) == 0:
            continue
        embeddings.append(np.asarray(feats[0], dtype=np.float32))

    if not embeddings:
        return None
    embedding = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(embedding)
    return embedding / norm if norm > 0 else embedding


def _cosine_similarity(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None:
        return -1.0
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else -1.0


def _tracks_overlap_in_time(track_a: dict[int, dict], track_b: dict[int, dict]) -> bool:
    """True if both tracks have at least one frame in common -- meaning
    they were two different things on screen at the same instant, so they
    can never be the same real player regardless of how similar they look."""
    a_frames, b_frames = track_a.keys(), track_b.keys()
    if not a_frames or not b_frames:
        return False
    if max(a_frames) < min(b_frames) or max(b_frames) < min(a_frames):
        return False
    return not set(a_frames).isdisjoint(b_frames)


def merge_broken_tracks_by_appearance(
    tracks: dict[int, dict[int, dict]],
    team_by_id: dict[int, str],
    frames: list[np.ndarray],
    fps: float,
    max_gap_seconds: float = APPEARANCE_MERGE_MAX_GAP_SECONDS,
    min_similarity: float = APPEARANCE_MERGE_MIN_SIMILARITY,
) -> tuple[dict[int, dict[int, dict]], dict[int, str]]:
    """Second merge pass, run after merge_broken_tracks. Bridges the same
    real player split across tracks by a gap too long for position alone to
    safely judge, using appearance similarity instead. See the module-level
    comment above this function for why this needs to exist as a separate
    pass from both merge_broken_tracks and BoT-SORT's own tracking-time ReID.

    frames is required to compute embeddings; if empty, this is a no-op.
    """
    if not frames:
        return tracks, team_by_id

    fps = fps or 25.0
    max_gap_frames = max(1, round(max_gap_seconds * fps))
    appearance_model = _get_appearance_model()

    player_ids = [
        tid for tid, track in tracks.items()
        if any(f["class_name"] == "player" for f in track.values())
    ]
    player_ids.sort(key=lambda tid: min(tracks[tid].keys()))

    embeddings = {tid: _track_embedding(tracks[tid], frames, appearance_model) for tid in player_ids}

    parent: dict[int, int] = {}
    # root_id -> {"end_frame": int, "embedding": np.ndarray | None}
    root_state: dict[int, dict] = {}

    for tid in player_ids:
        track = tracks[tid]
        start_frame = min(track.keys())
        end_frame = max(track.keys())
        emb = embeddings.get(tid)

        best_root, best_score = None, min_similarity
        if emb is not None:
            for root, state in root_state.items():
                if team_by_id.get(root) != team_by_id.get(tid):
                    continue
                gap = start_frame - state["end_frame"]
                if gap < 0 or gap > max_gap_frames:
                    continue
                score = _cosine_similarity(emb, state["embedding"])
                if score > best_score:
                    best_root, best_score = root, score

        root = best_root if best_root is not None else tid
        parent[tid] = root

        prev_embedding = root_state.get(root, {}).get("embedding")
        if prev_embedding is not None and emb is not None:
            merged_embedding = (prev_embedding + emb) / 2
        else:
            merged_embedding = emb if emb is not None else prev_embedding
        root_state[root] = {"end_frame": end_frame, "embedding": merged_embedding}

    merged_tracks: dict[int, dict[int, dict]] = defaultdict(dict)
    merged_team: dict[int, str] = {}
    for tid in player_ids:
        root = parent[tid]
        merged_tracks[root].update(tracks[tid])
        merged_team[root] = team_by_id[root]

    for tid, track in tracks.items():
        if tid not in parent:  # referees and other non-player tracks
            merged_tracks[tid] = track

    return dict(merged_tracks), merged_team


def enforce_roster_size(
    tracks: dict[int, dict[int, dict]],
    team_by_id: dict[int, str],
    frames: list[np.ndarray],
    fps: float,
    target_size: int | None = None,
    min_similarity: float = ROSTER_MERGE_MIN_SIMILARITY,
) -> tuple[dict[int, dict[int, dict]], dict[int, str]]:
    """Final guardrail, run after both merge passes above: cap each team at
    target_size tracked players -- the match's real squad size (7 for
    7-a-side, 11 for 11-a-side, etc.) when the caller knows it, or a
    generous safety ceiling otherwise (see run_pipeline.run's
    players_per_team / MAX_PLAYERS_PER_TEAM_SAFETY_CAP).

    Whatever is still over target_size at this point isn't a real extra
    rostered player -- both merge passes have already had their chance to
    reunite genuine fragments. It's noise: a misclassified referee/staff/
    substitute, or a short false detection. Each excess track (shortest-
    lived first are cut) is either folded into whichever *kept* player it
    most resembles -- only if they were never on screen together and the
    appearance match clears min_similarity -- or dropped outright. Dropping
    is preferred over a low-confidence merge: a wrong merge corrupts a real
    player's speed/distance with a jump to wherever the noise track was,
    which is worse than that player simply missing a few seconds of data.

    target_size=None disables this step entirely (kept for callers that
    don't know the true squad size).
    """
    if target_size is None:
        return tracks, team_by_id

    tracks = dict(tracks)
    team_by_id = dict(team_by_id)

    teams: dict[str, list[int]] = defaultdict(list)
    for tid, track in tracks.items():
        if any(f["class_name"] == "player" for f in track.values()):
            teams[team_by_id.get(tid, "Team A")].append(tid)

    appearance_model = None
    for ids in teams.values():
        if len(ids) <= target_size:
            continue
        if appearance_model is None:
            appearance_model = _get_appearance_model()

        durations = {tid: len(tracks[tid]) for tid in ids}
        ranked = sorted(ids, key=lambda tid: durations[tid], reverse=True)
        kept = ranked[:target_size]
        # Longest-lived leftovers merged first: they're the most likely to
        # be a genuine fragment worth reuniting rather than pure noise.
        leftover = sorted(ranked[target_size:], key=lambda tid: durations[tid], reverse=True)

        embeddings = {
            tid: _track_embedding(tracks[tid], frames, appearance_model)
            for tid in kept + leftover
        } if frames else {tid: None for tid in kept + leftover}

        for tid in leftover:
            track = tracks[tid]
            emb = embeddings.get(tid)

            best_target, best_score = None, min_similarity
            for k in kept:
                if _tracks_overlap_in_time(track, tracks[k]):
                    continue
                score = _cosine_similarity(emb, embeddings.get(k))
                if score > best_score:
                    best_target, best_score = k, score

            if best_target is not None:
                tracks[best_target].update(track)
                kept_emb = embeddings.get(best_target)
                embeddings[best_target] = (
                    (kept_emb + emb) / 2 if kept_emb is not None and emb is not None else (kept_emb or emb)
                )

            del tracks[tid]
            team_by_id.pop(tid, None)

    return tracks, team_by_id
