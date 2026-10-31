"""Pagination for crawl sessions and the New Session channel list."""
from datetime import datetime, timedelta

from app.config import settings
from app.models.channel import Channel
from app.models.crawl_session import CrawlSession

# Don't start the background scheduler while these tests boot the app.
settings.ENABLE_SCHEDULER = False


def _session(name, created_at, status="completed", recurrence_hours=None, parent_session_id=None):
    return CrawlSession(
        session_name=name,
        session_type="manual",
        status=status,
        channel_ids=[],
        filter_keywords=[],
        recurrence_hours=recurrence_hours,
        recurrence_active=True,
        parent_session_id=parent_session_id,
        created_at=created_at,
    )


def test_sessions_page_size_defaults_to_10_and_preserves_filters(client, db):
    base = datetime(2024, 6, 1, 0, 0, 0)
    for i in range(25):
        db.add(_session(
            f"Session {i:02d}",
            base + timedelta(minutes=i),
            status="completed" if i % 2 == 0 else "failed",
            # First 12 are recurring templates so the recurring list itself pages.
            recurrence_hours=3 if i < 12 else None,
        ))
    db.commit()

    parent = db.query(CrawlSession).filter(CrawlSession.session_name == "Session 00").one()
    parent.recurrence_active = False
    db.add(_session(
        "Child run",
        base + timedelta(days=1),
        status="running",
        recurrence_hours=3,
        parent_session_id=parent.id,
    ))
    db.commit()

    first = client.get("/api/sessions")
    assert first.status_code == 200
    body = first.json()
    assert isinstance(body, list)
    assert len(body) == 10
    assert first.headers["x-total-count"] == "26"
    # Newest first, with id as a tie-break. The child run is the newest row.
    assert body[0]["session_name"] == "Child run"
    assert [row["session_name"] for row in body[1:3]] == ["Session 24", "Session 23"]

    second = client.get("/api/sessions?skip=10&limit=10")
    assert [row["session_name"] for row in second.json()[:2]] == ["Session 15", "Session 14"]
    assert second.headers["x-total-count"] == "26"

    third = client.get("/api/sessions?skip=20&limit=10")
    assert len(third.json()) == 6
    assert third.json()[-1]["session_name"] == "Session 00"

    # Status filter still applies, and it pages independently of the full list.
    completed = client.get("/api/sessions?status=completed&limit=10")
    assert completed.headers["x-total-count"] == "13"
    assert len(completed.json()) == 10
    assert all(row["status"] == "completed" for row in completed.json())
    completed_page2 = client.get("/api/sessions?status=completed&skip=10&limit=10")
    assert [row["session_name"] for row in completed_page2.json()] == [
        "Session 04",
        "Session 02",
        "Session 00",
    ]

    # Recurring templates only: child runs stay out, paused templates stay in.
    recurring = client.get("/api/sessions?recurring=true&limit=10")
    assert recurring.status_code == 200
    assert recurring.headers["x-total-count"] == "12"
    assert len(recurring.json()) == 10
    names = [row["session_name"] for row in recurring.json()]
    assert "Child run" not in names
    assert names[0] == "Session 11"
    recurring_page2 = client.get("/api/sessions?recurring=true&skip=10&limit=10")
    assert [row["session_name"] for row in recurring_page2.json()] == ["Session 01", "Session 00"]
    assert recurring_page2.json()[-1]["recurrence_active"] is False

    # Older pages past the end are empty, and the total is unchanged.
    empty = client.get("/api/sessions?skip=100&limit=10")
    assert empty.status_code == 200
    assert empty.json() == []
    assert empty.headers["x-total-count"] == "26"


def test_recurrence_actions_still_work(client, db):
    base = datetime(2024, 7, 1, 0, 0, 0)
    session = _session("Recurring", base, status="running", recurrence_hours=2)
    db.add(session)
    db.commit()
    db.refresh(session)

    paused = client.put(f"/api/sessions/{session.id}/recurrence/pause")
    assert paused.status_code == 200
    db.refresh(session)
    assert session.recurrence_active is False

    resumed = client.put(f"/api/sessions/{session.id}/recurrence/resume")
    assert resumed.status_code == 200
    db.refresh(session)
    assert session.recurrence_active is True

    deleted = client.delete(f"/api/sessions/{session.id}")
    assert deleted.status_code == 204
    assert db.query(CrawlSession).filter(CrawlSession.id == session.id).first() is None


def test_new_session_channel_list_pages_and_sorts(client, db):
    base = datetime(2024, 1, 1, 0, 0, 0)
    names = ["Zulu", "alpha", "Mike", "bravo"] + [f"Chan {i:02d}" for i in range(8)]
    for i, name in enumerate(names):
        db.add(Channel(
            channel_id=f"ch-{i}",
            channel_name=name,
            channel_url=f"https://www.youtube.com/@ch{i}",
            keywords=[],
            crawl_enabled=True,
            crawl_frequency="manual",
            created_at=base + timedelta(hours=i),
            updated_at=base + timedelta(hours=i),
        ))
    db.commit()

    by_name = client.get("/api/channels?skip=0&limit=10&sort_by=name")
    assert by_name.status_code == 200
    assert by_name.headers["x-total-count"] == "12"
    assert len(by_name.json()) == 10
    page_names = [row["channel_name"] for row in by_name.json()]
    assert page_names == sorted(page_names, key=str.lower)

    page2 = client.get("/api/channels?skip=10&limit=10&sort_by=name")
    assert len(page2.json()) == 2
    assert page2.headers["x-total-count"] == "12"

    # Date added, newest first — the previous client-side sort.
    added = client.get("/api/channels?limit=10&sort_by=added")
    assert [row["channel_name"] for row in added.json()][:2] == ["Chan 07", "Chan 06"]

    # Callers that omit sort_by still get a plain list (channels page).
    plain = client.get("/api/channels?limit=50")
    assert plain.status_code == 200
    assert isinstance(plain.json(), list)
    assert plain.headers["x-total-count"] == "12"

    invalid = client.get("/api/channels?sort_by=nope")
    assert invalid.status_code == 400
