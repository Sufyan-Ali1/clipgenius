"""
Analysis Service - Single Responsibility: LLM engagement analysis

Analyzes transcription for viral-worthy segments using LLM.
"""

import json
import re
from pathlib import Path
from typing import Callable, List, Optional
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("analysis_service")


class AnalysisService:
    """
    Single Responsibility: Analyze transcription for engaging segments using LLM.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        self.min_duration = settings.MIN_CLIP_DURATION
        self.max_duration = settings.MAX_CLIP_DURATION
        self.prompts_dir = settings.BASE_DIR / "app" / "prompts"
        self._llm = None

    def _get_llm(self):
        """Get LLM provider instance."""
        if self._llm is None:
            from app.services.llm_service import get_llm_provider
            self._llm = get_llm_provider(self.provider)
        return self._llm

    def _load_prompt_template(self) -> str:
        """Load the engagement analysis prompt template."""
        prompt_file = self.prompts_dir / "engagement_prompt.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        else:
            return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """Return default prompt if template file doesn't exist."""
        return """You are an expert social media content analyst specializing in viral short-form video content for TikTok and YouTube Shorts.

Analyze the following video transcript and identify the most engaging segments that would work well as 60-90 second clips.

TRANSCRIPT:
{transcript}

ANALYSIS CRITERIA:
1. HOOKS - Strong opening lines that grab attention immediately
2. EMOTIONAL MOMENTS - Excitement, surprise, humor, inspiration, controversy
3. HIGH-VALUE CONTENT - Tips, insights, revelations, "aha" moments
4. STORY ARCS - Complete mini-stories with beginning, middle, end
5. QUOTABLE MOMENTS - Memorable phrases people would share
6. CURIOSITY GAPS - Statements that make viewers want to know more

For each potential clip, consider:
- Does it work standalone without context?
- Does it have a strong hook in the first 3 seconds?
- Would it make someone stop scrolling?
- Is there a satisfying payoff or conclusion?

IMPORTANT RULES:
- Each clip MUST be between {min_duration} and {max_duration} seconds
- Avoid cutting mid-sentence or mid-thought
- Prefer complete segments with natural start/end points
- Rank by viral potential (1-10 scale)

OUTPUT FORMAT (JSON only, no other text):
{{
  "clips": [
    {{
      "start": "MM:SS",
      "end": "MM:SS",
      "score": 8,
      "hook": "First few words that grab attention",
      "reason": "Why this would go viral",
      "type": "hook|emotional|insight|story|quotable"
    }}
  ]
}}

Identify the TOP 10 most engaging segments. Return ONLY valid JSON."""

    def _format_transcript_for_analysis(self, transcription: dict) -> str:
        """Format transcript with timestamps for LLM analysis."""
        lines = []
        for segment in transcription["segments"]:
            start_min = int(segment["start"] // 60)
            start_sec = int(segment["start"] % 60)
            timestamp = f"[{start_min:02d}:{start_sec:02d}]"
            lines.append(f"{timestamp} {segment['text']}")
        return "\n".join(lines)

    def _chunk_transcript(self, transcription: dict, chunk_duration: int = 600) -> list:
        """Split long transcripts into chunks for processing."""
        segments = transcription["segments"]
        if not segments:
            return []

        total_duration = segments[-1]["end"]

        if total_duration <= chunk_duration * 1.5:
            return [{
                "offset": 0,
                "segments": segments,
                "text": self._format_transcript_for_analysis(transcription)
            }]

        chunks = []
        current_chunk = []
        chunk_start = 0

        for segment in segments:
            current_chunk.append(segment)

            if segment["end"] - chunk_start >= chunk_duration:
                chunks.append({
                    "offset": chunk_start,
                    "segments": current_chunk,
                    "text": self._format_transcript_for_analysis({"segments": current_chunk})
                })
                chunk_start = segment["end"]
                current_chunk = []

        if current_chunk:
            chunks.append({
                "offset": chunk_start,
                "segments": current_chunk,
                "text": self._format_transcript_for_analysis({"segments": current_chunk})
            })

        return chunks

    def _parse_llm_response(self, response: str) -> list:
        """Parse LLM response to extract clip suggestions."""
        try:
            data = json.loads(response)
            return data.get("clips", [])
        except json.JSONDecodeError:
            pass

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return data.get("clips", [])
            except json.JSONDecodeError:
                pass

        json_match = re.search(r"\{[^{}]*\"clips\"[^{}]*\[.*?\]\s*\}", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return data.get("clips", [])
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM response as JSON")
        return []

    def _parse_timestamp(self, timestamp: str) -> float:
        """Convert MM:SS or HH:MM:SS timestamp to seconds."""
        parts = timestamp.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError(f"Invalid timestamp format: {timestamp}")

    def _analyze_sync(
        self,
        transcription: dict,
        output_path: Optional[Path] = None
    ) -> List[dict]:
        """Synchronous analysis."""
        llm = self._get_llm()

        if not llm.is_available():
            raise RuntimeError(f"LLM provider '{llm.name}' is not available.")

        chunks = self._chunk_transcript(transcription)
        logger.info(f"Processing {len(chunks)} transcript chunk(s)...")

        all_clips = []
        prompt_template = self._load_prompt_template()

        for i, chunk in enumerate(chunks):
            logger.info(f"Analyzing chunk {i+1}/{len(chunks)}...")

            prompt = prompt_template.format(
                transcript=chunk["text"],
                min_duration=self.min_duration,
                max_duration=self.max_duration
            )

            response = llm.generate(prompt)
            clips = self._parse_llm_response(response)

            for clip in clips:
                try:
                    start_seconds = self._parse_timestamp(clip["start"]) + chunk["offset"]
                    end_seconds = self._parse_timestamp(clip["end"]) + chunk["offset"]

                    clip["start_seconds"] = start_seconds
                    clip["end_seconds"] = end_seconds
                    clip["duration"] = end_seconds - start_seconds

                    all_clips.append(clip)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping invalid clip: {e}")
                    continue

        all_clips.sort(key=lambda x: x.get("score", 0), reverse=True)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"clips": all_clips}, f, indent=2)
            logger.info(f"Analysis saved: {output_path}")

        return all_clips

    async def analyze(
        self,
        transcription: dict,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> List[dict]:
        """
        Analyze transcription for engaging clip suggestions.

        Args:
            transcription: Transcription dict with segments
            output_path: Optional path to save analysis JSON
            progress_callback: Optional callback(progress, message)

        Returns:
            List of clip suggestions with timestamps and scores
        """
        logger.info(f"Starting analysis with {self.provider}/{self.model}")

        if progress_callback:
            progress_callback(0.0, f"Analyzing with {self.provider}...")

        loop = asyncio.get_event_loop()

        suggestions = await loop.run_in_executor(
            None,
            self._analyze_sync,
            transcription,
            output_path,
        )

        if progress_callback:
            progress_callback(1.0, "Analysis complete")

        logger.info(f"Analysis complete: {len(suggestions)} suggestions")
        return suggestions

    async def load_existing(self, analysis_path: Path) -> Optional[List[dict]]:
        """Load existing analysis from file."""
        if not analysis_path.exists():
            return None

        def _load():
            with open(analysis_path, "r", encoding="utf-8") as f:
                return json.load(f).get("clips", [])

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _load)
