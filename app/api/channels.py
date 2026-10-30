from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.association import channel_categories
from app.models.channel import Channel
from app.models.video import Video
from app.schemas.category import CategorySummary
from app.schemas.channel import (
    ChannelCreate,
    ChannelCreateFromUrl,
    ChannelUpdate,
    ChannelResponse,
    ChannelWithStats,
    CategorySuggestRequest,
    CategorySuggestResponse,
    ChannelPreviewRequest,
    ChannelPreviewResponse,
    ChannelAddWithCategories,
    CategorySuggestItem,
)
from app.services.admin_auth import require_admin
from app.services.channel_catalog import get_category
from app.services.category_assign import resolve_category_ids, set_channel_categories
from app.services.category_suggest import suggest_categories
from app.services.youtube_service import YouTubeService

router = APIRouter()


def _generate_reference_id(channel_name: str, channel_url: str) -> str:
    """Generate a unique reference ID from the channel name (or URL as fallback)"""
    import re as _re

    source = channel_name if channel_name else channel_url.rstrip('/').split('/')[-1]
    base = _re.sub(r'[^a-zA-Z0-9-_]+', '-', source).strip('-').lower() or 'channel'
    return base


def _categories_for_create(db: Session, category_ids, category_id) -> list:
    """Prefer category_ids (M2M); fall back to single category_id."""
    if category_ids is not None:
        return resolve_category_ids(db, category_ids)
    if category_id is not None and str(category_id).strip() != "":
        return resolve_category_ids(db, [category_id])
    return []


def channel_with_stats(db: Session, channel: Channel) -> ChannelWithStats:
    """Channel payload including primary + all categories and video counts."""
    video_count = db.query(Video).filter(Video.channel_id == channel.id).count()
    summarized_count = db.query(Video).filter(
        Video.channel_id == channel.id,
        Video.summary_text.isnot(None)
    ).count()
    cats = sorted(list(channel.categories or []), key=lambda c: (c.sort_order, c.id))
    summaries = [CategorySummary.model_validate(c) for c in cats]
    primary = None
    if channel.category is not None:
        primary = CategorySummary.model_validate(channel.category)
    elif summaries:
        primary = summaries[0]
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
        category_id=channel.category_id or (primary.id if primary else None),
        category=primary,
        categories=summaries,
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


def _load_channel(db: Session, channel_id: int) -> Channel:
    channel = (
        db.query(Channel)
        .options(joinedload(Channel.category), joinedload(Channel.categories))
        .filter(Channel.id == channel_id)
        .first()
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.get("/search/youtube", response_model=List[dict])
def search_youtube_channels(
    q: str = Query(..., min_length=2, description="Search keywords"),
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db)
):
    """Search YouTube for channels matching keywords. Flags which ones are already added."""
    youtube_service = YouTubeService()
    results = youtube_service.search_channels(q, max_results=limit)

    existing_ids = {
        c.youtube_channel_id for c in db.query(Channel.youtube_channel_id).all()
        if c.youtube_channel_id
    }
    for result in results:
        result['already_added'] = result['youtube_channel_id'] in existing_ids

    return results


@router.post("/suggest-categories", response_model=CategorySuggestResponse)
def suggest_channel_categories(payload: CategorySuggestRequest, db: Session = Depends(get_db)):
    """Auto-detect category suggestions for a channel (soft; empty OK)."""
    result = suggest_categories(
        db,
        channel_name=payload.channel_name,
        description=payload.description,
        youtube_channel_id=payload.youtube_channel_id,
        limit=payload.limit,
    )
    return CategorySuggestResponse(**result)


def _preview_existing(db: Session, yt_id: Optional[str], url: Optional[str]):
    existing = None
    if yt_id:
        existing = (
            db.query(Channel)
            .options(joinedload(Channel.categories), joinedload(Channel.category))
            .filter(Channel.youtube_channel_id == yt_id)
            .first()
        )
    if existing is None and url:
        existing = (
            db.query(Channel)
            .options(joinedload(Channel.categories), joinedload(Channel.category))
            .filter(Channel.channel_url == url)
            .first()
        )
    return existing


