from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class CrawlSession(Base):
    __tablename__ = "crawl_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_name = Column(String(500), nullable=False)
    session_type = Column(String(50), default="manual")  # manual/scheduled/keyword_filter
    status = Column(String(50), default="pending", index=True)  # pending/running/completed/failed/cancelled
    channel_ids = Column(JSON, default=list)  # List of channel IDs to crawl
    filter_keywords = Column(JSON, default=list)  # Keywords for filtering
    max_videos = Column(Integer, default=5)  # Max videos to fetch per channel in this session
    # Recurrence (feature 10): if set, the scheduler re-runs this session every
    # N hours by spawning child sessions. NULL = one-off session.
    recurrence_hours = Column(Integer, nullable=True)  # 1-720 hours, NULL = one-off
    recurrence_active = Column(Boolean, default=True)  # False = recurrence stopped
    parent_session_id = Column(Integer, ForeignKey("crawl_sessions.id"), nullable=True, index=True)
    total_channels = Column(Integer, default=0)
    processed_channels = Column(Integer, default=0)
    total_videos_found = Column(Integer, default=0)
    videos_processed = Column(Integer, default=0)
    videos_summarized = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    session_videos = relationship("SessionVideo", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CrawlSession(id={self.id}, name='{self.session_name}', status='{self.status}')>"


class SessionVideo(Base):
    """Many-to-many relationship between sessions and videos with processing status"""
    __tablename__ = "session_videos"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("crawl_sessions.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    processing_status = Column(String(50), default="pending")  # pending/processed/summarized/failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    session = relationship("CrawlSession", back_populates="session_videos")
    video = relationship("Video", back_populates="session_videos")

    def __repr__(self):
        return f"<SessionVideo(session_id={self.session_id}, video_id={self.video_id}, status='{self.processing_status}')>"
