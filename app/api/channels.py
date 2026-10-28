from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.channel import Channel
from app.models.video import Video
from app.schemas.category import CategorySummary
from app.schemas.channel import ChannelCreate, ChannelCreateFromUrl, ChannelUpdate, ChannelResponse, ChannelWithStats
from app.services.channel_catalog import get_category
from app.services.youtube_service import YouTubeService

router = APIRouter()


def _generate_reference_id(channel_name: str, channel_url: str) -> str:
    """Generate a unique reference ID from the channel name (or URL as fallback)"""
    import re as _re
    from sqlalchemy.orm import Session as _Session

    source = channel_name if channel_name else channel_url.rstrip('/').split('/')[-1]
    base = _re.sub(r'[^a-zA-Z0-9-_]+', '-', source).strip('-').lower() or 'channel'
    return base


def _resolve_category_id(db: Session, raw: Optional[str]) -> Optional[int]:
    """Map a slug or numeric id to categories.id. Unknown values are a 400."""
    if raw is None or str(raw).strip() == "":
        return None
    category = get_category(db, str(raw))
    if category is None:
        raise HTTPException(status_code=400, detail=f"Unknown category: {raw}")
    return category.id


def channel_with_stats(db: Session, channel: Channel) -> ChannelWithStats:
    """Channel payload including category summary and video counts."""
    video_count = db.query(Video).filter(Video.channel_id == channel.id).count()
    summarized_count = db.query(Video).filter(
        Video.channel_id == channel.id,
        Video.summary_text.isnot(None)
    ).count()
    category = None
    if channel.category is not None:
        category = CategorySummary.model_validate(channel.category)
    return ChannelWithStats(
        id=channel.id,
        channel_id=channel.channel_id,
        youtube_channel_id=channel.youtube_channel_id,
        channel_name=channel.channel_name,
        channel_url=channel.channel_url,
        thumbnail_url=channel.thumbnail_url,
        description=channel.description,
        keywords=channel.keywords or [],
        crawl_enabled=bool(channel.crawl_enabled),
        crawl_frequency=channel.crawl_frequency or "manual",
        category_id=channel.category_id,
        category=category,
        last_crawled_at=channel.last_crawled_at,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        video_count=video_count,
        summarized_count=summarized_count,
    )


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
    category_fk = _resolve_category_id(db, channel.category_id)
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
        crawl_frequency=channel.crawl_frequency,
        category_id=category_fk,
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)

    return db_channel


@router.get("/", response_model=List[ChannelWithStats])
def list_channels(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    crawl_enabled: Optional[bool] = None,
    category_id: Optional[str] = Query(None, description="Category numeric id or slug"),
    db: Session = Depends(get_db)
):
    """List all channels with pagination"""
    query = db.query(Channel).options(joinedload(Channel.category))

    if crawl_enabled is not None:
        query = query.filter(Channel.crawl_enabled == crawl_enabled)

    if category_id is not None and str(category_id).strip() != "":
        category = get_category(db, category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        query = query.filter(Channel.category_id == category.id)

    channels = query.order_by(Channel.id.asc()).offset(skip).limit(limit).all()
    return [channel_with_stats(db, channel) for channel in channels]


@router.get("/{channel_id}", response_model=ChannelWithStats)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    """Get a specific channel by ID"""
    channel = (
        db.query(Channel)
        .options(joinedload(Channel.category))
        .filter(Channel.id == channel_id)
        .first()
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return channel_with_stats(db, channel)


@router.put("/{channel_id}", response_model=ChannelResponse)
def update_channel(channel_id: int, channel_update: ChannelUpdate, db: Session = Depends(get_db)):
    """Update a channel"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Update fields
    update_data = channel_update.dict(exclude_unset=True)
    if "category_id" in update_data:
        channel.category_id = _resolve_category_id(db, update_data.pop("category_id"))
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
    category_fk = _resolve_category_id(db, data.category_id)
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
        crawl_frequency=data.crawl_frequency,
        category_id=category_fk,
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)

    return db_channel
# Force reload
