from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class YouTubeApiUsageDaily(Base):
    """Per-day, per-method YouTube Data API call counters.

    ``quota_date`` is the Google YouTube Data API quota day in America/Los_Angeles
    (Pacific Time). Quota resets at midnight Pacific Time.
    """

    __tablename__ = "youtube_api_usage_daily"
    __table_args__ = (
        UniqueConstraint("quota_date", "method", name="uq_yt_api_usage_day_method"),
    )

    id = Column(Integer, primary_key=True, index=True)
    quota_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD (PT)
    method = Column(String(64), nullable=False)  # e.g. channels.list
    call_count = Column(Integer, nullable=False, default=0)
    units = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<YouTubeApiUsageDaily(date={self.quota_date}, "
            f"method={self.method}, calls={self.call_count}, units={self.units})>"
        )
