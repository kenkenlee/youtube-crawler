from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


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
