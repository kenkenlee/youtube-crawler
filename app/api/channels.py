from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.channel import Channel
from app.models.video import Video
from app.schemas.channel import ChannelCreate, ChannelUpdate, ChannelResponse, ChannelWithStats
from app.services.youtube_service import YouTubeService

router = APIRouter()


@router.post("/", response_model=ChannelResponse, status_code=201)
def create_channel(channel: ChannelCreate, db: Session = Depends(get_db)):
    """Create a new channel with user-defined reference ID"""
    # Check if channel already exists (by user's reference ID)
    existing = db.query(Channel).filter(Channel.channel_id == channel.channel_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="A channel with this reference ID already exists")

    # Create channel with user's data (no validation needed)
    # YouTube channel ID will be extracted during first crawl
    db_channel = Channel(
        channel_id=channel.channel_id,  # User-defined reference ID
        youtube_channel_id=None,  # Will be extracted during crawl
        channel_name=channel.channel_name,
        channel_url=channel.channel_url,
        description=channel.description,
        keywords=channel.keywords,
        crawl_enabled=channel.crawl_enabled,
        crawl_frequency=channel.crawl_frequency
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)

    return db_channel


@router.get("/", response_model=List[ChannelWithStats])
def list_channels(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    crawl_enabled: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all channels with pagination"""
    query = db.query(Channel)

    if crawl_enabled is not None:
        query = query.filter(Channel.crawl_enabled == crawl_enabled)

    channels = query.offset(skip).limit(limit).all()

    # Add video counts
    result = []
    for channel in channels:
        video_count = db.query(Video).filter(Video.channel_id == channel.id).count()
        summarized_count = db.query(Video).filter(
            Video.channel_id == channel.id,
            Video.summary_text.isnot(None)
        ).count()

        channel_dict = {
            **channel.__dict__,
            'video_count': video_count,
            'summarized_count': summarized_count
        }
        result.append(ChannelWithStats(**channel_dict))

    return result


@router.get("/{channel_id}", response_model=ChannelWithStats)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    """Get a specific channel by ID"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Add video counts
    video_count = db.query(Video).filter(Video.channel_id == channel.id).count()
    summarized_count = db.query(Video).filter(
        Video.channel_id == channel.id,
        Video.summary_text.isnot(None)
    ).count()

    channel_dict = {
        **channel.__dict__,
        'video_count': video_count,
        'summarized_count': summarized_count
    }

    return ChannelWithStats(**channel_dict)


@router.put("/{channel_id}", response_model=ChannelResponse)
def update_channel(channel_id: int, channel_update: ChannelUpdate, db: Session = Depends(get_db)):
    """Update a channel"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Update fields
    update_data = channel_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)

    channel.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(channel)

    return channel


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    """Delete a channel"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    db.delete(channel)
    db.commit()

    return None


@router.get("/{channel_id}/videos", response_model=List[dict])
def get_channel_videos(
    channel_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get videos for a specific channel"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    videos = db.query(Video).filter(Video.channel_id == channel_id).offset(skip).limit(limit).all()

    return [
        {
            'id': v.id,
            'video_id': v.video_id,
            'title': v.title,
            'duration': v.duration,
            'published_at': v.published_at,
            'view_count': v.view_count,
            'has_summary': v.summary_text is not None,
            'matched_keywords': v.matched_keywords
        }
        for v in videos
    ]


@router.post("/from-url", response_model=ChannelResponse, status_code=201)
def create_channel_from_url(data: dict, db: Session = Depends(get_db)):
    """Create a channel from a YouTube URL"""
    url = data.get('url')
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    youtube_service = YouTubeService()

    # Extract channel ID from URL
    channel_id = youtube_service.extract_channel_id(url)
    if not channel_id:
        raise HTTPException(status_code=400, detail="Could not extract channel ID from URL. Supported formats: /channel/UCxxx, /@username, /c/name, /user/name")

    # Check if channel already exists
    existing = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel already exists")

    # Get channel info
    channel_info = youtube_service.get_channel_info(channel_id)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Channel not found on YouTube")

    # Create channel
    db_channel = Channel(
        channel_id=channel_id,
        channel_name=channel_info['channel_name'],
        channel_url=channel_info['channel_url'],
        description=channel_info.get('description', ''),
        keywords=[],
        crawl_enabled=True,
        crawl_frequency='manual'
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)

    return db_channel
# Force reload
