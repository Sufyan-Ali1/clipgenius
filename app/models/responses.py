"""
Pydantic response models
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from .enums import JobStatus


class ClipInfo(BaseModel):
    """Information about a generated clip."""

    clip_number: int = Field(..., description="Clip number in sequence")
    filename: str = Field(..., description="Output filename")
    start_seconds: float = Field(..., description="Start time in source video")
    end_seconds: float = Field(..., description="End time in source video")
    duration: float = Field(..., description="Clip duration in seconds")
    hook: Optional[str] = Field(None, description="Opening hook text")
    score: Optional[float] = Field(None, description="Virality score")
    drive_link: Optional[str] = Field(None, description="Google Drive link if uploaded")


class JobResults(BaseModel):
    """Results of a completed job."""

    clips: List[ClipInfo] = Field(default_factory=list, description="Generated clips")
    output_directory: Optional[str] = Field(None, description="Local output directory")
    drive_folder_link: Optional[str] = Field(None, description="Google Drive folder link")
    total_duration: Optional[float] = Field(None, description="Total clips duration")


class JobResponse(BaseModel):
    """Response model for job status."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Progress from 0.0 to 1.0"
    )
    current_step: str = Field(
        default="Pending",
        description="Description of current processing step"
    )
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    input_source: str = Field(..., description="Original input source")
    results: Optional[JobResults] = Field(None, description="Job results when completed")
    error: Optional[str] = Field(None, description="Error message if failed")


class JobListResponse(BaseModel):
    """Response model for listing jobs."""

    jobs: List[JobResponse] = Field(default_factory=list, description="List of jobs")
    total: int = Field(default=0, description="Total number of jobs")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.now, description="Current time")


class ConfigResponse(BaseModel):
    """Configuration response."""

    whisper_model: str
    llm_provider: str
    llm_model: str
    num_clips: int
    min_clip_duration: int
    max_clip_duration: int
    vertical_mode: bool
    add_subtitles: bool
    google_drive_enabled: bool


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
