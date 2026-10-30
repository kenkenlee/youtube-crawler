"""Helpers for many-to-many channel ↔ category assignment.

``channels.category_id`` remains the *primary* category (lowest sort_order
among assigned rows) so botalk sync, which still reads a single slug, keeps
working. All membership lives in ``channel_categories``.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.channel import Channel
from app.services.channel_catalog import get_category


def resolve_category_ids(db: Session, raws: Optional[Sequence[str]]) -> List[Category]:
    """Resolve a list of numeric ids / slugs to Category rows. Empty → []."""
    if not raws:
        return []
    cats: List[Category] = []
    seen = set()
    for raw in raws:
        if raw is None or str(raw).strip() == "":
            continue
        cat = get_category(db, str(raw))
        if cat is None:
            raise HTTPException(status_code=400, detail=f"Unknown category: {raw}")
        if cat.id in seen:
            continue
        seen.add(cat.id)
        cats.append(cat)
    return cats


def primary_category(categories: Iterable[Category]) -> Optional[Category]:
    cats = list(categories)
    if not cats:
        return None
    return sorted(cats, key=lambda c: (c.sort_order, c.id))[0]


def set_channel_categories(db: Session, channel: Channel, categories: Sequence[Category]) -> None:
    """Replace a channel's category membership and refresh primary category_id."""
    channel.categories = list(categories)
    primary = primary_category(categories)
    channel.category_id = primary.id if primary else None


def add_channel_categories(db: Session, channel: Channel, categories: Sequence[Category]) -> None:
    """Add categories without removing existing ones."""
    existing = {c.id: c for c in (channel.categories or [])}
    for cat in categories:
        existing[cat.id] = cat
    set_channel_categories(db, channel, list(existing.values()))


def remove_channel_categories(db: Session, channel: Channel, category_ids: Sequence[int]) -> None:
    """Remove specific categories from a channel."""
    drop = set(category_ids)
    remaining = [c for c in (channel.categories or []) if c.id not in drop]
    set_channel_categories(db, channel, remaining)


def ensure_m2m_schema(engine) -> None:
    """Create ``channel_categories`` and backfill from legacy ``channels.category_id``."""
    from sqlalchemy import inspect, text
    from app.models.association import channel_categories

    channel_categories.create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "channels" not in tables or "channel_categories" not in tables:
        return
    with engine.begin() as conn:
        # Backfill legacy single FK into the association table (idempotent).
        conn.execute(text(
            """
            INSERT OR IGNORE INTO channel_categories (channel_id, category_id)
            SELECT id, category_id FROM channels
            WHERE category_id IS NOT NULL
            """
        ))
