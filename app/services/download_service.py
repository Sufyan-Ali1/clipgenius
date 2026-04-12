"""
Download Service - Single Responsibility: YouTube video download

Downloads videos from YouTube using multiple fallback methods:
1. Piped API (primary - most reliable for datacenter IPs)
2. Invidious API (secondary - privacy-focused YouTube frontend)
3. yt-dlp (last resort - usually fails on datacenter IPs)
"""

import re
import httpx
from pathlib import Path
from typing import Callable, Optional
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("download_service")

# Piped instances (modern YouTube frontend - more reliable)
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.in.projectsegfau.lt",
    "https://api.piped.yt",
    "https://pipedapi.darkness.services",
]

# Invidious instances (fallback)
INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.jing.rocks",
    "https://yewtu.be",
    "https://vid.puffyan.us",
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
        # Format strings with proper fallbacks for videos without separate streams
        quality_map = {
            "best": "bestvideo*+bestaudio/best",
            "4k": "bestvideo*[height<=2160]+bestaudio/bestvideo*+bestaudio/best",
            "2k": "bestvideo*[height<=1440]+bestaudio/bestvideo*+bestaudio/best",
            "1080p": "bestvideo*[height<=1080]+bestaudio/bestvideo*+bestaudio/best",
            "720p": "bestvideo*[height<=720]+bestaudio/bestvideo*+bestaudio/best",
            "480p": "bestvideo*[height<=480]+bestaudio/bestvideo*+bestaudio/best",
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
            # Use multiple clients for better compatibility
            'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web']}},
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
            # Use multiple clients for better compatibility
            'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web']}},
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

    def _download_with_piped(self, url: str, output_path: Path) -> Optional[Path]:
        """Download video using Piped API (modern YouTube frontend)."""
        import time
        import subprocess

        video_id = self._extract_video_id(url)
        if not video_id:
            logger.warning(f"Could not extract video ID from URL: {url}")
            return None

        for instance in PIPED_INSTANCES:
            try:
                logger.info(f"Trying Piped: {instance}")

                # Get video streams from Piped API
                api_url = f"{instance}/streams/{video_id}"
                response = httpx.get(
                    api_url,
                    headers={"Accept": "application/json"},
                    timeout=30.0,
                    follow_redirects=True
                )

                if response.status_code != 200:
                    logger.warning(f"Piped returned {response.status_code}")
                    continue

                data = response.json()

                if data.get("error"):
                    logger.warning(f"Piped error: {data.get('message', 'Unknown error')}")
                    continue

                title = data.get("title", "video")
                logger.info(f"Found video: {title}")

                # Get video and audio streams
                video_streams = data.get("videoStreams", [])
                audio_streams = data.get("audioStreams", [])

                # Filter for MP4/webm video streams and sort by quality
                video_streams = [s for s in video_streams if s.get("videoOnly", False)]
                video_streams.sort(key=lambda x: int(x.get("height", 0) or 0), reverse=True)

                # Sort audio by bitrate
                audio_streams.sort(key=lambda x: int(x.get("bitrate", 0) or 0), reverse=True)

                download_url = None
                audio_url = None

                # Get best video (prefer 1080p or lower)
                for vs in video_streams:
                    height = int(vs.get("height", 0) or 0)
                    if height <= 1080 and vs.get("url"):
                        download_url = vs.get("url")
                        break

                if not download_url and video_streams:
                    download_url = video_streams[0].get("url")

                # Get best audio
                if audio_streams:
                    audio_url = audio_streams[0].get("url")

                # Fallback: try combined streams (non videoOnly)
                if not download_url:
                    combined_streams = [s for s in data.get("videoStreams", []) if not s.get("videoOnly", True)]
                    combined_streams.sort(key=lambda x: int(x.get("height", 0) or 0), reverse=True)
                    if combined_streams:
                        download_url = combined_streams[0].get("url")
                        audio_url = None

                if not download_url:
                    logger.warning("No download URL found in Piped response")
                    continue

                # Download video
                logger.info(f"Downloading video via Piped...")
                video_filename = output_path / f"video_{int(time.time())}.mp4"
                temp_video = output_path / f"temp_video_{int(time.time())}.webm"
                temp_audio = output_path / f"temp_audio_{int(time.time())}.webm"

                # Download video stream
                logger.info("Downloading video stream...")
                with httpx.stream("GET", download_url, timeout=600.0, follow_redirects=True) as stream:
                    stream.raise_for_status()
                    with open(temp_video, "wb") as f:
                        for chunk in stream.iter_bytes(chunk_size=65536):
                            f.write(chunk)

                # If we have separate audio, download and merge
                if audio_url:
                    logger.info("Downloading audio stream...")
                    with httpx.stream("GET", audio_url, timeout=300.0, follow_redirects=True) as stream:
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
                else:
                    # No separate audio, just convert/copy
                    merge_cmd = [
                        "ffmpeg", "-i", str(temp_video),
                        "-c:v", "copy", "-c:a", "copy", "-y", str(video_filename)
                    ]
                    result = subprocess.run(merge_cmd, capture_output=True)
                    if result.returncode != 0:
                        # Just rename if ffmpeg fails
                        temp_video.rename(video_filename)
                    else:
                        temp_video.unlink(missing_ok=True)

                if video_filename.exists() and video_filename.stat().st_size > 0:
                    logger.info(f"Piped download success: {video_filename} ({video_filename.stat().st_size / 1024 / 1024:.1f} MB)")
                    return video_filename

            except Exception as e:
                logger.warning(f"Piped instance {instance} failed: {e}")
                continue

        return None

    def _download_with_invidious(self, url: str, output_path: Path) -> Optional[Path]:
        """Download video using Invidious API (free YouTube frontend)."""
        import time

        video_id = self._extract_video_id(url)
        if not video_id:
            logger.warning(f"Could not extract video ID from URL: {url}")
            return None

        for instance in INVIDIOUS_INSTANCES:
            try:
                logger.info(f"Trying Invidious: {instance}")

                # Get video info from Invidious API
                api_url = f"{instance}/api/v1/videos/{video_id}"
                response = httpx.get(
                    api_url,
                    headers={"Accept": "application/json"},
                    timeout=30.0,
                    follow_redirects=True
                )

                if response.status_code != 200:
                    logger.warning(f"Invidious returned {response.status_code}")
                    continue

                data = response.json()
                title = data.get("title", "video")

                # Get best quality format
                # Try adaptiveFormats first (separate video+audio, higher quality)
                adaptive_formats = data.get("adaptiveFormats", [])
                format_streams = data.get("formatStreams", [])

                download_url = None
                audio_url = None

                # Find best video from adaptive formats
                video_formats = [f for f in adaptive_formats if f.get("type", "").startswith("video/")]
                audio_formats = [f for f in adaptive_formats if f.get("type", "").startswith("audio/")]

                # Sort by quality (resolution)
                video_formats.sort(key=lambda x: int(x.get("resolution", "0p").replace("p", "") or 0), reverse=True)
                audio_formats.sort(key=lambda x: int(x.get("bitrate", "0") or 0), reverse=True)

                if video_formats and audio_formats:
                    # Get best video (prefer 1080p or lower for reasonable file size)
                    for vf in video_formats:
                        res = int(vf.get("resolution", "0p").replace("p", "") or 0)
                        if res <= 1080:
                            download_url = vf.get("url")
                            break
                    if not download_url and video_formats:
                        download_url = video_formats[0].get("url")
                    audio_url = audio_formats[0].get("url")

                # Fallback to formatStreams (combined video+audio)
                if not download_url and format_streams:
                    # Sort by quality
                    format_streams.sort(key=lambda x: int(x.get("resolution", "0p").replace("p", "") or 0), reverse=True)
                    download_url = format_streams[0].get("url")
                    audio_url = None  # Not needed for combined formats

                if not download_url:
                    logger.warning(f"No download URL found in Invidious response")
                    continue

                # Download video
                logger.info(f"Downloading video via Invidious ({title})...")
                video_filename = output_path / f"video_{int(time.time())}.mp4"
                temp_video = output_path / f"temp_video_{int(time.time())}.mp4"
                temp_audio = output_path / f"temp_audio_{int(time.time())}.m4a"

                # Download video stream
                with httpx.stream("GET", download_url, timeout=300.0, follow_redirects=True) as stream:
                    stream.raise_for_status()
                    with open(temp_video if audio_url else video_filename, "wb") as f:
                        for chunk in stream.iter_bytes(chunk_size=8192):
                            f.write(chunk)

                # If we have separate audio, download and merge
                if audio_url:
                    logger.info("Downloading audio stream...")
                    with httpx.stream("GET", audio_url, timeout=300.0, follow_redirects=True) as stream:
                        stream.raise_for_status()
                        with open(temp_audio, "wb") as f:
                            for chunk in stream.iter_bytes(chunk_size=8192):
                                f.write(chunk)

                    # Merge with FFmpeg
                    logger.info("Merging video and audio...")
                    import subprocess
                    merge_cmd = [
                        "ffmpeg", "-i", str(temp_video), "-i", str(temp_audio),
                        "-c:v", "copy", "-c:a", "aac", "-y", str(video_filename)
                    ]
                    subprocess.run(merge_cmd, check=True, capture_output=True)

                    # Cleanup temp files
                    temp_video.unlink(missing_ok=True)
                    temp_audio.unlink(missing_ok=True)

                if video_filename.exists() and video_filename.stat().st_size > 0:
                    logger.info(f"Invidious download success: {video_filename}")
                    return video_filename

            except Exception as e:
                logger.warning(f"Invidious instance {instance} failed: {e}")
                continue

        return None

    def _download_sync(self, url: str, output_dir: Optional[Path] = None) -> Path:
        """Synchronous download. Tries: Piped -> Invidious -> yt-dlp."""
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

        output_path = Path(output_dir) if output_dir else self.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        # Strategy: Try Piped first (most reliable), then Invidious, then yt-dlp

        # Try Piped API first (most reliable for datacenter IPs)
        logger.info("Trying Piped API (primary method)...")
        piped_result = self._download_with_piped(url, output_path)
        if piped_result:
            return piped_result

        # Try Invidious API as second option
        logger.info("Piped failed, trying Invidious API...")
        invidious_result = self._download_with_invidious(url, output_path)
        if invidious_result:
            return invidious_result

        # Try yt-dlp as last resort (usually fails on datacenter IPs)
        logger.info("Invidious failed, trying yt-dlp as last resort...")
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

            return video_path

        except Exception as ytdlp_error:
            raise RuntimeError(f"All download methods failed. Piped, Invidious, and yt-dlp all returned errors. Last error: {ytdlp_error}")

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
