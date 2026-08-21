"""
Abstract base class for all transcript acquisition tiers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union
from transcript_engine.errors import TranscriptError


class TranscriptTier(ABC):
    """Common interface for every tier in the resilience ladder."""

    name: str = "base"

    @abstractmethod
    def fetch(self, video_id: str, languages: List[str] = None) -> Optional[Dict]:
        """
        Attempt to retrieve the transcript.

        Returns:
            dict with keys: video_id, lang, source_tier, segments
            or None if unavailable at this tier.
        Raises:
            BlockedError, UnavailableError, TransientError, ToolRotError
        """
        pass

    def normalize_segments(self, raw: List[Dict]) -> List[Dict]:
        """Convert any tier's output into the canonical segment schema."""
        normalized = []
        for item in raw:
            normalized.append({
                "text": item.get("text", "").strip(),
                "start": float(item.get("start", 0.0)),
                "duration": float(item.get("duration", 0.0))
            })
        return normalized