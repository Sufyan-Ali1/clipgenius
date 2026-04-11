"""
Configuration endpoints
"""

from fastapi import APIRouter

from app.models.responses import ConfigResponse
from app.core.config import settings

router = APIRouter()


@router.get(
    "/",
    response_model=ConfigResponse,
    summary="Get current configuration",
    description="Get the current API configuration settings",
)
async def get_config() -> ConfigResponse:
    """
    Get current configuration.

    Returns processing settings (not sensitive values like API keys).
    """
    return ConfigResponse(
        whisper_model=settings.WHISPER_MODEL,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
        num_clips=settings.NUM_CLIPS,
        min_clip_duration=settings.MIN_CLIP_DURATION,
        max_clip_duration=settings.MAX_CLIP_DURATION,
        vertical_mode=settings.VERTICAL_MODE,
        add_subtitles=settings.ADD_SUBTITLES,
        google_drive_enabled=settings.GOOGLE_DRIVE_ENABLED,
    )
