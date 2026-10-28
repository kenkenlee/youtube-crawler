"""Category seed data and catalog deduplication.

Categories come from ``data/channel_catalog_seed.json``. Existing channels are
categorized from ``existing_channel_category_map`` (exact ``channel_name``).
Anything still unmapped is matched against catalog search names, then falls
back to the ``other`` category. Channels and their videos are never deleted.

A catalog row is inserted only when it already has a verified YouTube channel
id (``resolved_by`` of ``youtube_data_api``, ``yt-dlp``, or ``manual``).
Search names are not channel ids. ``--resolve`` on the seed script may fill
ids after a real lookup whose title clearly matches, keeps any HK/香港 token
from the search name, and clears the subscriber and handle checks below.
It never invents an id. Channels under 1,000 subscribers, and short names
that are not echoed by the handle or description, stay unresolved.

Dedupe, in order:

1. Same ``youtube_channel_id``.
2. Same canonical channel URL (``/channel/UC…`` or ``/@handle``).
3. Clear name match: normalized equality, CJK names that differ only by a
   generic suffix such as 新聞, or an explicit alias group. A clear name match
   still counts when a lookup returned a different id; the stored id is kept.

Alias groups exist for identities the catalog spells differently from the
live crawler (MKBHD / Marques Brownlee, 謎米香港 / memehongkong, HOY / 有線新聞,
SCMP, 明報, RTHK, TVB News). Language markers such as 中文 keep channels apart,
so BBC News and BBC News 中文 stay separate.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models.category import Category
from app.models.channel import Channel

logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "channel_catalog_seed.json"

VERIFIED_RESOLVERS = frozenset({"youtube_data_api", "yt-dlp", "manual"})
YOUTUBE_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")
# Below this, a title match is treated as an impostor or an empty channel.
MIN_RESOLVED_SUBSCRIBERS = 1000
# Below this, an ASCII token from the search name must show up in the handle.
HANDLE_CHECK_BELOW_SUBSCRIBERS = 20000
_GEO_TOKENS = frozenset({"hk", "hong", "kong", "香港"})

# Tokens that may be added or dropped without making a channel a different one.
GENERIC_TOKENS = frozenset({
    "news", "official", "channel", "the", "tv", "hk", "hong", "kong",
    "香港", "新聞", "官方", "頻道", "youtube", "com", "ltd", "limited",
    "video", "videos", "media",
})

# Extra tokens that mean a different edition, not a display-name variant.
LANGUAGE_MARKERS = frozenset({
    "中文", "英文", "chinese", "english", "mandarin", "cantonese",
    "粵語", "普通话", "國語", "簡體", "繁體", "简体", "繁体",
})

# Surface forms that refer to one channel even when the automatic token
# comparison cannot see it. Membership is by whole token (or a CJK token
# plus a generic suffix), not by loose substring.
ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("MKBHD", "Marques Brownlee"),
    ("memehongkong", "謎米香港"),
    ("HOY", "HOY TV", "有線新聞", "i-CABLE", "i cable"),
    ("Mill MILK",),
    ("香港01", "HK01"),
    ("SCMP", "South China Morning Post"),
    ("明報", "Ming Pao", "Mingpao"),
    ("RTHK", "香港電台"),
    ("無綫新聞", "TVB News", "TVB NEWS"),
)

_SEPARATORS = re.compile(r"[\s/\\|×・•—–\-_.,:;+&()\[\]{}「」『』\"'`]+")
_CHANNEL_URL_ID = re.compile(r"youtube\.com/channel/(UC[\w-]{22})", re.I)
_CHANNEL_URL_HANDLE = re.compile(r"youtube\.com/@([\w.\-]+)", re.I)
_AUTO_REFERENCE = re.compile(r"^channel(?:-\d+)?$")


def catalog_path() -> Path:
    return CATALOG_PATH


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the seed catalog. Raises FileNotFoundError if it is missing."""
    target = Path(path) if path else CATALOG_PATH
    with target.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if "categories" not in data or "channels" not in data:
        raise ValueError(f"Catalog {target} is missing categories or channels")
    return data


