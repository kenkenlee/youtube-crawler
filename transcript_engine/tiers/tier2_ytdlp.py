"""
Tier 2: yt-dlp hardened subtitle extraction.

Features:
- Client rotation (web, mweb, android)
- PO Token provider plugin support (bgutil-ytdlp-pot-provider)
- Optional cookies_from_browser
- Sleep between requests
- Robust VTT/SRT parsing
"""

import tempfile
import os
import re
import subprocess
from typing import List, Optional, Dict
from pathlib import Path

import yt_dlp

from transcript_engine.tiers.base import TranscriptTier
from transcript_engine.errors import BlockedError, UnavailableError, TransientError, ToolRotError
from transcript_engine.governor import RateGovernor


class Tier2YtDlp(TranscriptTier):
    name = "tier2_ytdlp"

    # Client rotation order (ios is intentionally excluded — it drops cookies)
    CLIENTS = ["web", "mweb", "android"]

    def __init__(self, governor: RateGovernor, cookies_file: Optional[str] = None):
        self.governor = governor
        self.cookies_file = cookies_file
        self._current_client_index = 0

    def _get_next_client(self) -> str:
        client = self.CLIENTS[self._current_client_index]
        self._current_client_index = (self._current_client_index + 1) % len(self.CLIENTS)
        return client

    def fetch(self, video_id: str, languages: List[str] = None) -> Optional[Dict]:
        if languages is None:
            languages = ["en", "en-US", "en-GB"]

        self.governor.wait_for_token(self.name)

        url = f"https://www.youtube.com/watch?v={video_id}"
        client = self._get_next_client()

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": languages,
            "sleep_interval_requests": 2,
            "player_client": client,
            "outtmpl": "%(id)s.%(ext)s",
        }

        if self.cookies_file and os.path.exists(self.cookies_file):
            ydl_opts["cookiefile"] = self.cookies_file
        elif self.cookies_file == "browser":
            # Special value: use cookies_from_browser
            ydl_opts["cookiesfrombrowser"] = ("firefox",)

        # PO Token provider is auto-detected by yt-dlp if the plugin is installed
        # (bgutil-ytdlp-pot-provider + Deno/Node)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                ydl_opts["outtmpl"] = os.path.join(tmpdir, "%(id)s.%(ext)s")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Find subtitle file
                for filename in os.listdir(tmpdir):
                    if filename.endswith((".vtt", ".srt")):
                        filepath = os.path.join(tmpdir, filename)
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()

                        segments = self._parse_subtitle(content)
                        if segments:
                            return {
                                "video_id": video_id,
                                "lang": "en",  # yt-dlp doesn't always expose lang cleanly
                                "source_tier": self.name,
                                "segments": segments,
                                "player_client": client
                            }

                # No subtitle file found
                raise UnavailableError("No subtitle file produced by yt-dlp", self.name)

        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if "Sign in" in msg or "login" in msg.lower():
                raise BlockedError("yt-dlp requires login / cookies", self.name)
            if "429" in msg or "blocked" in msg.lower():
                self.governor.record_block(self.name)
                raise BlockedError(msg, self.name)
            raise TransientError(msg, self.name)
        except Exception as e:
            raise ToolRotError(f"yt-dlp extraction failed: {e}", self.name)

    def _parse_subtitle(self, content: str) -> List[Dict]:
        """Parse VTT or SRT into normalized segments."""
        lines = content.split("\n")
        segments = []
        current_text = []
        current_start = 0.0
        current_duration = 0.0

        time_pattern = re.compile(r"(\d+):(\d+):(\d+\.\d+) --> (\d+):(\d+):(\d+\.\d+)")

        for line in lines:
            line = line.strip()
            if not line or line.startswith(("WEBVTT", "NOTE", "STYLE")):
                continue

            match = time_pattern.search(line)
            if match:
                # Save previous segment
                if current_text:
                    text = " ".join(current_text).strip()
                    if text:
                        segments.append({
                            "text": text,
                            "start": current_start,
                            "duration": current_duration
                        })
                    current_text = []

                # Parse new timestamp
                h1, m1, s1, h2, m2, s2 = match.groups()
                start = int(h1) * 3600 + int(m1) * 60 + float(s1)
                end = int(h2) * 3600 + int(m2) * 60 + float(s2)
                current_start = start
                current_duration = end - start
                continue

            # Remove timestamp tags like <00:00:01.000>
            clean = re.sub(r"<\d+:\d+:\d+\.\d+>", "", line)
            if clean:
                current_text.append(clean)

        # Don't forget the last segment
        if current_text:
            text = " ".join(current_text).strip()
            if text:
                segments.append({
                    "text": text,
                    "start": current_start,
                    "duration": current_duration
                })

        return segments