@router.post("/preview", response_model=ChannelPreviewResponse)
def preview_channel(payload: ChannelPreviewRequest, db: Session = Depends(get_db)):
    """Resolve YouTube channel for Add-channel UI; includes category suggestions.

    When YouTube Data API is unavailable (quotaExceeded / IP), still returns a
    partial preview for bare UC… ids so the admin can confirm with a fallback name.
    """
    youtube_service = YouTubeService()
    raw_url = (payload.url or "").strip() or None
    yt_id = (payload.youtube_channel_id or "").strip() or None
    warning = None
    resolved_via = "partial"
    channel_info = None

    if not yt_id and raw_url:
        # Prefer local UC extract without API when possible
        import re as _re
        m = _re.search(r'youtube\.com/channel/(UC[\w-]+)', raw_url) or _re.match(r'^(UC[\w-]+)$', raw_url)
        if m:
            yt_id = m.group(1)
            resolved_via = "url_uc_id"
        else:
            try:
                yt_id = youtube_service.extract_channel_id(raw_url)
                if yt_id:
                    resolved_via = "youtube_api"
            except Exception as exc:  # noqa: BLE001
                warning = f"Could not resolve URL via YouTube API: {exc}"

    if yt_id:
        try:
            channel_info = youtube_service.get_channel_info(yt_id)
            if channel_info:
                resolved_via = "youtube_api"
        except Exception as exc:  # noqa: BLE001
            warning = (warning + "; " if warning else "") + f"YouTube lookup failed: {exc}"

    name = None
    url = None
    thumb = None
    desc = None
    if channel_info:
        name = channel_info.get("channel_name")
        url = channel_info.get("channel_url")
        thumb = channel_info.get("thumbnail") or ""
        desc = channel_info.get("description") or ""
    if not name and payload.channel_name:
        name = payload.channel_name.strip()
        resolved_via = resolved_via if resolved_via != "partial" else "provided"
    if not url and yt_id:
        url = f"https://www.youtube.com/channel/{yt_id}"
    elif not url and raw_url:
        url = raw_url

    if not yt_id and not name and not url:
        raise HTTPException(
            status_code=400,
            detail="Provide a YouTube URL, UC… channel id, or @handle. "
            "If search/API quota is exhausted, paste a /channel/UCxxx URL or UC id.",
        )

    existing = _preview_existing(db, yt_id, url)
    existing_cats = []
    if existing is not None:
        existing_cats = [CategorySummary.model_validate(c) for c in (existing.categories or [])]
        if not name:
            name = existing.channel_name
        if not thumb:
            thumb = existing.thumbnail_url
        if not yt_id:
            yt_id = existing.youtube_channel_id
        if not url:
            url = existing.channel_url
        resolved_via = "existing_db"

    if not channel_info and yt_id and not warning:
        warning = (
            "YouTube metadata unavailable (quota or API error). "
            "You can still add with this UC id; set a display name if needed."
        )

    suggest = suggest_categories(
        db,
        channel_name=name,
        description=desc or payload.channel_name,
        youtube_channel_id=yt_id,
        limit=5,
    )
    items = [CategorySuggestItem(**s) for s in suggest["suggestions"]]

    return ChannelPreviewResponse(
        youtube_channel_id=yt_id,
        channel_name=name,
        channel_url=url,
        thumbnail_url=thumb,
        description=desc,
        already_added=existing is not None,
        existing_channel_id=existing.id if existing else None,
        existing_categories=existing_cats,
        resolved_via=resolved_via,
        warning=warning,
        suggestions=items,
        suggested_category_ids=list(suggest["category_ids"]),
    )


