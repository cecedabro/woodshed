"""Tests for GET /progress part 2 — tempo progress table (SPEC 7.2).

Tests ``item_tempo_progress`` from ``stats.py`` and the BPM table
rendered on the /progress page.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Item, PracticeSession, SessionBlock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(db: Session, title: str = "Blues in A", **kwargs: object) -> Item:
    i = Item(kind="song", title=title, **kwargs)
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def _session(
    db: Session,
    item: Item,
    bpm: int | None,
    started_at: datetime,
    played_seconds: int = 600,
) -> PracticeSession:
    session = PracticeSession(
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=played_seconds // 60),
    )
    db.add(session)
    db.flush()

    block = SessionBlock(
        session=session,
        item_id=item.id,
        item_title=item.title,
        position=1,
        planned_seconds=played_seconds,
        played_seconds=played_seconds,
        bpm=bpm,
        ended_at=session.ended_at,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return session


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


def _progress_html(client: TestClient) -> str:
    _login(client)
    resp = client.get("/progress")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
    return resp.text


# ---------------------------------------------------------------------------
# Unit tests: item_tempo_progress
# ---------------------------------------------------------------------------


def test_empty_returns_empty_list(db: Session) -> None:
    from app.stats import item_tempo_progress

    result = item_tempo_progress(db)
    assert result == []


def test_no_bpm_returns_empty_list(db: Session) -> None:
    """Blocks with bpm=NULL are excluded."""
    from app.stats import item_tempo_progress

    item = _item(db, title="No BPM blues")
    _session(db, item, bpm=None, started_at=datetime.now(UTC) - timedelta(days=10))
    result = item_tempo_progress(db)
    assert result == []


def test_single_block_returns_one_row(db: Session) -> None:
    """One block → one row with diff=0."""
    from app.stats import item_tempo_progress

    item = _item(db, title="One tempo")
    _session(db, item, bpm=80, started_at=datetime.now(UTC) - timedelta(days=5))
    result = item_tempo_progress(db)
    assert len(result) == 1
    assert result[0]["title"] == "One tempo"
    assert result[0]["first_bpm"] == 80
    assert result[0]["latest_bpm"] == 80
    assert result[0]["diff"] == 0


def test_bpm_increase_shows_positive_diff(db: Session) -> None:
    """Two blocks with increasing BPM → positive diff."""
    from app.stats import item_tempo_progress

    item = _item(db, title="Speed demon")
    now = datetime.now(UTC)
    _session(db, item, bpm=80, started_at=now - timedelta(days=30))
    _session(db, item, bpm=104, started_at=now - timedelta(days=5))
    result = item_tempo_progress(db)
    assert len(result) == 1
    assert result[0]["first_bpm"] == 80
    assert result[0]["latest_bpm"] == 104
    assert result[0]["diff"] == 24


def test_bpm_decrease_shows_negative_diff(db: Session) -> None:
    """Two blocks with decreasing BPM → negative diff."""
    from app.stats import item_tempo_progress

    item = _item(db, title="Slow down")
    now = datetime.now(UTC)
    _session(db, item, bpm=120, started_at=now - timedelta(days=30))
    _session(db, item, bpm=90, started_at=now - timedelta(days=5))
    result = item_tempo_progress(db)
    assert len(result) == 1
    assert result[0]["first_bpm"] == 120
    assert result[0]["latest_bpm"] == 90
    assert result[0]["diff"] == -30


def test_middle_blocks_ignored(db: Session) -> None:
    """Only the earliest and latest blocks in the window count."""
    from app.stats import item_tempo_progress

    item = _item(db, title="Middle ignored")
    now = datetime.now(UTC)
    _session(db, item, bpm=60, started_at=now - timedelta(days=80))
    _session(db, item, bpm=100, started_at=now - timedelta(days=40))
    _session(db, item, bpm=90, started_at=now - timedelta(days=10))
    result = item_tempo_progress(db)
    assert len(result) == 1
    assert result[0]["first_bpm"] == 60
    assert result[0]["latest_bpm"] == 90
    assert result[0]["diff"] == 30


def test_91_day_block_excluded(db: Session) -> None:
    """A block older than 90 days is excluded from the window."""
    from app.stats import item_tempo_progress

    item = _item(db, title="Ancient tempo")
    now = datetime.now(UTC)
    # Only one block at 91 days — should not appear.
    _session(db, item, bpm=60, started_at=now - timedelta(days=91))
    result = item_tempo_progress(db)
    assert result == []


def test_90_day_block_included(db: Session) -> None:
    """A block exactly 90 days old is still included."""
    from app.stats import item_tempo_progress

    item = _item(db, title="Exactly 90")
    now = datetime.now(UTC)
    _session(db, item, bpm=72, started_at=now - timedelta(days=90))
    result = item_tempo_progress(db)
    assert len(result) == 1
    assert result[0]["first_bpm"] == 72


def test_multiple_items_sorted_by_first_bpm(db: Session) -> None:
    """Results are ordered by first_bpm ASC, title ASC."""
    from app.stats import item_tempo_progress

    now = datetime.now(UTC)

    b = _item(db, title="Blue")
    _session(db, b, bpm=100, started_at=now - timedelta(days=5))

    a = _item(db, title="Alpha")
    _session(db, a, bpm=60, started_at=now - timedelta(days=5))

    c = _item(db, title="Charlie")
    _session(db, c, bpm=60, started_at=now - timedelta(days=5))

    result = item_tempo_progress(db)
    assert len(result) == 3
    assert result[0]["first_bpm"] == 60
    assert result[0]["title"] == "Alpha"
    assert result[1]["first_bpm"] == 60
    assert result[1]["title"] == "Charlie"
    assert result[2]["first_bpm"] == 100


def test_mixed_null_and_valid_bpm(db: Session) -> None:
    """Items with only NULL BPM blocks don't appear."""
    from app.stats import item_tempo_progress

    now = datetime.now(UTC)

    bpm_item = _item(db, title="Has BPM")
    _session(db, bpm_item, bpm=80, started_at=now - timedelta(days=5))

    no_bpm_item = _item(db, title="No BPM")
    _session(db, no_bpm_item, bpm=None, started_at=now - timedelta(days=5))

    result = item_tempo_progress(db)
    assert len(result) == 1
    assert result[0]["title"] == "Has BPM"


