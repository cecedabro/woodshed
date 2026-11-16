"""Tests for tempo_history – per-day max BPM tracking (SPEC 7.1).

Validates the ``tempo_history(db, item_id)`` function in ``app.stats``
and the rendering of the tempo section on the item detail page.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Item, PracticeSession, SessionBlock
from app.stats import tempo_history

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_blocks(
    db: Session,
    item_id: int,
    entries: list[tuple[datetime, int | None]],
) -> list[SessionBlock]:
    """Create a practice session with blocks for *item_id*.

    Each entry is ``(ended_at, bpm)`` where *bpm* may be ``None``.
    Returns the created ``SessionBlock`` instances.
    """
    session = PracticeSession()
    db.add(session)
    db.flush()
    blocks: list[SessionBlock] = []
    for idx, (ended_at, bpm) in enumerate(entries):
        block = SessionBlock(
            session_id=session.id,
            item_id=item_id,
            item_title="Test",
            position=idx,
            planned_seconds=300,
            played_seconds=300,
            bpm=bpm,
            ended_at=ended_at,
        )
        db.add(block)
        blocks.append(block)
    db.commit()
    return blocks


# ---------------------------------------------------------------------------
# tempo_history – unit tests
# ---------------------------------------------------------------------------


def test_empty_returns_empty_list(db: Session) -> None:
    """No blocks for the item => empty list."""
    item = Item(kind="song", title="Empty")
    db.add(item)
    db.commit()
    db.refresh(item)

    result = tempo_history(db, item.id)
    assert result == []


def test_no_matching_blocks_returns_empty_list(db: Session) -> None:
    """Blocks exist but none match the item => empty list."""
    item_a = Item(kind="song", title="A")
    item_b = Item(kind="song", title="B")
    db.add(item_a)
    db.add(item_b)
    db.commit()
    db.refresh(item_a)
    db.refresh(item_b)

    _make_blocks(
        db,
        item_a.id,
        [
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), 100),
        ],
    )

    result = tempo_history(db, item_b.id)
    assert result == []


def test_null_bpm_ignored(db: Session) -> None:
    """BPM=NULL rows are excluded from the result."""
    item = Item(kind="song", title="Null BPM")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), None),
            (datetime(2025, 6, 2, 18, 0, tzinfo=UTC), 120),
        ],
    )

    result = tempo_history(db, item.id)
    assert len(result) == 1
    assert result[0] == (datetime(2025, 6, 2).date(), 120)


def test_max_bpm_same_day(db: Session) -> None:
    """Multiple blocks on the same local date return the maximum BPM."""
    item = Item(kind="song", title="Max BPM")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 1, 10, 0, tzinfo=UTC), 80),
            (datetime(2025, 6, 1, 14, 0, tzinfo=UTC), 100),
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), 90),
        ],
    )

    result = tempo_history(db, item.id)
    assert len(result) == 1
    assert result[0] == (datetime(2025, 6, 1).date(), 100)


def test_oldest_first_ordering(db: Session) -> None:
    """Results are ordered oldest-first by local date."""
    item = Item(kind="song", title="Ordered")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 3, 18, 0, tzinfo=UTC), 120),
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), 80),
            (datetime(2025, 6, 2, 18, 0, tzinfo=UTC), 100),
        ],
    )

    result = tempo_history(db, item.id)
    assert len(result) == 3
    assert result[0] == (datetime(2025, 6, 1).date(), 80)
    assert result[1] == (datetime(2025, 6, 2).date(), 100)
    assert result[2] == (datetime(2025, 6, 3).date(), 120)


def test_mixed_null_and_valid(db: Session) -> None:
    """NULL and valid BPMs on the same/other days handled correctly."""
    item = Item(kind="song", title="Mixed")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 1, 10, 0, tzinfo=UTC), 60),
            (datetime(2025, 6, 1, 14, 0, tzinfo=UTC), None),
            (datetime(2025, 6, 2, 10, 0, tzinfo=UTC), 90),
            (datetime(2025, 6, 2, 14, 0, tzinfo=UTC), 110),
        ],
    )

    result = tempo_history(db, item.id)
    assert len(result) == 2
    assert result[0] == (datetime(2025, 6, 1).date(), 60)
    assert result[1] == (datetime(2025, 6, 2).date(), 110)


def test_single_block(db: Session) -> None:
    """A single block returns a single entry."""
    item = Item(kind="song", title="Single")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 3, 15, 20, 30, tzinfo=UTC), 75),
        ],
    )

    result = tempo_history(db, item.id)
    assert len(result) == 1
    assert result[0] == (datetime(2025, 3, 15).date(), 75)


def test_all_null_bpm_returns_empty(db: Session) -> None:
    """Every block has NULL bpm => empty list."""
    item = Item(kind="song", title="All Null")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), None),
            (datetime(2025, 6, 2, 18, 0, tzinfo=UTC), None),
        ],
    )

    result = tempo_history(db, item.id)
    assert result == []


# ---------------------------------------------------------------------------
# Item detail page – integration tests
# ---------------------------------------------------------------------------


def test_page_without_tempo_history(client, db: Session) -> None:
    """Item page renders fine with no tempo history data."""
    item = Item(kind="song", title="No Tempo")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/items/{item.id}")
    assert resp.status_code == 200
    assert "Tempo History" not in resp.text
    assert "tempo-svg" not in resp.text


def test_page_with_tempo_history_text(client, db: Session) -> None:
    """Item page renders joined BPM text from tempo history."""
    item = Item(kind="song", title="Tempo Text")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), 60),
            (datetime(2025, 6, 2, 18, 0, tzinfo=UTC), 72),
            (datetime(2025, 6, 3, 18, 0, tzinfo=UTC), 84),
        ],
    )

    resp = client.get(f"/items/{item.id}")
    assert resp.status_code == 200
    assert "60 → 72 → 84" in resp.text


def test_page_with_tempo_svg(client, db: Session) -> None:
    """Item page renders an inline SVG when tempo history exists."""
    item = Item(kind="song", title="Tempo SVG")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), 60),
            (datetime(2025, 6, 2, 18, 0, tzinfo=UTC), 80),
        ],
    )

    resp = client.get(f"/items/{item.id}")
    assert resp.status_code == 200
    assert "<svg" in resp.text
    assert 'class="tempo-svg"' in resp.text
    assert 'aria-label="Tempo history"' in resp.text


def test_page_tempo_section_with_single_entry(client, db: Session) -> None:
    """A single tempo point still renders in the section."""
    item = Item(kind="song", title="Single Entry")
    db.add(item)
    db.commit()
    db.refresh(item)

    _make_blocks(
        db,
        item.id,
        [
            (datetime(2025, 6, 1, 18, 0, tzinfo=UTC), 90),
        ],
    )

    resp = client.get(f"/items/{item.id}")
    assert resp.status_code == 200
    assert "90" in resp.text
