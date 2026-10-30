from pydantic import BaseModel, Field
from typing import Optional, List


class CategorySummary(BaseModel):
    """Compact category payload embedded on channel responses."""

    id: int
    slug: str
    name_zh: str
    name_en: str

    class Config:
        from_attributes = True


class CategoryResponse(CategorySummary):
    sort_order: int


class CategoryWithCount(CategoryResponse):
    channel_count: int = Field(0, description="Channels currently assigned to this category")


class CategoryCreate(BaseModel):
    """Create a category. Slug is optional; generated from name_en / name_zh when omitted."""

    slug: Optional[str] = Field(
        None,
        description="Stable id used by botalk sync (e.g. 'hk-news'). Auto-generated when omitted.",
        max_length=64,
    )
    name_zh: str = Field(..., min_length=1, max_length=200)
    name_en: str = Field(..., min_length=1, max_length=200)
    sort_order: Optional[int] = Field(
        None,
        description="Display order. Defaults to (max existing + 1).",
    )


class CategoryUpdate(BaseModel):
    """Partial update. Slug changes affect the botalk sync id."""

    slug: Optional[str] = Field(None, max_length=64)
    name_zh: Optional[str] = Field(None, min_length=1, max_length=200)
    name_en: Optional[str] = Field(None, min_length=1, max_length=200)
    sort_order: Optional[int] = None


class CategoryChannelAssign(BaseModel):
    """Assign or unassign a list of channel primary keys to/from a category."""

    channel_ids: List[int] = Field(..., min_length=1, description="Channel integer primary keys")


class CategoryChannelAdd(BaseModel):
    """Add one channel to a category: existing id, or new YouTube URL / channel id.

    Provide exactly one of ``channel_id``, ``url``, or ``youtube_channel_id``.
    If the YouTube channel already exists in the crawler DB, it is assigned
    (not duplicated). New channels get an auto reference id (slug-friendly)
    for botalk sync.
    """

    channel_id: Optional[int] = Field(
        None, description="Existing crawler channel primary key to assign"
    )
    url: Optional[str] = Field(
        None, description="YouTube channel URL to create-or-assign"
    )
    youtube_channel_id: Optional[str] = Field(
        None, description="YouTube UC… id to create-or-assign"
    )
    crawl_enabled: bool = True
    crawl_frequency: str = Field("manual", description="manual | daily | weekly")
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
