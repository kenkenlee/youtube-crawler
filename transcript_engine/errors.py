"""
Error taxonomy for YouTube transcript acquisition.

All control flow in the engine is driven by these exception classes.
"""

from enum import Enum
from typing import Optional


class ErrorClass(str, Enum):
    """High-level error categories that drive tier escalation and circuit breakers."""

    BLOCKED = "BLOCKED"          # IP/request blocked, 429, "sign in to confirm"
    UNAVAILABLE = "UNAVAILABLE"  # No captions, disabled, private/deleted
    TRANSIENT = "TRANSIENT"      # Timeouts, 5xx, connection resets
    TOOL_ROT = "TOOL_ROT"        # yt-dlp parse failure, schema change, extractor broken
    FATAL = "FATAL"              # Bad video ID, config error, unrecoverable


class TranscriptError(Exception):
    """Base exception for all transcript operations."""

    def __init__(self, message: str, error_class: ErrorClass, tier: Optional[str] = None):
        super().__init__(message)
        self.error_class = error_class
        self.tier = tier
        self.message = message


class BlockedError(TranscriptError):
    """Raised when YouTube blocks the request (IP, rate, fingerprint)."""

    def __init__(self, message: str, tier: Optional[str] = None):
        super().__init__(message, ErrorClass.BLOCKED, tier)


class UnavailableError(TranscriptError):
    """Raised when the video has no transcript (disabled, private, deleted)."""

    def __init__(self, message: str, tier: Optional[str] = None):
        super().__init__(message, ErrorClass.UNAVAILABLE, tier)


class TransientError(TranscriptError):
    """Raised for temporary network/server errors that may succeed on retry."""

    def __init__(self, message: str, tier: Optional[str] = None):
        super().__init__(message, ErrorClass.TRANSIENT, tier)


class ToolRotError(TranscriptError):
    """Raised when the extraction tool (yt-dlp, parser) fails due to schema changes."""

    def __init__(self, message: str, tier: Optional[str] = None):
        super().__init__(message, ErrorClass.TOOL_ROT, tier)


class FatalError(TranscriptError):
    """Raised for unrecoverable configuration or input errors."""

    def __init__(self, message: str, tier: Optional[str] = None):
        super().__init__(message, ErrorClass.FATAL, tier)