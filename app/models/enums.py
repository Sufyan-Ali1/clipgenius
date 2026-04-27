"""
Status enums for job tracking
"""

from enum import Enum


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    UPLOADING_VIDEO = "uploading_video"  # Receiving uploaded video from client
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    SELECTING = "selecting"
    CUTTING = "cutting"
    CLIP_METADATA = "clip_metadata"
    SUBTITLING = "subtitling"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        """Check if job is actively processing."""
        return self not in (
            JobStatus.PENDING,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )
