"""
FastAPI dependencies for dependency injection
"""

from app.services.job_service import JobService, get_job_service
from app.services.transcription_service import TranscriptionService
from app.services.analysis_service import AnalysisService
from app.services.selection_service import SelectionService
from app.services.video_service import VideoService
from app.services.subtitle_service import SubtitleService
from app.services.download_service import DownloadService
from app.services.storage_service import StorageService


def get_transcription_service() -> TranscriptionService:
    """Get TranscriptionService instance."""
    return TranscriptionService()


def get_analysis_service() -> AnalysisService:
    """Get AnalysisService instance."""
    return AnalysisService()


def get_selection_service() -> SelectionService:
    """Get SelectionService instance."""
    return SelectionService()


def get_video_service() -> VideoService:
    """Get VideoService instance."""
    return VideoService()


def get_subtitle_service() -> SubtitleService:
    """Get SubtitleService instance."""
    return SubtitleService()


def get_download_service() -> DownloadService:
    """Get DownloadService instance."""
    return DownloadService()


def get_storage_service() -> StorageService:
    """Get StorageService instance."""
    return StorageService()


__all__ = [
    "get_job_service",
    "get_transcription_service",
    "get_analysis_service",
    "get_selection_service",
    "get_video_service",
    "get_subtitle_service",
    "get_download_service",
    "get_storage_service",
]
