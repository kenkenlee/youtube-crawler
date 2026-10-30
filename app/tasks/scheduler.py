from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# Content-category slugs treated as news (4x/day, never auto-demoted)
NEWS_CATEGORY_SLUGS = frozenset({"hk-news", "intl-news", "china-taiwan"})
NEWS_SLOT_HOURS = (6, 11, 16, 21)  # Asia/Shanghai
TZ_SHANGHAI = "Asia/Shanghai"


def _news_channel_ids(db):
    """Enabled channels in news categories."""
    from app.models.channel import Channel
    from app.models.category import Category

    rows = (
        db.query(Channel)
        .join(Category, Channel.category_id == Category.id, isouter=True)
        .filter(Channel.crawl_enabled.is_(True))
        .all()
    )
    ids = []
    for ch in rows:
        slug = ch.category.slug if ch.category is not None else None
        if slug in NEWS_CATEGORY_SLUGS:
            ids.append(ch.id)
    return ids


def recurring_sessions_job():
    """Check for due recurring sessions and spawn at most ONE child run per tick.

    A recurring session (recurrence_hours set, recurrence_active true) re-runs
    every N hours. The session itself acts as the template; each run is a child
    session (parent_session_id pointing back) so per-run history is preserved.
    Uses a 1-minute tolerance so a run is spawned when the elapsed time since
    the last run is >= the configured interval.

    Serialisation: never spawn while any non-template child is pending/running,
    or while the global crawl queue is busy. At most one new child per minute.
    """
    from app.database import SessionLocal
    from app.models.crawl_session import CrawlSession
    from app.tasks.crawl_queue import enqueue_crawl, is_busy

    if getattr(scheduler, "_recurring_job_running", False):
        return
    scheduler._recurring_job_running = True
    try:
        db = SessionLocal()
        try:
            active_count = db.query(CrawlSession).filter(
                CrawlSession.status.in_(("pending", "running")),
            ).count()
            if active_count or is_busy():
                logger.debug(
                    "Recurring job: skip tick (active_sessions=%s queue_busy=%s)",
                    active_count,
                    is_busy(),
                )
                return

            templates = (
                db.query(CrawlSession)
                .filter(
                    CrawlSession.recurrence_hours.isnot(None),
                    CrawlSession.recurrence_active.is_(True),
                    CrawlSession.parent_session_id.is_(None),
                )
                .order_by(CrawlSession.id.asc())
                .all()
            )

            now = datetime.utcnow()
            spawned = False
            for template in templates:
                if spawned:
                    break

                if template.status == "running":
                    continue

                latest_child = (
                    db.query(CrawlSession)
                    .filter(CrawlSession.parent_session_id == template.id)
                    .order_by(CrawlSession.created_at.desc())
                    .first()
                )
                if latest_child is not None:
                    if latest_child.status in ("pending", "running"):
                        continue
                    last_run = (
                        latest_child.created_at
                        or latest_child.started_at
                        or template.created_at
                    )
                else:
                    last_run = (
                        template.completed_at
                        or template.started_at
                        or template.created_at
                    )
                if last_run.tzinfo is not None:
                    last_run = last_run.replace(tzinfo=None)
                if now - last_run < timedelta(hours=template.recurrence_hours) - timedelta(
                    minutes=1
                ):
                    continue

                child = CrawlSession(
                    session_name=f"{template.session_name} (auto)",
                    session_type=template.session_type,
                    channel_ids=template.channel_ids,
                    filter_keywords=template.filter_keywords,
                    max_videos=template.max_videos,
                    parent_session_id=template.id,
                    status="pending",
                )
                db.add(child)
                db.commit()
                db.refresh(child)

                # Priority: news-named templates ahead of others
                name_l = (template.session_name or "").lower()
                if "news" in name_l or name_l.startswith("news"):
                    prio = 0
                elif "weekly" in name_l:
                    prio = 2
                else:
                    prio = 1

                logger.info(
                    f"Recurring session '{template.session_name}' (#{template.id}) due - "
                    f"spawned run #{child.id} (serial queue prio={prio})"
                )
                enqueue_crawl(child.id, priority=prio)
                spawned = True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in recurring sessions job: {e}")
    finally:
        scheduler._recurring_job_running = False


