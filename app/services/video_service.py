"""
Video Service - Single Responsibility: Video cutting

Cuts video clips using FFmpeg with optional vertical conversion.
"""

import subprocess
import json
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("video_service")


class VideoService:
    """
    Single Responsibility: Cut video into clips using FFmpeg.
    """

    def __init__(self, vertical_mode: Optional[bool] = None):
        self.output_dir = settings.OUTPUTS_DIR
        self.output_format = "mp4"
        self.vertical_mode = vertical_mode if vertical_mode is not None else settings.VERTICAL_MODE
        self.vertical_method = settings.VERTICAL_METHOD
        self.vertical_width = settings.VERTICAL_WIDTH
        self.vertical_height = settings.VERTICAL_HEIGHT
        self.video_crf = 17  # High quality (near lossless)
        self.use_hw_accel = self._check_hw_acceleration()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_ffmpeg()

    def _check_hw_acceleration(self) -> Optional[str]:
        """Check if hardware acceleration is available and working."""
        # Test NVIDIA NVENC by actually trying to use it
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1",
                    "-c:v", "h264_nvenc", "-f", "null", "-"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("NVIDIA NVENC hardware acceleration available and working")
                return "nvenc"
        except Exception as e:
            logger.debug(f"NVENC test failed: {e}")

        # Test Intel QSV
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1",
                    "-c:v", "h264_qsv", "-f", "null", "-"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("Intel QSV hardware acceleration available and working")
                return "qsv"
        except Exception as e:
            logger.debug(f"QSV test failed: {e}")

        logger.info("No hardware acceleration available, using CPU encoding")
        return None

    def _check_ffmpeg(self):
        """Verify FFmpeg is installed."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    def _get_video_info(self, video_path: Path) -> dict:
        """Get video dimensions using FFprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "json",
            str(video_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            info = json.loads(result.stdout)
            stream = info.get("streams", [{}])[0]
            return {
                "width": int(stream.get("width", 1920)),
                "height": int(stream.get("height", 1080)),
                "duration": float(stream.get("duration", 0))
            }
        except Exception:
            return {"width": 1920, "height": 1080, "duration": 0}

    def _build_vertical_filter(self, input_width: int, input_height: int) -> str:
        """Build FFmpeg filter for vertical video conversion."""
        out_w = self.vertical_width
        out_h = self.vertical_height

        if self.vertical_method in ["blur", "blur_padding"]:
            # Dark blur padding: Full video visible with darkened blurred background
            # Step 1: Create dark blurred background
            #   - Scale up to cover output dimensions
            #   - Crop to exact output size
            #   - Darken significantly (brightness=-0.4, saturation=0.3)
            #   - Apply heavy blur
            # Step 2: Scale foreground to fit inside output (preserving aspect ratio)
            # Step 3: Center overlay foreground on dark blurred background
            filter_complex = (
                f"[0:v]scale=w={out_w}:h={out_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{out_h}:(iw-{out_w})/2:(ih-{out_h})/2,"
                f"eq=brightness=-0.4:saturation=0.3,"
                f"boxblur=40:15[bg];"
                f"[0:v]scale=w={out_w}:h={out_h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
            )
        elif self.vertical_method == "black_bars":
            # Letterbox: Video centered with black bars
            filter_complex = (
                f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
                f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:black"
            )
        else:
            # Crop: Center crop (loses content on sides)
            filter_complex = (
                f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{out_h}"
            )

        return filter_complex

    def _cut_single_clip(
        self,
        video_path: Path,
        start_time: float,
        end_time: float,
        output_path: Path,
        vertical: Optional[bool] = None
    ) -> Path:
        """Cut a single clip from video."""
        use_vertical = vertical if vertical is not None else self.vertical_mode
        duration = end_time - start_time

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duration),
        ]

        if use_vertical:
            video_info = self._get_video_info(video_path)
            filter_str = self._build_vertical_filter(
                video_info["width"],
                video_info["height"]
            )
            cmd.extend(["-filter_complex", filter_str])

            # Use hardware acceleration if available
            if self.use_hw_accel == "nvenc":
                cmd.extend([
                    "-c:v", "h264_nvenc",
                    "-preset", "p4",  # Fast NVENC preset
                    "-cq", str(self.video_crf),
                ])
            elif self.use_hw_accel == "qsv":
                cmd.extend([
                    "-c:v", "h264_qsv",
                    "-preset", "fast",
                    "-global_quality", str(self.video_crf),
                ])
            else:
                # CPU encoding
                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", str(self.video_crf),
                ])

            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path)
            ])
        else:
            # No vertical conversion - stream copy for original quality
            cmd.extend([
                "-c:v", "copy",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(output_path)
            ])

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg error cutting clip: {error_msg}")

    def _cut_single_clip_task(
        self,
        video_path: Path,
        clip: dict,
        output_prefix: str = "clip"
    ) -> Tuple[int, Optional[Path], Optional[str]]:
        """Task for cutting a single clip (used in parallel processing)."""
        clip_num = clip.get("clip_number", 1)
        filename = clip.get("filename", f"{output_prefix}_{clip_num:03d}.{self.output_format}")
        output_path = self.output_dir / filename

        try:
            self._cut_single_clip(
                video_path,
                clip["start_seconds"],
                clip["end_seconds"],
                output_path
            )
            clip["output_path"] = str(output_path)
            return (clip_num, output_path, None)
        except Exception as e:
            return (clip_num, None, str(e))

    def _cut_clips_sync(
        self,
        video_path: Path,
        clips: List[dict],
        output_prefix: str = "clip"
    ) -> List[Path]:
        """Synchronous parallel clip cutting."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        logger.info(f"Cutting {len(clips)} clips from {video_path.name} (parallel)...")

        # Use ThreadPoolExecutor for parallel cutting
        # Limit workers to avoid overwhelming the system
        max_workers = min(len(clips), 3)
        output_paths = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all clip cutting tasks
            futures = {
                executor.submit(
                    self._cut_single_clip_task,
                    video_path,
                    clip,
                    output_prefix
                ): clip for clip in clips
            }

            # Collect results as they complete
            for future in as_completed(futures):
                clip_num, output_path, error = future.result()
                if output_path:
                    output_paths.append(output_path)
                    logger.info(f"  Cut clip {clip_num}: {output_path.name}")
                else:
                    logger.error(f"  Error cutting clip {clip_num}: {error}")

        # Sort by clip number to maintain order
        output_paths.sort(key=lambda p: p.name)

        logger.info(f"Successfully cut {len(output_paths)} clips")
        return output_paths

    async def cut_clips(
        self,
        video_path: Path,
        clips: List[dict],
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> List[Path]:
        """
        Cut video into multiple clips.

        Args:
            video_path: Source video file path
            clips: List of clip definitions with start/end times
            progress_callback: Optional callback(progress, message)

        Returns:
            List of output clip file paths
        """
        if progress_callback:
            progress_callback(0.0, "Preparing to cut clips...")

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        total_clips = len(clips)
        output_paths = []
        loop = asyncio.get_event_loop()

        for i, clip in enumerate(clips):
            if progress_callback:
                progress_callback(i / total_clips, f"Cutting clip {i+1}/{total_clips}...")

            clip_num = clip.get("clip_number", i + 1)
            filename = clip.get("filename", f"clip_{clip_num:03d}.{self.output_format}")
            output_path = self.output_dir / filename

            try:
                await loop.run_in_executor(
                    None,
                    self._cut_single_clip,
                    video_path,
                    clip["start_seconds"],
                    clip["end_seconds"],
                    output_path,
                    None,  # vertical (use default)
                )
                clip["output_path"] = str(output_path)
                output_paths.append(output_path)
                logger.info(f"  Cut clip {clip_num}: {output_path.name}")
            except Exception as e:
                logger.error(f"  Error cutting clip {clip_num}: {e}")

        if progress_callback:
            progress_callback(1.0, f"Cut {len(output_paths)} clips")

        return output_paths

    def _add_subtitles_sync(self, clip_path: Path, srt_path: Path) -> Path:
        """Synchronous subtitle burning."""
        output_path = clip_path.with_stem(f"{clip_path.stem}_subtitled")

        # Escape path for FFmpeg filter
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

        subtitle_filter = (
            f"subtitles='{srt_escaped}':"
            f"force_style='FontName={settings.SUBTITLE_FONT},"
            f"FontSize={settings.SUBTITLE_FONT_SIZE},"
            f"PrimaryColour=&HFFFFFF,"
            f"OutlineColour=&H000000,"
            f"BorderStyle=1,"
            f"Outline=2,"
            f"Alignment=2,"
            f"MarginV=10'"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(clip_path),
            "-vf", subtitle_filter,
        ]

        # Use hardware acceleration if available
        if self.use_hw_accel == "nvenc":
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-cq", str(self.video_crf),
            ])
        elif self.use_hw_accel == "qsv":
            cmd.extend([
                "-c:v", "h264_qsv",
                "-preset", "fast",
                "-global_quality", str(self.video_crf),
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", str(self.video_crf),
            ])

        cmd.extend(["-c:a", "copy", str(output_path)])

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg subtitle error: {error_msg}")

    async def add_subtitles(
        self,
        video_path: Path,
        srt_path: Path,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """
        Add subtitles to a video clip.

        Args:
            video_path: Video file to add subtitles to
            srt_path: SRT subtitle file
            progress_callback: Optional callback(progress, message)

        Returns:
            Path to subtitled video
        """
        if progress_callback:
            progress_callback(0.0, "Burning subtitles...")

        loop = asyncio.get_event_loop()

        output_path = await loop.run_in_executor(
            None,
            self._add_subtitles_sync,
            video_path,
            srt_path,
        )

        if progress_callback:
            progress_callback(1.0, "Subtitles added")

        return output_path
