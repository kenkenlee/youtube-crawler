"""Suggest categories for a channel (auto-detect).

Priority of signals (documented for operators):
1. Exact YouTube channel id match against catalog seed / name map.
2. Normalized channel-name match against seed search names + user table map.
3. Fuzzy/substring name overlap against the same maps.
4. Keyword / token heuristics against live category name_zh / name_en / slug.
5. Optional: categories already used by similarly named channels in the DB.

Suggestions are soft — the UI pre-checks them; empty is OK.
Never blocks channel add if this module or YouTube API fails.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.channel import Channel

logger = logging.getLogger(__name__)

_MAP_PATHS = (
    Path(__file__).resolve().parent / "category_name_map.json",
    Path("/app/app/services/category_name_map.json"),
    Path("/docker/youtube-crawler/data/channel_catalog_seed.json"),
)

# Extra keyword → slug hints for titles that don't hit the name map.
_KEYWORD_HINTS: Tuple[Tuple[str, str], ...] = (
    ("港聞", "hk-news"), ("hong kong news", "hk-news"), ("hk news", "hk-news"),
    ("rthk", "hk-news"), ("tvb news", "hk-news"), ("有線新聞", "hk-news"),
    ("兩岸", "china-taiwan"), ("china", "china-taiwan"), ("taiwan", "china-taiwan"),
    ("國際", "intl-news"), ("international", "intl-news"), ("bbc", "intl-news"),
    ("財經", "finance"), ("finance", "finance"), ("stock", "finance"), ("投資", "finance"),
    ("地產", "property"), ("property", "property"), ("樓市", "property"),
    ("娛樂", "entertainment"), ("entertainment", "entertainment"),
    ("音樂", "entertainment-music"), ("music", "entertainment-music"),
    ("體育", "sports"), ("sports", "sports"), ("足球", "sports-football"),
    ("football", "sports-football"), ("soccer", "sports-football"),
    ("賽車", "sports-motorsport"), ("f1", "sports-motorsport"), ("formula 1", "sports-motorsport"),
    ("欖球", "sports-rugby"), ("rugby", "sports-rugby"),
    ("羽毛球", "sports-badminton"), ("badminton", "sports-badminton"),
    ("網球", "sports-tennis"), ("tennis", "sports-tennis"),
    ("馬經", "horse-racing"), ("jockey", "horse-racing"), ("racing", "horse-racing"),
    ("評論", "opinion"), ("opinion", "opinion"), ("editorial", "opinion"),
    ("飲食", "food"), ("food", "food"), ("cooking", "food"), ("食譜", "food"),
    ("旅遊", "travel"), ("travel", "travel"), ("旅遊飲食", "travel-food"),
    ("科技", "tech"), ("tech", "tech"), ("gadget", "tech"),
    ("音響", "tech-audio"), ("audio", "tech-audio"),
    ("汽車", "motoring"), ("car", "motoring"), ("motoring", "motoring"),
    ("時尚", "fashion"), ("beauty", "fashion"), ("fashion", "fashion"),
    ("健康", "health"), ("health", "health"), ("健身", "health-fitness"),
    ("fitness", "health-fitness"), ("yoga", "health-fitness"),
    ("親子", "family"), ("family", "family"), ("教育", "family-edu"),
    ("文化", "culture"), ("culture", "culture"), ("museum", "culture"),
    ("人物", "people"), ("電影", "film-culture"), ("film", "film-culture"),
    ("科普", "edu-science"), ("science", "edu-science"),
)


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFKC", s or "").strip().lower()
    t = re.sub(r"[\s\-_/|·・，,。.!?:;（）()【】\[\]\"'`]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def _load_name_map() -> Dict[str, Any]:
    for path in _MAP_PATHS:
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            # Slim map shipped with this patch
            if "by_youtube_channel_id" in data or "by_name_normalized" in data:
                return {
                    "by_yt": dict(data.get("by_youtube_channel_id") or {}),
                    "by_name": dict(data.get("by_name_normalized") or {}),
                }
            # Full catalog seed on VPS data/
            by_yt: Dict[str, str] = {}
            by_name: Dict[str, str] = {}
            for ch in data.get("channels") or []:
                slug = ch.get("category_id")
                if not slug:
                    continue
                yt = ch.get("youtube_channel_id")
                if yt:
                    by_yt[yt] = slug
                for key in ("search_name", "channel_name"):
                    n = _norm(ch.get(key) or "")
                    if n and n not in by_name:
                        by_name[n] = slug
            for name, slug in (data.get("existing_channel_category_map") or {}).items():
                n = _norm(name)
                if n and n not in by_name:
                    by_name[n] = slug
            if by_yt or by_name:
                return {"by_yt": by_yt, "by_name": by_name}
        except Exception as exc:  # noqa: BLE001
            logger.warning("category_suggest: failed to load map from %s: %s", path, exc)
    return {"by_yt": {}, "by_name": {}}


def _slug_to_category(db: Session, slug: str) -> Optional[Category]:
    if not slug:
        return None
    return db.query(Category).filter(Category.slug == slug).first()


def _add_suggestion(
    out: Dict[int, Dict[str, Any]],
    cat: Category,
    reason: str,
    score: float,
) -> None:
    prev = out.get(cat.id)
    if prev is None or score > prev["score"]:
        out[cat.id] = {
            "id": cat.id,
            "slug": cat.slug,
            "name_zh": cat.name_zh,
            "name_en": cat.name_en,
            "reason": reason,
            "score": round(score, 3),
        }
    elif prev and reason not in prev["reason"]:
        prev["reason"] = prev["reason"] + "; " + reason


def suggest_categories(
    db: Session,
    *,
    channel_name: Optional[str] = None,
    description: Optional[str] = None,
    youtube_channel_id: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Return ranked category suggestions for a channel preview/add flow."""
    name = (channel_name or "").strip()
    desc = (description or "").strip()
    yt_id = (youtube_channel_id or "").strip()
    text = f"{name} {desc}".strip()
    nname = _norm(name)
    ntext = _norm(text)

    methods: List[str] = []
    scored: Dict[int, Dict[str, Any]] = {}
    name_map = _load_name_map()

    # 1) Exact YouTube id
    if yt_id:
        slug = name_map["by_yt"].get(yt_id)
        cat = _slug_to_category(db, slug) if slug else None
        if cat:
            _add_suggestion(scored, cat, f"catalog youtube_channel_id={yt_id}", 1.0)
            methods.append("youtube_id_map")

    # 2) Exact normalized name
    if nname:
        slug = name_map["by_name"].get(nname)
        cat = _slug_to_category(db, slug) if slug else None
        if cat:
            _add_suggestion(scored, cat, "exact name map match", 0.95)
            methods.append("name_map_exact")

    # 3) Substring / containment against name map
    if nname and len(nname) >= 2:
        for mapped_name, slug in name_map["by_name"].items():
            if len(mapped_name) < 2:
                continue
            if mapped_name in nname or nname in mapped_name:
                cat = _slug_to_category(db, slug)
                if cat:
                    score = 0.8 if mapped_name in nname else 0.7
                    _add_suggestion(
                        scored, cat, f"name overlap with '{mapped_name}'", score
                    )
                    if "name_map_fuzzy" not in methods:
                        methods.append("name_map_fuzzy")

    # 4) Keyword hints + live category name tokens
    cats: Sequence[Category] = (
        db.query(Category).order_by(Category.sort_order.asc(), Category.id.asc()).all()
    )
    if ntext:
        for needle, slug in _KEYWORD_HINTS:
            if _norm(needle) in ntext:
                cat = _slug_to_category(db, slug)
                if cat:
                    _add_suggestion(scored, cat, f"keyword '{needle}'", 0.55)
                    if "keyword_hint" not in methods:
                        methods.append("keyword_hint")

        _STOP = {"and", "the", "for", "with", "from", "of", "to", "in", "a", "an", "or"}
        for cat in cats:
            for label in (cat.name_zh, cat.name_en, cat.slug.replace("-", " ")):
                nl = _norm(label or "")
                if not nl or len(nl) < 2:
                    continue
                # Whole label substring, or a meaningful token (len>=4, not stopword)
                tokens = [tok for tok in nl.split() if len(tok) >= 4 and tok not in _STOP]
                if nl in ntext or any(tok in ntext for tok in tokens):
                    _add_suggestion(
                        scored, cat, f"matches category label '{label}'", 0.5
                    )
                    if "category_label" not in methods:
                        methods.append("category_label")

    # 5) Similar existing channels in DB (reuse their primary / M2M cats)
    if nname and len(nname) >= 3:
        try:
            candidates = (
                db.query(Channel)
                .options(joinedload(Channel.categories))
                .filter(Channel.channel_name.isnot(None))
                .limit(500)
                .all()
            )
            for ch in candidates:
                cn = _norm(ch.channel_name or "")
                if not cn:
                    continue
                if cn == nname or (len(nname) >= 4 and (nname in cn or cn in nname)):
                    for cat in ch.categories or []:
                        _add_suggestion(
                            scored,
                            cat,
                            f"similar existing channel '{ch.channel_name}'",
                            0.65,
                        )
                    if "similar_channel" not in methods:
                        methods.append("similar_channel")
        except Exception as exc:  # noqa: BLE001
            logger.warning("category_suggest similar-channel lookup failed: %s", exc)

    ranked = sorted(scored.values(), key=lambda x: (-x["score"], x["id"]))
    if limit and limit > 0:
        ranked = ranked[:limit]

    return {
        "suggestions": ranked,
        "category_ids": [s["id"] for s in ranked],
        "methods": methods,
        "input": {
            "channel_name": name or None,
            "youtube_channel_id": yt_id or None,
            "has_description": bool(desc),
        },
    }
