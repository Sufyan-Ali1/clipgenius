"""
Selection Service - Single Responsibility: Clip validation and selection

Validates and selects final clips from LLM suggestions.
"""

import json
from pathlib import Path
from typing import Callable, List, Optional
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("selection_service")


class SelectionService:
    """
    Single Responsibility: Validate and select final clips from suggestions.
    """

    def __init__(
        self,
        num_clips: Optional[int] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
    ):
        self.num_clips = num_clips if num_clips is not None else settings.NUM_CLIPS
        self.min_duration = min_duration if min_duration is not None else settings.MIN_CLIP_DURATION
        self.max_duration = max_duration if max_duration is not None else settings.MAX_CLIP_DURATION
        self.target_duration = 75  # Target duration in seconds
        self.min_score = settings.MIN_VIRALITY_SCORE

    def _find_sentence_boundary(
        self,
        transcription: dict,
        target_time: float,
        direction: str = "nearest"
    ) -> float:
        """Find the nearest sentence boundary to a target time."""
        segments = transcription["segments"]
        sentence_ends = {".", "!", "?", ":", ";"}

        best_time = target_time
        best_diff = float("inf")

        for segment in segments:
            diff = abs(segment["end"] - target_time)

            if direction == "before" and segment["end"] <= target_time and diff < best_diff:
                best_time = segment["end"]
                best_diff = diff
            elif direction == "after" and segment["end"] >= target_time and diff < best_diff:
                best_time = segment["end"]
                best_diff = diff
            elif direction == "nearest" and diff < best_diff:
                best_time = segment["end"]
                best_diff = diff

            if "words" in segment:
                for word in segment["words"]:
                    word_text = word["word"].strip()
                    if word_text and word_text[-1] in sentence_ends:
                        diff = abs(word["end"] - target_time)

                        if direction == "before" and word["end"] <= target_time and diff < best_diff:
                            best_time = word["end"]
                            best_diff = diff
                        elif direction == "after" and word["end"] >= target_time and diff < best_diff:
                            best_time = word["end"]
                            best_diff = diff
                        elif direction == "nearest" and diff < best_diff:
                            best_time = word["end"]
                            best_diff = diff

        return best_time

    def _adjust_clip_boundaries(self, clip: dict, transcription: dict) -> dict:
        """Adjust clip boundaries to avoid mid-sentence cuts."""
        start = clip["start_seconds"]
        end = clip["end_seconds"]

        segments = transcription["segments"]
        for segment in segments:
            if segment["start"] >= start - 2 and segment["start"] <= start + 2:
                start = segment["start"]
                break

        adjusted_end = self._find_sentence_boundary(transcription, end, "nearest")
        duration = adjusted_end - start

        if duration < self.min_duration:
            adjusted_end = start + self.min_duration
            adjusted_end = self._find_sentence_boundary(transcription, adjusted_end, "after")
        elif duration > self.max_duration:
            adjusted_end = start + self.max_duration
            adjusted_end = self._find_sentence_boundary(transcription, adjusted_end, "before")

        clip["start_seconds"] = round(start, 2)
        clip["end_seconds"] = round(adjusted_end, 2)
        clip["duration"] = round(adjusted_end - start, 2)

        return clip

    def _check_overlap(self, clip1: dict, clip2: dict, min_gap: float = 5.0) -> bool:
        """Check if two clips overlap or are too close."""
        return not (
            clip1["end_seconds"] + min_gap < clip2["start_seconds"] or
            clip2["end_seconds"] + min_gap < clip1["start_seconds"]
        )

    def _remove_overlapping(self, clips: list) -> list:
        """Remove overlapping clips, keeping higher scored ones."""
        if not clips:
            return []

        sorted_clips = sorted(clips, key=lambda x: x.get("score", 0), reverse=True)
        selected = []

        for clip in sorted_clips:
            has_overlap = any(
                self._check_overlap(clip, selected_clip)
                for selected_clip in selected
            )
            if not has_overlap:
                selected.append(clip)

        return selected

    def _merge_adjacent_clips(self, clips: list, max_gap: float = 10.0) -> list:
        """Merge adjacent clips if they're close together."""
        if len(clips) < 2:
            return clips

        sorted_clips = sorted(clips, key=lambda x: x["start_seconds"])
        merged = []
        current = sorted_clips[0].copy()

        for next_clip in sorted_clips[1:]:
            gap = next_clip["start_seconds"] - current["end_seconds"]

            if gap <= max_gap:
                merged_duration = next_clip["end_seconds"] - current["start_seconds"]

                if merged_duration <= self.max_duration:
                    current["end_seconds"] = next_clip["end_seconds"]
                    current["duration"] = merged_duration
                    current["score"] = max(
                        current.get("score", 0),
                        next_clip.get("score", 0)
                    )
                    current["reason"] = f"{current.get('reason', '')} + {next_clip.get('reason', '')}"
                    continue

            merged.append(current)
            current = next_clip.copy()

        merged.append(current)
        return merged

    def _extend_short_clips(self, clips: list, transcription: dict) -> list:
        """Extend short clips to meet minimum duration."""
        extended = []
        for clip in clips:
            duration = clip.get("duration", 0)
            if duration < self.min_duration:
                new_end = clip["start_seconds"] + self.min_duration
                video_duration = transcription.get("duration", float("inf"))
                new_end = min(new_end, video_duration)

                clip = clip.copy()
                clip["end_seconds"] = new_end
                clip["duration"] = new_end - clip["start_seconds"]

            if clip["duration"] >= self.min_duration * 0.8:
                extended.append(clip)
        return extended

    def _select_sync(
        self,
        suggestions: list,
        transcription: dict,
        output_path: Optional[Path] = None
    ) -> List[dict]:
        """Synchronous clip selection."""
        logger.info(f"Selecting best {self.num_clips} clips from {len(suggestions)} suggestions...")

        # Filter by minimum score
        filtered = [
            clip for clip in suggestions
            if clip.get("score", 0) >= self.min_score
        ]
        logger.info(f"  {len(filtered)} clips meet minimum score of {self.min_score}")

        # Merge adjacent clips
        merged = self._merge_adjacent_clips(filtered, max_gap=5.0)
        logger.info(f"  {len(merged)} clips after merging adjacent segments")

        # Filter by duration
        valid_duration = []
        for clip in merged:
            duration = clip.get("duration", 0)
            if duration >= self.min_duration * 0.5 and duration <= self.max_duration * 1.2:
                valid_duration.append(clip)
        logger.info(f"  {len(valid_duration)} clips have valid duration")

        # Extend short clips if needed
        if not valid_duration and merged:
            logger.info("  Attempting to extend short clips...")
            valid_duration = self._extend_short_clips(merged, transcription)
            logger.info(f"  {len(valid_duration)} clips after extension")

        # Adjust boundaries
        adjusted = []
        for clip in valid_duration:
            adjusted_clip = self._adjust_clip_boundaries(clip, transcription)
            if adjusted_clip["duration"] >= self.min_duration * 0.8:
                adjusted.append(adjusted_clip)
        logger.info(f"  {len(adjusted)} clips after boundary adjustment")

        # Remove overlaps
        non_overlapping = self._remove_overlapping(adjusted)
        logger.info(f"  {len(non_overlapping)} non-overlapping clips")

        # Take top N
        final_clips = sorted(
            non_overlapping,
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:self.num_clips]

        # Sort by start time
        final_clips.sort(key=lambda x: x["start_seconds"])

        # Add clip numbers
        for i, clip in enumerate(final_clips, 1):
            clip["clip_number"] = i
            clip["filename"] = f"clip_{i:03d}.mp4"

        logger.info(f"Selected {len(final_clips)} final clips.")

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"clips": final_clips}, f, indent=2)
            logger.info(f"Final clips saved: {output_path}")

        return final_clips

    async def select_clips(
        self,
        suggestions: List[dict],
        transcription: dict,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> List[dict]:
        """
        Select and validate clips from LLM suggestions.

        Args:
            suggestions: Raw clip suggestions from LLM
            transcription: Original transcription for validation
            output_path: Optional path to save selected clips JSON
            progress_callback: Optional callback(progress, message)

        Returns:
            List of validated, selected clips
        """
        if progress_callback:
            progress_callback(0.0, "Validating clips...")

        loop = asyncio.get_event_loop()

        final_clips = await loop.run_in_executor(
            None,
            self._select_sync,
            suggestions,
            transcription,
            output_path,
        )

        if progress_callback:
            progress_callback(1.0, f"Selected {len(final_clips)} clips")

        return final_clips
