"""Category seeding and catalog deduplication."""
import json
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.models.channel import Channel
from app.models.video import Video
from app.services.channel_catalog import (
    accept_resolved_channel,
    apply_catalog,
    ensure_category_schema,
    is_verified_entry,
    load_catalog,
    match_kind,
    names_clearly_match,
)

FIXTURE = Path(__file__).parent / "fixtures" / "live_channels.json"

# Catalog search names that are the same channel as one of the 27 live rows.
EXPECTED_LIVE_MATCHES = {
    "香港電台 RTHK": "香港電台新聞 RTHK News",
    "有線新聞 i-CABLE News": "HOY 78 × 有線新聞 Cable News",
    "無綫新聞 TVB News": "無綫新聞 TVB NEWS Official",
    "香港01": "香港01",
    "明報 Ming Pao": "明報 Mingpao",
    "South China Morning Post": "South China Morning Post",
    "謎米香港 memehongkong": "memehongkong",
    "Mill MILK": "Mill MILK",
    "HOY TV": "HOY 78 × 有線新聞 Cable News",
    "Marques Brownlee / MKBHD": "MKBHD",
}


def _channels_from_fixture():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [
        Channel(
            channel_id=row["channel_id"],
            youtube_channel_id=row["youtube_channel_id"],
            channel_name=row["channel_name"],
            channel_url=row["channel_url"],
            keywords=[],
        )
        for row in rows
    ]


def test_seed_file_has_170_channels_and_no_invented_ids():
    catalog = load_catalog()
    slugs = [row["id"] for row in catalog["categories"]]
    assert len(slugs) == len(set(slugs))
    assert "other" in slugs
    assert len(catalog["channels"]) == 170
    assert len(catalog["existing_channel_category_map"]) == 27
    for entry in catalog["channels"]:
        assert entry["category_id"] in slugs
        if entry.get("youtube_channel_id"):
            assert is_verified_entry(entry)
        else:
            assert not entry.get("resolved_by")
    for slug in catalog["existing_channel_category_map"].values():
        assert slug in slugs


def test_clear_name_matches_and_language_editions_stay_separate():
    assert names_clearly_match("MKBHD", "Marques Brownlee / MKBHD")
    assert names_clearly_match("MKBHD", "Marques Brownlee")
    assert names_clearly_match("memehongkong", "謎米香港 memehongkong")
    assert names_clearly_match("HOY TV", "HOY 78 × 有線新聞 Cable News")
    assert names_clearly_match("有線新聞 i-CABLE News", "HOY 78 × 有線新聞 Cable News")
    assert names_clearly_match("Mill MILK", "Mill MILK")
    assert names_clearly_match("香港01", "香港01")
    assert names_clearly_match("SCMP", "South China Morning Post")
    assert names_clearly_match("明報 Ming Pao", "明報 Mingpao")
    assert names_clearly_match("香港電台 RTHK", "香港電台新聞 RTHK News")
    assert names_clearly_match("無綫新聞 TVB News", "無綫新聞 TVB NEWS Official")
    assert not names_clearly_match("BBC News", "BBC News 中文")
    assert not names_clearly_match("BBC News", "BBC News Chinese")
    assert not names_clearly_match("ERROR", "Trial & Error")
    assert not names_clearly_match("TVB 官方頻道", "無綫新聞 TVB NEWS Official")


def test_live_catalog_matches_only_the_known_channels():
    from app.services.channel_catalog import find_matching_channel

    catalog = load_catalog()
    channels = _channels_from_fixture()
    found = {}
    for entry in catalog["channels"]:
        hit = find_matching_channel(channels, entry)
        if hit is not None:
            found[entry["search_name"]] = hit.channel_name
    assert found == EXPECTED_LIVE_MATCHES


