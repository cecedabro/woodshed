"""Tests for routine pages (SPEC 4.1, 4.3).

Routes: GET /routines, GET/POST /routines/new,
        GET/POST /routines/{id}/delete, GET /routines/{id}/edit
"""

from datetime import UTC

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /routines — list
# ---------------------------------------------------------------------------


def test_get_routines_returns_200(client: TestClient) -> None:
    """Login-required route returns 200 once logged in (cookie set)."""
    _login(client)
    resp = client.get("/routines")
    assert resp.status_code == 200


def test_routines_page_has_nav(client: TestClient) -> None:
    """SPEC 10.1: Routines page includes navigation."""
    _login(client)
    resp = client.get("/routines")
    html = resp.text
    assert "<nav" in html
    assert 'href="/routines"' in html


def test_routines_nav_active(client: TestClient) -> None:
    """SPEC 10.1: The Routines nav link has aria-current='page'."""
    _login(client)
    resp = client.get("/routines")
    assert 'aria-current="page"' in resp.text
    assert 'href="/routines"' in resp.text


def test_routines_empty_state(client: TestClient) -> None:
    """Empty routine list shows a message."""
    _login(client)
    resp = client.get("/routines")
    assert "No routines" in resp.text
    assert 'href="/routines/new"' in resp.text


