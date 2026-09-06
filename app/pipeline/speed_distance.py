"""Speed and distance calculation (PRD sections 17-18).

Works on already camera-compensated, perspective-transformed positions
(in meters). Speed is computed over a sliding window of frames rather than
frame-to-frame, since per-frame jitter in detection/tracking would produce
noisy, unrealistic instantaneous speeds.
"""

from .utils import measure_distance

SPEED_WINDOW_FRAMES = 5  # ~0.2s at 25fps — smooths detection jitter

# No human football player has ever been recorded going anywhere near this
# in a match. The best-documented figures (verified against multiple
# sources): Kylian Mbappe's ~38 km/h is the most-cited highest speed ever
# officially recorded in professional football (including 37.61 km/h at
# the 2026 World Cup); the Premier League's own on-record fastest sprint is
# Micky van de Ven at 37.38 km/h. Usain Bolt's ~44.72 km/h sprinting peak is
# NOT a valid reference point here — that's a specialized 100m sprinter at
# a dead run in spikes, not a footballer changing direction on grass in
# football boots across 90 minutes, and no footballer has come close to it.
# 40 km/h is a deliberate small buffer above that ~38 km/h real-world
# ceiling: enough to not clip a genuine record-approaching sprint, not so
# much that it stops doing its actual job below.
MAX_PLAUSIBLE_PLAYER_SPEED_KMH = 40.0

# The ball isn't human, so it needs its own (much higher) ceiling, but it
# still isn't unbounded — the same perspective-transform noise amplification
# that inflated player speeds does the same to the ball, and "uncapped"
# still let one real run report a 540 km/h shot. The hardest recorded
# football strikes sit around 130 km/h; this leaves real margin above that
# without also passing through the noise as gospel.
MAX_PLAUSIBLE_BALL_SPEED_KMH = 150.0


def compute_player_movement(
    positions_m: dict[int, tuple[float, float]],
    fps: float,
    max_plausible_speed_kmh: float | None = None,
) -> dict:
    """positions_m: {frame_index: (x_m, y_m)} for a single tracked player,
    already camera-compensated and perspective-transformed.

    max_plausible_speed_kmh excludes windowed speed samples (and distance
    steps whose implied speed) above the ceiling, treating them as noise
    rather than real measurements — leave it None for the ball, which can
    legitimately exceed any human speed cap.

    This used to CLAMP an implausible reading down to the ceiling instead
    of excluding it, which silently corrupted the reported numbers in a way
    that looked like real data: a noisy window computing to, say, 200 km/h
    and a genuinely fast sprint at 39 km/h both ended up reported as the
    exact same flat value (the ceiling), indistinguishable from each other
    and from every other capped noise sample in the same track. Excluding
    an implausible sample instead means maximum_speed_kmh reflects the
    fastest reading actually trusted as real, not an artificial ceiling
    that every noisy or near-record-fast track alike gets pinned to.

    Returns per-frame speed (km/h) plus total distance (m) and
    average/min/max speed for the whole track.
    """
    max_plausible_m_per_s = (
        max_plausible_speed_kmh / 3.6 if max_plausible_speed_kmh is not None else None
    )

    frame_indices = sorted(positions_m.keys())
    speeds_kmh: dict[int, float] = {}
    # Cumulative distance-so-far at each frame (not just the final total) —
    # lets the annotated video show a live "X.XX m" readout per player per
    # frame, the same way it shows a live speed reading.
    per_frame_distance_m: dict[int, float] = {}
    total_distance_m = 0.0
    if frame_indices:
        per_frame_distance_m[frame_indices[0]] = 0.0

    for i in range(len(frame_indices)):
        current_frame = frame_indices[i]
        window_start_idx = max(0, i - SPEED_WINDOW_FRAMES)
        window_start_frame = frame_indices[window_start_idx]

        if window_start_frame == current_frame:
            continue

        distance = measure_distance(
            positions_m[window_start_frame], positions_m[current_frame]
        )
        elapsed_seconds = (current_frame - window_start_frame) / fps
        if elapsed_seconds <= 0:
            continue

        speed_m_per_s = distance / elapsed_seconds
        # Exclude (not clamp) an implausible window — see the docstring for
        # why clamping silently made noise and real fast sprints look alike.
        if max_plausible_m_per_s is None or speed_m_per_s <= max_plausible_m_per_s:
            speeds_kmh[current_frame] = speed_m_per_s * 3.6

        # Total distance accumulates frame-to-frame (not window-to-window)
        # to avoid double counting.
        if i > 0:
            prev_frame = frame_indices[i - 1]
            step_distance = measure_distance(
                positions_m[prev_frame], positions_m[current_frame]
            )
            step_seconds = (current_frame - prev_frame) / fps
            step_is_plausible = (
                max_plausible_m_per_s is None
                or step_seconds <= 0
                or (step_distance / step_seconds) <= max_plausible_m_per_s
            )
            # An implausible single-frame jump is excluded from the running
            # total entirely, same reasoning as the speed exclusion above —
            # a fabricated "at most this far" contribution is still a
            # fabricated number, just a smaller one. per_frame_distance_m
            # still gets an entry for every frame (carrying the total
            # forward unchanged) since it's read as a live running total by
            # the annotated-video overlay, which needs a value for every
            # frame regardless of whether this particular step was trusted.
            if step_is_plausible:
                total_distance_m += step_distance
            per_frame_distance_m[current_frame] = total_distance_m

    if not speeds_kmh:
        return {
            "per_frame_speed_kmh": {},
            "per_frame_distance_m": per_frame_distance_m,
            "average_speed_kmh": 0.0,
            "minimum_speed_kmh": 0.0,
            "maximum_speed_kmh": 0.0,
            "total_distance_m": round(total_distance_m, 1),
        }

    values = list(speeds_kmh.values())
    return {
        "per_frame_speed_kmh": speeds_kmh,
        "per_frame_distance_m": per_frame_distance_m,
        "average_speed_kmh": round(sum(values) / len(values), 2),
        "minimum_speed_kmh": round(min(values), 2),
        "maximum_speed_kmh": round(max(values), 2),
        "total_distance_m": round(total_distance_m, 1),
    }
