from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String(255), unique=True, nullable=False, index=True)  # User-defined reference ID
    youtube_channel_id = Column(String(255), nullable=True)  # Actual YouTube channel ID (optional)
    channel_name = Column(String(500), nullable=False)
    channel_url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)  # Channel icon/avatar URL
    keywords = Column(JSON, default=list)  # List of keywords for filtering
    crawl_enabled = Column(Boolean, default=True)
    crawl_frequency = Column(String(50), default="manual")  # daily/weekly/manual
    last_crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Channel(id={self.id}, name='{self.channel_name}')>"
