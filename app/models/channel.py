from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.association import channel_categories


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String(255), unique=True, nullable=False, index=True)
    youtube_channel_id = Column(String(255), nullable=True)
    channel_name = Column(String(500), nullable=False)
    channel_url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    keywords = Column(JSON, default=list)
    crawl_enabled = Column(Boolean, default=True)
    crawl_frequency = Column(String(50), default="manual")
    # Primary category (lowest sort_order among assigned). Kept for botalk sync
    # which still reads a single category.slug / category_id.
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    last_crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    category = relationship("Category", foreign_keys=[category_id])
    categories = relationship(
        "Category",
        secondary=channel_categories,
        back_populates="channels",
    )
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Channel(id={self.id}, name='{self.channel_name}')>"
