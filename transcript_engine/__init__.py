"""
transcript_engine — resilient, multi-tier YouTube transcript acquisition system.

Implements the architecture described in TRANSCRIPT_RESILIENCE_PLAN.md.
"""

from .engine import TranscriptEngine
from .store import TranscriptStore
from .governor import RateGovernor
from .errors import (
    ErrorClass, TranscriptError, BlockedError, UnavailableError,
    TransientError, ToolRotError, FatalError
)

__all__ = [
    "TranscriptEngine",
    "TranscriptStore",
    "RateGovernor",
    "ErrorClass",
    "TranscriptError",
    "BlockedError",
    "UnavailableError",
    "TransientError",
    "ToolRotError",
    "FatalError",
]