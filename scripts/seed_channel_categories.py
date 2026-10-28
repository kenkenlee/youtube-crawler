#!/usr/bin/env python3
"""Seed categories and import catalog channels without creating duplicates.

Safe to re-run against the SQLite database used by Docker. The script never
deletes channels or videos, never turns crawling off for a channel that is
already stored, and never writes a ``youtube_channel_id`` that was not resolved
from the YouTube Data API, yt-dlp, or an existing verified seed value
(``resolved_by`` of ``youtube_data_api``, ``yt-dlp``, or ``manual``).

From the app directory on the host, or inside the container (``WORKDIR /app``):

    python scripts/seed_channel_categories.py
    python scripts/seed_channel_categories.py --dry-run
    python scripts/seed_channel_categories.py --resolve
    python scripts/seed_channel_categories.py --resolve --limit 20
    docker compose exec youtube-crawler python scripts/seed_channel_categories.py

What the default run does:

1. Create the ``categories`` table and ``channels.category_id`` column if the
   database was created before categories existed.
2. Upsert every category in ``data/channel_catalog_seed.json``.
3. Assign each existing channel from ``existing_channel_category_map``
   (match on ``channel_name``). Unmapped channels use a clear catalog name
   match, or ``other``.
4. For each catalog search name, if a stored channel already matches by
   YouTube id, channel URL, or clear name (see
   ``app/services/channel_catalog.py``), update nothing except a missing
   category. Do not insert a second row.
5. Insert a catalog channel only when the seed row has a verified YouTube
   channel id. New rows are ``crawl_enabled=false`` unless ``--enable-crawl``
   is set.

``--resolve`` looks up unresolved search names (Data API when
``YOUTUBE_API_KEY`` is set, otherwise ``yt-dlp``). A hit is kept only when the
returned id looks like ``UC…``, the channel title clearly matches the search
name (HK / 香港 tokens included), the channel has at least 1,000 subscribers,
and a short or lookalike name is echoed by the handle or description.
BBC News and BBC News 中文 are not treated as the same channel.
Unresolved rows stay in the seed file with a null id.

The application also runs steps 1–3 on startup. Importing new channels happens
only when this script runs.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.models  # noqa: F401  (register tables on Base.metadata)
from app.database import Base, SessionLocal, engine
from app.services.channel_catalog import (
    apply_catalog,
    ensure_category_schema,
    load_catalog,
    resolve_catalog_entries,
    save_catalog,
)


def format_report(report: dict) -> str:
    lines = [
        f"Categories upserted: {report['categories_upserted']}",
        f"Existing channels categorized: {len(report['assignments'])}",
    ]
    for row in report["assignments"]:
        lines.append(f"  {row['channel_name']} -> {row['category_slug']} ({row['source']})")
    lines.append(f"Catalog rows matched to an existing channel: {len(report['matched_existing'])}")
    for row in report["matched_existing"]:
        lines.append(
            f"  [{row['match']}] {row['search_name']} -> {row['channel_name']} ({row['category_slug']})"
        )
    lines.append(f"New channels inserted: {len(report['inserted'])}")
    for row in report["inserted"]:
        lines.append(
            f"  {row['search_name']} -> {row['youtube_channel_id']} "
            f"[{row['category_slug']}] via {row['resolved_by']}"
        )
    lines.append(f"Catalog rows left as seed only: {len(report['skipped_unresolved'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed channel categories and import verified catalog channels.")
    parser.add_argument("--dry-run", action="store_true", help="Print the report and roll back database writes.")
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="Look up unresolved search names with the YouTube Data API or yt-dlp.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max unresolved names to look up with --resolve.")
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Only upsert categories and categorize channels that are already stored.",
    )
    parser.add_argument(
        "--enable-crawl",
        action="store_true",
        help="Set crawl_enabled on newly imported channels. Existing channels are unchanged.",
    )
    args = parser.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    ensure_category_schema(engine)

    catalog = load_catalog()
    if args.resolve:
        draft = copy.deepcopy(catalog)
        resolution = resolve_catalog_entries(draft, limit=args.limit)
        print(
            f"Resolve checked {resolution['checked']}: "
            f"{len(resolution['resolved'])} verified, {len(resolution['unresolved'])} still unknown"
        )
        for row in resolution["resolved"]:
            print(f"  resolved {row['search_name']} -> {row['youtube_channel_id']} ({row['channel_name']})")
        if args.dry_run:
            catalog = draft
        else:
            save_catalog(draft)
            catalog = draft

    db = SessionLocal()
    try:
        report = apply_catalog(
            db,
            catalog,
            import_resolved=not args.no_import,
            enable_crawl=args.enable_crawl,
        )
        print(format_report(report))
        if args.dry_run:
            db.rollback()
            print("Dry run: database changes rolled back.")
        else:
            db.commit()
            print("Saved.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
