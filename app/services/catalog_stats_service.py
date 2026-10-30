from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict
from zoneinfo import ZoneInfo
from sqlalchemy import func, case, select
from app.database import SessionLocal
from app.models.association import channel_categories
from app.models.category import Category
from app.models.channel import Channel
from app.models.video import Video
from app.models.crawl_session import CrawlSession

SHANGHAI = ZoneInfo("Asia/Shanghai")


def get_catalog_stats() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        now_sh = datetime.now(tz=SHANGHAI)
        day7 = (now_sh - timedelta(days=7)).replace(tzinfo=None)
        day30 = (now_sh - timedelta(days=30)).replace(tzinfo=None)

        categories_total = db.query(func.count(Category.id)).scalar() or 0
        channels_total = db.query(func.count(Channel.id)).scalar() or 0
        channels_enabled = (
            db.query(func.count(Channel.id))
            .filter(Channel.crawl_enabled.is_(True))
            .scalar()
            or 0
        )
        assigned_ids = select(channel_categories.c.channel_id).distinct()
        channels_uncategorized = (
            db.query(func.count(Channel.id))
            .filter(~Channel.id.in_(assigned_ids))
            .scalar()
            or 0
        )
        videos_total = db.query(func.count(Video.id)).scalar() or 0
        videos_with_transcript = (
            db.query(func.count(Video.id))
            .filter(Video.transcript_text.isnot(None), Video.transcript_text != "")
            .scalar()
            or 0
        )
        videos_with_summary = (
            db.query(func.count(Video.id))
            .filter(Video.summary_text.isnot(None), Video.summary_text != "")
            .scalar()
            or 0
        )
        videos_last_7d = (
            db.query(func.count(Video.id)).filter(Video.created_at >= day7).scalar() or 0
        )
        videos_last_30d = (
            db.query(func.count(Video.id)).filter(Video.created_at >= day30).scalar() or 0
        )
        channels_crawled_7d = (
            db.query(func.count(Channel.id)).filter(Channel.last_crawled_at >= day7).scalar() or 0
        )
        channels_never_crawled = (
            db.query(func.count(Channel.id)).filter(Channel.last_crawled_at.is_(None)).scalar() or 0
        )
        sessions_total = db.query(func.count(CrawlSession.id)).scalar() or 0
        sessions_completed = (
            db.query(func.count(CrawlSession.id)).filter(CrawlSession.status == "completed").scalar() or 0
        )

        # Videos per category via M2M (a video counts for every category its channel is in)
        video_by_cat_rows = (
            db.query(
                channel_categories.c.category_id.label("category_id"),
                func.count(Video.id).label("video_count"),
            )
            .select_from(channel_categories)
            .join(Channel, Channel.id == channel_categories.c.channel_id)
            .outerjoin(Video, Video.channel_id == Channel.id)
            .group_by(channel_categories.c.category_id)
            .all()
        )
        video_by_cat = {row.category_id: int(row.video_count or 0) for row in video_by_cat_rows}

        channel_agg = (
            db.query(
                Category.id,
                Category.slug,
                Category.name_zh,
                Category.name_en,
                Category.sort_order,
                func.count(channel_categories.c.channel_id).label("channel_count"),
                func.sum(case((Channel.crawl_enabled.is_(True), 1), else_=0)).label("channels_enabled"),
            )
            .outerjoin(channel_categories, channel_categories.c.category_id == Category.id)
            .outerjoin(Channel, Channel.id == channel_categories.c.channel_id)
            .group_by(
                Category.id, Category.slug, Category.name_zh, Category.name_en, Category.sort_order
            )
            .order_by(Category.sort_order.asc(), Category.id.asc())
            .all()
        )

        by_category = []
        for r in channel_agg:
            by_category.append({
                "id": r.id,
                "slug": r.slug,
                "name_zh": r.name_zh,
                "name_en": r.name_en,
                "sort_order": r.sort_order,
                "channel_count": int(r.channel_count or 0),
                "channels_enabled": int(r.channels_enabled or 0),
                "video_count": int(video_by_cat.get(r.id, 0)),
            })

        by_frequency = {
            (freq or "manual"): int(count)
            for freq, count in db.query(Channel.crawl_frequency, func.count(Channel.id))
            .group_by(Channel.crawl_frequency)
            .all()
        }

        latest_video = db.query(Video).order_by(Video.created_at.desc()).first()
        latest_session = db.query(CrawlSession).order_by(CrawlSession.id.desc()).first()
        top_categories = sorted(by_category, key=lambda c: (-c["channel_count"], c["sort_order"]))[:10]

        totals = {
            "categories": int(categories_total),
            "channels": int(channels_total),
            "channels_crawl_enabled": int(channels_enabled),
            "channels_crawl_disabled": int(channels_total - channels_enabled),
            "channels_uncategorized": int(channels_uncategorized),
            "videos": int(videos_total),
            "videos_with_transcript": int(videos_with_transcript),
            "videos_with_summary": int(videos_with_summary),
            "videos_created_last_7d": int(videos_last_7d),
            "videos_created_last_30d": int(videos_last_30d),
            "channels_crawled_last_7d": int(channels_crawled_7d),
            "channels_never_crawled": int(channels_never_crawled),
            "sessions": int(sessions_total),
            "sessions_completed": int(sessions_completed),
        }
        latest = {
            "video_id": latest_video.id if latest_video else None,
            "video_title": latest_video.title if latest_video else None,
            "video_created_at": (
                latest_video.created_at.isoformat()
                if latest_video and latest_video.created_at else None
            ),
            "session_id": latest_session.id if latest_session else None,
            "session_name": latest_session.session_name if latest_session else None,
            "session_status": latest_session.status if latest_session else None,
            "session_created_at": (
                latest_session.created_at.isoformat()
                if latest_session and latest_session.created_at else None
            ),
        }
        return {
            "generated_at": now_sh.isoformat(),
            "timezone": "Asia/Shanghai",
            "totals": totals,
            "by_frequency": by_frequency,
            "by_category": by_category,
            "top_categories": top_categories,
            "latest": latest,
        }
    finally:
        db.close()