def test_resolution_rejects_impostors_and_keeps_echoed_names():
    assert not accept_resolved_channel(
        "ERROR",
        "Error",
        handle="@Bruhkamas",
        description="bruh",
        subscriber_count=1180000,
    )
    assert not accept_resolved_channel(
        "Channel C HK",
        "Channel C",
        handle="@channelconline",
        description="Cinema and art",
        subscriber_count=1300000,
    )
    assert not accept_resolved_channel(
        "阿滴英文",
        "阿滴英文",
        handle="@user-gv7bj2jo2g",
        description="",
        subscriber_count=16,
    )
    assert not accept_resolved_channel(
        "香港電台 RTHK",
        "香港電台 RTHK",
        handle="@hongkongghoststori",
        description="",
        subscriber_count=15300,
    )
    assert accept_resolved_channel(
        "NBA",
        "NBA",
        handle="@NBA",
        description="The NBA is the premier professional basketball league",
        subscriber_count=24600000,
    )
    assert accept_resolved_channel(
        "Marques Brownlee / MKBHD",
        "Marques Brownlee",
        handle="@mkbhd",
        description="MKBHD",
        subscriber_count=21400000,
    )


def test_clear_name_match_survives_a_different_youtube_id(db):
    """RTHK News stays the stored row when a lookup returns a different RTHK id."""
    news_id = "UCwuTCNZqSMfaiP63cGDb8LQ"
    other_id = "UC" + "e" * 22
    channel = Channel(
        channel_id="rthk-news",
        channel_name="香港電台新聞 RTHK News",
        channel_url=f"https://www.youtube.com/channel/{news_id}",
        youtube_channel_id=news_id,
        crawl_enabled=True,
        keywords=[],
    )
    db.add(channel)
    db.commit()
    catalog = {
        "categories": [
            {"id": "hk-news", "name_zh": "港聞", "name_en": "Hong Kong news"},
            {"id": "other", "name_zh": "其他", "name_en": "Other"},
        ],
        "existing_channel_category_map": {"香港電台新聞 RTHK News": "hk-news"},
        "channels": [{
            "list_no": 1,
            "category_id": "hk-news",
            "search_name": "香港電台 RTHK",
            "youtube_channel_id": other_id,
            "channel_url": f"https://www.youtube.com/channel/{other_id}",
            "channel_name": "香港電台 RTHK",
            "resolved_by": "yt-dlp",
        }],
    }
    assert match_kind(channel, catalog["channels"][0]) == "name"
    report = apply_catalog(db, catalog, import_resolved=True)
    db.commit()
    assert report["inserted"] == []
    db.refresh(channel)
    assert channel.youtube_channel_id == news_id
    assert db.query(Channel).count() == 1


def test_different_youtube_ids_are_not_merged():
    bbc = Channel(
        channel_id="bbc-news-channel",
        channel_name="BBC News",
        channel_url="https://www.youtube.com/@BBCNews",
        youtube_channel_id="UC16niRr50-MSBwiO3YDb3RA",
        keywords=[],
    )
    other_id = "UC" + "a" * 22
    entry = {
        "search_name": "BBC News 中文",
        "youtube_channel_id": other_id,
        "channel_url": f"https://www.youtube.com/channel/{other_id}",
        "resolved_by": "manual",
    }
    assert match_kind(bbc, entry) is None

    same = {
        "search_name": "Some other label",
        "youtube_channel_id": bbc.youtube_channel_id,
        "resolved_by": "manual",
    }
    assert match_kind(bbc, same) == "youtube_id"


