from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def recurring_sessions_job():
    """Check for due recurring sessions and spawn a child run for each.

    A recurring session (recurrence_hours set, recurrence_active true) re-runs
    every N hours. The session itself acts as the template; each run is a child
    session (parent_session_id pointing back) so per-run history is preserved.
    Uses a 1-minute tolerance so a run is spawned when the elapsed time since
    the last run is >= the configured interval.
    """
    from app.database import SessionLocal
    from app.models.crawl_session import CrawlSession
    from app.api.sessions import run_crawl_session

    # Skip if a previous tick is still spawning (avoid duplicate child runs)
    if getattr(scheduler, '_recurring_job_running', False):
        return
    scheduler._recurring_job_running = True
    try:
        db = SessionLocal()
        try:
            templates = db.query(CrawlSession).filter(
                CrawlSession.recurrence_hours.isnot(None),
                CrawlSession.recurrence_active.is_(True),
                CrawlSession.parent_session_id.is_(None)  # templates only, not child runs
            ).all()

            now = datetime.utcnow()
            for template in templates:
                # Don't stack runs if a previous run is still in progress
                if template.status == 'running':
                    continue

                last_run = template.completed_at or template.started_at or template.created_at
                if last_run.tzinfo is not None:
                    last_run = last_run.replace(tzinfo=None)
                if now - last_run < timedelta(hours=template.recurrence_hours) - timedelta(minutes=1):
                    continue  # Not due yet

                child = CrawlSession(
                    session_name=f"{template.session_name} (auto)",
                    session_type=template.session_type,
                    channel_ids=template.channel_ids,
                    filter_keywords=template.filter_keywords,
                    max_videos=template.max_videos,
                    parent_session_id=template.id,
                    status="pending"
                )
                db.add(child)
                db.commit()
                db.refresh(child)

                logger.info(
                    f"Recurring session '{template.session_name}' (#{template.id}) due - "
                    f"spawned run #{child.id}"
                )
                # Run in the background thread pool; the job returns quickly
                import threading
                threading.Thread(
                    target=run_crawl_session,
                    args=(child.id,),
                    daemon=True
                ).start()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in recurring sessions job: {e}")
    finally:
        scheduler._recurring_job_running = False


def start_scheduler():
    """Initialize and start the background scheduler"""
    if not settings.ENABLE_SCHEDULER:
        logger.info("Scheduler is disabled")
        return

    # Parse daily crawl time
    try:
        hour, minute = settings.DAILY_CRAWL_TIME.split(':')
        hour = int(hour)
        minute = int(minute)
    except:
        logger.error(f"Invalid DAILY_CRAWL_TIME format: {settings.DAILY_CRAWL_TIME}")
        hour, minute = 2, 0

    # Schedule daily crawl job
    scheduler.add_job(
        daily_crawl_job,
        CronTrigger(hour=hour, minute=minute),
        id='daily_crawl',
        name='Daily Channel Crawl',
        replace_existing=True
    )

    # Schedule auto-summarize job (every hour)
    scheduler.add_job(
        auto_summarize_job,
        CronTrigger(minute=0),
        id='auto_summarize',
        name='Auto Summarize Videos',
        replace_existing=True
    )

    # Schedule daily summary generation (at 23:55)
    scheduler.add_job(
        generate_daily_summary_job,
        CronTrigger(hour=23, minute=55),
        id='daily_summary',
        name='Generate Daily Summary',
        replace_existing=True
    )

    # Schedule recurring session runner (checks every minute for due sessions)
    scheduler.add_job(
        recurring_sessions_job,
        'interval',
        minutes=1,
        id='recurring_sessions',
        name='Recurring Sessions Runner',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started successfully")


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def daily_crawl_job():
    """Job to crawl all enabled channels daily"""
    from app.database import SessionLocal
    from app.models.channel import Channel
    from app.models.crawl_session import CrawlSession
    from app.services.crawler_service import CrawlerService
    import asyncio

    logger.info("Starting daily crawl job")

    db = SessionLocal()
    try:
        # Get all enabled channels
        channels = db.query(Channel).filter(
            Channel.crawl_enabled == True,
            Channel.crawl_frequency == 'daily'
        ).all()

        if not channels:
            logger.info("No channels configured for daily crawl")
            return

        # Create crawl session
        session = CrawlSession(
            session_name=f"Daily Crawl - {datetime.utcnow().strftime('%Y-%m-%d')}",
            session_type="scheduled",
            channel_ids=[c.id for c in channels],
            filter_keywords=[],
            status="pending"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Start crawling
        crawler_service = CrawlerService(db)
        asyncio.run(crawler_service.start_crawl_session(session.id))

        logger.info(f"Daily crawl job completed: {len(channels)} channels processed")

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
        # Get videos without summaries (limit to 10 per run)
        videos = db.query(Video).filter(
            Video.summary_text.is_(None),
            Video.transcript_text.isnot(None)
        ).limit(10).all()

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

        # Count completed sessions
        sessions_completed = db.query(CrawlSession).filter(
            CrawlSession.completed_at >= start_of_day,
            CrawlSession.completed_at <= end_of_day,
            CrawlSession.status == "completed"
        ).count()

        # Count videos crawled
        videos_crawled = db.query(Video).filter(
            Video.created_at >= start_of_day,
            Video.created_at <= end_of_day
        ).count()

        # Count videos summarized
        videos_summarized = db.query(Video).filter(
            Video.summary_generated_at >= start_of_day,
            Video.summary_generated_at <= end_of_day
        ).count()

        summary = f"""
Daily Summary - {today.isoformat()}
================================
Sessions Completed: {sessions_completed}
Videos Crawled: {videos_crawled}
Videos Summarized: {videos_summarized}
"""

        logger.info(summary)

        # TODO: Optionally save to database or send notification

    except Exception as e:
        logger.error(f"Error generating daily summary: {e}")
    finally:
        db.close()
