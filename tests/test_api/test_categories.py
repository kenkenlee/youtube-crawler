"""Category API tests."""
from app.models.channel import Channel
from app.services.channel_catalog import apply_catalog


def _seed_mkbhd(db):
    channel = Channel(
        channel_id="mkbhd",
        channel_name="MKBHD",
        channel_url="https://www.youtube.com/@mkbhd",
        youtube_channel_id="UCBJycsmduvYEL83R_U4JriQ",
        keywords=[],
        crawl_enabled=True,
    )
    db.add(channel)
    db.commit()
    apply_catalog(db, import_resolved=False)
    db.commit()
    db.refresh(channel)
    return channel


def test_list_categories_includes_channel_count(client, db):
    _seed_mkbhd(db)
    response = client.get("/api/categories/")
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    slugs = [row["slug"] for row in body]
    assert slugs[0] == "hk-news"
    assert [row["sort_order"] for row in body] == list(range(1, len(body) + 1))
    tech = next(row for row in body if row["slug"] == "tech")
    assert tech["name_zh"] == "果籽・科技"
    assert tech["name_en"] == "Lifestyle—Technology"
    assert tech["channel_count"] == 1
    other = next(row for row in body if row["slug"] == "other")
    assert other["channel_count"] == 0


def test_filter_channels_by_category_slug_and_id(client, db):
    channel = _seed_mkbhd(db)
    listed = client.get("/api/channels/?category_id=tech")
    assert listed.status_code == 200
    payload = listed.json()
    assert len(payload) == 1
    assert payload[0]["channel_name"] == "MKBHD"
    assert payload[0]["category_id"] == channel.category_id
    assert payload[0]["category"]["slug"] == "tech"
    assert payload[0]["category"]["name_en"] == "Lifestyle—Technology"

    by_slug = client.get("/api/categories/tech/channels")
    assert by_slug.status_code == 200
    assert [row["id"] for row in by_slug.json()] == [channel.id]

    by_id = client.get(f"/api/categories/{channel.category_id}/channels")
    assert by_id.status_code == 200
    assert by_id.json()[0]["channel_id"] == "mkbhd"

    missing = client.get("/api/categories/not-a-category/channels")
    assert missing.status_code == 404
    missing_filter = client.get("/api/channels/?category_id=not-a-category")
    assert missing_filter.status_code == 404


def test_update_channel_category(client, db):
    channel = _seed_mkbhd(db)
    updated = client.put(f"/api/channels/{channel.id}", json={"category_id": "intl-news"})
    assert updated.status_code == 200
    assert updated.json()["category"]["slug"] == "intl-news"

    invalid = client.put(f"/api/channels/{channel.id}", json={"category_id": "nope"})
    assert invalid.status_code == 400

    cleared = client.put(f"/api/channels/{channel.id}", json={"category_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["category_id"] is None
    assert cleared.json()["category"] is None


def test_create_channel_rejects_unknown_category(client, db):
    apply_catalog(db, import_resolved=False)
    db.commit()
    response = client.post("/api/channels/", json={
        "channel_id": "example",
        "channel_name": "Example",
        "channel_url": "https://www.youtube.com/@example",
        "category_id": "not-a-real-category",
    })
    assert response.status_code == 400
