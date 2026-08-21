#!/usr/bin/env python3
"""
YouTube Transcript Fetcher (Standalone CLI)

This is a thin wrapper around the project's TranscriptService.
It always stays in sync with the main implementation.

Usage:
    python get_transcript.py <video_id_or_url>
    python get_transcript.py https://www.youtube.com/watch?v=xxxxxxxxxxx
    python get_transcript.py xxxxxxxxxxx --cookies cookies.txt

Requirements:
    The script must be run from the project root (where app/ exists),
    or you must have the project in your PYTHONPATH.
"""

import sys
import re
from pathlib import Path

# Ensure we can import from the project
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from app.services.transcript_service import TranscriptService
except ImportError as e:
    print("❌ Failed to import TranscriptService from the project.")
    print("   Make sure you are running this from the project root directory.")
    print(f"   Error: {e}")
    sys.exit(1)


def extract_video_id(url_or_id: str) -> str:
    """Extract clean video ID from URL or return as-is."""
    if not url_or_id:
        return ""

    # Already a clean video ID
    if re.match(r'^[A-Za-z0-9_-]{11}$', url_or_id):
        return url_or_id

    # Extract from URL
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return url_or_id


def main():
    if len(sys.argv) < 2:
        print("YouTube Transcript Fetcher")
        print("=" * 50)
        print("Usage:")
        print("  python get_transcript.py <video_id_or_url>")
        print("  python get_transcript.py xxxxxxxxxxx")
        print("  python get_transcript.py 'https://www.youtube.com/watch?v=xxxxxxxxxxx'")
        print("  python get_transcript.py xxxxxxxxxxx --cookies cookies.txt")
        print()
        print("Options:")
        print("  --cookies <file>   Use browser cookies (helps bypass rate limits)")
        sys.exit(1)

    video_input = sys.argv[1]
    cookies_file = None

    if "--cookies" in sys.argv:
        idx = sys.argv.index("--cookies")
        if idx + 1 < len(sys.argv):
            cookies_file = sys.argv[idx + 1]

    video_id = extract_video_id(video_input)

    print(f"📥 Fetching transcript for: {video_id}")
    if cookies_file:
        print(f"🍪 Using cookies: {cookies_file}")

    # Call the project's service
    transcript = TranscriptService.get_transcript(video_id, cookies_file=cookies_file)

    if transcript:
        print(f"\n✅ Success! ({len(transcript)} characters)\n")
        print("=" * 70)
        print("TRANSCRIPT:")
        print("=" * 70)
        # Print first 3000 chars to avoid flooding terminal
        print(transcript[:3000])
        if len(transcript) > 3000:
            print(f"\n... ({len(transcript) - 3000} more characters)")
        print("=" * 70)
    else:
        print("\n❌ No transcript available.")
        print("   Possible reasons:")
        print("   - Video has no captions")
        print("   - YouTube rate limited the request (try --cookies)")
        print("   - Video is private / region restricted")
        sys.exit(1)


if __name__ == "__main__":
    main()