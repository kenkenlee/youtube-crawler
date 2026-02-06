from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SessionBase(BaseModel):
    session_name: str = Field(..., description="User-defined session name")
    session_type: str = Field(default="manual", description="manual/scheduled/keyword_filter")
    channel_ids: List[int] = Field(..., description="List of channel IDs to crawl")
    filter_keywords: List[str] = Field(default_factory=list, description="Keywords for filtering")


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    status: Optional[str] = None


class SessionResponse(SessionBase):
    id: int
    status: str
    total_channels: int = 0
    processed_channels: int = 0
    total_videos_found: int = 0
    videos_processed: int = 0
    videos_summarized: int = 0
    error_count: int = 0
    error_log: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionProgress(BaseModel):
    session_id: int
    status: str
    progress_percentage: float
    channels_progress: str
    videos_progress: str
    current_activity: str
    errors: int


class SessionVideoResponse(BaseModel):
    id: int
    session_id: int
    video_id: int
    processing_status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
