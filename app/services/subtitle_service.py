"""
Subtitle Service - Single Responsibility: SRT generation

Creates SRT subtitle files from transcription data.
"""

from pathlib import Path
from typing import Callable, List, Optional
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("subtitle_service")


class SubtitleService:
    """
    Single Responsibility: Generate SRT subtitle files.
    """

    def __init__(self):
        self.temp_dir = settings.TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _get_segments_for_range(
        self,
        transcription: dict,
        start_time: float,
        end_time: float
    ) -> list:
        """Get transcription segments within a time range."""
        segments = []
        for segment in transcription["segments"]:
            if segment["start"] < end_time and segment["end"] > start_time:
                segments.append(segment)
        return segments

    def _generate_srt_sync(
        self,
        transcription: dict,
        output_path: Path,
        start_offset: float = 0.0,
        time_range: Optional[tuple] = None,
        max_chars_per_line: int = 42,
        max_lines: int = 2
    ) -> Path:
        """Synchronous SRT generation."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if time_range:
            segments = self._get_segments_for_range(
                transcription,
                time_range[0],
                time_range[1]
            )
        else:
            segments = transcription["segments"]

        srt_lines = []
        subtitle_index = 1

        for segment in segments:
            start = max(0, segment["start"] - start_offset)
            end = max(0, segment["end"] - start_offset)

            if time_range:
                if end < 0 or start > (time_range[1] - start_offset):
                    continue

            text = segment["text"].strip()
            if not text:
                continue

            # Split long text into multiple lines
            words = text.split()
            lines = []
            current_line = []
            current_length = 0

            for word in words:
                word_length = len(word) + (1 if current_line else 0)

                if current_length + word_length > max_chars_per_line:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                        current_length = len(word)

                        if len(lines) >= max_lines:
                            srt_lines.append(str(subtitle_index))
                            srt_lines.append(
                                f"{self._format_timestamp(start)} --> "
                                f"{self._format_timestamp(end)}"
                            )
                            srt_lines.append("\n".join(lines))
                            srt_lines.append("")
                            subtitle_index += 1
                            lines = []
                else:
                    current_line.append(word)
                    current_length += word_length

            if current_line:
                lines.append(" ".join(current_line))

            if lines:
                srt_lines.append(str(subtitle_index))
                srt_lines.append(
                    f"{self._format_timestamp(start)} --> "
                    f"{self._format_timestamp(end)}"
                )
                srt_lines.append("\n".join(lines))
                srt_lines.append("")
                subtitle_index += 1

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        return output_path

    def _generate_clip_subtitles_sync(
        self,
        transcription: dict,
        clips: List[dict],
        output_dir: Path
    ) -> List[Path]:
        """Synchronous subtitle generation for multiple clips."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        srt_paths = []

        for clip in clips:
            clip_num = clip.get("clip_number", len(srt_paths) + 1)
            start = clip["start_seconds"]
            end = clip["end_seconds"]

            srt_filename = f"clip_{clip_num:03d}.srt"
            srt_path = output_dir / srt_filename

            self._generate_srt_sync(
                transcription,
                srt_path,
                start_offset=start,
                time_range=(start, end)
            )

            srt_paths.append(srt_path)
            clip["srt_path"] = str(srt_path)

        logger.info(f"Generated {len(srt_paths)} subtitle files.")
        return srt_paths

    async def generate_subtitles(
        self,
        transcription: dict,
        clips: List[dict],
        output_dir: Path,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> List[Path]:
        """
        Generate SRT subtitle files for clips.

        Args:
            transcription: Full transcription with word timestamps
            clips: List of clip definitions
            output_dir: Directory to save SRT files
            progress_callback: Optional callback(progress, message)

        Returns:
            List of generated SRT file paths
        """
        if progress_callback:
            progress_callback(0.0, "Generating subtitle files...")

        loop = asyncio.get_event_loop()

        srt_paths = await loop.run_in_executor(
            None,
            self._generate_clip_subtitles_sync,
            transcription,
            clips,
            output_dir,
        )

        if progress_callback:
            progress_callback(1.0, f"Generated {len(srt_paths)} subtitle files")

        return srt_paths

    async def generate_single_srt(
        self,
        transcription: dict,
        output_path: Path,
        start_offset: float = 0.0,
        time_range: Optional[tuple] = None,
    ) -> Path:
        """Generate a single SRT file."""
        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            self._generate_srt_sync,
            transcription,
            output_path,
            start_offset,
            time_range,
        )
