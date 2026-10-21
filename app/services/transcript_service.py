from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# Import the new resilient engine (preferred path)
try:
    from transcript_engine import TranscriptEngine
    _ENGINE_AVAILABLE = True
except Exception:
    _ENGINE_AVAILABLE = False
    TranscriptEngine = None


class TranscriptService:
    """Legacy wrapper. Delegates to the new TranscriptEngine when available."""

    DEFAULT_LANGUAGES = ['en', 'en-US', 'en-GB']
    _engine: Optional['TranscriptEngine'] = None

    @classmethod
    def _get_engine(cls):
        if cls._engine is None and _ENGINE_AVAILABLE:
            cls._engine = TranscriptEngine()
        return cls._engine

    @classmethod
    def get_transcript(cls, video_id: str, languages: List[str] = None,
                       cookies_file: str = None, use_browser: bool = False) -> Optional[str]:
        """
        Main entry point. Delegates to the resilient TranscriptEngine when available.
        """
        if languages is None:
            languages = cls.DEFAULT_LANGUAGES

        engine = cls._get_engine()
        if engine:
            result = engine.fetch(video_id, languages, force_refresh=use_browser)
            if result:
                # Flatten segments back into plain text for backward compatibility
                text = " ".join(seg["text"] for seg in result.get("segments", []))
                return text.strip() or None
            return None

        # transcript_engine is not available — no transcript source to use.
        logger.warning("transcript_engine not available — no transcript source")
        return None
