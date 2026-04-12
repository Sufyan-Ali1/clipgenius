"""
Settings management using Pydantic
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Settings
    API_TITLE: str = "Video Clips Extractor API"
    API_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    OUTPUTS_DIR: Path = STORAGE_DIR / "outputs"
    TEMP_DIR: Path = STORAGE_DIR / "temp"

    # Whisper Settings
    WHISPER_PROVIDER: str = "groq"  # Options: groq, local
    WHISPER_MODEL: str = "whisper-large-v3"  # For Groq; use "base", "small", "medium" for local
    WHISPER_LANGUAGE: Optional[str] = None
    WHISPER_CHUNK_DURATION: int = 600  # 10 minutes per chunk (for files > 25MB)

    # LLM Settings
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.3

    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    TOGETHER_API_KEY: Optional[str] = None

    # Clip Settings
    NUM_CLIPS: int = 5
    MIN_CLIP_DURATION: int = 30
    MAX_CLIP_DURATION: int = 90
    MIN_VIRALITY_SCORE: float = 6.0

    # Video Settings
    VERTICAL_MODE: bool = True
    VERTICAL_WIDTH: int = 1080
    VERTICAL_HEIGHT: int = 1920
    VERTICAL_METHOD: str = "blur_padding"
    VIDEO_QUALITY: str = "high"

    # Subtitle Settings
    ADD_SUBTITLES: bool = False  # Disabled by default, user can enable via frontend
    SUBTITLE_FONT: str = "Arial"
    SUBTITLE_FONT_SIZE: int = 24
    SUBTITLE_COLOR: str = "white"
    SUBTITLE_OUTLINE_COLOR: str = "black"
    SUBTITLE_POSITION: str = "bottom"

    # Google Drive Settings
    GOOGLE_CREDENTIALS_PATH: Optional[str] = None
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = None
    GOOGLE_DRIVE_ENABLED: bool = False  # Disabled - clips served from server
    DELETE_CLIPS_AFTER_UPLOAD: bool = True

    # Clip Retention Settings
    CLIP_RETENTION_HOURS: int = 1  # Auto-delete clips after this many hours

    # YouTube Settings
    YOUTUBE_QUALITY: str = "best"  # Options: best, 4k, 2k, 1080p, 720p, 480p
    YOUTUBE_FORMAT: str = "bestvideo+bestaudio/best"
    DELETE_DOWNLOADED_VIDEO: bool = True

    # Cleanup
    CLEANUP_TEMP: bool = True
    VERBOSE: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()
