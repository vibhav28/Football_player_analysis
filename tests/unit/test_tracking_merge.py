"""app/pipeline/tracking.py — the ID-churn stitching passes and the fixed
roster-size guardrail:

- merge_broken_tracks: a same-team reappearance nearby and soon after a
  track ends gets merged, a different player never does (even if their
  track overlaps in time), and a chain of 3+ fragments for the same player
  collapses into one track, not just pairs.
- merge_broken_tracks_by_appearance / enforce_roster_size: appearance
  (OSNet ReID embedding) drives long-gap merging and the final per-team
  player cap, in place of position — see the module comment above
  merge_broken_tracks_by_appearance in tracking.py for why. The real
  network isn't exercised here (would make this a slow integration test,
  not a unit test); _track_embedding/_get_appearance_model are monkeypatched
  to fixed vectors keyed by which synthetic track object was passed in, so
  these tests pin down the *merge/cap decision logic* given known
  similarities, independent of whether OSNet itself judges two crops
  similar."""

import numpy as np

import app.pipeline.tracking as tracking
from app.pipeline.tracking import enforce_roster_size, merge_broken_tracks, merge_broken_tracks_by_appearance

FPS = 25.0


def _patch_embeddings(monkeypatch, embedding_by_track_id, tracks):
    """Route _track_embedding to a fixed vector per track (matched by
    object identity, since the real function only ever sees the track dict,
    not its id) and _get_appearance_model to a harmless sentinel so no real
    model gets loaded."""
    vector_by_object_id = {id(tracks[tid]): vec for tid, vec in embedding_by_track_id.items()}

    def fake_embedding(track, frames, appearance_model):
        return vector_by_object_id.get(id(track))

    monkeypatch.setattr(tracking, "_track_embedding", fake_embedding)
    monkeypatch.setattr(tracking, "_get_appearance_model", lambda: "fake-model")


def _track(frames, x_start, y=200, class_name="player"):
    """A player moving 1px/frame to the right, starting at x_start, over
    the given frame range."""
    return {f: {"bbox": (x_start + i, y, x_start + i + 30, y + 60), "class_name": class_name}
            for i, f in enumerate(frames)}


def test_merges_same_team_reappearance_nearby_and_soon_after():
    tracks = {
        1: _track(range(0, 25), x_start=100),
        # Gap of 20 frames (0.8s @ 25fps), reappears close to where it left off.
        2: _track(range(45, 70), x_start=145),
    }
    team_by_id = {1: "Team A", 2: "Team A"}

    merged, merged_team = merge_broken_tracks(tracks, team_by_id, fps=FPS)

    assert set(merged.keys()) == {1}
    assert len(merged[1]) == 50
    assert merged_team[1] == "Team A"


def test_does_not_merge_a_different_player_even_if_time_overlaps():
    tracks = {
        1: _track(range(0, 25), x_start=100),
        # On screen at the same time, far away, different team -> clearly not the same person.
        3: _track(range(0, 25), x_start=900, y=900),
    }
    team_by_id = {1: "Team A", 3: "Team B"}

    merged, _ = merge_broken_tracks(tracks, team_by_id, fps=FPS)

    assert set(merged.keys()) == {1, 3}


def test_does_not_merge_across_gap_that_is_too_large():
    tracks = {
        1: _track(range(0, 25), x_start=100),
        # 5 second gap - far beyond MERGE_MAX_GAP_SECONDS.
        2: _track(range(150, 175), x_start=145),
    }
    team_by_id = {1: "Team A", 2: "Team A"}

    merged, _ = merge_broken_tracks(tracks, team_by_id, fps=FPS)

    assert set(merged.keys()) == {1, 2}


def test_does_not_merge_reappearance_too_far_away():
    tracks = {
        1: _track(range(0, 25), x_start=100),
        # Same team, small gap, but reappears 2000px away - not physically plausible.
        2: _track(range(30, 55), x_start=2100),
    }
    team_by_id = {1: "Team A", 2: "Team A"}

    merged, _ = merge_broken_tracks(tracks, team_by_id, fps=FPS)

    assert set(merged.keys()) == {1, 2}


def test_chain_of_three_fragments_collapses_into_one_track():
    tracks = {
        1: _track(range(0, 25), x_start=100),
        2: _track(range(45, 70), x_start=145),
        3: _track(range(90, 115), x_start=190),
    }
    team_by_id = {1: "Team A", 2: "Team A", 3: "Team A"}

    merged, _ = merge_broken_tracks(tracks, team_by_id, fps=FPS)

    assert set(merged.keys()) == {1}
    assert len(merged[1]) == 75


