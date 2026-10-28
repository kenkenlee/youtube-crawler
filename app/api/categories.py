from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.api.channels import channel_with_stats
from app.database import get_db
from app.models.category import Category
from app.models.channel import Channel
from app.schemas.category import CategoryWithCount
from app.schemas.channel import ChannelWithStats
from app.services.channel_catalog import get_category

router = APIRouter()


@router.get("/", response_model=List[CategoryWithCount])
def list_categories(db: Session = Depends(get_db)):
    """List categories in catalog order, with the number of channels in each."""
    rows = (
        db.query(Category, func.count(Channel.id))
        .outerjoin(Channel, Channel.category_id == Category.id)
        .group_by(Category.id)
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
            channel_count=count,
        )
        for category, count in rows
    ]


@router.get("/{category_id}/channels", response_model=List[ChannelWithStats])
def list_category_channels(
    category_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Channels in one category. ``category_id`` is the numeric id or the slug."""
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    channels = (
        db.query(Channel)
        .options(joinedload(Channel.category))
        .filter(Channel.category_id == category.id)
        .order_by(Channel.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [channel_with_stats(db, channel) for channel in channels]
