"""
Transcript Engine — orchestrates the full tiered fallback chain.

Usage:
    engine = TranscriptEngine()
    result = engine.fetch("rCaotedYlos", languages=["en"])
"""

from typing import List, Optional, Dict
from transcript_engine.store import TranscriptStore
from transcript_engine.governor import RateGovernor
from transcript_engine.tiers.base import TranscriptTier
from transcript_engine.tiers.tier1_api import Tier1Api
from transcript_engine.tiers.tier2_ytdlp import Tier2YtDlp
from transcript_engine.errors import (
    BlockedError, UnavailableError, TransientError, ToolRotError, FatalError
)


class TranscriptEngine:
    def __init__(self, db_path: str = "data/transcript_cache.db"):
        self.store = TranscriptStore(db_path)
        self.governor = RateGovernor(self.store)
        self.tiers: List[TranscriptTier] = [
            Tier1Api(self.governor),
            Tier2YtDlp(self.governor),
            # Tier3Proxy, Tier4DataApi, Tier5ASR will be added later
        ]

    def fetch(self, video_id: str, languages: List[str] = None, force_refresh: bool = False) -> Optional[Dict]:
        """
        Main entry point. Tries tiers in order until success or terminal failure.
        """
        if languages is None:
            languages = ["en", "en-US", "en-GB"]

        # Tier 0: Cache first
        if not force_refresh:
            cached = self.store.get_transcript(video_id, languages[0])
            if cached:
                print(f"[engine] Cache hit for {video_id}")
                return cached

        last_error = None

        for tier in self.tiers:
            # Skip if circuit breaker is open for this tier
            if self.governor.is_tier_blocked(tier.name):
                print(f"[engine] Skipping {tier.name} — circuit breaker open")
                continue

            try:
                print(f"[engine] Trying {tier.name} for {video_id}...")
                result = tier.fetch(video_id, languages)
                if result:
                    self.store.save_transcript(
                        video_id, result["lang"], tier.name, result
                    )
                    print(f"[engine] SUCCESS via {tier.name}")
                    return result
            except UnavailableError as e:
                print(f"[engine] {tier.name}: unavailable ({e})")
                self.store.save_negative(video_id, languages[0], "UNAVAILABLE", tier.name)
                return None   # terminal for this video
            except BlockedError as e:
                print(f"[engine] {tier.name}: BLOCKED — escalating")
                last_error = e
                continue
            except (TransientError, ToolRotError) as e:
                print(f"[engine] {tier.name}: transient/rot error — trying next tier")
                last_error = e
                continue
            except FatalError as e:
                print(f"[engine] FATAL: {e}")
                raise

        print(f"[engine] All tiers exhausted for {video_id}")
        return None

    def status(self) -> Dict:
        return self.store.get_status()