def test_referee_tracks_pass_through_untouched():
    tracks = {
        1: _track(range(0, 25), x_start=100),
        9: _track(range(0, 25), x_start=500, class_name="referee"),
    }
    team_by_id = {1: "Team A"}

    merged, merged_team = merge_broken_tracks(tracks, team_by_id, fps=FPS)

    assert 9 in merged
    assert merged[9] == tracks[9]
    assert 9 not in merged_team


def test_appearance_merge_reunites_same_player_across_a_long_gap(monkeypatch):
    tracks = {
        # 15s gap (375 frames @ 25fps) — far beyond merge_broken_tracks'
        # MERGE_MAX_GAP_SECONDS, but within the appearance pass's budget.
        1: _track(range(0, 25), x_start=100),
        2: _track(range(375, 400), x_start=900),  # reappears far away, same look
    }
    team_by_id = {1: "Team A", 2: "Team A"}
    same_player = np.array([1.0, 0.0, 0.0])
    _patch_embeddings(monkeypatch, {1: same_player, 2: same_player}, tracks)

    merged, merged_team = merge_broken_tracks_by_appearance(tracks, team_by_id, frames=["f"] * 400, fps=FPS)

    assert set(merged.keys()) == {1}
    assert len(merged[1]) == 50
    assert merged_team[1] == "Team A"


def test_appearance_merge_leaves_dissimilar_players_separate(monkeypatch):
    tracks = {
        1: _track(range(0, 25), x_start=100),
        2: _track(range(375, 400), x_start=900),
    }
    team_by_id = {1: "Team A", 2: "Team A"}
    _patch_embeddings(
        monkeypatch,
        {1: np.array([1.0, 0.0, 0.0]), 2: np.array([0.0, 1.0, 0.0])},
        tracks,
    )

    merged, _ = merge_broken_tracks_by_appearance(tracks, team_by_id, frames=["f"] * 400, fps=FPS)

    assert set(merged.keys()) == {1, 2}


def test_enforce_roster_size_merges_matching_fragment_and_drops_noise(monkeypatch):
    tracks = {
        1: _track(range(0, 100), x_start=100),      # kept, identity X
        2: _track(range(200, 300), x_start=100),    # kept, identity Y
        3: _track(range(400, 500), x_start=100),    # kept, identity Z
        4: _track(range(600, 620), x_start=100),    # leftover, same look as 1 -> merges into 1
        5: _track(range(700, 710), x_start=100),    # leftover, unlike anyone -> dropped
    }
    team_by_id = {tid: "Team A" for tid in tracks}
    vec_x, vec_y, vec_z = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])
    vec_noise = np.array([-1.0, -1.0, -1.0])
    _patch_embeddings(
        monkeypatch,
        {1: vec_x, 2: vec_y, 3: vec_z, 4: vec_x, 5: vec_noise},
        tracks,
    )

    result_tracks, result_team = enforce_roster_size(
        tracks, team_by_id, frames=["f"] * 800, fps=FPS, target_size=3
    )

    assert set(result_tracks.keys()) == {1, 2, 3}
    assert len(result_tracks[1]) == 120  # track 4's 20 frames folded into 1
    assert 5 not in result_tracks and 4 not in result_tracks
    assert set(result_team.keys()) == {1, 2, 3}


def test_enforce_roster_size_is_noop_when_under_target():
    tracks = {1: _track(range(0, 25), x_start=100), 2: _track(range(30, 55), x_start=900)}
    team_by_id = {1: "Team A", 2: "Team A"}

    result_tracks, result_team = enforce_roster_size(
        tracks, team_by_id, frames=[], fps=FPS, target_size=7
    )

    assert result_tracks == tracks
    assert result_team == team_by_id


def test_enforce_roster_size_disabled_when_target_is_none():
    tracks = {tid: _track(range(0, 10), x_start=tid * 500) for tid in range(1, 10)}
    team_by_id = {tid: "Team A" for tid in tracks}

    result_tracks, result_team = enforce_roster_size(
        tracks, team_by_id, frames=[], fps=FPS, target_size=None
    )

    assert result_tracks == tracks
    assert result_team == team_by_id


def test_enforce_roster_size_default_target_size_is_none():
    """Regression guard: target_size used to default to a hardcoded
    PLAYERS_PER_TEAM = 7, which silently trimmed any team over 7 players
    even when the caller never asked for a cap at all (the actual bug
    behind '11v11 gets miscounted as 7v7' — see run_pipeline.run for where
    the real per-match target now comes from instead). A team of 11 real
    players, capped by nothing but the function's own default, must come
    back untouched."""
    tracks = {tid: _track(range(0, 10), x_start=tid * 500) for tid in range(1, 12)}
    team_by_id = {tid: "Team A" for tid in tracks}

    result_tracks, result_team = enforce_roster_size(tracks, team_by_id, frames=[], fps=FPS)

    assert result_tracks == tracks
    assert result_team == team_by_id
