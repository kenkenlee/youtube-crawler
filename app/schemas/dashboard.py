from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime


class DashboardStats(BaseModel):
    total_channels: int
    active_channels: int
    total_videos: int
    summarized_videos: int
    active_sessions: int
    completed_sessions: int
    failed_sessions: int


class DailySummary(BaseModel):
    date: str
    sessions_completed: int
    videos_crawled: int
    videos_summarized: int
    channels_crawled: int
    errors: int


class ChannelSummary(BaseModel):
    channel_id: int
    channel_name: str
    video_count: int
    last_crawled: str


class RecentActivity(BaseModel):
    timestamp: datetime
    activity_type: str
    description: str
    status: str
