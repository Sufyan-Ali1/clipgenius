"""
Download Service - Single Responsibility: YouTube video download

Downloads videos from YouTube using residential proxy:
- Extracts video URL via proxy
- Downloads video via proxy (URLs are IP-locked)
"""

import re
import httpx
import subprocess
from pathlib import Path
from typing import Callable, Optional
import asyncio
import time

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("download_service")


class DownloadService:
    """
    Single Responsibility: Download videos from YouTube using residential proxy.
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

        # Log proxy configuration status
        logger.info("=" * 50)
        logger.info("DOWNLOAD SERVICE INITIALIZED")
        logger.info(f"PROXY_ENABLED: {settings.PROXY_ENABLED}")
        if settings.PROXY_ENABLED:
            logger.info(f"PROXY_HOST: {settings.PROXY_HOST}")
            logger.info(f"PROXY_PORT: {settings.PROXY_PORT}")
            logger.info(f"PROXY_USER: {settings.PROXY_USER[:4]}****" if settings.PROXY_USER else "PROXY_USER: Not set")
            logger.info(f"PROXY_PASS: ****" if settings.PROXY_PASS else "PROXY_PASS: Not set")
            if all([settings.PROXY_HOST, settings.PROXY_PORT, settings.PROXY_USER, settings.PROXY_PASS]):
                logger.info("PROXY STATUS: Ready to use")
            else:
                logger.warning("PROXY STATUS: Missing configuration!")
        else:
            logger.warning("PROXY STATUS: DISABLED - YouTube downloads will fail!")
        logger.info("=" * 50)

    def _get_proxy_url(self) -> Optional[str]:
        """Get proxy URL string for requests."""
        if not settings.PROXY_ENABLED:
            logger.warning("_get_proxy_url: PROXY_ENABLED is False")
            return None
        if not all([settings.PROXY_HOST, settings.PROXY_PORT, settings.PROXY_USER, settings.PROXY_PASS]):
            logger.warning("_get_proxy_url: Missing proxy configuration")
            logger.warning(f"  PROXY_HOST: {'Set' if settings.PROXY_HOST else 'MISSING'}")
            logger.warning(f"  PROXY_PORT: {'Set' if settings.PROXY_PORT else 'MISSING'}")
            logger.warning(f"  PROXY_USER: {'Set' if settings.PROXY_USER else 'MISSING'}")
            logger.warning(f"  PROXY_PASS: {'Set' if settings.PROXY_PASS else 'MISSING'}")
            return None
        proxy_url = f"http://{settings.PROXY_USER}:{settings.PROXY_PASS}@{settings.PROXY_HOST}:{settings.PROXY_PORT}"
        logger.info(f"Proxy URL configured: http://{settings.PROXY_USER[:4]}****:****@{settings.PROXY_HOST}:{settings.PROXY_PORT}")
        return proxy_url

    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube video URL."""
        for pattern in self.YOUTUBE_PATTERNS:
            if re.match(pattern, url):
                return True
        return False

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _download_with_proxy_smart(self, url: str, output_path: Path) -> Optional[Path]:
        """
        Smart proxy approach: Use proxy ONLY to extract direct video URL,
        then download the actual video directly (saves proxy bandwidth).
        """
        proxy_url = self._get_proxy_url()
        if not proxy_url:
            logger.error("Proxy URL is not configured")
            return None

        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp not installed")
            return None

        video_id = self._extract_video_id(url)
        if not video_id:
            logger.error(f"Could not extract video ID from URL: {url}")
            return None

        try:
            logger.info(f"Using residential proxy to extract video URLs...")
            logger.info(f"Proxy: {settings.PROXY_HOST}:{settings.PROXY_PORT}")

            # Step 1: Use proxy to extract video info and direct URLs
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'proxy': proxy_url,
                'socket_timeout': 30,
                'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web']}},
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                logger.warning("Could not extract video info via proxy")
                return None

            title = info.get('title', 'video')
            logger.info(f"Found video via proxy: {title}")

            # Get the best format URLs
            formats = info.get('formats', [])
            if not formats:
                logger.warning("No formats found")
                return None

            # Find best video and audio formats
            video_url = None
            audio_url = None

            # Filter video formats (prefer mp4, max 1080p)
            video_formats = [f for f in formats if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') == 'none']
            video_formats = [f for f in video_formats if (f.get('height') or 0) <= 1080]
            video_formats.sort(key=lambda x: (x.get('height') or 0), reverse=True)

            # Filter audio formats
            audio_formats = [f for f in formats if f.get('acodec', 'none') != 'none' and f.get('vcodec', 'none') == 'none']
            audio_formats.sort(key=lambda x: (x.get('abr') or 0), reverse=True)

            # Get best combined format as fallback
            combined_formats = [f for f in formats if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none']
            combined_formats = [f for f in combined_formats if (f.get('height') or 0) <= 1080]
            combined_formats.sort(key=lambda x: (x.get('height') or 0), reverse=True)

            if video_formats and audio_formats:
                video_format = video_formats[0]
                audio_format = audio_formats[0]
                video_url = video_format.get('url')
                audio_url = audio_format.get('url')
                logger.info(f"Got separate streams: {video_format.get('height')}p video + {audio_format.get('abr')}kbps audio")
            elif combined_formats:
                video_format = combined_formats[0]
                video_url = video_format.get('url')
                logger.info(f"Got combined stream: {video_format.get('height')}p")

            if not video_url:
                logger.warning("Could not find suitable video URL")
                return None

            # Step 2: Download video THROUGH proxy (URLs are IP-locked)
            logger.info("Downloading video through proxy (URLs are IP-locked to proxy IP)...")
            video_filename = output_path / f"video_{int(time.time())}.mp4"
            temp_video = output_path / f"temp_video_{int(time.time())}.mp4"
            temp_audio = output_path / f"temp_audio_{int(time.time())}.m4a"

            # Download video stream through proxy
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://www.youtube.com',
                'Referer': 'https://www.youtube.com/',
            }

            logger.info("Downloading video stream through proxy...")
            with httpx.stream("GET", video_url, headers=headers, timeout=600.0, follow_redirects=True, proxy=proxy_url) as stream:
                stream.raise_for_status()
                total = int(stream.headers.get('content-length', 0))
                downloaded = 0
                with open(temp_video if audio_url else video_filename, "wb") as f:
                    for chunk in stream.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            percent = (downloaded / total) * 100
                            if downloaded % (5 * 1024 * 1024) < 65536:  # Log every 5MB
                                logger.info(f"Video: {percent:.1f}% ({downloaded / 1024 / 1024:.1f}MB)")

            # Download and merge audio if separate
            if audio_url:
                logger.info("Downloading audio stream through proxy...")
                with httpx.stream("GET", audio_url, headers=headers, timeout=300.0, follow_redirects=True, proxy=proxy_url) as stream:
                    stream.raise_for_status()
                    with open(temp_audio, "wb") as f:
                        for chunk in stream.iter_bytes(chunk_size=65536):
                            f.write(chunk)

                # Merge with FFmpeg
                logger.info("Merging video and audio...")
                merge_cmd = [
                    "ffmpeg", "-i", str(temp_video), "-i", str(temp_audio),
                    "-c:v", "copy", "-c:a", "aac", "-y", str(video_filename)
                ]
                result = subprocess.run(merge_cmd, capture_output=True)
                if result.returncode != 0:
                    # Try with re-encoding if copy fails
                    merge_cmd = [
                        "ffmpeg", "-i", str(temp_video), "-i", str(temp_audio),
                        "-c:v", "libx264", "-c:a", "aac", "-y", str(video_filename)
                    ]
                    subprocess.run(merge_cmd, check=True, capture_output=True)

                # Cleanup temp files
                temp_video.unlink(missing_ok=True)
                temp_audio.unlink(missing_ok=True)

            if video_filename.exists() and video_filename.stat().st_size > 0:
                size_mb = video_filename.stat().st_size / 1024 / 1024
                logger.info(f"Download success: {video_filename} ({size_mb:.1f} MB)")
                logger.info(f"Proxy bandwidth used: ~{size_mb:.1f} MB (full video download)")
                return video_filename

        except Exception as e:
            logger.error(f"Proxy download failed: {e}")
            # Cleanup temp files on error
            for f in output_path.glob("temp_*"):
                f.unlink(missing_ok=True)

        return None

    def _download_sync(self, url: str, output_dir: Optional[Path] = None) -> Path:
        """Synchronous download using residential proxy."""
        logger.info("=" * 50)
        logger.info("STARTING YOUTUBE DOWNLOAD")
        logger.info(f"URL: {url}")
        logger.info("=" * 50)

        try:
            import yt_dlp
            logger.info("yt-dlp loaded successfully")
        except ImportError:
            logger.error("yt-dlp not installed!")
            raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

        output_path = Path(output_dir) if output_dir else self.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        # Check proxy is enabled
        logger.info(f"Checking proxy... PROXY_ENABLED={settings.PROXY_ENABLED}")
        if not settings.PROXY_ENABLED:
            logger.error("PROXY_ENABLED is False or not set!")
            raise RuntimeError("Proxy is not enabled. Set PROXY_ENABLED=true in .env")

        logger.info(f"Proxy config: {settings.PROXY_HOST}:{settings.PROXY_PORT}")
        logger.info("Starting download via Residential Proxy (smart mode)...")

        proxy_result = self._download_with_proxy_smart(url, output_path)

        if proxy_result:
            logger.info(f"Download completed successfully: {proxy_result}")
            return proxy_result

        logger.error("Proxy download returned None - failed!")
        raise RuntimeError("Proxy download failed. Check proxy settings and try again.")

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
