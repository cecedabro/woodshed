"""Tests for Sessions API (SPEC 5.4–5.6, backend.md §sessions).

Routes:
    POST /api/sessions                        — create a session
    POST /api/sessions/{id}/blocks            — log a block
    POST /api/sessions/{id}/finish            — finish a session
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


# ---------------------------------------------------------------------------
# POST /api/sessions — create
# ---------------------------------------------------------------------------


def test_create_session_returns_id(client: TestClient) -> None:
    """POST /api/sessions returns 201 with an id."""
    _login(client)
    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert isinstance(data["id"], int)
    assert data["id"] > 0


def test_unauthenticated_create_returns_401(client: TestClient) -> None:
    """POST /api/sessions returns 401 when not logged in."""
    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 401


def test_unauthenticated_log_block_returns_401(client: TestClient) -> None:
    """POST /api/sessions/{id}/blocks returns 401 when not logged in."""
    resp = client.post("/api/sessions/1/blocks", json={})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/sessions/{id}/blocks — log a block
# ---------------------------------------------------------------------------


def test_log_block_stores_all_values(client: TestClient, db: Session) -> None:
    """POST /api/sessions/{id}/blocks stores row with all values."""
    from app.models import Item, PracticeSession

    _login(client)

    item = Item(kind="song", title="Blues in E")
    db.add(item)
    db.flush()

    base_time = datetime.now(UTC) - timedelta(minutes=5)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=5)):
        resp = client.post(
            f"/api/sessions/{session.id}/blocks",
            json={
                "item_id": item.id,
                "item_title": "Blues in E",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 280,
                "bpm": 120,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stored"] is True
    assert data["played_seconds"] == 280

    blocks = session.blocks
    assert len(blocks) == 1
    b = blocks[0]
    assert b.item_id == item.id
    assert b.item_title == "Blues in E"
    assert b.position == 0
    assert b.planned_seconds == 300
    assert b.played_seconds == 280
    assert b.bpm == 120


def test_log_block_clamps_played_seconds(client: TestClient, db: Session) -> None:
    """Log block clamps played_seconds to elapsed_since_start + 60."""
    from datetime import datetime, timedelta
    from unittest.mock import patch

    from app.models import Item, PracticeSession

    _login(client)

    item = Item(kind="song", title="Test Song")
    db.add(item)
    db.flush()

    base_time = datetime.now(UTC) - timedelta(minutes=2)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    base_time = datetime.now(UTC) - timedelta(minutes=2)

    # elapsed = 2 min = 120s; max_played = 120 + 60 = 180
    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=2)):
        resp = client.post(
            f"/api/sessions/{session.id}/blocks",
            json={
                "item_id": item.id,
                "item_title": "Test Song",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 500,  # should be clamped to 180
                "bpm": None,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stored"] is True
    assert data["played_seconds"] == 180

    blocks = session.blocks
    assert len(blocks) == 1
    assert blocks[0].played_seconds == 180


def test_log_block_under_10_seconds_stored_false(client: TestClient, db: Session) -> None:
    """Log block with <10s returned played_seconds returns stored=false."""
    from datetime import datetime, timedelta
    from unittest.mock import patch

    from app.models import PracticeSession

    _login(client)

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    # elapsed = 60s; max_played = 60 + 60 = 120; clamped = 5
    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=1)):
        resp = client.post(
            f"/api/sessions/{session.id}/blocks",
            json={
                "item_id": None,
                "item_title": "",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 5,
                "bpm": None,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stored"] is False

    # Verify no block was stored
    blocks = session.blocks
    assert len(blocks) == 0


def test_log_block_bpm_updates_item(client: TestClient, db: Session) -> None:
    """Log block with BPM updates item.current_bpm."""
    from datetime import datetime, timedelta
    from unittest.mock import patch

    from app.models import Item, PracticeSession

    _login(client)

    item = Item(kind="song", title="BPM Test", current_bpm=100)
    db.add(item)
    db.flush()

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=1)):
        resp = client.post(
            f"/api/sessions/{session.id}/blocks",
            json={
                "item_id": item.id,
                "item_title": "BPM Test",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 60,
                "bpm": 130,
            },
        )

    assert resp.status_code == 200
    db.expire(item)
    assert item.current_bpm == 130


# ---------------------------------------------------------------------------
# POST /api/sessions/{id}/finish — finish
# ---------------------------------------------------------------------------


def test_finish_returns_summary(client: TestClient, db: Session) -> None:
    """POST /api/sessions/{id}/finish returns summary with blocks, minutes, per_block."""
    from datetime import datetime, timedelta

    from app.models import Item, PracticeSession, SessionBlock

    _login(client)

    item = Item(kind="song", title="Summary Song")
    db.add(item)
    db.flush()

    session = PracticeSession()
    db.add(session)
    db.flush()

    base_time = datetime.now(UTC) - timedelta(minutes=10)

    # Pre-populate blocks
    block1 = SessionBlock(
        session_id=session.id,
        item_id=item.id,
        item_title="Summary Song",
        position=0,
        planned_seconds=300,
        played_seconds=250,
        bpm=120,
        ended_at=base_time + timedelta(minutes=5),
    )
    block2 = SessionBlock(
        session_id=session.id,
        item_id=item.id,
        item_title="Warm up",
        position=1,
        planned_seconds=120,
        played_seconds=90,
        bpm=100,
        ended_at=base_time + timedelta(minutes=10),
    )
    db.add_all([block1, block2])
    db.commit()

    resp = client.post(f"/api/sessions/{session.id}/finish")
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocks"] == 2
    assert data["minutes"] == (250 + 90) // 60  # 340 // 60 = 5
    assert len(data["per_block"]) == 2
    assert data["per_block"][0]["item_title"] == "Summary Song"
    assert data["per_block"][0]["planned_seconds"] == 300
    assert data["per_block"][0]["played_seconds"] == 250
    assert data["per_block"][0]["bpm"] == 120
    assert data["per_block"][1]["item_title"] == "Warm up"


def test_finish_unknown_session_returns_404(client: TestClient) -> None:
    """POST /api/sessions/99999/finish returns 404 for unknown session."""
    _login(client)
    resp = client.post("/api/sessions/99999/finish")
    assert resp.status_code == 404
    assert "Not Found" in resp.json()["detail"]
