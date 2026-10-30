from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime


def _list_or_empty(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, str):
        import json
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    if isinstance(v, list):
        return v
    return []


class VideoBase(BaseModel):
    video_id: str = Field(..., description="YouTube video ID")
    title: str
    description: Optional[str] = None
    duration: Optional[int] = None
    published_at: Optional[datetime] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    tags: List[str] = Field(default_factory=list)
    ai_categories: List[str] = Field(default_factory=list)

    @field_validator("tags", "ai_categories", mode="before")
    @classmethod
    def coerce_list(cls, v):
        return _list_or_empty(v)


class VideoCreate(VideoBase):
    channel_id: int
    matched_keywords: List[str] = Field(default_factory=list)


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    transcript_text: Optional[str] = None
    summary_text: Optional[str] = None


class VideoResponse(VideoBase):
    id: int
    channel_id: int
    matched_keywords: List[str] = Field(default_factory=list)
    transcript_text: Optional[str] = None
    summary_text: Optional[str] = None
    summary_generated_at: Optional[datetime] = None
    detail_summary: Optional[str] = None
    detail_summary_generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("matched_keywords", mode="before")
    @classmethod
    def coerce_matched(cls, v):
        return _list_or_empty(v)

    class Config:
        from_attributes = True


class VideoWithChannel(VideoResponse):
    channel_name: str
    channel_url: str
    channel_thumbnail_url: Optional[str] = None


class VideoSummaryRequest(BaseModel):
    video_id: int
    force_regenerate: bool = False


class DetailSummaryRequest(BaseModel):
    video_id: int
    force_regenerate: bool = False


class MindMapRequest(BaseModel):
    video_id: int
    format: str = "markdown"  # "markdown" or "json"
