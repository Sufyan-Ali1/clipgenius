"""
Download Service - Single Responsibility: YouTube video download

Downloads videos from YouTube using yt-dlp.
"""

import re
from pathlib import Path
from typing import Callable, Optional
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("download_service")


class DownloadService:
    """
    Single Responsibility: Download videos from YouTube.
    """

    YOUTUBE_PATTERNS = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+',
    ]

    def __init__(self, quality: str = None):
        self.output_dir = settings.UPLOADS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quality = quality or settings.YOUTUBE_QUALITY
        self.format = settings.YOUTUBE_FORMAT

    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube video URL."""
        for pattern in self.YOUTUBE_PATTERNS:
            if re.match(pattern, url):
                return True
        return False

    def _get_ydl_opts(self, output_path: Path) -> dict:
        """Get yt-dlp options."""
        quality_map = {
            "best": "bestvideo+bestaudio/best",
            "4k": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
            "2k": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        }

        format_str = quality_map.get(self.quality.lower(), quality_map["best"])

        return {
            'format': format_str,
            'outtmpl': str(output_path / '%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
            'merge_output_format': 'mp4',
        }

    def _progress_hook(self, d: dict):
        """Progress callback for download status."""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            logger.info(f"Downloading: {percent} at {speed}")
        elif d['status'] == 'finished':
            logger.info("Download complete, processing...")

    def _get_video_info(self, url: str) -> dict:
        """Get video information without downloading."""
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'channel': info.get('channel', 'Unknown'),
                'view_count': info.get('view_count', 0),
            }

    def _download_sync(self, url: str, output_dir: Optional[Path] = None) -> Path:
        """Synchronous download."""
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

        output_path = Path(output_dir) if output_dir else self.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info("Fetching video info...")
        info = self._get_video_info(url)
        logger.info(f"  Title: {info['title']}")
        logger.info(f"  Duration: {info['duration'] // 60}:{info['duration'] % 60:02d}")
        logger.info(f"  Channel: {info['channel']}")

        logger.info(f"Downloading video (quality: {self.quality})...")

        ydl_opts = self._get_ydl_opts(output_path)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            if 'requested_downloads' in info:
                filename = info['requested_downloads'][0]['filepath']
            else:
                filename = ydl.prepare_filename(info)
                base = Path(filename).stem
                for ext in ['mp4', 'mkv', 'webm']:
                    potential = output_path / f"{base}.{ext}"
                    if potential.exists():
                        filename = str(potential)
                        break

        video_path = Path(filename)

        if not video_path.exists():
            sanitized_title = re.sub(r'[^\w\s-]', '', info.get('title', 'video'))
            sanitized_title = re.sub(r'\s+', '_', sanitized_title)
            for file in output_path.glob(f"*{sanitized_title}*"):
                if file.suffix in ['.mp4', '.mkv', '.webm']:
                    video_path = file
                    break

        if not video_path.exists():
            raise FileNotFoundError("Downloaded video not found")

        logger.info(f"Video saved: {video_path}")
        logger.info(f"File size: {video_path.stat().st_size / (1024*1024):.1f} MB")

        return video_path

    async def download(
        self,
        url: str,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """
        Download video from YouTube.

        Args:
            url: YouTube video URL
            output_dir: Optional output directory
            progress_callback: Optional callback(progress, message)

        Returns:
            Path to downloaded video file
        """
        logger.info(f"Downloading from YouTube: {url}")

        if progress_callback:
            progress_callback(0.0, "Connecting to YouTube...")

        loop = asyncio.get_event_loop()

        if progress_callback:
            progress_callback(0.1, "Downloading video...")

        video_path = await loop.run_in_executor(
            None,
            self._download_sync,
            url,
            output_dir,
        )

        if progress_callback:
            progress_callback(1.0, "Download complete")

        return video_path

    async def delete_video(self, video_path: Path) -> bool:
        """Delete a downloaded video file."""
        try:
            if video_path.exists():
                video_path.unlink()
                logger.info(f"Deleted video: {video_path}")
                return True
        except Exception as e:
            logger.warning(f"Could not delete video: {e}")
        return False
