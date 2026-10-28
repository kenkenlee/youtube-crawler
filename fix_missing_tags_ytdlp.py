"""
Backfill YouTube tags with the Data API, then yt-dlp for public tags.

Prefer ``python backfill_video_tags.py``. This entry point calls the same
command so existing runbooks keep working.
"""

from backfill_video_tags import main

if __name__ == "__main__":
    raise SystemExit(main())
