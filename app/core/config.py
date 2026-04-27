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

    # CORS Settings (comma-separated list of allowed origins)
    CORS_ORIGINS: str = "*"  # e.g., "https://your-app.vercel.app,https://another-domain.com"

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    OUTPUTS_DIR: Path = STORAGE_DIR / "outputs"
    TEMP_DIR: Path = STORAGE_DIR / "temp"
    ASSETS_DIR: Path = BASE_DIR / "assets"

    # Whisper Settings (Groq API)
    WHISPER_MODEL: str = "whisper-large-v3"
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
    MIN_CLIP_DURATION: int = 60
    MAX_CLIP_DURATION: int = 100
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

    # Watermark Settings
    WATERMARK_ENABLED: bool = True
    WATERMARK_PATH: Optional[Path] = None  # Will default to assets/watermark.png
    WATERMARK_OPACITY: float = 0.3  # 30% opacity (0.0 = invisible, 1.0 = fully opaque)
    WATERMARK_SCALE: float = 0.1  # 10% of video width
    WATERMARK_POSITION: str = "bottom_right"  # bottom_right, bottom_left, top_right, top_left
    WATERMARK_MARGIN: int = 20  # pixels from edge

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
    YOUTUBE_COOKIES: Optional[str] = None  # Cookies content for YouTube auth (paste cookies.txt content)
    DELETE_DOWNLOADED_VIDEO: bool = True

    # Residential Proxy Settings (IPRoyal)
    PROXY_ENABLED: bool = False
    PROXY_HOST: Optional[str] = None  # e.g., geo.iproyal.com
    PROXY_PORT: Optional[int] = None  # e.g., 12321
    PROXY_USER: Optional[str] = None
    PROXY_PASS: Optional[str] = None

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
        self.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    def get_watermark_path(self) -> Optional[Path]:
        """Get watermark path, defaulting to assets/watermark.png."""
        if self.WATERMARK_PATH:
            return self.WATERMARK_PATH
        default_path = self.ASSETS_DIR / "watermark.png"
        return default_path if default_path.exists() else None


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()
