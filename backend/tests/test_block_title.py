"""Tests for SPEC 5.6 — server copies item title when logging a block.

The server fetches the title from the item record; the client sends only
``item_id``.  An unknown ``item_id`` returns 422 and nothing is stored.
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
# Title copying — SPEC 5.6
# ---------------------------------------------------------------------------


def test_block_title_copied_from_item(client: TestClient, db: Session) -> None:
    """Block title comes from the item database row, not the client payload."""
    from app.models import Item, PracticeSession

    _login(client)

    item = Item(kind="song", title="My Real Title")
    db.add(item)
    db.flush()

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=1)):
        resp = client.post(
            f"/api/sessions/{session.id}/blocks",
            json={
                "item_id": item.id,
                "item_title": "Client Lie",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 60,
                "bpm": None,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stored"] is True

    # The stored row has the item's title, not what the client sent.
    block = session.blocks[0]
    assert block.item_id == item.id
    assert block.item_title == "My Real Title"


def test_block_unknown_item_id_returns_422(client: TestClient, db: Session) -> None:
    """Unknown item_id → 422 and no block is stored."""
    from app.models import PracticeSession

    _login(client)

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=1)):
        resp = client.post(
            "/api/sessions/1/blocks",
            json={
                "item_id": 99999,
                "item_title": "Whatever",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 60,
                "bpm": None,
            },
        )

    assert resp.status_code == 422
    assert len(session.blocks) == 0


def test_block_unknown_item_id_no_404(client: TestClient, db: Session) -> None:
    """Unknown item_id returns 422, not 404."""
    from app.models import PracticeSession

    _login(client)

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=1)):
        resp = client.post(
            f"/api/sessions/{session.id}/blocks",
            json={
                "item_id": 99999,
                "item_title": "Whatever",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 60,
                "bpm": None,
            },
        )

    assert resp.status_code == 422
    detail = resp.json().get("detail", "")
    assert "not found" in detail.lower() or "Not found" in detail


def test_block_with_null_item_id_still_works(client: TestClient, db: Session) -> None:
    """null item_id → no title copy needed; block stores with empty title."""
    from app.models import PracticeSession

    _login(client)

    base_time = datetime.now(UTC) - timedelta(minutes=1)

    session = PracticeSession(started_at=base_time)
    db.add(session)
    db.commit()

    with patch("app.sessions.clock_now", return_value=base_time + timedelta(minutes=1)):
        resp = client.post(
            f"/api/sessions/{session.id}/blocks",
            json={
                "item_id": None,
                "item_title": "",
                "position": 0,
                "planned_seconds": 300,
                "played_seconds": 60,
                "bpm": None,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stored"] is True

    block = session.blocks[0]
    assert block.item_id is None
    assert block.item_title == ""