# ---------------------------------------------------------------------------
# Page rendering tests
# ---------------------------------------------------------------------------


def test_progress_page_contains_tempo_section(client: TestClient, db: Session) -> None:
    """When there are BPM items, the tempo section renders."""
    item = _item(db, title="Tempo item")
    _session(db, item, bpm=80, started_at=datetime.now(UTC) - timedelta(days=5))
    html = _progress_html(client)
    assert "Tempo, last 90 days" in html
    assert "Tempo item" in html


def test_progress_page_shows_bpm_values(client: TestClient, db: Session) -> None:
    """The table shows first BPM, latest BPM and the change string."""
    item = _item(db, title="BPM page test")
    _session(db, item, bpm=70, started_at=datetime.now(UTC) - timedelta(days=10))
    _session(db, item, bpm=94, started_at=datetime.now(UTC) - timedelta(days=2))
    html = _progress_html(client)
    assert "70" in html
    assert "94" in html
    assert "24 bpm" in html


def test_progress_page_delta_up_class(client: TestClient, db: Session) -> None:
    """Positive diff shows with a + prefix in the row value."""
    item = _item(db, title="Get faster")
    _session(db, item, bpm=80, started_at=datetime.now(UTC) - timedelta(days=10))
    _session(db, item, bpm=100, started_at=datetime.now(UTC) - timedelta(days=2))
    html = _progress_html(client)
    assert "+20 bpm" in html


def test_progress_page_delta_down_class(client: TestClient, db: Session) -> None:
    """Negative diff shows the negative number in the row value."""
    item = _item(db, title="Slow down")
    _session(db, item, bpm=120, started_at=datetime.now(UTC) - timedelta(days=10))
    _session(db, item, bpm=90, started_at=datetime.now(UTC) - timedelta(days=2))
    html = _progress_html(client)
    assert "-30 bpm" in html


def test_progress_page_no_tempo_section_when_empty(client: TestClient, db: Session) -> None:
    """When no items have BPM in the window, the tempo section is absent."""
    no_bpm_item = _item(db, title="No BPM item")
    _session(db, no_bpm_item, bpm=None, started_at=datetime.now(UTC) - timedelta(days=5))
    html = _progress_html(client)
    assert "Tempo, last 90 days" not in html


def test_progress_page_item_links_to_detail(client: TestClient, db: Session) -> None:
    """Item name in the tempo table links to /items/{id}."""
    item = _item(db, title="Link test")
    _session(db, item, bpm=80, started_at=datetime.now(UTC) - timedelta(days=5))
    html = _progress_html(client)
    assert f'href="/items/{item.id}"' in html


def test_progress_page_table_headers(client: TestClient, db: Session) -> None:
    """The tempo section shows the expected header."""
    item = _item(db, title="Header test")
    _session(db, item, bpm=80, started_at=datetime.now(UTC) - timedelta(days=5))
    html = _progress_html(client)
    assert "Tempo, last 90 days" in html
