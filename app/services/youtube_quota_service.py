"""Track YouTube Data API quota usage for the Settings page.

Quota day = America/Los_Angeles (Pacific Time), matching Google's YouTube Data
API daily quota reset at midnight PT. Units are estimates from the public
quota table:
  channels.list / playlistItems.list / videos.list = 1
  search.list = 100
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
import logging
import threading

from sqlalchemy import func

from app.database import SessionLocal
from app.models.youtube_api_usage import YouTubeApiUsageDaily
from app.models.crawl_session import CrawlSession
from app.models.video import Video
from app.models.channel import Channel

logger = logging.getLogger(__name__)

QUOTA_TZ = ZoneInfo("America/Los_Angeles")
DAILY_QUOTA_LIMIT = 10_000

METHOD_UNITS = {
    "channels.list": 1,
    "playlistItems.list": 1,
    "videos.list": 1,
    "search.list": 100,
}

_lock = threading.Lock()


def current_quota_date(now: Optional[datetime] = None) -> str:
    """Return today's YouTube quota date (YYYY-MM-DD) in Pacific Time."""
    dt = now or datetime.now(tz=QUOTA_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=QUOTA_TZ)
    else:
        dt = dt.astimezone(QUOTA_TZ)
    return dt.date().isoformat()


def quota_reset_at_iso() -> str:
    """Next Pacific midnight as ISO-8601 (with offset)."""
    now = datetime.now(tz=QUOTA_TZ)
    tomorrow = (now + timedelta(days=1)).date()
    reset = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=QUOTA_TZ)
    return reset.isoformat()


def units_for(method: str) -> int:
    return METHOD_UNITS.get(method, 1)


def record_api_call(method: str, units: Optional[int] = None, calls: int = 1) -> None:
    """Increment today's counter for ``method``. Never raises to callers."""
    if calls <= 0:
        return
    cost = units if units is not None else units_for(method)
    total_units = cost * calls
    quota_date = current_quota_date()
    try:
        with _lock:
            db = SessionLocal()
            try:
                row = (
                    db.query(YouTubeApiUsageDaily)
                    .filter(
                        YouTubeApiUsageDaily.quota_date == quota_date,
                        YouTubeApiUsageDaily.method == method,
                    )
                    .first()
                )
                if row:
                    row.call_count = int(row.call_count or 0) + calls
                    row.units = int(row.units or 0) + total_units
                else:
                    db.add(
                        YouTubeApiUsageDaily(
                            quota_date=quota_date,
                            method=method,
                            call_count=calls,
                            units=total_units,
                        )
                    )
                db.commit()
            finally:
                db.close()
    except Exception as e:
        logger.warning("Failed to record YouTube API usage for %s: %s", method, e)


def get_today_summary() -> Dict[str, Any]:
    """Aggregate today's API usage + crawl fetch stats for Settings UI."""
    quota_date = current_quota_date()
    db = SessionLocal()
    try:
        rows = (
            db.query(YouTubeApiUsageDaily)
            .filter(YouTubeApiUsageDaily.quota_date == quota_date)
            .order_by(YouTubeApiUsageDaily.method.asc())
            .all()
        )
        by_method: List[Dict[str, Any]] = []
        total_calls = 0
        total_units = 0
        for row in rows:
            calls = int(row.call_count or 0)
            units = int(row.units or 0)
            total_calls += calls
            total_units += units
            by_method.append(
                {
                    "method": row.method,
                    "call_count": calls,
                    "units": units,
                    "unit_cost": units_for(row.method),
                }
            )

        # Crawl activity for the current PT quota day (sessions started in that window)
        day_start = datetime.fromisoformat(quota_date).replace(tzinfo=QUOTA_TZ)
        day_end = day_start + timedelta(days=1)
        # SQLite often stores naive UTC-ish timestamps; compare as naive PT wall times
        # and also as UTC-naive approx. Prefer filtering on started_at / created_at.
        day_start_naive = day_start.replace(tzinfo=None)
        day_end_naive = day_end.replace(tzinfo=None)

        sessions = (
            db.query(CrawlSession)
            .filter(
                CrawlSession.created_at >= day_start_naive,
                CrawlSession.created_at < day_end_naive,
            )
            .order_by(CrawlSession.id.desc())
            .limit(20)
            .all()
        )

        channels_crawled = sum(int(s.processed_channels or 0) for s in sessions)
        videos_found = sum(int(s.total_videos_found or 0) for s in sessions)
        videos_processed = sum(int(s.videos_processed or 0) for s in sessions)

        # New videos inserted during the quota day (best-effort from created_at)
        videos_new = 0
        try:
            videos_new = (
                db.query(func.count(Video.id))
                .filter(
                    Video.created_at >= day_start_naive,
                    Video.created_at < day_end_naive,
                )
                .scalar()
                or 0
            )
        except Exception:
            videos_new = 0

        channels_total = db.query(func.count(Channel.id)).scalar() or 0
        videos_total = db.query(func.count(Video.id)).scalar() or 0

        recent_sessions = [
            {
                "id": s.id,
                "session_name": s.session_name,
                "status": s.status,
                "processed_channels": s.processed_channels or 0,
                "total_channels": s.total_channels or 0,
                "total_videos_found": s.total_videos_found or 0,
                "videos_processed": s.videos_processed or 0,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions[:10]
        ]

        remaining = max(0, DAILY_QUOTA_LIMIT - total_units)
        return {
            "quota_day": quota_date,
            "quota_timezone": "America/Los_Angeles",
            "quota_timezone_note": (
                "YouTube Data API daily quota resets at midnight Pacific Time (PT). "
                "This panel uses the PT quota day, not Asia/Shanghai calendar day."
            ),
            "quota_limit": DAILY_QUOTA_LIMIT,
            "units_used": total_units,
            "units_remaining_estimate": remaining,
            "percent_used": round(min(100.0, (total_units / DAILY_QUOTA_LIMIT) * 100), 1)
            if DAILY_QUOTA_LIMIT
            else 0.0,
            "total_calls": total_calls,
            "by_method": by_method,
            "method_costs": METHOD_UNITS,
            "quota_resets_at": quota_reset_at_iso(),
            "crawl": {
                "channels_crawled_today": channels_crawled,
                "videos_found_today": videos_found,
                "videos_processed_today": videos_processed,
                "videos_new_today": int(videos_new),
                "channels_total": int(channels_total),
                "videos_total": int(videos_total),
            },
            "recent_sessions": recent_sessions,
        }
    finally:
        db.close()
