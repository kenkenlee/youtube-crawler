from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import re
import hashlib
import unicodedata

from app.api.channels import channel_with_stats
from app.database import get_db
from app.models.association import channel_categories
from app.models.category import Category
from app.models.channel import Channel
from app.schemas.category import (
    CategoryWithCount,
    CategoryCreate,
    CategoryUpdate,
    CategoryChannelAssign,
    CategoryChannelAdd,
)
from app.schemas.channel import ChannelWithStats
from app.services.admin_auth import require_admin
from app.services.category_assign import (
    resolve_category_ids,
    add_channel_categories,
    remove_channel_categories,
    set_channel_categories,
)
from app.services.channel_catalog import get_category

router = APIRouter()

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip().lower()
    ascii_slug = _SLUG_RE.sub("-", text).strip("-")
    if ascii_slug:
        return ascii_slug[:64]
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return "category"
    digest = hashlib.md5(compact.encode("utf-8")).hexdigest()[:8]
    return f"category-{digest}"[:64]


def _unique_slug(db: Session, base: str, *, exclude_id: Optional[int] = None) -> str:
    candidate = (base or "category")[:64]
    counter = 2
    while True:
        query = db.query(Category).filter(Category.slug == candidate)
        if exclude_id is not None:
            query = query.filter(Category.id != exclude_id)
        if query.first() is None:
            return candidate
        suffix = f"-{counter}"
        candidate = f"{base[: 64 - len(suffix)]}{suffix}"
        counter += 1


def _category_with_count(db: Session, category: Category) -> CategoryWithCount:
    count = (
        db.query(func.count())
        .select_from(channel_categories)
        .filter(channel_categories.c.category_id == category.id)
        .scalar()
        or 0
    )
    return CategoryWithCount(
        id=category.id,
        slug=category.slug,
        name_zh=category.name_zh,
        name_en=category.name_en,
        sort_order=category.sort_order,
        channel_count=int(count),
    )


@router.get("/", response_model=List[CategoryWithCount])
def list_categories(db: Session = Depends(get_db)):
    """List categories in catalog order, with channel counts (many-to-many)."""
    count_sq = (
        db.query(
            channel_categories.c.category_id.label("category_id"),
            func.count(channel_categories.c.channel_id).label("channel_count"),
        )
        .group_by(channel_categories.c.category_id)
        .subquery()
    )
    rows = (
        db.query(Category, func.coalesce(count_sq.c.channel_count, 0))
        .outerjoin(count_sq, count_sq.c.category_id == Category.id)
        .order_by(Category.sort_order.asc(), Category.id.asc())
        .all()
    )
    return [
        CategoryWithCount(
            id=category.id,
            slug=category.slug,
            name_zh=category.name_zh,
            name_en=category.name_en,
            sort_order=category.sort_order,
            channel_count=int(count),
        )
        for category, count in rows
    ]