@router.post("/add-with-categories", response_model=ChannelWithStats, status_code=201)
def add_channel_with_categories(
    payload: ChannelAddWithCategories,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create or reuse a channel and set its M2M categories (admin).

    Designed for the page-level Add channel modal: admin confirms category
    checkboxes after auto-detect. If the YouTube channel already exists, categories
    are replaced with the confirmed set (set_channel_categories).
    """
    require_admin(request)
    cats = resolve_category_ids(db, payload.category_ids or [])
    youtube_service = YouTubeService()

    # --- Existing crawler PK ---
    if payload.channel_id is not None:
        channel = _load_channel(db, payload.channel_id)
        set_channel_categories(db, channel, cats)
        if payload.crawl_enabled is not None:
            channel.crawl_enabled = bool(payload.crawl_enabled)
        if payload.crawl_frequency:
            channel.crawl_frequency = payload.crawl_frequency
        channel.updated_at = datetime.utcnow()
        db.commit()
        return channel_with_stats(db, _load_channel(db, channel.id))

    raw_url = (payload.url or "").strip() or None
    yt_id = (payload.youtube_channel_id or "").strip() or None
    if not yt_id and raw_url:
        import re as _re
        m = _re.search(r'youtube\.com/channel/(UC[\w-]+)', raw_url) or _re.match(r'^(UC[\w-]+)$', raw_url)
        if m:
            yt_id = m.group(1)
        else:
            yt_id = youtube_service.extract_channel_id(raw_url)

    if not yt_id and not raw_url:
        raise HTTPException(
            status_code=400,
            detail="Provide url, youtube_channel_id, or channel_id",
        )

    existing = _preview_existing(db, yt_id, raw_url)
    if existing is not None:
        set_channel_categories(db, existing, cats)
        existing.crawl_enabled = bool(payload.crawl_enabled)
        existing.crawl_frequency = payload.crawl_frequency or existing.crawl_frequency or "manual"
        if payload.description is not None:
            existing.description = payload.description
        existing.updated_at = datetime.utcnow()
        db.commit()
        return channel_with_stats(db, _load_channel(db, existing.id))

    if not yt_id:
        raise HTTPException(
            status_code=400,
            detail="Could not extract channel ID from URL. Use /channel/UCxxx, UC… id, or @handle.",
        )

    channel_info = None
    try:
        channel_info = youtube_service.get_channel_info(yt_id)
    except Exception:
        channel_info = None

    channel_name = (
        (channel_info or {}).get("channel_name")
        or (payload.channel_name or "").strip()
        or yt_id
    )
    channel_url = (
        (channel_info or {}).get("channel_url")
        or raw_url
        or f"https://www.youtube.com/channel/{yt_id}"
    )
    thumbnail = (channel_info or {}).get("thumbnail") or ""

    if not channel_info and not (payload.channel_name or "").strip():
        # Allow bare UC add, but warn via name fallback to yt_id
        pass

    reference_id = _unique_reference_id(
        db, _generate_reference_id(channel_name, channel_url)
    )
    db_channel = Channel(
        channel_id=reference_id,
        youtube_channel_id=yt_id,
        channel_name=channel_name,
        channel_url=channel_url,
        description=payload.description,
        keywords=payload.keywords or [],
        thumbnail_url=thumbnail,
        crawl_enabled=bool(payload.crawl_enabled),
        crawl_frequency=payload.crawl_frequency or "manual",
    )
    db.add(db_channel)
    db.flush()
    set_channel_categories(db, db_channel, cats)
    db.commit()
    return channel_with_stats(db, _load_channel(db, db_channel.id))


@router.post("/", response_model=ChannelWithStats, status_code=201)
def create_channel(channel: ChannelCreate, db: Session = Depends(get_db)):
    """Create a new channel. Reference ID and channel name are auto-assigned when omitted."""
    cats = _categories_for_create(db, channel.category_ids, channel.category_id)
    youtube_service = YouTubeService()
    youtube_channel_id = channel.youtube_channel_id
    channel_name = channel.channel_name

    if youtube_channel_id is None:
        youtube_channel_id = youtube_service.extract_channel_id(channel.channel_url)

    channel_info = None
    if youtube_channel_id:
        channel_info = youtube_service.get_channel_info(youtube_channel_id)

    if channel_info:
        if not channel_name:
            channel_name = channel_info['channel_name']
        canonical_url = channel_info['channel_url']
    else:
        canonical_url = channel.channel_url

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
        channel_id=reference_id,
        youtube_channel_id=youtube_channel_id,
        channel_name=channel_name or reference_id,
        channel_url=canonical_url,
        description=channel.description,
        keywords=channel.keywords,
        crawl_enabled=channel.crawl_enabled,
        crawl_frequency=channel.crawl_frequency,
    )
    db.add(db_channel)
    db.flush()
    set_channel_categories(db, db_channel, cats)
    db.commit()
    return channel_with_stats(db, _load_channel(db, db_channel.id))


@router.get("/", response_model=List[ChannelWithStats])
def list_channels(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    crawl_enabled: Optional[bool] = None,
    category_id: Optional[str] = Query(None, description="Category numeric id or slug (M2M membership)"),
    db: Session = Depends(get_db)
):
    """List all channels with pagination"""
    query = db.query(Channel).options(joinedload(Channel.category), joinedload(Channel.categories))

    if crawl_enabled is not None:
        query = query.filter(Channel.crawl_enabled == crawl_enabled)

    if category_id is not None and str(category_id).strip() != "":
        category = get_category(db, category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        query = (
            query.join(channel_categories, channel_categories.c.channel_id == Channel.id)
            .filter(channel_categories.c.category_id == category.id)
        )

    channels = query.order_by(Channel.id.asc()).offset(skip).limit(limit).all()
    return [channel_with_stats(db, channel) for channel in channels]


@router.get("/{channel_id}", response_model=ChannelWithStats)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    """Get a specific channel by ID"""
    return channel_with_stats(db, _load_channel(db, channel_id))


@router.put("/{channel_id}", response_model=ChannelWithStats)
def update_channel(channel_id: int, channel_update: ChannelUpdate, db: Session = Depends(get_db)):
    """Update a channel. Use category_ids for many-to-many replace; category_id sets a single primary."""
    channel = _load_channel(db, channel_id)

    update_data = channel_update.model_dump(exclude_unset=True)
    cats_set = False
    if "category_ids" in update_data:
        raw = update_data.pop("category_ids")
        set_channel_categories(db, channel, resolve_category_ids(db, raw or []))
        cats_set = True
        update_data.pop("category_id", None)
    elif "category_id" in update_data:
        raw = update_data.pop("category_id")
        if raw is None or str(raw).strip() == "":
            set_channel_categories(db, channel, [])
        else:
            set_channel_categories(db, channel, resolve_category_ids(db, [raw]))
        cats_set = True

    for field, value in update_data.items():
        setattr(channel, field, value)

    channel.updated_at = datetime.utcnow()
    db.commit()
    return channel_with_stats(db, _load_channel(db, channel_id))


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


@router.post("/from-url", response_model=ChannelWithStats, status_code=201)
def create_channel_from_url(data: ChannelCreateFromUrl, db: Session = Depends(get_db)):
    """Create a channel from a YouTube URL. Reference ID and name are assigned automatically."""
    cats = _categories_for_create(db, data.category_ids, data.category_id)
    youtube_service = YouTubeService()

    channel_id = youtube_service.extract_channel_id(data.url)
    if not channel_id:
        raise HTTPException(
            status_code=400,
            detail="Could not extract channel ID from URL. Supported formats: /channel/UCxxx, /@username, /c/name, /user/name",
        )

    existing = db.query(Channel).filter(
        (Channel.youtube_channel_id == channel_id) | (Channel.channel_url == data.url)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel already exists")

    channel_info = youtube_service.get_channel_info(channel_id)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Channel not found on YouTube")

    reference_id = _unique_reference_id(db, _generate_reference_id(channel_info['channel_name'], data.url))

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
    )
    db.add(db_channel)
    db.flush()
    set_channel_categories(db, db_channel, cats)
    db.commit()
    return channel_with_stats(db, _load_channel(db, db_channel.id))
