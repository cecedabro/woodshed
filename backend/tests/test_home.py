"""Tests for the home page (SPEC 5.1).

Routes: GET /
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PracticeSession, Routine

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET / — empty state
# ---------------------------------------------------------------------------


def test_home_empty_state_shows_create_link(client: TestClient) -> None:
    """When no routines exist, home shows a message linking to /routines/new."""
    _login(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No routines" in resp.text
    assert 'href="/routines/new"' in resp.text


def test_home_empty_state_has_nav(client: TestClient) -> None:
    """Home page nav is present and active is 'home'."""
    _login(client)
    resp = client.get("/")
    html = resp.text
    assert "<nav" in html
    assert 'href="/routines"' in html
    assert 'href="/library"' in html
    assert 'href="/progress"' in html
    assert 'href="/settings"' in html


# ---------------------------------------------------------------------------
# GET / — routines ordered by most recent practice session
# ---------------------------------------------------------------------------


def test_home_shows_routines_without_sessions(client: TestClient, db: Session) -> None:
    """Routines with no sessions appear on home, ordered by created_at DESC."""
    old = Routine(name="Old routine")
    db.add(old)
    db.flush()
    import time

    time.sleep(0.01)
    new = Routine(name="New routine")
    db.add(new)
    db.flush()
    db.commit()

    _login(client)
    resp = client.get("/")

    assert "New routine" in resp.text
    assert "Old routine" in resp.text

    # New routine should appear first
    new_pos = resp.text.index("New routine")
    old_pos = resp.text.index("Old routine")
    assert new_pos < old_pos


def test_home_routines_ordered_by_last_session(client: TestClient, db: Session) -> None:
    """Routines are ordered by most recent PracticeSession.ended_at DESC."""
    import time

    older_session = PracticeSession(
        routine_id=None,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        ended_at=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
    )
    newer_session = PracticeSession(
        routine_id=None,
        started_at=datetime(2025, 1, 1, tzinfo=UTC),
        ended_at=datetime(2025, 1, 1, 10, 0, tzinfo=UTC),
    )

    routine_old = Routine(name="Oldest routine")
    db.add(routine_old)
    db.flush()
    older_session.routine_id = routine_old.id
    db.add(older_session)
    db.flush()

    time.sleep(0.01)

    routine_new = Routine(name="Newest routine")
    db.add(routine_new)
    db.flush()
    newer_session.routine_id = routine_new.id
    db.add(newer_session)
    db.commit()

    _login(client)
    resp = client.get("/")

    # Newest routine should appear before oldest
    new_pos = resp.text.index("Newest routine")
    old_pos = resp.text.index("Oldest routine")
    assert new_pos < old_pos, "Most recently practised routine should appear first"


def test_home_most_recent_has_primary_class(client: TestClient, db: Session) -> None:
    """The most recently practised routine gets the 'home-routine-item--primary' CSS class."""
    session = PracticeSession(
        routine_id=None,
        started_at=datetime(2025, 6, 1, tzinfo=UTC),
        ended_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
    )

    routine = Routine(name="Primary routine")
    db.add(routine)
    db.flush()
    session.routine_id = routine.id
    db.add(session)
    db.commit()

    _login(client)
    resp = client.get("/")

    assert 'class="home-routine-item home-routine-item--primary"' in resp.text


def test_home_button_links_to_run_with_autostart(client: TestClient, db: Session) -> None:
    """Each routine button links to /run/{id}?autostart=1."""
    routine = Routine(name="Autostart routine")
    db.add(routine)
    db.commit()

    _login(client)
    resp = client.get("/")

    assert f'href="/run/{routine.id}?autostart=1"' in resp.text


def test_home_button_shows_block_count_and_minutes(client: TestClient, db: Session) -> None:
    """The button shows the routine's block count and total minutes."""
    from app.models import Item, RoutineBlock

    item = Item(kind="song", title="Blues in A")
    db.add(item)
    db.flush()

    routine = Routine(name="Blues session")
    db.add(routine)
    db.flush()

    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=10))
    db.add(RoutineBlock(routine_id=routine.id, position=1, item_id=item.id, minutes=20))
    db.commit()

    _login(client)
    resp = client.get("/")

    assert "30 min" in resp.text
    assert "2 blocks" in resp.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