def test_apply_catalog_categorizes_without_deleting_or_duplicating(db):
    mkbhd = Channel(
        channel_id="mkbhd",
        channel_name="MKBHD",
        channel_url="https://www.youtube.com/@mkbhd",
        youtube_channel_id="UCBJycsmduvYEL83R_U4JriQ",
        crawl_enabled=True,
        keywords=[],
    )
    mystery = Channel(
        channel_id="mystery-show",
        channel_name="Mystery Show",
        channel_url="https://www.youtube.com/@mysteryshow",
        youtube_channel_id="UC" + "b" * 22,
        crawl_enabled=True,
        keywords=[],
    )
    bbc = Channel(
        channel_id="bbc-news-channel",
        channel_name="BBC News",
        channel_url="https://www.youtube.com/@BBCNews",
        youtube_channel_id="UC16niRr50-MSBwiO3YDb3RA",
        crawl_enabled=True,
        keywords=[],
    )
    db.add_all([mkbhd, mystery, bbc])
    db.commit()
    db.refresh(mkbhd)
    video = Video(channel_id=mkbhd.id, video_id="vid-keep", title="Keep me", video_url="https://www.youtube.com/watch?v=vid-keep")
    db.add(video)
    db.commit()

    verified_id = "UC" + "c" * 22
    catalog = {
        "categories": [
            {"id": "tech", "name_zh": "科技", "name_en": "Technology"},
            {"id": "intl-news", "name_zh": "國際", "name_en": "International"},
            {"id": "other", "name_zh": "其他", "name_en": "Other"},
        ],
        "existing_channel_category_map": {"MKBHD": "tech", "BBC News": "intl-news"},
        "channels": [
            {"list_no": 1, "category_id": "tech", "search_name": "Marques Brownlee / MKBHD"},
            {
                "list_no": 2,
                "category_id": "intl-news",
                "search_name": "BBC News 中文",
                "youtube_channel_id": verified_id,
                "channel_url": f"https://www.youtube.com/channel/{verified_id}",
                "channel_name": "BBC News 中文",
                "resolved_by": "manual",
            },
            {
                "list_no": 3,
                "category_id": "tech",
                "search_name": "Not A Real Channel",
                "youtube_channel_id": "fake-id",
                "resolved_by": "manual",
            },
            {"list_no": 4, "category_id": "tech", "search_name": "Still Unresolved"},
        ],
    }

    first = apply_catalog(db, catalog, import_resolved=True)
    db.commit()
    by_name = {row["channel_name"]: row["category_slug"] for row in first["assignments"]}
    assert by_name["MKBHD"] == "tech"
    assert by_name["BBC News"] == "intl-news"
    assert by_name["Mystery Show"] == "other"
    assert {row["search_name"] for row in first["matched_existing"]} == {"Marques Brownlee / MKBHD"}
    assert [row["search_name"] for row in first["inserted"]] == ["BBC News 中文"]
    assert {row["search_name"] for row in first["skipped_unresolved"]} == {"Not A Real Channel", "Still Unresolved"}

    db.refresh(mkbhd)
    assert mkbhd.crawl_enabled is True
    assert db.query(Video).filter(Video.video_id == "vid-keep").count() == 1
    assert db.query(Channel).filter(Channel.channel_name == "BBC News 中文").count() == 1

    second = apply_catalog(db, catalog, import_resolved=True)
    db.commit()
    assert second["inserted"] == []
    assert db.query(Channel).count() == 4


def test_import_resolved_false_leaves_verified_rows_uninserted(db):
    catalog = {
        "categories": [{"id": "other", "name_zh": "其他", "name_en": "Other"}],
        "existing_channel_category_map": {},
        "channels": [{
            "list_no": 1,
            "category_id": "other",
            "search_name": "BBC News 中文",
            "youtube_channel_id": "UC" + "d" * 22,
            "resolved_by": "yt-dlp",
            "channel_name": "BBC News 中文",
        }],
    }
    report = apply_catalog(db, catalog, import_resolved=False)
    assert report["inserted"] == []
    assert len(report["skipped_unresolved"]) == 1
    assert db.query(Channel).count() == 0


def test_ensure_category_schema_adds_column_on_sqlite(tmp_path):
    database_file = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database_file}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE channels (id INTEGER PRIMARY KEY, channel_name TEXT)"))
    ensure_category_schema(engine)
    inspector = inspect(engine)
    assert "categories" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("channels")}
    assert "category_id" in columns
    # Re-running must not raise.
    ensure_category_schema(engine)
    engine.dispose()
