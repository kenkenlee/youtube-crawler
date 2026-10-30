from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.schemas.category import CategorySummary


class ChannelCreate(BaseModel):
    channel_id: Optional[str] = Field(None, description="User-defined reference ID. Auto-generated when omitted.")
    youtube_channel_id: Optional[str] = Field(None, description="YouTube channel ID (optional, auto-extracted)")
    channel_name: Optional[str] = Field(None, description="Channel name (auto-fetched from YouTube when omitted)")
    channel_url: str = Field(..., description="Full YouTube channel URL")
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list, description="Keywords for video filtering")
    crawl_enabled: bool = True
    crawl_frequency: str = Field(default="manual", description="daily/weekly/manual")
    category_id: Optional[str] = Field(
        None,
        description="Primary category numeric id or slug. Also accepted as a single-item shortcut.",
    )
    category_ids: Optional[List[str]] = Field(
        None,
        description="One or more category ids/slugs (many-to-many). Overrides category_id when set.",
    )


class ChannelCreateFromUrl(BaseModel):
    """Payload for adding a channel by URL only — reference ID and name are assigned automatically."""
    url: str = Field(..., description="YouTube channel URL (any format)")
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list, description="Keywords for video filtering")
    crawl_enabled: bool = True
    crawl_frequency: str = Field(default="manual", description="daily/weekly/manual")
    category_id: Optional[str] = Field(None, description="Primary category id or slug")
    category_ids: Optional[List[str]] = Field(
        None,
        description="One or more category ids/slugs (many-to-many).",
    )


class ChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    crawl_enabled: Optional[bool] = None
    crawl_frequency: Optional[str] = None
    category_id: Optional[str] = Field(
        None,
        description="Set primary category (replaces all assignments with this one). Null clears all.",
    )
    category_ids: Optional[List[str]] = Field(
        None,
        description="Replace all category assignments with this list (many-to-many). Empty list clears.",
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
    id: int
    category_id: Optional[int] = None
    category: Optional[CategorySummary] = None
    categories: List[CategorySummary] = Field(default_factory=list)
    last_crawled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChannelWithStats(ChannelResponse):
    video_count: int = 0
    summarized_count: int = 0


class CategorySuggestRequest(BaseModel):
    """Inputs for auto-detect category suggestions (soft; never required to add)."""

    channel_name: Optional[str] = Field(None, description="Channel title / display name")
    description: Optional[str] = Field(None, description="Optional channel description")
    youtube_channel_id: Optional[str] = Field(None, description="YouTube UC… id if known")
    url: Optional[str] = Field(None, description="Optional URL (unused for matching; for context)")
    limit: int = Field(5, ge=1, le=20)


class CategorySuggestItem(BaseModel):
    id: int
    slug: str
    name_zh: str
    name_en: str
    reason: str = ""
    score: float = 0.0


class CategorySuggestResponse(BaseModel):
    suggestions: List[CategorySuggestItem] = Field(default_factory=list)
    category_ids: List[int] = Field(default_factory=list)
    methods: List[str] = Field(default_factory=list)
    input: dict = Field(default_factory=dict)


class ChannelPreviewRequest(BaseModel):
    """Resolve a YouTube URL / UC id / @handle for the Add channel modal."""

    url: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    channel_name: Optional[str] = Field(
        None,
        description="Optional display name when YouTube lookup fails (quota).",
    )


class ChannelPreviewResponse(BaseModel):
    youtube_channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    already_added: bool = False
    existing_channel_id: Optional[int] = None
    existing_categories: List[CategorySummary] = Field(default_factory=list)
    resolved_via: str = Field(
        "unknown",
        description="youtube_api | url_uc_id | provided | existing_db | partial",
    )
    warning: Optional[str] = None
    suggestions: List[CategorySuggestItem] = Field(default_factory=list)
    suggested_category_ids: List[int] = Field(default_factory=list)


class ChannelAddWithCategories(BaseModel):
    """Page-level Add channel: create or reuse, then set M2M categories."""

    url: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    channel_id: Optional[int] = Field(
        None, description="Existing crawler channel primary key to re-categorize"
    )
    channel_name: Optional[str] = Field(
        None,
        description="Fallback name when YouTube API fails (quota) and channel is new",
    )
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    crawl_enabled: bool = True
    crawl_frequency: str = Field(default="manual", description="daily/weekly/manual")
    category_ids: List[str] = Field(
        default_factory=list,
        description="Final category ids/slugs after admin confirm (may be empty)",
    )
