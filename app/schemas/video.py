from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoWithChannel(VideoResponse):
    channel_name: str
    channel_url: str


class VideoSummaryRequest(BaseModel):
    video_id: int
    force_regenerate: bool = False
