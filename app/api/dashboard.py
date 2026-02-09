from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List

from app.database import get_db
from app.models.channel import Channel
from app.models.video import Video
from app.models.crawl_session import CrawlSession
from app.schemas.dashboard import DashboardStats, DailySummary, ChannelSummary, RecentActivity

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get overall dashboard statistics"""

    # Count channels
    total_channels = db.query(Channel).count()
    active_channels = db.query(Channel).filter(Channel.crawl_enabled == True).count()

    # Count videos
    total_videos = db.query(Video).count()
    summarized_videos = db.query(Video).filter(Video.summary_text.isnot(None)).count()

    # Count sessions
    active_sessions = db.query(CrawlSession).filter(CrawlSession.status == "running").count()
    completed_sessions = db.query(CrawlSession).filter(CrawlSession.status == "completed").count()
    failed_sessions = db.query(CrawlSession).filter(CrawlSession.status == "failed").count()

    return DashboardStats(
        total_channels=total_channels,
        active_channels=active_channels,
        total_videos=total_videos,
        summarized_videos=summarized_videos,
        active_sessions=active_sessions,
        completed_sessions=completed_sessions,
        failed_sessions=failed_sessions
    )


@router.get("/daily-summary", response_model=List[DailySummary])
def get_daily_summary(days: int = 7, db: Session = Depends(get_db)):
    """Get daily completion summary for the last N days"""

    summaries = []

    for i in range(days):
        date = datetime.utcnow().date() - timedelta(days=i)
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())

        # Count sessions completed on this day
        sessions_completed = db.query(CrawlSession).filter(
            CrawlSession.completed_at >= start_of_day,
            CrawlSession.completed_at <= end_of_day,
            CrawlSession.status == "completed"
        ).count()

        # Count videos created on this day
        videos_crawled = db.query(Video).filter(
            Video.created_at >= start_of_day,
            Video.created_at <= end_of_day
        ).count()

        # Count videos summarized on this day
        videos_summarized = db.query(Video).filter(
            Video.summary_generated_at >= start_of_day,
            Video.summary_generated_at <= end_of_day
        ).count()

        # Count unique channels crawled
        channels_crawled = db.query(Channel).filter(
            Channel.last_crawled_at >= start_of_day,
            Channel.last_crawled_at <= end_of_day
        ).count()

        # Count errors
        errors = db.query(CrawlSession).filter(
            CrawlSession.completed_at >= start_of_day,
            CrawlSession.completed_at <= end_of_day
        ).with_entities(func.sum(CrawlSession.error_count)).scalar() or 0

        summaries.append(DailySummary(
            date=date.isoformat(),
            sessions_completed=sessions_completed,
            videos_crawled=videos_crawled,
            videos_summarized=videos_summarized,
            channels_crawled=channels_crawled,
            errors=int(errors)
        ))

    return summaries


@router.get("/channels-summary", response_model=List[ChannelSummary])
def get_channels_summary(limit: int = 10, db: Session = Depends(get_db)):
    """Get summary of top channels by video count"""

    channels = db.query(Channel).order_by(Channel.last_crawled_at.desc()).limit(limit).all()

    result = []
    for channel in channels:
        video_count = db.query(Video).filter(Video.channel_id == channel.id).count()
        last_crawled = channel.last_crawled_at.isoformat() if channel.last_crawled_at else "Never"

        result.append(ChannelSummary(
            channel_id=channel.id,
            channel_name=channel.channel_name,
            video_count=video_count,
            last_crawled=last_crawled
        ))

    return result


@router.get("/recent-activity", response_model=List[RecentActivity])
def get_recent_activity(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent activity feed"""

    activities = []

    # Get recent sessions
    recent_sessions = db.query(CrawlSession).order_by(CrawlSession.created_at.desc()).limit(limit).all()

    for session in recent_sessions:
        if session.status == "completed":
            description = f"Crawl session '{session.session_name}' completed: {session.videos_processed} videos processed"
        elif session.status == "running":
            description = f"Crawl session '{session.session_name}' is running"
        elif session.status == "failed":
            description = f"Crawl session '{session.session_name}' failed"
        else:
            description = f"Crawl session '{session.session_name}' {session.status}"

        activities.append(RecentActivity(
            timestamp=session.created_at,
            activity_type="session",
            description=description,
            status=session.status,
            session_id=session.id,
            channel_id=None
        ))

    # Sort by timestamp
    activities.sort(key=lambda x: x.timestamp, reverse=True)

    return activities[:limit]
