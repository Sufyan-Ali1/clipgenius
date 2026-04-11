"""
Status enums for job tracking
"""

from enum import Enum


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    SELECTING = "selecting"
    CUTTING = "cutting"
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
