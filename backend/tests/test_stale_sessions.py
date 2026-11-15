"""Tests for close_stale_sessions (SPEC 5.7).

A session left unfinished for 6 hours counts as finished at its last block's
end time.  5 h 59 min stays open; 6 h 1 min is closed.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PracticeSession, SessionBlock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


def _make_session(db: Session, started_at: datetime) -> PracticeSession:
    """Create a session and flush it."""
    s = PracticeSession(started_at=started_at)
    db.add(s)
    db.flush()
    return s


def _make_block(db: Session, session: PracticeSession, ended_at: datetime) -> None:
    """Add a block to a session and flush."""
    b = SessionBlock(
        session_id=session.id,
        item_title="Test",
        position=0,
        planned_seconds=300,
        played_seconds=250,
        ended_at=ended_at,
    )
    db.add(b)
    db.flush()


# ---------------------------------------------------------------------------
# Direct _close_stale_sessions tests
# ---------------------------------------------------------------------------


def test_session_open_5h59_stays_open(db: Session) -> None:
    """A session opened 5h59m ago is not stale (SPEC 5.7)."""
    from app.sessions import _close_stale_sessions

    now = datetime.now(UTC)
    started = now - timedelta(hours=5, minutes=59)
    session = _make_session(db, started)
    db.commit()

    _close_stale_sessions(db, now)
    db.expire(session)

    session = db.get(PracticeSession, session.id)
    assert session is not None
    assert session.ended_at is None


def test_session_open_6h1m_gets_ended_at_from_last_block(db: Session) -> None:
    """A session opened 6h1m with a block gets ended_at = block's ended_at."""
    from app.sessions import _close_stale_sessions

    now = datetime.now(UTC)
    block_ended = now - timedelta(hours=1)
    started = block_ended - timedelta(hours=5, minutes=1)
    session = _make_session(db, started)
    _make_block(db, session, block_ended)
    db.commit()

    _close_stale_sessions(db, now)

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session is not None
    assert session.ended_at == block_ended


def test_session_open_6h1m_no_blocks_gets_started_at(db: Session) -> None:
    """A stale session with no blocks gets ended_at = started_at."""
    from app.sessions import _close_stale_sessions

    now = datetime.now(UTC)
    started = now - timedelta(hours=6, minutes=1)
    session = _make_session(db, started)
    db.commit()

    _close_stale_sessions(db, now)

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session is not None
    assert session.ended_at == started


def test_already_ended_session_not_modified(db: Session) -> None:
    """A session that already has ended_at is not touched."""
    from app.sessions import _close_stale_sessions

    now = datetime.now(UTC)
    old_ended = now - timedelta(hours=1)
    started = old_ended - timedelta(hours=5)
    session = _make_session(db, started)
    session.ended_at = old_ended
    db.commit()

    _close_stale_sessions(db, now)

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session.ended_at == old_ended


def test_multiple_stale_sessions_all_closed(db: Session) -> None:
    """Multiple stale sessions are all closed."""
    from app.sessions import _close_stale_sessions

    now = datetime.now(UTC)

    s1 = _make_session(db, now - timedelta(hours=7))
    _make_block(db, s1, now - timedelta(hours=2))

    s2 = _make_session(db, now - timedelta(hours=8))

    db.commit()

    _close_stale_sessions(db, now)

    db.expire_all()

    s1 = db.get(PracticeSession, s1.id)
    assert s1.ended_at == now - timedelta(hours=2)
    s2 = db.get(PracticeSession, s2.id)
    assert s2.ended_at is not None


def test_stale_session_with_blocks_uses_last_block_ended_at(db: Session) -> None:
    """When a stale session has multiple blocks, ended_at = the last block's ended_at."""
    from app.sessions import _close_stale_sessions

    now = datetime.now(UTC)
    started = now - timedelta(hours=6, minutes=2)
    session = _make_session(db, started)

    _make_block(db, session, now - timedelta(hours=5))
    _make_block(db, session, now - timedelta(hours=3))
    last_block_ended = now - timedelta(hours=1)
    _make_block(db, session, last_block_ended)

    db.commit()

    _close_stale_sessions(db, now)

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session.ended_at == last_block_ended


# ---------------------------------------------------------------------------
# API-integrated tests: POST /api/sessions triggers close_stale
# ---------------------------------------------------------------------------


def test_create_session_closes_stale_sessions(client: TestClient, db: Session) -> None:
    """Creating a session triggers stale-session close."""
    _login(client)

    now = datetime.now(UTC)
    started = now - timedelta(hours=6, minutes=2)
    session = _make_session(db, started)
    db.commit()

    # Trigger stale close by creating a new session
    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 201

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session.ended_at is not None
    assert session.ended_at == started


def test_create_session_closes_stale_with_blocks(client: TestClient, db: Session) -> None:
    """Stale session with blocks gets ended_at from last block via API."""
    _login(client)

    now = datetime.now(UTC)
    block_ended = now - timedelta(hours=2)
    started = block_ended - timedelta(hours=4)
    session = _make_session(db, started)
    _make_block(db, session, block_ended)
    db.commit()

    client.post("/api/sessions", json={})

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session.ended_at == block_ended


def test_boundary_5h59m_not_closed_via_api(client: TestClient, db: Session) -> None:
    """5h59m is below threshold; creating a session does not close it."""
    _login(client)

    now = datetime.now(UTC)
    started = now - timedelta(hours=5, minutes=59)
    session = _make_session(db, started)
    db.commit()

    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 201

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session.ended_at is None


def test_boundary_6h01m_closed_via_api(client: TestClient, db: Session) -> None:
    """6h01m exceeds threshold; creating a session closes it."""
    _login(client)

    now = datetime.now(UTC)
    started = now - timedelta(hours=6, minutes=1)
    session = _make_session(db, started)
    db.commit()

    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 201

    db.expire(session)
    session = db.get(PracticeSession, session.id)
    assert session.ended_at is not None
