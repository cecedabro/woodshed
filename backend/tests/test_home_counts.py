"""Tests for home page routine counts — multiplication fix (SPEC 5.1).

The home page query must count blocks/minutes and the last session in
separate subqueries so that N blocks × M sessions never inflate the
counts ("30 blocks · 250 min" for a 3-block, 25-min routine).

Routes: GET /
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Item as ItemModel
from app.models import PracticeSession, Routine, RoutineBlock


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


# ---------------------------------------------------------------------------
# GET / — blocks and minutes are never inflated by sessions
# ---------------------------------------------------------------------------


def test_home_routine_counts_not_inflated_by_sessions(client: TestClient, db: Session) -> None:
    """A routine with blocks of 5, 10 and 5 min and 4 finished sessions shows
    '3 blocks · 20 min', not inflated by the 4 sessions.
    """
    # Create 3 blocks: 5 + 10 + 5 = 20 min
    song = ItemModel(kind="song", title="Test song")
    db.add(song)
    db.flush()

    routine = Routine(name="Counted routine")
    db.add(routine)
    db.flush()

    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=song.id, minutes=5))
    db.add(RoutineBlock(routine_id=routine.id, position=1, item_id=song.id, minutes=10))
    db.add(RoutineBlock(routine_id=routine.id, position=2, item_id=song.id, minutes=5))

    # Create 4 finished sessions
    for i in range(4):
        session = PracticeSession(
            routine_id=routine.id,
            started_at=datetime(2025, 3, i + 1, tzinfo=UTC),
            ended_at=datetime(2025, 3, i + 1, 10, 0, tzinfo=UTC),
        )
        db.add(session)

    db.commit()

    _login(client)
    resp = client.get("/")

    assert resp.status_code == 200
    # 3 blocks, 20 minutes — NOT 12 blocks, 100 minutes
    assert "3 blocks" in resp.text
    assert "20 min" in resp.text
    # Sanity: should not show inflated values
    assert "12 blocks" not in resp.text
    assert "100 min" not in resp.text


def test_home_no_blocks_shows_zero(client: TestClient, db: Session) -> None:
    """A routine with no blocks shows '0 blocks · 0 min'."""
    routine = Routine(name="Empty routine")
    db.add(routine)
    db.commit()

    _login(client)
    resp = client.get("/")

    assert resp.status_code == 200
    assert "0 blocks" in resp.text
    assert "0 min" in resp.text


def test_home_routine_with_one_block_one_session(client: TestClient, db: Session) -> None:
    """A routine with 1 block of 15 min and 1 session shows '1 blocks · 15 min'."""
    song = ItemModel(kind="song", title="One block song")
    db.add(song)
    db.flush()

    routine = Routine(name="One block routine")
    db.add(routine)
    db.flush()

    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=song.id, minutes=15))
    db.commit()

    # Add one session after commit
    session = PracticeSession(
        routine_id=routine.id,
        started_at=datetime(2025, 6, 1, tzinfo=UTC),
        ended_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
    )
    db.add(session)
    db.commit()

    _login(client)
    resp = client.get("/")

    assert resp.status_code == 200
    assert "1 blocks" in resp.text
    assert "15 min" in resp.text


def test_home_routine_with_blocks_no_sessions(client: TestClient, db: Session) -> None:
    """A routine with blocks but no sessions shows correct counts."""
    song = ItemModel(kind="song", title="No session song")
    db.add(song)
    db.flush()

    routine = Routine(name="No session routine")
    db.add(routine)
    db.flush()

    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=song.id, minutes=8))
    db.add(RoutineBlock(routine_id=routine.id, position=1, item_id=song.id, minutes=12))
    db.commit()

    _login(client)
    resp = client.get("/")

    assert resp.status_code == 200
    assert "2 blocks" in resp.text
    assert "20 min" in resp.text


# ---------------------------------------------------------------------------
# GET / — multiple routines: each shows its own correct count
# ---------------------------------------------------------------------------


def test_home_multiple_routines_each_has_correct_count(client: TestClient, db: Session) -> None:
    """Two routines with different block/session counts each show their
    own correct block/minute counts on the home page.

    Routine A: 2 blocks (10 + 20 = 30 min), 3 sessions
    Routine B: 1 block (5 min), 0 sessions
    """
    song_a = ItemModel(kind="song", title="Song A")
    song_b = ItemModel(kind="song", title="Song B")
    db.add_all([song_a, song_b])
    db.flush()

    routine_a = Routine(name="Routine A")
    routine_b = Routine(name="Routine B")
    db.add_all([routine_a, routine_b])
    db.flush()

    # Routine A: 2 blocks = 30 min
    db.add(RoutineBlock(routine_id=routine_a.id, position=0, item_id=song_a.id, minutes=10))
    db.add(RoutineBlock(routine_id=routine_a.id, position=1, item_id=song_a.id, minutes=20))

    # Routine A: 3 sessions
    for i in range(3):
        session = PracticeSession(
            routine_id=routine_a.id,
            started_at=datetime(2025, 3, i + 1, tzinfo=UTC),
            ended_at=datetime(2025, 3, i + 1, 10, 0, tzinfo=UTC),
        )
        db.add(session)

    # Routine B: 1 block = 5 min, no sessions
    db.add(RoutineBlock(routine_id=routine_b.id, position=0, item_id=song_b.id, minutes=5))

    db.commit()

    _login(client)
    resp = client.get("/")

    assert resp.status_code == 200
    assert "30 min" in resp.text
    assert "5 min" in resp.text
    assert "2 blocks" in resp.text
    assert "1 blocks" in resp.text
