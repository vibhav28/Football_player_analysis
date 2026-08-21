from typing import Literal, Optional

from pydantic import BaseModel

JobStatus = Literal["Uploaded", "Processing", "Completed", "Failed"]


class ProcessingStep(BaseModel):
    name: str
    status: Literal["waiting", "running", "done", "failed"]


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
