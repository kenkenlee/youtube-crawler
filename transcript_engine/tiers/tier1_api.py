"""
Tier 1: youtube-transcript-api (direct, throttled, cheapest path)
"""

from typing import List, Optional, Dict
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    RequestBlocked, IpBlocked, TranscriptsDisabled, NoTranscriptFound
)

from transcript_engine.tiers.base import TranscriptTier
from transcript_engine.errors import BlockedError, UnavailableError, TransientError
from transcript_engine.governor import RateGovernor


class Tier1Api(TranscriptTier):
    name = "tier1_api"

    def __init__(self, governor: RateGovernor):
        self.governor = governor
        self.api = YouTubeTranscriptApi()

    def fetch(self, video_id: str, languages: List[str] = None) -> Optional[Dict]:
        if languages is None:
            languages = ["en", "en-US", "en-GB"]

        self.governor.wait_for_token(self.name)

        try:
            transcript_list = self.api.list(video_id)
            transcript = None

            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except NoTranscriptFound:
                    continue

            if not transcript:
                for lang in languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        break
                    except NoTranscriptFound:
                        continue

            if not transcript:
                for t in transcript_list:
                    transcript = t
                    break

            if not transcript:
                raise UnavailableError("No transcript available", self.name)

            data = transcript.fetch()
            segments = [{"text": e.text, "start": e.start, "duration": e.duration} for e in data]

            return {
                "video_id": video_id,
                "lang": transcript.language_code,
                "source_tier": self.name,
                "segments": segments
            }

        except (RequestBlocked, IpBlocked) as e:
            self.governor.record_block(self.name)
            raise BlockedError(str(e), self.name)
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            raise UnavailableError(str(e), self.name)
        except Exception as e:
            raise TransientError(str(e), self.name)