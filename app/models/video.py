from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    video_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds
    published_at = Column(DateTime, nullable=True)
    view_count = Column(BigInteger, default=0)
    like_count = Column(BigInteger, default=0)
    comment_count = Column(BigInteger, default=0)
    tags = Column(JSON, default=list)
    matched_keywords = Column(JSON, default=list)  # Keywords that matched this video
    transcript_text = Column(Text, nullable=True)
    summary_text = Column(Text, nullable=True)
    summary_generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    channel = relationship("Channel", back_populates="videos")
    session_videos = relationship("SessionVideo", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Video(id={self.id}, title='{self.title[:50]}')>"
