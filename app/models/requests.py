"""
Pydantic request models
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


class JobRequest(BaseModel):
    """Request model for creating a new processing job.

    Only input_source is required. All other fields are optional and
    default to values from .env settings.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input_source": "https://youtube.com/watch?v=xxxxx"
            }
        }
    )

    input_source: str = Field(
        ...,
        description="Path to video file OR YouTube URL"
    )

    # All optional - defaults come from .env settings
    num_clips: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        json_schema_extra={"hidden": True}
    )
    min_duration: Optional[int] = Field(
        default=None,
        ge=15,
        le=120,
        json_schema_extra={"hidden": True}
    )
    max_duration: Optional[int] = Field(
        default=None,
        ge=30,
        le=180,
        json_schema_extra={"hidden": True}
    )
    add_subtitles: Optional[bool] = Field(
        default=None,
        json_schema_extra={"hidden": True}
    )
    vertical_mode: Optional[bool] = Field(
        default=None,
        json_schema_extra={"hidden": True}
    )
    upload_to_drive: Optional[bool] = Field(
        default=None,
        json_schema_extra={"hidden": True}
    )
    provider: Optional[str] = Field(
        default=None,
        json_schema_extra={"hidden": True}
    )
    model: Optional[str] = Field(
        default=None,
        json_schema_extra={"hidden": True}
    )
    video_quality: Optional[str] = Field(
        default=None,
        json_schema_extra={"hidden": True}
    )

    @field_validator("input_source")
    @classmethod
    def validate_input_source(cls, v: str) -> str:
        """Validate input source is either a file path or YouTube URL."""
        v = v.strip()
        if not v:
            raise ValueError("Input source cannot be empty")
        return v

    @field_validator("max_duration")
    @classmethod
    def validate_max_duration(cls, v: Optional[int], info) -> Optional[int]:
        """Ensure max_duration is greater than min_duration."""
        if v is None:
            return v
        min_dur = info.data.get("min_duration")
        if min_dur is not None and v <= min_dur:
            raise ValueError("max_duration must be greater than min_duration")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        """Validate LLM provider."""
        if v is None:
            return v
        valid_providers = ["openai", "gemini", "groq", "together", "ollama"]
        if v.lower() not in valid_providers:
            raise ValueError(f"Provider must be one of: {', '.join(valid_providers)}")
        return v.lower()

    @field_validator("video_quality")
    @classmethod
    def validate_video_quality(cls, v: Optional[str]) -> Optional[str]:
        """Validate video quality."""
        if v is None:
            return v
        valid_qualities = ["best", "4k", "2k", "1080p", "720p", "480p"]
        if v.lower() not in valid_qualities:
            raise ValueError(f"Quality must be one of: {', '.join(valid_qualities)}")
        return v.lower()