def save_catalog(catalog: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Write the catalog atomically so a crash cannot truncate the seed file."""
    target = Path(path) if path else CATALOG_PATH
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def ensure_category_schema(engine: Engine) -> None:
    """Create ``categories`` and add ``channels.category_id`` on an existing SQLite DB.

    ``create_all`` builds the table for new databases. Older files already have
    ``channels`` and need an ALTER. Nothing is dropped.
    """
    Category.__table__.create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "channels" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("channels")}
    with engine.begin() as conn:
        if "category_id" not in columns:
            conn.execute(text("ALTER TABLE channels ADD COLUMN category_id INTEGER"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_channels_category_id ON channels (category_id)"
        ))


def normalize_name(value: Optional[str]) -> str:
    """Case-fold and turn punctuation into spaces. Empty input stays empty."""
    if not value:
        return ""
    text_value = unicodedata.normalize("NFKC", value).lower().strip()
    text_value = _SEPARATORS.sub(" ", text_value)
    return re.sub(r"\s+", " ", text_value).strip()


def _has_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _is_language_token(token: str) -> bool:
    compact = token.replace(" ", "")
    if compact in LANGUAGE_MARKERS:
        return True
    return any(marker in compact for marker in LANGUAGE_MARKERS)


def _is_generic_token(token: str) -> bool:
    """True when ``token`` is generic or a concatenation of generic tokens."""
    if not token or _is_language_token(token):
        return False
    if token in GENERIC_TOKENS:
        return True
    remaining = token.replace(" ", "")
    generics = sorted(GENERIC_TOKENS, key=len, reverse=True)
    while remaining:
        matched = False
        for generic in generics:
            if remaining.startswith(generic):
                remaining = remaining[len(generic):]
                matched = True
                break
        if not matched:
            return False
    return True


def tokens_equivalent(left: str, right: str) -> bool:
    """CJK tokens match when the extra characters are only a generic suffix."""
    if left == right:
        return True
    if not left or not right or not (_has_cjk(left) and _has_cjk(right)):
        return False
    if left in right:
        extra = right.replace(left, "", 1).strip()
    elif right in left:
        extra = left.replace(right, "", 1).strip()
    else:
        return False
    if not extra:
        return True
    if _is_language_token(extra):
        return False
    return _is_generic_token(extra)


def _alias_in_name(alias: str, name: str) -> bool:
    alias_norm = normalize_name(alias)
    name_norm = normalize_name(name)
    if not alias_norm or not name_norm:
        return False
    if alias_norm == name_norm:
        return True
    alias_compact = alias_norm.replace(" ", "")
    name_compact = name_norm.replace(" ", "")
    if alias_compact == name_compact and len(alias_compact) >= 4:
        return True
    alias_tokens = alias_norm.split()
    name_tokens = name_norm.split()
    if len(alias_tokens) == 1:
        token = alias_tokens[0]
        if len(token) < 3 and not _has_cjk(token):
            return False
        return any(token == candidate or tokens_equivalent(token, candidate) for candidate in name_tokens)
    used = [False] * len(name_tokens)
    for token in alias_tokens:
        found = False
        for index, candidate in enumerate(name_tokens):
            if used[index]:
                continue
            if token == candidate or tokens_equivalent(token, candidate):
                used[index] = True
                found = True
                break
        if not found:
            return False
    return True


def _alias_groups_for(name: str) -> set:
    hits = set()
    for index, group in enumerate(ALIAS_GROUPS):
        if any(_alias_in_name(alias, name) for alias in group):
            hits.add(index)
    return hits


def _language_conflict(left_tokens: Sequence[str], right_tokens: Sequence[str]) -> bool:
    if any(_is_language_token(token) for token in left_tokens) != any(
        _is_language_token(token) for token in right_tokens
    ):
        return True
    # Same script marker on both sides is fine; a marker on only some leftover
    # tokens is handled by the caller. This catches 中文 vs no 中文.
    left_marks = {token for token in left_tokens if _is_language_token(token)}
    right_marks = {token for token in right_tokens if _is_language_token(token)}
    return left_marks != right_marks


def _covered_with_generic_extras(shorter: Sequence[str], longer: Sequence[str]) -> bool:
    if not shorter:
        return False
    used = [False] * len(longer)
    for token in shorter:
        found = False
        for index, candidate in enumerate(longer):
            if used[index]:
                continue
            if token == candidate or tokens_equivalent(token, candidate):
                used[index] = True
                found = True
                break
        if not found:
            return False
    leftovers = [token for index, token in enumerate(longer) if not used[index]]
    if any(_is_language_token(token) for token in leftovers):
        return False
    return all(_is_generic_token(token) for token in leftovers)


def names_clearly_match(left: Optional[str], right: Optional[str]) -> bool:
    """True when two labels are the same channel, not merely the same topic."""
    normalized_left = normalize_name(left)
    normalized_right = normalize_name(right)
    if not normalized_left or not normalized_right:
        return False
    if normalized_left == normalized_right:
        return True
    compact_left = normalized_left.replace(" ", "")
    compact_right = normalized_right.replace(" ", "")
    if compact_left == compact_right and len(compact_left) >= 4:
        return True
    left_tokens = normalized_left.split()
    right_tokens = normalized_right.split()
    if _language_conflict(left_tokens, right_tokens):
        return False
    if _alias_groups_for(normalized_left) & _alias_groups_for(normalized_right):
        return True
    shorter, longer = (left_tokens, right_tokens) if len(left_tokens) <= len(right_tokens) else (
        right_tokens, left_tokens
    )
    return _covered_with_generic_extras(shorter, longer)


def canonical_url_key(url: Optional[str]) -> Optional[str]:
    """Identity key for a YouTube channel URL. None when it is not a channel URL."""
    if not url:
        return None
    match = _CHANNEL_URL_ID.search(url)
    if match:
        return "id:" + match.group(1)
    match = _CHANNEL_URL_HANDLE.search(url)
    if match:
        return "handle:" + match.group(1).lower()
    return None


def _reference_label(channel_id: Optional[str]) -> Optional[str]:
    """Turn a reference id into a name candidate. Skip auto ids like ``channel-2``."""
    if not channel_id or _AUTO_REFERENCE.match(channel_id):
        return None
    label = channel_id.replace("-", " ").strip()
    if len(label) < 3 or label.isdigit():
        return None
    return label


def channel_name_candidates(channel: Channel) -> List[str]:
    names = []
    if channel.channel_name:
        names.append(channel.channel_name)
    reference = _reference_label(channel.channel_id)
    if reference:
        names.append(reference)
    return names


def channel_matches_name(channel: Channel, search_name: Optional[str]) -> bool:
    if not search_name:
        return False
    return any(names_clearly_match(candidate, search_name) for candidate in channel_name_candidates(channel))


def is_verified_channel_id(youtube_channel_id: Optional[str], resolved_by: Optional[str]) -> bool:
    """A verified id is a real UC id that came from a lookup or an operator."""
    if resolved_by not in VERIFIED_RESOLVERS:
        return False
    return bool(youtube_channel_id and YOUTUBE_CHANNEL_ID_RE.match(youtube_channel_id))


def is_verified_entry(entry: Dict[str, Any]) -> bool:
    return is_verified_channel_id(entry.get("youtube_channel_id"), entry.get("resolved_by"))


def match_kind(channel: Channel, entry: Dict[str, Any]) -> Optional[str]:
    """Why ``channel`` is the same as this catalog row, or None.

    A different YouTube id does not override a clear name match. RTHK News and
    a search hit titled 香港電台 RTHK stay one channel. BBC News and BBC News 中文
    do not, because the names themselves differ. An existing id is never replaced.
    """
    youtube_id = entry.get("youtube_channel_id") or None
    if youtube_id and channel.youtube_channel_id and channel.youtube_channel_id == youtube_id:
        return "youtube_id"
    entry_url_key = canonical_url_key(entry.get("channel_url"))
    channel_url_key = canonical_url_key(channel.channel_url)
    if entry_url_key and channel_url_key and entry_url_key == channel_url_key:
        return "url"
    if channel_matches_name(channel, entry.get("search_name")):
        return "name"
    return None


def find_matching_channel(channels: Iterable[Channel], entry: Dict[str, Any]) -> Optional[Channel]:
    for channel in channels:
        if match_kind(channel, entry):
            return channel
    return None


def get_category(db: Session, category_id: Optional[str]) -> Optional[Category]:
    """Resolve a numeric primary key or a catalog slug."""
    if category_id is None:
        return None
    text_id = str(category_id).strip()
    if not text_id:
        return None
    if text_id.isdigit():
        found = db.query(Category).filter(Category.id == int(text_id)).first()
        if found:
            return found
    return db.query(Category).filter(Category.slug == text_id).first()


def upsert_categories(db: Session, catalog: Dict[str, Any]) -> int:
    """Insert or update every catalog category. Returns the number of slugs."""
    count = 0
    for sort_order, raw in enumerate(catalog.get("categories") or [], start=1):
        slug = raw["id"]
        row = db.query(Category).filter(Category.slug == slug).first()
        if row is None:
            row = Category(slug=slug)
            db.add(row)
        row.name_zh = raw.get("name_zh") or raw.get("name") or slug
        row.name_en = raw.get("name_en") or raw.get("name") or slug
        row.sort_order = sort_order
        count += 1
    db.flush()
    return count


def _category_slug_map(db: Session) -> Dict[str, Category]:
    return {row.slug: row for row in db.query(Category).all()}


def assign_existing_categories(db: Session, catalog: Dict[str, Any]) -> List[Dict[str, str]]:
    """Set ``category_id`` on every current channel. Does not delete rows."""
    categories = _category_slug_map(db)
    other = categories.get("other")
    mapping = catalog.get("existing_channel_category_map") or {}
    catalog_channels = catalog.get("channels") or []
    report: List[Dict[str, str]] = []
    for channel in db.query(Channel).order_by(Channel.id.asc()).all():
        source = "fallback"
        slug = "other"
        if channel.channel_name in mapping:
            slug = mapping[channel.channel_name]
            source = "map"
        else:
            for entry in catalog_channels:
                if match_kind(channel, entry):
                    slug = entry.get("category_id") or "other"
                    source = "catalog"
                    break
        category = categories.get(slug) or other
        if category is not None and channel.category_id != category.id:
            channel.category_id = category.id
        report.append({
            "channel_name": channel.channel_name,
            "category_slug": category.slug if category is not None else slug,
            "source": source,
        })
    db.flush()
    return report


def _reference_id(db: Session, entry: Dict[str, Any], reserved: set) -> str:
    source = entry.get("channel_name") or entry.get("search_name") or ""
    latin = re.sub(r"[^a-zA-Z0-9]+", "-", source).strip("-").lower()
    if len(latin) < 2:
        latin = f"catalog-{entry.get('list_no') or 'channel'}"
    base = latin[:48].strip("-") or "catalog"
    candidate = base
    suffix = 2
    while candidate in reserved or db.query(Channel).filter(Channel.channel_id == candidate).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    reserved.add(candidate)
    return candidate


def sync_catalog_channels(
    db: Session,
    catalog: Dict[str, Any],
    *,
    import_resolved: bool = False,
    enable_crawl: bool = False,
) -> Dict[str, Any]:
    """Match catalog rows to existing channels. Insert only verified new ids.

    When several catalog rows match one channel, the existing-channel map wins.
    Otherwise the earliest ``list_no`` supplies the category. Later rows do not
    create a second channel and do not override that category.
    """
    categories = _category_slug_map(db)
    mapping = catalog.get("existing_channel_category_map") or {}
    existing = db.query(Channel).order_by(Channel.id.asc()).all()
    reserved_ids = {channel.channel_id for channel in existing}
    claimed: Dict[int, str] = {}
    matched: List[Dict[str, Any]] = []
    inserted: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    entries = sorted(catalog.get("channels") or [], key=lambda item: item.get("list_no") or 0)
    for entry in entries:
        hit = find_matching_channel(existing, entry)
        if hit is not None:
            kind = match_kind(hit, entry)
            if hit.channel_name not in mapping and hit.id not in claimed:
                category = categories.get(entry.get("category_id"))
                if category is not None:
                    hit.category_id = category.id
                    claimed[hit.id] = category.slug
            elif hit.id not in claimed and hit.category_id:
                current = next((row.slug for row in categories.values() if row.id == hit.category_id), None)
                if current:
                    claimed[hit.id] = current
            if is_verified_entry(entry) and not hit.youtube_channel_id:
                hit.youtube_channel_id = entry["youtube_channel_id"]
            matched.append({
                "list_no": entry.get("list_no"),
                "search_name": entry.get("search_name"),
                "channel_name": hit.channel_name,
                "category_slug": claimed.get(hit.id),
                "match": kind,
            })
            continue

        if not import_resolved or not is_verified_entry(entry):
            skipped.append({
                "list_no": entry.get("list_no"),
                "search_name": entry.get("search_name"),
                "category_id": entry.get("category_id"),
            })
            continue

        category = categories.get(entry.get("category_id"))
        youtube_id = entry["youtube_channel_id"]
        channel_name = entry.get("channel_name") or entry.get("search_name")
        channel_url = entry.get("channel_url") or f"https://www.youtube.com/channel/{youtube_id}"
        created = Channel(
            channel_id=_reference_id(db, entry, reserved_ids),
            youtube_channel_id=youtube_id,
            channel_name=channel_name,
            channel_url=channel_url,
            description=None,
            keywords=[],
            crawl_enabled=bool(enable_crawl),
            crawl_frequency="manual",
            category_id=category.id if category is not None else None,
        )
        db.add(created)
        db.flush()
        existing.append(created)
        claimed[created.id] = category.slug if category is not None else None
        inserted.append({
            "list_no": entry.get("list_no"),
            "search_name": entry.get("search_name"),
            "channel_name": channel_name,
            "youtube_channel_id": youtube_id,
            "category_slug": category.slug if category is not None else None,
            "resolved_by": entry.get("resolved_by"),
        })

    db.flush()
    return {"matched_existing": matched, "inserted": inserted, "skipped_unresolved": skipped}


def apply_catalog(
    db: Session,
    catalog: Optional[Dict[str, Any]] = None,
    *,
    import_resolved: bool = False,
    enable_crawl: bool = False,
) -> Dict[str, Any]:
    """Upsert categories, categorize existing channels, optionally import verified rows.

    The caller commits. This function flushes but does not delete channels or videos.
    """
    payload = catalog if catalog is not None else load_catalog()
    category_count = upsert_categories(db, payload)
    assignments = assign_existing_categories(db, payload)
    synced = sync_catalog_channels(
        db,
        payload,
        import_resolved=import_resolved,
        enable_crawl=enable_crawl,
    )
    return {
        "categories_upserted": category_count,
        "assignments": assignments,
        **synced,
    }


def accept_resolved_channel(
    search_name: str,
    title: str,
    *,
    handle: str = "",
    description: str = "",
    subscriber_count: Optional[int] = None,
) -> bool:
    """Whether a lookup is safe to store for ``search_name``.

    A matching title is required. HK / 香港 in the search name must still be
    present on the title (so "Channel C" is not stored as "Channel C HK").
    Results under 1,000 subscribers are left unresolved. From 1,000 up to
    20,000, the handle must contain an ASCII token from the search name when
    the search name has one (this drops renamed impostors such as a ghost-story
    channel titled 香港電台 RTHK). A single short Latin name must also appear in
    the handle or description, not only the title.
    """
    if not search_name or not title or not names_clearly_match(search_name, title):
        return False
    search_tokens = normalize_name(search_name).split()
    title_tokens = set(normalize_name(title).split())
    missing_geo = (set(search_tokens) & _GEO_TOKENS) - title_tokens
    if missing_geo:
        search_compact = "".join(search_tokens)
        title_compact = normalize_name(title).replace(" ", "")
        if search_compact not in title_compact:
            return False
    if subscriber_count is not None and subscriber_count < MIN_RESOLVED_SUBSCRIBERS:
        return False

    distinctive = [
        token for token in search_tokens
        if token not in GENERIC_TOKENS
        and not _is_language_token(token)
        and (len(token) >= 4 or _has_cjk(token))
    ]
    handle_blob = (handle or "").lower().lstrip("@")
    detail_blob = f"{handle_blob} {(description or '').lower()}"
    if len(distinctive) == 1 and distinctive[0].isascii() and len(distinctive[0]) <= 6:
        if distinctive[0] not in detail_blob:
            return False
    ascii_distinctive = [token for token in distinctive if token.isascii()]
    if (
        subscriber_count is not None
        and subscriber_count < HANDLE_CHECK_BELOW_SUBSCRIBERS
        and handle_blob
        and ascii_distinctive
        and not any(token in handle_blob for token in ascii_distinctive)
    ):
        return False
    return True


def _ytdlp_channel_metadata(url: str) -> Dict[str, Any]:
    """Subscriber count, handle, and description for one channel URL."""
    binary = shutil.which("yt-dlp")
    if not binary or not url:
        return {}
    try:
        completed = subprocess.run(
            [binary, "-J", "--flat-playlist", "--playlist-end", "1", "--no-warnings", url],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("yt-dlp metadata failed for %s: %s", url, exc)
        return {}
    if completed.returncode != 0 or not completed.stdout.strip():
        return {}
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}
    return {
        "subscriber_count": data.get("channel_follower_count"),
        "handle": data.get("uploader_id") or "",
        "description": data.get("description") or "",
        "channel_name": data.get("channel") or data.get("title") or "",
    }


def resolve_with_youtube_api(query: str) -> Optional[Dict[str, str]]:
    """Top Data API channel whose title clearly matches ``query``. None if unavailable."""
    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        try:
            from app.services.settings_service import SettingsService
            api_key = SettingsService.get("YOUTUBE_API_KEY", None)
        except Exception:
            api_key = None
    if not api_key:
        return None
    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        response = youtube.search().list(
            part="snippet",
            type="channel",
            q=query,
            maxResults=5,
        ).execute()
    except Exception as exc:
        logger.warning("YouTube API channel search failed for %s: %s", query, exc)
        return None
    for item in response.get("items") or []:
        snippet = item.get("snippet") or {}
        identifier = snippet.get("channelId") or (item.get("id") or {}).get("channelId")
        title = snippet.get("title") or ""
        description = snippet.get("description") or ""
        handle = snippet.get("customUrl") or ""
        if not identifier or not names_clearly_match(query, title):
            continue
        subscriber_count = None
        try:
            details = youtube.channels().list(part="statistics,snippet", id=identifier).execute()
            detail_items = details.get("items") or []
            if detail_items:
                statistics = detail_items[0].get("statistics") or {}
                if statistics.get("subscriberCount") is not None:
                    subscriber_count = int(statistics["subscriberCount"])
                detail_snippet = detail_items[0].get("snippet") or {}
                description = detail_snippet.get("description") or description
                title = detail_snippet.get("title") or title
                handle = detail_snippet.get("customUrl") or handle
        except Exception as exc:
            logger.warning("YouTube API channel details failed for %s: %s", query, exc)
        if accept_resolved_channel(
            query,
            title,
            handle=handle,
            description=description,
            subscriber_count=subscriber_count,
        ):
            return {
                "youtube_channel_id": identifier,
                "channel_name": title,
                "channel_url": f"https://www.youtube.com/channel/{identifier}",
                "resolved_by": "youtube_data_api",
                "subscriber_count": subscriber_count,
                "handle": handle,
                "description": description,
            }
    return None


def _walk_entries(node: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(node, dict):
        if "entries" in node and isinstance(node["entries"], list):
            for child in node["entries"]:
                yield from _walk_entries(child)
        else:
            yield node
    elif isinstance(node, list):
        for child in node:
            yield from _walk_entries(child)


def resolve_with_ytdlp(query: str) -> Optional[Dict[str, str]]:
    """First yt-dlp channel-search hit whose title clearly matches. None if unavailable."""
    binary = shutil.which("yt-dlp")
    if not binary:
        return None
    quoted = urllib.parse.quote(query)
    # sp=EgIQAg== restricts YouTube results to channels.
    url = f"https://www.youtube.com/results?search_query={quoted}&sp=EgIQAg%3D%3D"
    try:
        completed = subprocess.run(
            [binary, "--flat-playlist", "--playlist-end", "5", "-J", "--no-warnings", url],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("yt-dlp channel search failed for %s: %s", query, exc)
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        logger.warning("yt-dlp channel search returned nothing for %s", query)
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        logger.warning("yt-dlp returned non-JSON for %s", query)
        return None
    for entry in _walk_entries(payload):
        identifier = str(entry.get("channel_id") or entry.get("id") or "")
        title = entry.get("channel") or entry.get("title") or ""
        title = re.sub(r"\s+-\s+YouTube$", "", str(title)).strip()
        if not YOUTUBE_CHANNEL_ID_RE.match(identifier) or not names_clearly_match(query, title):
            continue
        channel_url = (
            entry.get("channel_url")
            or entry.get("url")
            or entry.get("webpage_url")
            or f"https://www.youtube.com/channel/{identifier}"
        )
        handle = entry.get("uploader_id") or ""
        description = entry.get("description") or ""
        subscriber_count = entry.get("channel_follower_count")
        if subscriber_count is None or not description or not handle:
            hydrated = _ytdlp_channel_metadata(channel_url)
            if subscriber_count is None:
                subscriber_count = hydrated.get("subscriber_count")
            handle = handle or hydrated.get("handle") or ""
            description = description or hydrated.get("description") or ""
            if hydrated.get("channel_name"):
                title = hydrated["channel_name"]
        if not accept_resolved_channel(
            query,
            title,
            handle=handle,
            description=description,
            subscriber_count=subscriber_count,
        ):
            continue
        if not canonical_url_key(channel_url):
            channel_url = f"https://www.youtube.com/channel/{identifier}"
        return {
            "youtube_channel_id": identifier,
            "channel_name": title,
            "channel_url": channel_url,
            "resolved_by": "yt-dlp",
            "subscriber_count": subscriber_count,
            "handle": handle,
            "description": description,
        }
    return None


def resolve_search_name(query: str) -> Optional[Dict[str, str]]:
    """Resolve one search name. Tries the Data API, then yt-dlp. Never guesses an id."""
    for resolver in (resolve_with_youtube_api, resolve_with_ytdlp):
        hit = resolver(query)
        if not hit:
            continue
        if not is_verified_channel_id(hit.get("youtube_channel_id"), hit.get("resolved_by")):
            continue
        if not accept_resolved_channel(
            query,
            hit.get("channel_name") or "",
            handle=hit.get("handle") or "",
            description=hit.get("description") or "",
            subscriber_count=hit.get("subscriber_count"),
        ):
            continue
        channel_url = hit.get("channel_url") or ""
        if not canonical_url_key(channel_url):
            hit["channel_url"] = f"https://www.youtube.com/channel/{hit['youtube_channel_id']}"
        return hit
    return None


def resolve_catalog_entries(
    catalog: Dict[str, Any],
    *,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Fill verified ids on catalog rows that do not already have one.

    Rows that cannot be resolved keep ``youtube_channel_id`` null.
    """
    resolved: List[Dict[str, str]] = []
    unresolved: List[str] = []
    checked = 0
    for entry in catalog.get("channels") or []:
        if is_verified_entry(entry):
            continue
        if limit is not None and checked >= limit:
            break
        checked += 1
        hit = resolve_search_name(entry.get("search_name") or "")
        if not hit:
            entry["youtube_channel_id"] = None
            entry["resolved_by"] = None
            unresolved.append(entry.get("search_name") or "")
            continue
        entry["youtube_channel_id"] = hit["youtube_channel_id"]
        entry["channel_url"] = hit["channel_url"]
        entry["channel_name"] = hit["channel_name"]
        entry["resolved_by"] = hit["resolved_by"]
        resolved.append({
            "search_name": entry.get("search_name") or "",
            "youtube_channel_id": hit["youtube_channel_id"],
            "channel_name": hit["channel_name"],
            "resolved_by": hit["resolved_by"],
        })
    return {"checked": checked, "resolved": resolved, "unresolved": unresolved}
