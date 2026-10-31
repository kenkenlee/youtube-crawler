from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.channel import Channel
from app.models.video import Video
from app.schemas.channel import ChannelCreate, ChannelCreateFromUrl, ChannelUpdate, ChannelResponse, ChannelWithStats
from app.services.youtube_service import YouTubeService

router = APIRouter()


def _generate_reference_id(channel_name: str, channel_url: str) -> str:
    """Generate a unique reference ID from the channel name (or URL as fallback)"""
    import re as _re
    from sqlalchemy.orm import Session as _Session

    source = channel_name if channel_name else channel_url.rstrip('/').split('/')[-1]
    base = _re.sub(r'[^a-zA-Z0-9-_]+', '-', source).strip('-').lower() or 'channel'
    return base


def _unique_reference_id(db: Session, base: str) -> str:
    """Append a numeric suffix until the reference ID is unique"""
    candidate = base
    counter = 2
    while db.query(Channel).filter(Channel.channel_id == candidate).first():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


@router.get("/search/youtube", response_model=List[dict])
def search_youtube_channels(
    q: str = Query(..., min_length=2, description="Search keywords"),
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db)
):
    """Search YouTube for channels matching keywords. Flags which ones are already added."""
    youtube_service = YouTubeService()
    results = youtube_service.search_channels(q, max_results=limit)

    # Mark channels that are already in the database (by YouTube channel ID)
    existing_ids = {
        c.youtube_channel_id for c in db.query(Channel.youtube_channel_id).all()
        if c.youtube_channel_id
    }
    for result in results:
        result['already_added'] = result['youtube_channel_id'] in existing_ids

    return results


@router.post("/", response_model=ChannelResponse, status_code=201)
def create_channel(channel: ChannelCreate, db: Session = Depends(get_db)):
    """Create a new channel. Reference ID and channel name are auto-assigned when omitted."""
    # Resolve the YouTube channel ID from the URL when possible
    youtube_service = YouTubeService()
    youtube_channel_id = channel.youtube_channel_id
    channel_name = channel.channel_name

    if youtube_channel_id is None:
        youtube_channel_id = youtube_service.extract_channel_id(channel.channel_url)

    # Fetch channel metadata from YouTube when the name wasn't provided
    channel_info = None
    if youtube_channel_id:
        channel_info = youtube_service.get_channel_info(youtube_channel_id)

    if channel_info:
        if not channel_name:
            channel_name = channel_info['channel_name']
        canonical_url = channel_info['channel_url']
    else:
        canonical_url = channel.channel_url

    # Auto-generate the reference ID from the channel name (or URL)
    reference_id = channel.channel_id
    if not reference_id:
        reference_id = _unique_reference_id(
            db,
            _generate_reference_id(channel_name or '', canonical_url)
        )
    else:
        existing = db.query(Channel).filter(Channel.channel_id == reference_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="A channel with this reference ID already exists")

    db_channel = Channel(
        channel_id=reference_id,  # User-defined or auto-generated reference ID
        youtube_channel_id=youtube_channel_id,
        channel_name=channel_name or reference_id,
        channel_url=canonical_url,
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
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    crawl_enabled: Optional[bool] = None,
    sort_by: Optional[str] = Query(
        None,
        description="Optional sort: 'name' (A–Z) or 'added' (newest first). Omit to keep the default order.",
    ),
    db: Session = Depends(get_db)
):
    """List all channels with pagination.

    The total matching rows is returned in the ``X-Total-Count`` header.
    ``sort_by`` is optional so existing callers keep the previous order.
    """
    query = db.query(Channel)

    if crawl_enabled is not None:
        query = query.filter(Channel.crawl_enabled == crawl_enabled)

    if sort_by == "":
        sort_by = None
    if sort_by not in (None, "name", "added"):
        raise HTTPException(status_code=400, detail="sort_by must be 'name' or 'added'")

    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if sort_by == "name":
        query = query.order_by(func.lower(Channel.channel_name).asc(), Channel.id.asc())
    elif sort_by == "added":
        query = query.order_by(Channel.created_at.desc(), Channel.id.desc())

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
def create_channel_from_url(data: ChannelCreateFromUrl, db: Session = Depends(get_db)):
    """Create a channel from a YouTube URL. Reference ID and name are assigned automatically."""
    youtube_service = YouTubeService()

    # Extract channel ID from URL
    channel_id = youtube_service.extract_channel_id(data.url)
    if not channel_id:
        raise HTTPException(status_code=400, detail="Could not extract channel ID from URL. Supported formats: /channel/UCxxx, /@username, /c/name, /user/name")

    # Check if this YouTube channel has already been added
    existing = db.query(Channel).filter(
        (Channel.youtube_channel_id == channel_id) |
        (Channel.channel_url == data.url)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel already exists")

    # Get channel info
    channel_info = youtube_service.get_channel_info(channel_id)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Channel not found on YouTube")

    # Auto-generate a unique reference ID from the channel name
    reference_id = _unique_reference_id(db, _generate_reference_id(channel_info['channel_name'], data.url))

    # Create channel
    db_channel = Channel(
        channel_id=reference_id,
        youtube_channel_id=channel_id,
        channel_name=channel_info['channel_name'],
        channel_url=channel_info['channel_url'],
        description=data.description,
        keywords=data.keywords,
        thumbnail_url=channel_info.get('thumbnail', ''),
        crawl_enabled=data.crawl_enabled,
        crawl_frequency=data.crawl_frequency
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)

    return db_channel
# Force reload
