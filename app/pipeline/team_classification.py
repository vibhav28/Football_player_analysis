"""Jersey-color based team classification (PRD section 13).

Clusters players into two visual groups (Team A / Team B) with K-Means on
jersey color, sampled once per player from an early frame and then reused
for that tracking_id for the rest of the video, since jersey color doesn't
change mid-match.
"""

import numpy as np

TEAM_LABELS = {0: "Team A", 1: "Team B"}


def _kmeans_fit(
    data: np.ndarray, n_clusters: int, n_init: int = 10, max_iter: int = 100, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """Minimal, dependency-free Lloyd's-algorithm K-Means.

    Deliberately not scikit-learn: scikit-learn's KMeans links its own
    OpenMP runtime, separate from the one torch/ultralytics already loads
    for YOLO detection. Calling it here — up to ~15 times per video (once
    per player for jersey-color extraction, plus once for the final
    2-team split) right after a torch-heavy detection pass — reliably
    segfaulted the whole backend process (two OpenMP runtimes racing in
    the same process; see app/pipeline/__init__.py and
    processing_manager.py for the full story). Inputs here are tiny
    (never more than a few thousand pixels, k=2), so a plain NumPy
    implementation is both simple and fast enough, and it removes the
    conflicting runtime entirely rather than just mitigating it.

    Returns (labels, cluster_centers), matching the pieces of sklearn's
    KMeans this module actually used. Runs `n_init` random restarts and
    keeps the lowest-inertia result.
    """
    if len(data) == 0:
        raise ValueError("Cannot cluster empty data")

    n_clusters = min(n_clusters, len(data))
    rng = np.random.default_rng(seed)

    best_labels = None
    best_centers = None
    best_inertia = np.inf

    for _ in range(n_init):
        centers = data[rng.choice(len(data), size=n_clusters, replace=False)].copy()

        for _ in range(max_iter):
            distances = np.linalg.norm(data[:, None, :] - centers[None, :, :], axis=2)
            labels = np.argmin(distances, axis=1)
            new_centers = np.array(
                [
                    data[labels == k].mean(axis=0) if np.any(labels == k) else centers[k]
                    for k in range(n_clusters)
                ]
            )
            converged = np.allclose(new_centers, centers)
            centers = new_centers
            if converged:
                break

        distances = np.linalg.norm(data[:, None, :] - centers[None, :, :], axis=2)
        labels = np.argmin(distances, axis=1)
        inertia = float(np.sum((data - centers[labels]) ** 2))

        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels
            best_centers = centers

    return best_labels, best_centers


def get_player_color(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Sample the dominant color of a player's jersey — the torso region
    (horizontal center, upper-but-not-topmost band), not the full top half.

    At typical broadcast-camera player sizes (bboxes as small as ~25x50px
    at this project's tested resolution), background/pitch bleeding into
    the box edges can easily outnumber true jersey pixels — verified on
    real detections, where a white-kit player's top-half crop split
    62%/38% background/jersey. Assuming "the larger cluster is the
    jersey" then picks background instead, which is what was happening.
    Narrowing the sample region to the torso avoids relying on that
    assumption at all, rather than trying to guess which cluster is which
    after the fact.
    """
    x1, y1, x2, y2 = (int(v) for v in bbox)
    width, height = x2 - x1, y2 - y1
    # horizontal center 60%, vertical band 15%-55% (skips the head and
    # stays well above the shorts/socks line)
    tx1 = x1 + int(width * 0.2)
    tx2 = x1 + int(width * 0.8)
    ty1 = y1 + int(height * 0.15)
    ty2 = y1 + int(height * 0.55)
    torso = frame[ty1:ty2, tx1:tx2]

    if torso.size == 0:
        crop = frame[y1:y2, x1:x2]
        return crop.reshape(-1, 3).astype(np.float32).mean(axis=0) if crop.size else np.array([0, 0, 0])

    pixels = torso.reshape(-1, 3).astype(np.float32)
    if len(pixels) < 2:
        return pixels.mean(axis=0) if len(pixels) else np.array([0, 0, 0])

    # Still 2-means the torso crop (rather than a flat mean) so a stray
    # shadow/highlight band within the torso region doesn't wash out the
    # true jersey color — but now pick the lower-variance (tighter) of
    # the two clusters as the jersey, since fabric under roughly uniform
    # lighting is more internally consistent than a grass/shadow/skin
    # mix, regardless of which cluster happens to be larger.
    labels, centers = _kmeans_fit(pixels, n_clusters=2, n_init=5, seed=0)
    variances = [
        float(np.var(pixels[labels == k])) if np.any(labels == k) else np.inf
        for k in range(len(centers))
    ]
    tightest_cluster = int(np.argmin(variances))
    return centers[tightest_cluster]


def assign_teams(
    frames: list[np.ndarray],
    tracks: dict[int, dict[int, dict]],
) -> dict[int, str]:
    """Assign each tracking_id to Team A or Team B.

    Samples one representative color per player (first frame they appear
    in), fits a single 2-cluster K-Means over all players, then labels
    clusters as Team A / Team B.
    """
    player_ids = [
        tid for tid, track in tracks.items()
        if any(f["class_name"] == "player" for f in track.values())
    ]

    colors_by_id: dict[int, np.ndarray] = {}
    for tracking_id in player_ids:
        track = tracks[tracking_id]
        first_frame_index = min(track.keys())
        bbox = track[first_frame_index]["bbox"]
        colors_by_id[tracking_id] = get_player_color(frames[first_frame_index], bbox)

    if len(colors_by_id) < 2:
        return {tid: "Team A" for tid in colors_by_id}

    ids = list(colors_by_id.keys())
    color_matrix = np.array([colors_by_id[tid] for tid in ids])

    labels, _ = _kmeans_fit(color_matrix, n_clusters=2, n_init=10, seed=0)

    return {
        tracking_id: TEAM_LABELS[label]
        for tracking_id, label in zip(ids, labels)
    }
