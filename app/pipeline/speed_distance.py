"""Speed and distance calculation (PRD sections 17-18).

Works on already camera-compensated, perspective-transformed positions
(in meters). Speed is computed over a sliding window of frames rather than
frame-to-frame, since per-frame jitter in detection/tracking would produce
noisy, unrealistic instantaneous speeds.
"""

from .utils import measure_distance

SPEED_WINDOW_FRAMES = 5  # ~0.2s at 25fps — smooths detection jitter


def compute_player_movement(
    positions_m: dict[int, tuple[float, float]], fps: float
) -> dict:
    """positions_m: {frame_index: (x_m, y_m)} for a single tracked player,
    already camera-compensated and perspective-transformed.

    Returns per-frame speed (km/h) plus total distance (m) and
    average/min/max speed for the whole track.
    """
    frame_indices = sorted(positions_m.keys())
    speeds_kmh: dict[int, float] = {}
    total_distance_m = 0.0

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
        speeds_kmh[current_frame] = speed_m_per_s * 3.6

        # Total distance accumulates frame-to-frame (not window-to-window)
        # to avoid double counting.
        if i > 0:
            prev_frame = frame_indices[i - 1]
            total_distance_m += measure_distance(
                positions_m[prev_frame], positions_m[current_frame]
            )

    if not speeds_kmh:
        return {
            "per_frame_speed_kmh": {},
            "average_speed_kmh": 0.0,
            "minimum_speed_kmh": 0.0,
            "maximum_speed_kmh": 0.0,
            "total_distance_m": round(total_distance_m, 1),
        }

    values = list(speeds_kmh.values())
    return {
        "per_frame_speed_kmh": speeds_kmh,
        "average_speed_kmh": round(sum(values) / len(values), 2),
        "minimum_speed_kmh": round(min(values), 2),
        "maximum_speed_kmh": round(max(values), 2),
        "total_distance_m": round(total_distance_m, 1),
    }