def test_routines_shows_routines_with_minutes(client: TestClient, db: Session) -> None:
    """Routines list shows name and total planned minutes (SPEC 4.1, 4.2)."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="Blues in E")
    db.add(item)
    db.flush()

    routine = Routine(name="Morning warmup")
    db.add(routine)
    db.flush()

    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=5))
    db.add(RoutineBlock(routine_id=routine.id, position=1, item_id=item.id, minutes=10))
    db.commit()

    _login(client)
    resp = client.get("/routines")

    assert "Morning warmup" in resp.text
    assert "15 min" in resp.text
    assert "2 blocks" in resp.text


def test_routines_shows_zero_minutes_for_empty_routine(client: TestClient, db: Session) -> None:
    """A routine with no blocks shows 0 minutes."""
    from app.models import Routine

    routine = Routine(name="Empty routine")
    db.add(routine)
    db.commit()

    _login(client)
    resp = client.get("/routines")

    assert "Empty routine" in resp.text
    assert "0 min" in resp.text
    assert "0 blocks" in resp.text


def test_routines_order_by_updated_desc(client: TestClient, db: Session) -> None:
    """Routines are ordered by updated_at descending (newest first)."""
    from app.models import Routine

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
    resp = client.get("/routines")
    html = resp.text

    # "New routine" should appear before "Old routine" in the HTML
    new_pos = html.index("New routine")
    old_pos = html.index("Old routine")
    assert new_pos < old_pos, "Routines should be ordered by updated_at DESC"


# ---------------------------------------------------------------------------
# GET /routines/new
# ---------------------------------------------------------------------------


def test_get_new_routine_page(client: TestClient) -> None:
    """GET /routines/new returns 200 with a name form."""
    _login(client)
    resp = client.get("/routines/new")
    assert resp.status_code == 200
    assert 'name="name"' in resp.text
    assert "New Routine" in resp.text


def test_new_routine_page_has_nav(client: TestClient) -> None:
    """SPEC 10.1: New routine page nav has active='routines'."""
    _login(client)
    resp = client.get("/routines/new")
    assert 'aria-current="page"' in resp.text
    assert 'href="/routines"' in resp.text


# ---------------------------------------------------------------------------
# POST /routines/new
# ---------------------------------------------------------------------------


def test_post_new_routine_empty_name_422(client: TestClient) -> None:
    """Empty routine name returns 422 with an error message."""
    _login(client)
    resp = client.post("/routines/new", data={"name": ""})
    assert resp.status_code == 422
    assert "Name is required" in resp.text


def test_post_new_routine_whitespace_name_422(client: TestClient) -> None:
    """Whitespace-only routine name returns 422."""
    _login(client)
    resp = client.post("/routines/new", data={"name": "   "})
    assert resp.status_code == 422
    assert "Name is required" in resp.text


def test_post_new_routine_creates_and_redirects(client: TestClient, db: Session) -> None:
    """Valid POST creates a routine and redirects to the edit page."""
    from app.models import Routine

    _login(client)
    resp = client.post("/routines/new", data={"name": "Morning warmup"}, follow_redirects=False)
    assert resp.status_code == 303
    assert "/routines/" in resp.headers["location"]

    routine_id = int(resp.headers["location"].split("/")[-2])
    with db.begin():
        routine = db.get(Routine, routine_id)
        assert routine is not None
        assert routine.name == "Morning warmup"


def test_post_new_routine_visible_in_list(client: TestClient, db: Session) -> None:
    """Created routine appears in the list immediately."""

    _login(client)
    client.post("/routines/new", data={"name": "Blues session"})

    with db.begin():
        routine = db.scalar(text("SELECT id FROM routine WHERE name = 'Blues session' LIMIT 1"))
        assert routine is not None

    resp = client.get("/routines")
    assert "Blues session" in resp.text


# ---------------------------------------------------------------------------
# GET /routines/{id}/edit (stub)
# ---------------------------------------------------------------------------


def test_get_routine_edit_returns_200(client: TestClient, db: Session) -> None:
    """GET /routines/{id}/edit returns 200 for an existing routine."""
    from app.models import Routine

    routine = Routine(name="Edit test")
    db.add(routine)
    db.commit()

    _login(client)
    resp = client.get(f"/routines/{routine.id}/edit")
    assert resp.status_code == 200
    assert "Edit test" in resp.text


def test_get_routine_edit_404(client: TestClient) -> None:
    """GET /routines/99999/edit returns 404."""
    _login(client)
    resp = client.get("/routines/99999/edit")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /routines/{id}/delete
# ---------------------------------------------------------------------------


def test_get_delete_routine_confirm(client: TestClient, db: Session) -> None:
    """GET /routines/{id}/delete shows a confirmation page."""
    from app.models import Routine

    routine = Routine(name="To delete")
    db.add(routine)
    db.commit()

    _login(client)
    resp = client.get(f"/routines/{routine.id}/delete")
    assert resp.status_code == 200
    assert "To delete" in resp.text
    assert "Are you sure" in resp.text


def test_get_delete_routine_404(client: TestClient) -> None:
    """GET /routines/99999/delete returns 404."""
    _login(client)
    resp = client.get("/routines/99999/delete")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /routines/{id}/delete
# ---------------------------------------------------------------------------


def test_post_delete_routine_redirects(client: TestClient, db: Session) -> None:
    """POST /routines/{id}/delete redirects to /routines."""
    from app.models import Routine

    routine = Routine(name="Deleted")
    db.add(routine)
    db.commit()

    _login(client)
    resp = client.post(f"/routines/{routine.id}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/routines"


def test_post_delete_routine_removes_from_db(client: TestClient, db: Session) -> None:
    """Routine is removed from the database after deletion."""
    from app.models import Routine

    routine = Routine(name="Gone")
    db.add(routine)
    db.commit()

    _login(client)
    client.post(f"/routines/{routine.id}/delete")

    # expire_on_commit=False keeps the object in the identity map;
    # expunge so db.get() does a fresh SELECT instead of trying to refresh.
    db.expunge(routine)
    db.expire_all()
    gone = db.get(Routine, routine.id)
    assert gone is None


def test_post_delete_routine_404(client: TestClient) -> None:
    """POST /routines/99999/delete returns 404."""
    _login(client)
    resp = client.post("/routines/99999/delete")
    assert resp.status_code == 404


def test_delete_routine_keeps_sessions(client: TestClient, db: Session) -> None:
    """SPEC 4.3: Deleting a routine keeps its logged sessions."""
    from datetime import datetime

    from app.models import PracticeSession, Routine

    routine = Routine(name="Kept sessions")
    db.add(routine)
    db.flush()

    session = PracticeSession(
        routine_id=routine.id,
        started_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()

    session_id = session.id

    _login(client)
    client.post(f"/routines/{routine.id}/delete")

    # expire_on_commit=False keeps the routine in the identity map
    db.expunge(routine)
    db.expire_all()
    routine_check = db.get(Routine, routine.id)
    assert routine_check is None

    # Session should still exist with routine_id NULL
    session_check = db.get(PracticeSession, session_id)
    assert session_check is not None
    assert session_check.routine_id is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
