"""Tests for the runner page (SPEC 5.2).

Routes: GET /run/{routine_id}
"""

import html
import json
import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


def test_get_run_unknown_routine_404(client: TestClient) -> None:
    """GET /run/99999 returns 404 for an unknown routine."""
    _login(client)
    resp = client.get("/run/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Page content and data-blocks JSON
# ---------------------------------------------------------------------------


def test_get_run_returns_200(client: TestClient, db: Session) -> None:
    """Login-required runner route returns 200 once logged in."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="Blues in A")
    db.add(item)
    db.flush()

    routine = Routine(name="Morning warmup")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=10))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    assert resp.status_code == 200


def test_run_page_has_nav(client: TestClient, db: Session) -> None:
    """SPEC 10.1: Runner page includes navigation."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="Test song")
    db.add(item)
    db.flush()
    routine = Routine(name="Test routine")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=5))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text
    assert "<nav" in html
    assert 'href="/"' in html


def test_run_page_has_module_script(client: TestClient, db: Session) -> None:
    """The page includes a module script tag for run-page.js."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="Test")
    db.add(item)
    db.flush()
    routine = Routine(name="Test")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=5))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text

    assert '<script type="module" src="/static/js/run-page.js">' in html


def test_run_page_has_controls(client: TestClient, db: Session) -> None:
    """Runner page has Start, +1 min, and Skip buttons with expected IDs."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="Control test")
    db.add(item)
    db.flush()
    routine = Routine(name="Control routine")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=5))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text

    assert 'id="run-main"' in html
    assert 'id="run-plus"' in html
    assert 'id="run-skip"' in html
    assert "Start" in html
    assert "+1 min" in html
    assert "Skip" in html


def test_run_page_attachment_links(client: TestClient, db: Session) -> None:
    """Each block has an attachment links container."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="Attachment test")
    db.add(item)
    db.flush()

    routine = Routine(name="Attachment routine")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=10))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text

    assert 'id="run-links"' in html
    assert "group" in html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


# ---------------------------------------------------------------------------
# data-blocks JSON (SPEC 5.2, 6.2)
# ---------------------------------------------------------------------------


def _blocks(client: TestClient, path: str) -> list[dict]:
    resp = client.get(path)
    assert resp.status_code == 200
    match = re.search(r'data-blocks="([^"]*)"', resp.text)
    assert match is not None, "data-blocks attribute not found"
    return json.loads(html.unescape(match.group(1)))


def _routine(db: Session, *blocks: tuple[str, int | None, int | None, int]) -> int:
    """Blocks are (title, item current_bpm, block bpm, minutes)."""
    from app.models import Item, Routine, RoutineBlock

    routine = Routine(name="R")
    db.add(routine)
    db.flush()
    for pos, (title, item_bpm, block_bpm, minutes) in enumerate(blocks):
        item = Item(kind="song", title=title, current_bpm=item_bpm)
        db.add(item)
        db.flush()
        db.add(
            RoutineBlock(
                routine_id=routine.id, position=pos, item_id=item.id, minutes=minutes, bpm=block_bpm
            )
        )
    db.commit()
    return routine.id


def test_data_blocks_fields_and_order(client: TestClient, db: Session) -> None:
    rid = _routine(db, ("Song A", None, None, 5), ("Exercise B", None, 120, 15))
    blocks = _blocks(client, f"/run/{rid}")
    assert [b["title"] for b in blocks] == ["Song A", "Exercise B"]
    assert [b["planned_seconds"] for b in blocks] == [300, 900]
    assert all(isinstance(b["item_id"], int) for b in blocks)


def test_start_bpm_falls_back_to_item_bpm(client: TestClient, db: Session) -> None:
    rid = _routine(db, ("Song", 72, None, 5))
    assert _blocks(client, f"/run/{rid}")[0]["start_bpm"] == 72


def test_block_bpm_wins(client: TestClient, db: Session) -> None:
    rid = _routine(db, ("Song", 72, 100, 5))
    assert _blocks(client, f"/run/{rid}")[0]["start_bpm"] == 100


def test_no_bpm_anywhere_is_80(client: TestClient, db: Session) -> None:
    rid = _routine(db, ("Song", None, None, 5))
    assert _blocks(client, f"/run/{rid}")[0]["start_bpm"] == 80


def test_awkward_title_survives(client: TestClient, db: Session) -> None:
    title = """Don't "Stop" <me>"""
    rid = _routine(db, (title, None, None, 5))
    assert _blocks(client, f"/run/{rid}")[0]["title"] == title


def test_free_practice_uses_item_bpm(client: TestClient, db: Session) -> None:
    from app.models import Item

    item = Item(kind="exercise", title="Spider", current_bpm=90)
    db.add(item)
    db.commit()
    blocks = _blocks(client, f"/run/item/{item.id}?minutes=10")
    assert blocks == [
        {"item_id": item.id, "title": "Spider", "planned_seconds": 600, "start_bpm": 90}
    ]
