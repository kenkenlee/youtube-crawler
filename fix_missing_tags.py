"""
Backfill YouTube tags for videos that don't have any.

Prefer ``python backfill_video_tags.py`` — this file calls the same command
so existing runbooks keep working. Tags are written to ``videos.tags`` as a
JSON array of strings.
"""
from backfill_video_tags import main

if __name__ == "__main__":
    raise SystemExit(main())
