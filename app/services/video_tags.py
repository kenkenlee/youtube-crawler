"""Resolve and store YouTube video tags.

The Data API field ``snippet.tags`` is returned only for videos owned by the
API credential, so a crawl of someone else's channel usually sees an empty
list. Public tags come from yt-dlp (``info["tags"]``), which reads the watch
page keywords.

Persistence contract for sync clients (botalk-news and others):

- Database column ``videos.tags`` is a JSON array of strings.
- ``GET /api/videos/`` and ``GET /api/videos/{id}`` return the same array on
  the ``tags`` field. Videos are keyed by ``video_id`` (the YouTube id), not
  the integer primary key.
- CSV and Excel exports append a ``Tags`` column (comma-separated, one cell).
  Existing columns stay in place.
- ``tags_checked_at`` is internal. It is not part of the API response.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

YOUTUBE_BATCH_SIZE = 50


@dataclass
class TagFetchResult:
    tags: List[str]
    ok: bool
    source: str  # "api", "ytdlp", or "unresolved"


def normalize_tags(raw: Any) -> List[str]:
    """Return a clean list of tag strings, preserving first-seen order.

    Accepts a list, a comma-separated string, or anything else (treated as
    empty). Does not case-fold: YouTube keeps distinct casings.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if text in {"", "[]", "null"}:
            return []
        if text.startswith("["):
            try:
                import json
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            raw = parsed if isinstance(parsed, list) else [part.strip() for part in text.split(",")]
        else:
            raw = [part.strip() for part in text.split(",")]
    if isinstance(raw, (bytes, bytearray)) or not isinstance(raw, Iterable):
        return []

    seen = set()
    tags: List[str] = []
    for item in raw:
        if item is None:
            continue
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        tags.append(text)
    return tags


def tags_missing(raw: Any) -> bool:
    return not normalize_tags(raw)


def tags_to_csv(raw: Any) -> str:
    """Comma-separated form used by the CSV/Excel ``Tags`` column."""
    return ", ".join(normalize_tags(raw))


def fetch_tags_via_ytdlp(video_id: str) -> tuple:
    """Read public tags for one video.

    Returns ``(tags, ok)``. ``ok`` is False when yt-dlp is missing or the
    request failed, so callers can retry later. An empty list with ``ok``
    True means the video has no public tags.
    """
    if not video_id:
        return [], False
    try:
        import yt_dlp
    except ImportError:
        logger.warning("yt-dlp is not installed; cannot read public YouTube tags")
        return [], False

    url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 20,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.warning("yt-dlp tag fetch failed for %s: %s", video_id, exc)
        return [], False
    if not isinstance(info, dict):
        return [], False
    return normalize_tags(info.get("tags") or info.get("keywords") or []), True


def resolve_tags(video_id: str, api_tags: Any = None, *, allow_ytdlp: bool = True) -> TagFetchResult:
    """Prefer Data API tags. Fall back to yt-dlp only when the API list is empty."""
    from_api = normalize_tags(api_tags)
    if from_api:
        return TagFetchResult(tags=from_api, ok=True, source="api")
    if not allow_ytdlp:
        return TagFetchResult(tags=[], ok=False, source="unresolved")
    tags, ok = fetch_tags_via_ytdlp(video_id)
    if not ok:
        return TagFetchResult(tags=[], ok=False, source="ytdlp")
    return TagFetchResult(tags=tags, ok=True, source="ytdlp")


def backfill_missing_tags(
    db,
    youtube_service=None,
    *,
    limit: Optional[int] = None,
    force: bool = False,
    allow_ytdlp: bool = True,
    sleep_seconds: float = 1.0,
    video_ids: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Fill ``videos.tags`` for rows already in the database.

    By default only videos with no tags are fetched. ``force`` also refreshes
    videos that already have tags. A successful fetch stamps ``tags_checked_at``
    even when the video genuinely has no tags, so the timed crawl will not
    retry it. A failed fetch leaves the row untouched for a later run.

    Non-empty tags are never replaced with an empty list.
    """
    from datetime import datetime

    from sqlalchemy.orm import load_only

    from app.models.video import Video

    query = db.query(Video).options(
        load_only(Video.id, Video.video_id, Video.tags, Video.tags_checked_at)
    )
    if video_ids:
        query = query.filter(Video.video_id.in_(video_ids))
    rows = query.order_by(Video.id).all()
    if not force:
        rows = [row for row in rows if tags_missing(row.tags)]
    if limit is not None:
        rows = rows[:limit]

    stats = {"examined": 0, "updated": 0, "unchanged": 0, "failed": 0}

    for start in range(0, len(rows), YOUTUBE_BATCH_SIZE):
        chunk = rows[start:start + YOUTUBE_BATCH_SIZE]
        details: Dict[str, Dict[str, Any]] = {}
        if youtube_service is not None:
            try:
                details = youtube_service.get_videos_details([row.video_id for row in chunk]) or {}
            except Exception as exc:
                logger.error("YouTube API tag batch failed: %s", exc)
                details = {}

        for row in chunk:
            stats["examined"] += 1
            api_tags = (details.get(row.video_id) or {}).get("tags")
            try:
                result = resolve_tags(row.video_id, api_tags, allow_ytdlp=allow_ytdlp)
            except Exception as exc:
                logger.error("Tag resolve failed for %s: %s", row.video_id, exc)
                stats["failed"] += 1
                continue

            if not result.ok:
                stats["failed"] += 1
                continue

            old_tags = normalize_tags(row.tags)
            new_tags = result.tags
            # Keep a previously stored list if the new fetch found nothing.
            if not new_tags and old_tags:
                new_tags = old_tags

            changed = new_tags != old_tags
            if not dry_run:
                if changed or row.tags is None:
                    row.tags = new_tags
                row.tags_checked_at = datetime.utcnow()
            if changed:
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1

            if (
                not dry_run
                and (stats["updated"] + stats["unchanged"]) % 25 == 0
            ):
                db.commit()

            if result.source == "ytdlp" and sleep_seconds > 0:
                time.sleep(sleep_seconds)

    if not dry_run:
        db.commit()
    return stats
