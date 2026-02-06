from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChannelBase(BaseModel):
    channel_id: str = Field(..., description="User-defined reference ID (e.g., 'tech-channel-1', 'mkbhd')")
    youtube_channel_id: Optional[str] = Field(None, description="YouTube channel ID (optional, auto-extracted)")
    channel_name: str = Field(..., description="Channel name")
    channel_url: str = Field(..., description="Full YouTube channel URL")
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list, description="Keywords for video filtering")
    crawl_enabled: bool = True
    crawl_frequency: str = Field(default="manual", description="daily/weekly/manual")


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    crawl_enabled: Optional[bool] = None
    crawl_frequency: Optional[str] = None


class ChannelResponse(ChannelBase):
    id: int
    last_crawled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChannelWithStats(ChannelResponse):
    video_count: int = 0
    summarized_count: int = 0
