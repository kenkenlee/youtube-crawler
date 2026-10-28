from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.schemas.category import CategorySummary


class ChannelCreate(BaseModel):
    channel_id: Optional[str] = Field(None, description="User-defined reference ID (e.g., 'tech-channel-1', 'mkbhd'). Auto-generated when omitted.")
    youtube_channel_id: Optional[str] = Field(None, description="YouTube channel ID (optional, auto-extracted)")
    channel_name: Optional[str] = Field(None, description="Channel name (auto-fetched from YouTube when omitted)")
    channel_url: str = Field(..., description="Full YouTube channel URL")
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list, description="Keywords for video filtering")
    crawl_enabled: bool = True
    crawl_frequency: str = Field(default="manual", description="daily/weekly/manual")
    category_id: Optional[str] = Field(
        None,
        description="Category numeric id or slug (for example 'hk-news'). Omitted leaves the channel uncategorized.",
    )


class ChannelCreateFromUrl(BaseModel):
    """Payload for adding a channel by URL only — reference ID and name are assigned automatically."""
    url: str = Field(..., description="YouTube channel URL (any format)")
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list, description="Keywords for video filtering")
    crawl_enabled: bool = True
    crawl_frequency: str = Field(default="manual", description="daily/weekly/manual")
    category_id: Optional[str] = Field(
        None,
        description="Category numeric id or slug (for example 'hk-news'). Omitted leaves the channel uncategorized.",
    )


class ChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    crawl_enabled: Optional[bool] = None
    crawl_frequency: Optional[str] = None
    category_id: Optional[str] = Field(
        None,
        description="Category numeric id or slug. Null clears the category.",
    )


class ChannelResponse(BaseModel):
    channel_id: str
    youtube_channel_id: Optional[str] = None
    channel_name: str
    channel_url: str
    thumbnail_url: Optional[str] = Field(None, description="Channel logo/avatar URL")
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    crawl_enabled: bool = True
    crawl_frequency: str = "manual"
    thumbnail_url: Optional[str] = None
    id: int
    category_id: Optional[int] = None
    category: Optional[CategorySummary] = None
    last_crawled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChannelWithStats(ChannelResponse):
    video_count: int = 0
    summarized_count: int = 0