def news_slot_crawl_job():
    """Crawl all news-category channels (4x/day, Asia/Shanghai clock slots)."""
    from app.database import SessionLocal
    from app.models.crawl_session import CrawlSession
    from app.tasks.crawl_queue import enqueue_crawl, is_busy

    logger.info("Starting news-slot crawl job")
    db = SessionLocal()
    try:
        channel_ids = _news_channel_ids(db)
        if not channel_ids:
            logger.info("News-slot crawl: no enabled news channels")
            return

        # Local wall-clock label in Asia/Shanghai
        try:
            from zoneinfo import ZoneInfo

            label = datetime.now(ZoneInfo(TZ_SHANGHAI)).strftime("%H:%M")
        except Exception:
            label = datetime.utcnow().strftime("%H:%M UTC")

        session = CrawlSession(
            session_name=f"NEWS slot {label} - {datetime.utcnow().strftime('%Y-%m-%d')}",
            session_type="scheduled",
            channel_ids=channel_ids,
            filter_keywords=[],
            max_videos=10,
            status="pending",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Always enqueue at highest priority so news jumps ahead of any
        # leftover daily/weekly work still in the FIFO/priority queue.
        enqueue_crawl(session.id, priority=0)
        logger.info(
            f"News-slot crawl enqueued session #{session.id}: {len(channel_ids)} channels "
            f"(queue_busy_before_ok={is_busy()})"
        )
    except Exception as e:
        logger.error(f"Error in news-slot crawl job: {e}")
    finally:
        db.close()


def weekly_crawl_job():
    """Sunday Asia/Shanghai 03:00 — crawl channels with crawl_frequency=weekly."""
    from app.database import SessionLocal
    from app.models.channel import Channel
    from app.models.category import Category
    from app.models.crawl_session import CrawlSession
    from app.tasks.crawl_queue import enqueue_crawl, is_busy

    logger.info("Starting weekly crawl job")
    if is_busy():
        logger.info("Weekly crawl deferred — serial crawl queue busy (will not retry this hour)")
        # Still create? Better skip entirely this week tick if busy — news may be running.
        # Create + low priority enqueue so it runs after whatever is in flight.
        pass

    db = SessionLocal()
    try:
        channels = (
            db.query(Channel)
            .filter(Channel.crawl_enabled.is_(True), Channel.crawl_frequency == "weekly")
            .all()
        )
        # Safety: never include news categories even if mis-tagged weekly
        channel_ids = []
        for ch in channels:
            slug = ch.category.slug if ch.category is not None else None
            if slug in NEWS_CATEGORY_SLUGS:
                continue
            channel_ids.append(ch.id)

        if not channel_ids:
            logger.info("No channels configured for weekly crawl")
            return

        session = CrawlSession(
            session_name=f"Weekly Crawl - {datetime.utcnow().strftime('%Y-%m-%d')}",
            session_type="scheduled",
            channel_ids=channel_ids,
            filter_keywords=[],
            max_videos=10,
            status="pending",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        enqueue_crawl(session.id, priority=2)
        logger.info(f"Weekly crawl enqueued session #{session.id}: {len(channel_ids)} channels")
    except Exception as e:
        logger.error(f"Error in weekly crawl job: {e}")
    finally:
        db.close()


def start_scheduler():
    """Initialize and start the background scheduler"""
    if not settings.ENABLE_SCHEDULER:
        logger.info("Scheduler is disabled")
        return

    try:
        hour, minute = settings.DAILY_CRAWL_TIME.split(":")
        hour = int(hour)
        minute = int(minute)
    except Exception:
        logger.error(f"Invalid DAILY_CRAWL_TIME format: {settings.DAILY_CRAWL_TIME}")
        hour, minute = 2, 0

    # Daily non-news crawl — interpret DAILY_CRAWL_TIME in Asia/Shanghai
    scheduler.add_job(
        daily_crawl_job,
        CronTrigger(hour=hour, minute=minute, timezone=TZ_SHANGHAI),
        id="daily_crawl",
        name="Daily Channel Crawl (non-news)",
        replace_existing=True,
    )

    # News slots 06/11/16/21 Asia/Shanghai
    for h in NEWS_SLOT_HOURS:
        scheduler.add_job(
            news_slot_crawl_job,
            CronTrigger(hour=h, minute=0, timezone=TZ_SHANGHAI),
            id=f"news_slot_{h:02d}",
            name=f"News Slot {h:02d}:00 Asia/Shanghai",
            replace_existing=True,
        )

    # Weekly slow channels — Sunday 03:00 Asia/Shanghai
    scheduler.add_job(
        weekly_crawl_job,
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=TZ_SHANGHAI),
        id="weekly_crawl",
        name="Weekly Channel Crawl",
        replace_existing=True,
    )

    scheduler.add_job(
        auto_summarize_job,
        CronTrigger(minute=0, timezone=TZ_SHANGHAI),
        id="auto_summarize",
        name="Auto Summarize Videos",
        replace_existing=True,
    )

    scheduler.add_job(
        generate_daily_summary_job,
        CronTrigger(hour=23, minute=55, timezone=TZ_SHANGHAI),
        id="daily_summary",
        name="Generate Daily Summary",
        replace_existing=True,
    )

    scheduler.add_job(
        recurring_sessions_job,
        "interval",
        minutes=1,
        id="recurring_sessions",
        name="Recurring Sessions Runner",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started (TZ=%s): daily=%02d:%02d, news_slots=%s, weekly=Sun 03:00",
        TZ_SHANGHAI,
        hour,
        minute,
        list(NEWS_SLOT_HOURS),
    )


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def daily_crawl_job():
    """Job to crawl enabled non-news channels with crawl_frequency=daily"""
    from app.database import SessionLocal
    from app.models.channel import Channel
    from app.models.crawl_session import CrawlSession
    from app.tasks.crawl_queue import enqueue_crawl, is_busy

    logger.info("Starting daily crawl job (non-news only)")

    if is_busy():
        logger.info("Daily crawl deferred — serial crawl queue busy")
        return

    db = SessionLocal()
    try:
        channels = (
            db.query(Channel)
            .filter(Channel.crawl_enabled.is_(True), Channel.crawl_frequency == "daily")
            .all()
        )

        channel_ids = []
        for ch in channels:
            slug = ch.category.slug if ch.category is not None else None
            if slug in NEWS_CATEGORY_SLUGS:
                continue  # news handled by news_slot_crawl_job
            channel_ids.append(ch.id)

        if not channel_ids:
            logger.info("No channels configured for daily crawl")
            return

        session = CrawlSession(
            session_name=f"Daily Crawl - {datetime.utcnow().strftime('%Y-%m-%d')}",
            session_type="scheduled",
            channel_ids=channel_ids,
            filter_keywords=[],
            max_videos=10,
            status="pending",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        enqueue_crawl(session.id, priority=1)
        logger.info(
            f"Daily crawl job enqueued session #{session.id}: {len(channel_ids)} channels"
        )

    except Exception as e:
        logger.error(f"Error in daily crawl job: {e}")
    finally:
        db.close()


def auto_summarize_job():
    """Job to automatically summarize videos without summaries"""
    from app.database import SessionLocal
    from app.models.video import Video
    from app.services.crawler_service import CrawlerService
    import asyncio

    if not settings.AUTO_SUMMARIZE:
        return

    logger.info("Starting auto-summarize job")

    db = SessionLocal()
    try:
        videos = (
            db.query(Video)
            .filter(Video.summary_text.is_(None), Video.transcript_text.isnot(None))
            .limit(10)
            .all()
        )

        if not videos:
            logger.info("No videos to summarize")
            return

        crawler_service = CrawlerService(db)
        for video in videos:
            try:
                asyncio.run(crawler_service.summarize_video(video))
            except Exception as e:
                logger.error(f"Error summarizing video {video.id}: {e}")

        logger.info(f"Auto-summarize job completed: {len(videos)} videos processed")

    except Exception as e:
        logger.error(f"Error in auto-summarize job: {e}")
    finally:
        db.close()


def generate_daily_summary_job():
    """Job to generate daily completion summary"""
    from app.database import SessionLocal
    from app.models.crawl_session import CrawlSession
    from app.models.video import Video
    from datetime import datetime, timedelta

    logger.info("Generating daily summary")

    db = SessionLocal()
    try:
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        sessions_completed = (
            db.query(CrawlSession)
            .filter(
                CrawlSession.completed_at >= start_of_day,
                CrawlSession.completed_at <= end_of_day,
                CrawlSession.status == "completed",
            )
            .count()
        )

        videos_crawled = (
            db.query(Video)
            .filter(Video.created_at >= start_of_day, Video.created_at <= end_of_day)
            .count()
        )

        videos_summarized = (
            db.query(Video)
            .filter(
                Video.summary_generated_at >= start_of_day,
                Video.summary_generated_at <= end_of_day,
            )
            .count()
        )

        summary = f"""
Daily Summary - {today.isoformat()}
================================
Sessions Completed: {sessions_completed}
Videos Crawled: {videos_crawled}
Videos Summarized: {videos_summarized}
"""

        logger.info(summary)

    except Exception as e:
        logger.error(f"Error generating daily summary: {e}")
    finally:
        db.close()
