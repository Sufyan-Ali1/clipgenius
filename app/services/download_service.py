"""
Download Service - Single Responsibility: YouTube video download

Downloads videos from YouTube using yt-dlp with Cobalt API fallback.
"""

import re
import httpx
from pathlib import Path
from typing import Callable, Optional
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("download_service")

# Cobalt API instances (free YouTube download proxies)
# Using Cobalt API v10 format
COBALT_INSTANCES = [
    "https://api.cobalt.tools",
    "https://cobalt.canine.tools",
    "https://api.spdload.cc",
]


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
        self._cookies_path = None

    def _get_cookies_file(self) -> Optional[Path]:
        """Create temp cookies file from environment variable."""
        if not settings.YOUTUBE_COOKIES:
            logger.warning("YOUTUBE_COOKIES environment variable not set")
            return None

        # Write cookies to temp file (only once)
        if self._cookies_path is None or not self._cookies_path.exists():
            settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
            self._cookies_path = settings.TEMP_DIR / "yt_cookies.txt"

            cookies_content = settings.YOUTUBE_COOKIES.strip()
            logger.info(f"Raw cookies length: {len(cookies_content)}, starts with: {cookies_content[:20]}")

            # Check if content is base64 encoded (for Render deployment)
            # Base64 strings don't contain spaces or # at the start
            if not cookies_content.startswith('#') and '\t' not in cookies_content[:100]:
                try:
                    import base64
                    cookies_content = base64.b64decode(cookies_content).decode('utf-8')
                    logger.info(f"Decoded base64 cookies ({len(cookies_content)} bytes)")
                except Exception as e:
                    logger.warning(f"Base64 decode failed: {e}")

            # Fix potential line break issues from environment variable
            cookies_content = cookies_content.replace('\\n', '\n')

            self._cookies_path.write_text(cookies_content)
            logger.info(f"YouTube cookies saved to {self._cookies_path}")

        return self._cookies_path

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

        opts = {
            'format': format_str,
            'outtmpl': str(output_path / '%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
            'merge_output_format': 'mp4',
            # Use Android client to bypass some restrictions
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        }

        # Add cookies if available
        cookies_path = self._get_cookies_file()
        if cookies_path:
            opts['cookiefile'] = str(cookies_path)

        return opts

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
            # Use Android client to bypass some restrictions
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        }

        # Add cookies if available
        cookies_path = self._get_cookies_file()
        if cookies_path:
            ydl_opts['cookiefile'] = str(cookies_path)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'channel': info.get('channel', 'Unknown'),
                'view_count': info.get('view_count', 0),
            }

    def _download_with_cobalt(self, url: str, output_path: Path) -> Optional[Path]:
        """Download video using Cobalt API (fallback for blocked IPs)."""
        import time

        for instance in COBALT_INSTANCES:
            try:
                logger.info(f"Trying Cobalt API: {instance}")

                # Cobalt API v10 format
                response = httpx.post(
                    instance,
                    json={
                        "url": url,
                        "videoQuality": "1080",
                        "filenameStyle": "basic",
                    },
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.warning(f"Cobalt returned {response.status_code}: {response.text[:200]}")
                    continue

                data = response.json()
                logger.info(f"Cobalt response status: {data.get('status')}")

                if data.get("status") == "error":
                    error_info = data.get("error", {})
                    error_code = error_info.get("code", "unknown") if isinstance(error_info, dict) else str(error_info)
                    logger.warning(f"Cobalt error: {error_code}")
                    continue

                # Get download URL - can be in "url" or need to handle "tunnel"/"redirect" status
                download_url = data.get("url")
                status = data.get("status")

                if status == "picker":
                    # Multiple formats available, pick first video
                    picker = data.get("picker", [])
                    if picker:
                        download_url = picker[0].get("url")

                if not download_url:
                    logger.warning(f"No download URL in Cobalt response: {data}")
                    continue

                # Download the video file
                logger.info("Downloading video via Cobalt...")
                video_filename = output_path / f"video_{int(time.time())}.mp4"

                with httpx.stream("GET", download_url, timeout=300.0, follow_redirects=True) as stream:
                    stream.raise_for_status()
                    with open(video_filename, "wb") as f:
                        for chunk in stream.iter_bytes(chunk_size=8192):
                            f.write(chunk)

                if video_filename.exists() and video_filename.stat().st_size > 0:
                    logger.info(f"Cobalt download success: {video_filename}")
                    return video_filename

            except Exception as e:
                logger.warning(f"Cobalt instance {instance} failed: {e}")
                continue

        return None

    def _download_sync(self, url: str, output_dir: Optional[Path] = None) -> Path:
        """Synchronous download with Cobalt fallback."""
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

        output_path = Path(output_dir) if output_dir else self.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        # Try yt-dlp first
        try:
            logger.info("Fetching video info...")
            info = self._get_video_info(url)
            logger.info(f"  Title: {info['title']}")
            logger.info(f"  Duration: {info['duration'] // 60}:{info['duration'] % 60:02d}")
            logger.info(f"  Channel: {info['channel']}")
        except Exception as e:
            logger.warning(f"yt-dlp info failed: {e}")
            # Try Cobalt directly if yt-dlp fails
            logger.info("Trying Cobalt API as fallback...")
            cobalt_result = self._download_with_cobalt(url, output_path)
            if cobalt_result:
                return cobalt_result
            raise RuntimeError(f"Both yt-dlp and Cobalt failed: {e}")

        logger.info(f"Downloading video (quality: {self.quality})...")

        # Try yt-dlp first
        try:
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

        except Exception as ytdlp_error:
            logger.warning(f"yt-dlp download failed: {ytdlp_error}")
            logger.info("Trying Cobalt API as fallback...")

            cobalt_result = self._download_with_cobalt(url, output_path)
            if cobalt_result:
                return cobalt_result

            raise RuntimeError(f"Both yt-dlp and Cobalt failed. yt-dlp error: {ytdlp_error}")

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
