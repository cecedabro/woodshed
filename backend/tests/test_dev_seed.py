"""Tests for seed_db in backend/scripts/dev.py (T42).

Verifies:
- Correct row counts after seeding (8 items, 3 routines, 30 sessions across 10 weeks).
- Idempotency: calling seed_db twice does not create duplicate rows.
"""

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

# scripts/ is on the path when running via ``pytest backend/``
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from scripts.dev import seed_db  # noqa: E402

# ---------------------------------------------------------------------------
# Row counts
# ---------------------------------------------------------------------------


def test_seed_creates_8_items(db: Session) -> None:
    """seed_db inserts exactly 8 items (4 songs + 4 exercises)."""
    seed_db(db)

    count = db.scalar(text("SELECT COUNT(*) FROM item"))
    assert count == 8


def test_seed_creates_3_routines(db: Session) -> None:
    """seed_db inserts exactly 3 routines."""
    seed_db(db)

    count = db.scalar(text("SELECT COUNT(*) FROM routine"))
    assert count == 3


def test_seed_creates_30_sessions(db: Session) -> None:
    """10 weeks × 3 routines = 30 practice sessions."""
    seed_db(db)

    count = db.scalar(text("SELECT COUNT(*) FROM practice_session"))
    assert count == 30


def test_seed_creates_27_session_blocks(db: Session) -> None:
    """
    Morning warmup: 3 blocks × 10 weeks = 30
    Rock session:    3 blocks × 10 weeks = 30
    Evening practice: 2 blocks × 10 weeks = 20
    Total = 80 session blocks.
    """
    seed_db(db)

    count = db.scalar(text("SELECT COUNT(*) FROM session_block"))
    assert count == 80


def test_seed_creates_10_distinct_weeks(db: Session) -> None:
    """Sessions span exactly 10 distinct weeks (Mondays)."""
    seed_db(db)

    # Count distinct week-Mondays from practice_session started_at
    count = db.scalar(
        text(
            "SELECT COUNT(DISTINCT started_at::date - EXTRACT(dow FROM started_at)::int) "
            "FROM practice_session"
        )
    )
    assert count == 10


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_seed_idempotent_items(db: Session) -> None:
    """Running seed_db twice produces the same number of items."""
    seed_db(db)
    first_count = db.scalar(text("SELECT COUNT(*) FROM item"))

    seed_db(db)
    second_count = db.scalar(text("SELECT COUNT(*) FROM item"))

    assert first_count == second_count == 8


def test_seed_idempotent_routines(db: Session) -> None:
    """Running seed_db twice produces the same number of routines."""
    seed_db(db)
    first_count = db.scalar(text("SELECT COUNT(*) FROM routine"))

    seed_db(db)
    second_count = db.scalar(text("SELECT COUNT(*) FROM routine"))

    assert first_count == second_count == 3


def test_seed_idempotent_sessions(db: Session) -> None:
    """Running seed_db twice produces the same number of sessions."""
    seed_db(db)
    first_count = db.scalar(text("SELECT COUNT(*) FROM practice_session"))

    seed_db(db)
    second_count = db.scalar(text("SELECT COUNT(*) FROM practice_session"))

    assert first_count == second_count == 30


def test_seed_idempotent_blocks(db: Session) -> None:
    """Running seed_db twice produces the same number of routine blocks."""
    seed_db(db)
    first_count = db.scalar(text("SELECT COUNT(*) FROM routine_block"))

    seed_db(db)
    second_count = db.scalar(text("SELECT COUNT(*) FROM routine_block"))

    assert first_count == second_count == 8


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


def test_seed_items_have_correct_kinds(db: Session) -> None:
    """Items include both 'song' and 'exercise' kinds."""
    seed_db(db)

    songs = db.scalar(text("SELECT COUNT(*) FROM item WHERE kind = 'song'"))
    exercises = db.scalar(text("SELECT COUNT(*) FROM item WHERE kind = 'exercise'"))
    assert songs == 4
    assert exercises == 4


def test_seed_routine_blocks_have_positions(db: Session) -> None:
    """Routine blocks have unique (routine_id, position) pairs."""
    seed_db(db)

    dups = db.scalar(
        text(
            "SELECT COUNT(*) FROM ("
            "  SELECT routine_id, position, COUNT(*) "
            "  FROM routine_block "
            "  GROUP BY routine_id, position "
            "  HAVING COUNT(*) > 1"
            ") t"
        )
    )
    assert dups == 0


def test_seed_bpm_increases_over_weeks(db: Session) -> None:
    """BPM in session blocks increases across weeks for the first routine."""
    seed_db(db)

    rows = db.execute(
        text(
            "SELECT sb.bpm "
            "FROM session_block sb "
            "JOIN practice_session ps ON ps.id = sb.session_id "
            "JOIN routine r ON r.id = ps.routine_id "
            "WHERE r.name = 'Morning blues warmup' "
            "  AND sb.position = 0 "
            "ORDER BY ps.started_at ASC"
        )
    ).fetchall()

    bpms = [r[0] for r in rows]
    assert len(bpms) == 10
    # First week = base BPM (80), last week = 80 + 9*2 = 98
    assert bpms[0] == 80
    assert bpms[9] == 98
    # Steady increment of 2 per week
    for i in range(1, len(bpms)):
        assert bpms[i] == bpms[i - 1] + 2
