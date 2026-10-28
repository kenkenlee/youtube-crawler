#!/usr/bin/env python3
"""Backfill YouTube tags onto videos already stored in the crawler database.

The timed crawl stores tags for videos it visits. This script covers the
catalog already in the database, including rows saved when ``snippet.tags``
came back empty (YouTube only returns that field for videos the API
credential owns). Public tags are read with yt-dlp.

Stored field
    videos.tags              JSON array of strings, e.g. ["euv", "chips"]
    videos.tags_checked_at   internal; not returned by the API

Sync field
    GET /api/videos/ and GET /api/videos/{id} include ``tags`` as a JSON
    array. Key videos by ``video_id`` (the YouTube id). CSV/Excel append a
    comma-separated ``Tags`` column without moving existing columns.

Examples
    python backfill_video_tags.py
    python backfill_video_tags.py --limit 100
    python backfill_video_tags.py --video-id dQw4w9WgXcQ
    python backfill_video_tags.py --force
    python backfill_video_tags.py --dry-run
    python backfill_video_tags.py --no-ytdlp
"""

import argparse
import sys

from sqlalchemy import inspect, text

from app.database import SessionLocal, engine
from app.services.video_tags import backfill_missing_tags


def ensure_tag_columns(db_engine=None) -> None:
    """Add tags_checked_at on databases created before this column existed.

    ``videos.tags`` itself is part of the original model. Starting the app
    also applies this ALTER; the script repeats it so a backfill can run
    before the next server boot.
    """
    db_engine = db_engine or engine
    inspector = inspect(db_engine)
    if "videos" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("videos")}
    if "tags_checked_at" in columns:
        return
    with db_engine.connect() as conn:
        conn.execute(text("ALTER TABLE videos ADD COLUMN tags_checked_at DATETIME"))
        conn.commit()
    print("Added videos.tags_checked_at")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="Maximum videos to fetch this run")
    parser.add_argument(
        "--video-id",
        action="append",
        dest="video_ids",
        default=None,
        help="YouTube video id to refresh. Repeat for several. Default: every video with no tags.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Also re-fetch videos that already have tags. A non-empty list is never replaced with an empty one.",
    )
    parser.add_argument(
        "--no-ytdlp",
        action="store_true",
        help="Use the Data API only. Tags on videos you do not own will stay empty.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to wait between yt-dlp requests (default: 1).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing")
    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")

    ensure_tag_columns()

    youtube_service = None
    try:
        from app.services.youtube_service import YouTubeService
        youtube_service = YouTubeService()
    except Exception as exc:
        print(f"YouTube Data API unavailable ({exc}).")
        if args.no_ytdlp:
            print("Cannot backfill with --no-ytdlp while the Data API is unavailable.")
            return 1
        print("Continuing with yt-dlp only.")

    db = SessionLocal()
    try:
        stats = backfill_missing_tags(
            db,
            youtube_service,
            limit=args.limit,
            force=args.force,
            allow_ytdlp=not args.no_ytdlp,
            sleep_seconds=args.sleep,
            video_ids=args.video_ids,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        db.rollback()
        print(f"Backfill failed: {exc}")
        return 1
    finally:
        db.close()

    prefix = "Dry run." if args.dry_run else "Done."
    print(
        f"{prefix} examined={stats['examined']} updated={stats['updated']} "
        f"unchanged={stats['unchanged']} failed={stats['failed']}"
    )
    print("Tags are stored on videos.tags (JSON array) and returned as `tags` by the video list and detail APIs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
