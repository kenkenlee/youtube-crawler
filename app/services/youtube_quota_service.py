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
import json
import logging
import threading

from sqlalchemy import func

from app.database import SessionLocal
from app.models.youtube_api_usage import YouTubeApiUsageDaily, YouTubeApiErrorDaily
from app.models.crawl_session import CrawlSession
from app.models.video import Video
from app.models.channel import Channel

logger = logging.getLogger(__name__)

QUOTA_TZ = ZoneInfo("America/Los_Angeles")
DAILY_QUOTA_LIMIT = 10_000
NEAR_LIMIT_PERCENT = 80.0

METHOD_UNITS = {
    "channels.list": 1,
    "playlistItems.list": 1,
    "videos.list": 1,
    "search.list": 100,
}

QUOTA_EXCEEDED_REASONS = frozenset(
    {
        "quotaExceeded",
        "dailyLimitExceeded",
    }
)

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


def parse_http_error(exc: Any) -> Dict[str, Any]:
    """Extract status / reason / message from googleapiclient HttpError (or similar)."""
    status = 0
    reason = "unknown"
    message = str(exc) if exc is not None else "unknown error"
    try:
        resp = getattr(exc, "resp", None)
        if resp is not None:
            status = int(getattr(resp, "status", 0) or 0)
    except Exception:
        status = 0
    try:
        content = getattr(exc, "content", None)
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        if content:
            data = json.loads(content)
            err = data.get("error") or {}
            if isinstance(err, dict):
                message = (err.get("message") or message)[:500]
                errors = err.get("errors") or []
                if errors and isinstance(errors[0], dict):
                    reason = (errors[0].get("reason") or reason)[:64]
                if reason == "unknown" and err.get("status"):
                    reason = str(err.get("status"))[:64]
    except Exception:
        pass
    if reason == "unknown" and status == 403 and "quota" in message.lower():
        reason = "quotaExceeded"
    return {
        "http_status": status or None,
        "reason": reason or "unknown",
        "message": message[:500],
    }


def record_api_error(method: str, exc: Any = None, *, reason: Optional[str] = None,
                     http_status: Optional[int] = None, message: Optional[str] = None) -> None:
    """Increment today's error counter. Never raises to callers."""
    parsed = parse_http_error(exc) if exc is not None else {
        "http_status": http_status,
        "reason": reason or "unknown",
        "message": (message or "")[:500],
    }
    if reason:
        parsed["reason"] = reason[:64]
    if http_status is not None:
        parsed["http_status"] = http_status
    if message:
        parsed["message"] = message[:500]

    method = (method or "unknown")[:64]
    err_reason = (parsed.get("reason") or "unknown")[:64]
    quota_date = current_quota_date()
    try:
        with _lock:
            db = SessionLocal()
            try:
                row = (
                    db.query(YouTubeApiErrorDaily)
                    .filter(
                        YouTubeApiErrorDaily.quota_date == quota_date,
                        YouTubeApiErrorDaily.method == method,
                        YouTubeApiErrorDaily.reason == err_reason,
                    )
                    .first()
                )
                if row:
                    row.error_count = int(row.error_count or 0) + 1
                    if parsed.get("http_status"):
                        row.http_status = parsed["http_status"]
                    if parsed.get("message"):
                        row.last_message = parsed["message"]
                else:
                    db.add(
                        YouTubeApiErrorDaily(
                            quota_date=quota_date,
                            method=method,
                            reason=err_reason,
                            http_status=parsed.get("http_status"),
                            error_count=1,
                            last_message=parsed.get("message"),
                        )
                    )
                db.commit()
            finally:
                db.close()
    except Exception as e:
        logger.warning("Failed to record YouTube API error for %s: %s", method, e)


def _build_alert(
    *,
    units_used: int,
    percent_used: float,
    quota_error_count: int,
    total_errors: int,
    resets_at: str,
) -> Optional[Dict[str, Any]]:
    """Return a UI alert when quota is exceeded or near the daily limit."""
    exceeded = units_used >= DAILY_QUOTA_LIMIT or quota_error_count > 0
    if exceeded:
        parts = []
        if quota_error_count:
            parts.append(
                f"Google returned quotaExceeded/dailyLimitExceeded "
                f"({quota_error_count} error(s) today)."
            )
        if units_used >= DAILY_QUOTA_LIMIT:
            parts.append(
                f"Estimated usage reached {units_used:,} / {DAILY_QUOTA_LIMIT:,} units."
            )
        parts.append(f"Quota resets at {resets_at} (midnight Pacific Time).")
        if total_errors and not quota_error_count:
            parts.append(f"Other API errors today: {total_errors}.")
        return {
            "level": "danger",
            "code": "quota_exceeded",
            "title": "YouTube API daily quota exceeded",
            "message": " ".join(parts),
            "quota_exceeded": True,
            "near_limit": False,
        }
    if percent_used >= NEAR_LIMIT_PERCENT:
        return {
            "level": "warning",
            "code": "near_limit",
            "title": "YouTube API quota nearly exhausted",
            "message": (
                f"Estimated usage is {percent_used:.1f}% "
                f"({units_used:,} / {DAILY_QUOTA_LIMIT:,} units). "
                f"Quota resets at {resets_at} (midnight Pacific Time)."
            ),
            "quota_exceeded": False,
            "near_limit": True,
        }
    return None


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

        error_rows = (
            db.query(YouTubeApiErrorDaily)
            .filter(YouTubeApiErrorDaily.quota_date == quota_date)
            .order_by(
                YouTubeApiErrorDaily.error_count.desc(),
                YouTubeApiErrorDaily.reason.asc(),
                YouTubeApiErrorDaily.method.asc(),
            )
            .all()
        )
        errors: List[Dict[str, Any]] = []
        total_errors = 0
        quota_error_count = 0
        for er in error_rows:
            cnt = int(er.error_count or 0)
            total_errors += cnt
            is_quota = er.reason in QUOTA_EXCEEDED_REASONS
            if is_quota:
                quota_error_count += cnt
            errors.append(
                {
                    "method": er.method,
                    "reason": er.reason,
                    "http_status": er.http_status,
                    "error_count": cnt,
                    "last_message": er.last_message,
                    "updated_at": er.updated_at.isoformat() if er.updated_at else None,
                    "is_quota_exceeded": is_quota,
                }
            )

        # Crawl activity for the current PT quota day (sessions started in that window)
        day_start = datetime.fromisoformat(quota_date).replace(tzinfo=QUOTA_TZ)
        day_end = day_start + timedelta(days=1)
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
        percent_used = (
            round(min(100.0, (total_units / DAILY_QUOTA_LIMIT) * 100), 1)
            if DAILY_QUOTA_LIMIT
            else 0.0
        )
        resets_at = quota_reset_at_iso()
        alert = _build_alert(
            units_used=total_units,
            percent_used=percent_used,
            quota_error_count=quota_error_count,
            total_errors=total_errors,
            resets_at=resets_at,
        )

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
            "percent_used": percent_used,
            "total_calls": total_calls,
            "by_method": by_method,
            "method_costs": METHOD_UNITS,
            "quota_resets_at": resets_at,
            "quota_exceeded": bool(alert and alert.get("quota_exceeded")),
            "near_limit": bool(
                (alert and alert.get("near_limit"))
                or (not (alert and alert.get("quota_exceeded")) and percent_used >= NEAR_LIMIT_PERCENT)
            ),
            "alert": alert,
            "errors": errors,
            "error_total": total_errors,
            "quota_error_count": quota_error_count,
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
