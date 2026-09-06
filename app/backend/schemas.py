from typing import Literal, Optional

from pydantic import BaseModel

JobStatus = Literal["Uploaded", "Processing", "Completed", "Failed"]


class ProcessingStep(BaseModel):
    name: str
    status: Literal["waiting", "running", "done", "failed"]


class CalibrationPoint(BaseModel):
    """One pixel corner plus the timestamp it was picked at. Points don't
    all have to come from the same frame — a camera pan/zoom means no
    single frame always shows all four pitch corners, so the calibration
    UI lets each point be placed on whatever frame is on screen when it's
    clicked."""

    x: float
    y: float
    time_seconds: float


MatchFormat = Literal["5v5", "7v7", "9v9", "11v11", "custom"]

# players_per_team, pitch_width_m, pitch_length_m per standard format.
# 11v11 matches PerspectiveTransformer's own FIFA-standard default exactly.
# The smaller formats are reasonable grassroots/FA-style approximations,
# not authoritative pitch dimensions for any specific venue -- match_format
# "custom" (with explicit pitch_width_m/pitch_length_m) is the accurate
# path when the real pitch has been measured.
MATCH_FORMAT_PRESETS: dict[str, tuple[int, float, float]] = {
    "5v5": (5, 20.0, 40.0),
    "7v7": (7, 40.0, 60.0),
    "9v9": (9, 50.0, 82.0),
    "11v11": (11, 68.0, 105.0),
}


class CalibrationRequest(BaseModel):
    """Body for POST /{video_id}/calibrate (PRD section 35, Perspective
    Calibration). Four pixel corners of a known rectangular pitch region,
    ordered top-left, top-right, bottom-right, bottom-left, each tagged
    with the video timestamp it was picked at (see CalibrationPoint).
    Omit pitch_pixel_corners to skip calibration and proceed with
    speed/distance reported as 0.

    match_format optionally selects a standard preset from
    MATCH_FORMAT_PRESETS, which sets both the expected per-team player
    count and pitch dimensions together (both are consequences of the same
    real-world choice -- a 7v7 match is both fewer players AND a smaller
    pitch). Explicit players_per_team/pitch_width_m/pitch_length_m values,
    if given, override the selected preset's individual fields (or stand
    alone under match_format="custom"/omitted). Omitting match_format and
    all three overrides means the caller didn't specify a format at all --
    see run_pipeline.run's players_per_team default (a generous safety
    cap, not a forced squad size) and PerspectiveTransformer's 68m/105m
    default for what that falls back to.
    """

    pitch_pixel_corners: Optional[list[CalibrationPoint]] = None
    match_format: Optional[MatchFormat] = None
    players_per_team: Optional[int] = None
    pitch_width_m: Optional[float] = None
    pitch_length_m: Optional[float] = None


class Job(BaseModel):
    """Persisted as results/<video_id>/job.json — this is the file-based
    stand-in for a jobs table (PRD section 27/29)."""

    video_id: str
    original_filename: str
    status: JobStatus
    error_message: Optional[str] = None
    steps: list[ProcessingStep] = []


class PlayerStats(BaseModel):
    tracking_id: int
    team: str
    average_speed_kmh: float
    minimum_speed_kmh: float
    maximum_speed_kmh: float
    total_distance_m: float


class VideoMeta(BaseModel):
    filename: str
    duration: float
    fps: float


class StatisticsResult(BaseModel):
    video: VideoMeta
    players: list[PlayerStats]
