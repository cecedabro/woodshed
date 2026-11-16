"""Tests for the runner page (SPEC 5.2).

Routes: GET /run/{routine_id}
"""

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_get_run_requires_login(client: TestClient) -> None:
    """GET /run/{id} requires login (401)."""
    resp = client.get("/run/1", follow_redirects=False)
    assert resp.status_code == 401


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
    assert 'href="/routines"' in html


def test_run_page_data_blocks_json(client: TestClient, db: Session) -> None:
    """SPEC 5.2, 6.2: data-blocks contains valid JSON with required fields."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="Blues in E")
    db.add(item)
    db.flush()

    routine = Routine(name="Morning warmup")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=10, bpm=70))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text

    # Find the data-blocks attribute
    assert 'data-blocks="' in html or "data-blocks='" in html

    # Extract JSON from data-blocks
    import re

    match = re.search(r"data-blocks=\'([^\']*)\'", html)
    if not match:
        match = re.search(r'data-blocks="([^"]*)"', html)
    assert match is not None, "data-blocks attribute not found in HTML"

    blocks_json = match.group(1)
    blocks = json.loads(blocks_json)
    assert len(blocks) == 1

    block = blocks[0]
    assert block["item_id"] == item.id
    assert block["title"] == "Blues in E"
    assert block["planned_seconds"] == 600  # 10 minutes * 60
    assert block["start_bpm"] == 70


def test_run_page_data_blocks_multiple(client: TestClient, db: Session) -> None:
    """data-blocks contains all blocks in order."""
    from app.models import Item, Routine, RoutineBlock

    item_a = Item(kind="song", title="Song A")
    item_b = Item(kind="exercise", title="Exercise B")
    db.add_all([item_a, item_b])
    db.flush()

    routine = Routine(name="Multi-block")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item_a.id, minutes=5))
    db.add(RoutineBlock(routine_id=routine.id, position=1, item_id=item_b.id, minutes=15, bpm=120))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text

    import re

    match = re.search(r"data-blocks=\'([^\']*)\'", html)
    assert match is not None

    blocks = json.loads(match.group(1))
    assert len(blocks) == 2
    assert blocks[0]["item_id"] == item_a.id
    assert blocks[0]["title"] == "Song A"
    assert blocks[0]["planned_seconds"] == 300
    assert blocks[0]["start_bpm"] is None
    assert blocks[1]["item_id"] == item_b.id
    assert blocks[1]["title"] == "Exercise B"
    assert blocks[1]["planned_seconds"] == 900
    assert blocks[1]["start_bpm"] == 120


def test_run_page_no_bpm_is_null(client: TestClient, db: Session) -> None:
    """BPM is null (JSON null, not a string) when not set."""
    from app.models import Item, Routine, RoutineBlock

    item = Item(kind="song", title="No BPM song")
    db.add(item)
    db.flush()
    routine = Routine(name="No BPM routine")
    db.add(routine)
    db.flush()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=10))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text

    import re

    match = re.search(r"data-blocks=\'([^\']*)\'", html)
    assert match is not None
    blocks = json.loads(match.group(1))
    assert blocks[0]["start_bpm"] is None


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
    """Each block has Start, Pause, and Skip buttons with labels."""
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

    assert 'data-action="start"' in html
    assert 'data-action="pause"' in html
    assert 'data-action="skip"' in html
    assert "Start" in html
    assert "Pause" in html
    assert "Skip" in html


def test_run_page_attachment_links(client: TestClient, db: Session) -> None:
    """Each block has links to its item's tab, PDF and audio attachments."""
    from app.models import Attachment, Item, Routine, RoutineBlock

    item = Item(kind="song", title="Attachment test")
    db.add(item)
    db.flush()

    routine = Routine(name="Attachment routine")
    db.add(routine)
    db.flush()

    tab = Attachment(
        item_id=item.id,
        kind="tab",
        label="Main tab",
        filename="test.tab",
        stored_name="test.tab",
        content_type="text/plain",
        size_bytes=100,
    )
    pdf = Attachment(
        item_id=item.id,
        kind="pdf",
        label="Liner notes",
        filename="notes.pdf",
        stored_name="notes.pdf",
        content_type="application/pdf",
        size_bytes=200,
    )
    audio = Attachment(
        item_id=item.id,
        kind="audio",
        label="Backing track",
        filename="track.mp3",
        stored_name="track.mp3",
        content_type="audio/mpeg",
        size_bytes=300,
    )
    db.add_all([tab, pdf, audio])
    db.commit()
    db.add(RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=10))
    db.commit()

    _login(client)
    resp = client.get(f"/run/{routine.id}")
    html = resp.text

    assert f"/media/attachment/{tab.id}" in html
    assert f"/media/attachment/{pdf.id}" in html
    assert f"/media/attachment/{audio.id}" in html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