@router.get("/uncategorized/channels", response_model=List[ChannelWithStats])
def list_uncategorized_channels(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Channels with no category membership."""
    assigned = select(channel_categories.c.channel_id)
    channels = (
        db.query(Channel)
        .options(joinedload(Channel.category), joinedload(Channel.categories))
        .filter(~Channel.id.in_(assigned))
        .order_by(Channel.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [channel_with_stats(db, channel) for channel in channels]


@router.get("/{category_id}/channels", response_model=List[ChannelWithStats])
def list_category_channels(
    category_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Channels in one category (many-to-many). ``category_id`` is numeric id or slug."""
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    channels = (
        db.query(Channel)
        .options(joinedload(Channel.category), joinedload(Channel.categories))
        .join(channel_categories, channel_categories.c.channel_id == Channel.id)
        .filter(channel_categories.c.category_id == category.id)
        .order_by(Channel.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [channel_with_stats(db, channel) for channel in channels]


@router.post("/", response_model=CategoryWithCount, status_code=201)
def create_category(payload: CategoryCreate, request: Request, db: Session = Depends(get_db)):
    """Create a category (admin)."""
    require_admin(request)
    raw_slug = (payload.slug or "").strip() or _slugify(payload.name_en or payload.name_zh)
    slug = _unique_slug(db, raw_slug)
    if payload.sort_order is None:
        max_order = db.query(func.max(Category.sort_order)).scalar() or 0
        sort_order = int(max_order) + 1
    else:
        sort_order = payload.sort_order

    category = Category(
        slug=slug,
        name_zh=payload.name_zh.strip(),
        name_en=payload.name_en.strip(),
        sort_order=sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_with_count(db, category)


@router.put("/{category_id}", response_model=CategoryWithCount)
def update_category(
    category_id: str,
    payload: CategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Rename / reorder a category (admin)."""
    require_admin(request)
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] is not None:
        new_slug = str(data["slug"]).strip()
        if not new_slug:
            raise HTTPException(status_code=400, detail="Slug cannot be empty")
        new_slug = _SLUG_RE.sub("-", new_slug.lower()).strip("-") or new_slug
        category.slug = _unique_slug(db, new_slug[:64], exclude_id=category.id)
    if "name_zh" in data and data["name_zh"] is not None:
        category.name_zh = data["name_zh"].strip()
    if "name_en" in data and data["name_en"] is not None:
        category.name_en = data["name_en"].strip()
    if "sort_order" in data and data["sort_order"] is not None:
        category.sort_order = data["sort_order"]

    db.commit()
    db.refresh(category)
    return _category_with_count(db, category)


@router.delete("/{category_id}")
def delete_category(
    category_id: str,
    request: Request,
    db: Session = Depends(get_db),
    reassign_to: Optional[str] = Query(
        None,
        description="Optional category id/slug to keep channels in. Default: just drop this membership.",
    ),
):
    """Delete a category (admin). Channels keep other category memberships."""
    require_admin(request)
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    target = None
    if reassign_to is not None and str(reassign_to).strip() != "":
        target = get_category(db, reassign_to)
        if target is None:
            raise HTTPException(status_code=400, detail=f"Unknown reassign_to category: {reassign_to}")
        if target.id == category.id:
            raise HTTPException(status_code=400, detail="reassign_to cannot be the category being deleted")

    # Channels currently in this category
    members = (
        db.query(Channel)
        .options(joinedload(Channel.categories))
        .join(channel_categories, channel_categories.c.channel_id == Channel.id)
        .filter(channel_categories.c.category_id == category.id)
        .all()
    )
    moved = 0
    for ch in members:
        remaining = [c for c in (ch.categories or []) if c.id != category.id]
        if target is not None and all(c.id != target.id for c in remaining):
            remaining.append(target)
            moved += 1
        set_channel_categories(db, ch, remaining)

    db.delete(category)
    db.commit()
    return {
        "ok": True,
        "deleted_id": category.id,
        "deleted_slug": category.slug,
        "channels_touched": len(members),
        "channels_reassigned": moved,
        "reassigned_to": target.id if target else None,
    }


@router.post("/{category_id}/assign", response_model=dict)
def assign_channels(
    category_id: str,
    payload: CategoryChannelAssign,
    request: Request,
    db: Session = Depends(get_db),
):
    """Add this category to the listed channels (admin; keeps existing memberships)."""
    require_admin(request)
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    channels = (
        db.query(Channel)
        .options(joinedload(Channel.categories))
        .filter(Channel.id.in_(payload.channel_ids))
        .all()
    )
    found = {c.id for c in channels}
    missing = [cid for cid in payload.channel_ids if cid not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Channels not found: {missing}")

    for channel in channels:
        add_channel_categories(db, channel, [category])
    db.commit()
    return {"ok": True, "category_id": category.id, "assigned": len(channels)}


@router.post("/{category_id}/unassign", response_model=dict)
def unassign_channels(
    category_id: str,
    payload: CategoryChannelAssign,
    request: Request,
    db: Session = Depends(get_db),
):
    """Remove this category from the listed channels (admin)."""
    require_admin(request)
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    channels = (
        db.query(Channel)
        .options(joinedload(Channel.categories))
        .filter(Channel.id.in_(payload.channel_ids))
        .all()
    )
    for channel in channels:
        remove_channel_categories(db, channel, [category.id])
    db.commit()
    return {"ok": True, "category_id": category.id, "unassigned": len(channels)}


@router.post("/{category_id}/channels", response_model=ChannelWithStats, status_code=201)
def add_channel_to_category(
    category_id: str,
    payload: CategoryChannelAdd,
    request: Request,
    db: Session = Depends(get_db),
):
    """Add a channel to this category (admin).

    - ``channel_id``: assign an existing crawler channel (keeps other memberships).
    - ``url`` / ``youtube_channel_id``: create from YouTube if new, or assign if
      the channel already exists. Reference ``channel_id`` slug is auto-assigned
      for botalk sync.
    """
    require_admin(request)
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    from app.api.channels import (
        _generate_reference_id,
        _unique_reference_id,
        channel_with_stats,
        _load_channel,
    )
    from app.services.youtube_service import YouTubeService

    provided = sum(
        1
        for v in (payload.channel_id, payload.url, payload.youtube_channel_id)
        if v is not None and str(v).strip() != ""
    )
    if provided != 1:
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of channel_id, url, or youtube_channel_id",
        )

    # --- Existing crawler channel ---
    if payload.channel_id is not None:
        channel = (
            db.query(Channel)
            .options(joinedload(Channel.categories), joinedload(Channel.category))
            .filter(Channel.id == payload.channel_id)
            .first()
        )
        if channel is None:
            raise HTTPException(status_code=404, detail="Channel not found")
        add_channel_categories(db, channel, [category])
        db.commit()
        return channel_with_stats(db, _load_channel(db, channel.id))

    youtube_service = YouTubeService()
    yt_id = None
    source_url = None

    if payload.youtube_channel_id and str(payload.youtube_channel_id).strip():
        yt_id = str(payload.youtube_channel_id).strip()
        source_url = f"https://www.youtube.com/channel/{yt_id}"
    else:
        source_url = str(payload.url).strip()
        yt_id = youtube_service.extract_channel_id(source_url)
        if not yt_id:
            raise HTTPException(
                status_code=400,
                detail="Could not extract channel ID from URL. Supported: /channel/UCxxx, /@username, /c/name, /user/name",
            )

    existing = (
        db.query(Channel)
        .options(joinedload(Channel.categories), joinedload(Channel.category))
        .filter(Channel.youtube_channel_id == yt_id)
        .first()
    )
    if existing is None and source_url:
        existing = (
            db.query(Channel)
            .options(joinedload(Channel.categories), joinedload(Channel.category))
            .filter(Channel.channel_url == source_url)
            .first()
        )

    if existing is not None:
        add_channel_categories(db, existing, [category])
        db.commit()
        return channel_with_stats(db, _load_channel(db, existing.id))

    channel_info = youtube_service.get_channel_info(yt_id)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Channel not found on YouTube")

    reference_id = _unique_reference_id(
        db, _generate_reference_id(channel_info["channel_name"], source_url or yt_id)
    )
    db_channel = Channel(
        channel_id=reference_id,
        youtube_channel_id=yt_id,
        channel_name=channel_info["channel_name"],
        channel_url=channel_info.get("channel_url") or source_url,
        description=payload.description,
        keywords=payload.keywords or [],
        thumbnail_url=channel_info.get("thumbnail", ""),
        crawl_enabled=bool(payload.crawl_enabled),
        crawl_frequency=payload.crawl_frequency or "manual",
    )
    db.add(db_channel)
    db.flush()
    set_channel_categories(db, db_channel, [category])
    db.commit()
    return channel_with_stats(db, _load_channel(db, db_channel.id))


@router.delete("/{category_id}/channels/{channel_id}")
def remove_channel_from_category(
    category_id: str,
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    hard_delete: bool = Query(
        False,
        description="If true, delete the channel (and its videos) entirely. "
        "Default: only remove this category membership.",
    ),
):
    """Remove a channel from this category (admin). Default is unassign only."""
    require_admin(request)
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    channel = (
        db.query(Channel)
        .options(joinedload(Channel.categories), joinedload(Channel.category))
        .filter(Channel.id == channel_id)
        .first()
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    if hard_delete:
        db.delete(channel)
        db.commit()
        return {
            "ok": True,
            "action": "hard_deleted",
            "channel_id": channel_id,
            "category_id": category.id,
        }

    remove_channel_categories(db, channel, [category.id])
    db.commit()
    return {
        "ok": True,
        "action": "unassigned",
        "channel_id": channel_id,
        "category_id": category.id,
        "remaining_categories": [c.id for c in (channel.categories or [])],
    }
