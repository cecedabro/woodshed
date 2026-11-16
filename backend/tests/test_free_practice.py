"""Tests for Free Practice (SPEC 5.8).

Routes: GET /run/item/{item_id}?minutes=10
"""

import html as html_mod
import json
import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


def test_get_run_item_unknown_404(client: TestClient) -> None:
    """GET /run/item/99999 returns 404 for an unknown item."""
    _login(client)
    resp = client.get("/run/item/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Page content and data-blocks JSON
# ---------------------------------------------------------------------------


def test_get_run_item_returns_200(client: TestClient, db: Session) -> None:
    """Free practice route returns 200 for a known item."""
    from app.models import Item

    item = Item(kind="song", title="Blues in A")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    assert resp.status_code == 200


def test_run_item_data_blocks_json(client: TestClient, db: Session) -> None:
    """SPEC 5.8: data-blocks contains valid JSON with required fields for free practice."""
    from app.models import Item

    item = Item(kind="song", title="Free Practice Song")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    match = re.search(r'data-blocks="([^"]*)"', html)
    assert match is not None, "data-blocks attribute not found in HTML"

    blocks = json.loads(html_mod.unescape(match.group(1)))
    assert len(blocks) == 1

    block = blocks[0]
    assert block["item_id"] == item.id
    assert block["title"] == "Free Practice Song"
    assert block["planned_seconds"] == 600  # default 10 minutes * 60
    assert block["start_bpm"] == 80  # no BPM anywhere (SPEC 6.2)


def test_run_item_routine_id_null(client: TestClient, db: Session) -> None:
    """SPEC 5.8: data-routine-id is 'null' for free practice sessions."""
    from app.models import Item

    item = Item(kind="song", title="Solo Item")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    match = re.search(r'data-routine-id="([^"]*)"', html)
    assert match is not None, "data-routine-id not found in HTML"
    assert match.group(1) == "null"


def test_run_item_custom_minutes(client: TestClient, db: Session) -> None:
    """Custom ?minutes=15 changes planned_seconds to 900."""
    from app.models import Item

    item = Item(kind="exercise", title="Drill C")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}?minutes=15")
    html = resp.text

    match = re.search(r'data-blocks="([^"]*)"', html)
    assert match is not None

    blocks = json.loads(html_mod.unescape(match.group(1)))
    assert blocks[0]["planned_seconds"] == 900  # 15 * 60


def test_run_item_heading_is_item_title(client: TestClient, db: Session) -> None:
    """The h1 heading shows the item title for free practice."""
    from app.models import Item

    item = Item(kind="song", title="My Blues Song")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    assert "<h1>My Blues Song</h1>" in html


def test_run_item_has_library_back_link(client: TestClient, db: Session) -> None:
    """Free practice page links to /library, not /routines."""
    from app.models import Item

    item = Item(kind="song", title="Back Link Test")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    assert 'href="/library"' in html


def test_run_item_has_module_script(client: TestClient, db: Session) -> None:
    """The free practice page includes a module script tag for run-page.js."""
    from app.models import Item

    item = Item(kind="song", title="Script Test")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    assert '<script type="module" src="/static/js/run-page.js">' in html


def test_run_item_has_controls(client: TestClient, db: Session) -> None:
    """Free practice block has Start, Pause, and Skip buttons."""
    from app.models import Item

    item = Item(kind="song", title="Controls Test")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    assert 'data-action="start"' in html
    assert 'data-action="pause"' in html
    assert 'data-action="skip"' in html
    assert "Start" in html
    assert "Pause" in html
    assert "Skip" in html


def test_run_item_attachment_links(client: TestClient, db: Session) -> None:
    """Free practice shows item attachments (Tab, PDF, Audio)."""
    from app.models import Attachment, Item

    item = Item(kind="song", title="Attachment Test")
    db.add(item)
    db.commit()

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
        label="Notes",
        filename="notes.pdf",
        stored_name="notes.pdf",
        content_type="application/pdf",
        size_bytes=200,
    )
    audio = Attachment(
        item_id=item.id,
        kind="audio",
        label="Backing",
        filename="track.mp3",
        stored_name="track.mp3",
        content_type="audio/mpeg",
        size_bytes=300,
    )
    db.add_all([tab, pdf, audio])
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    assert f"/media/attachment/{tab.id}" in html
    assert f"/media/attachment/{pdf.id}" in html
    assert f"/media/attachment/{audio.id}" in html


def test_practise_button_on_item_detail(client: TestClient, db: Session) -> None:
    """SPEC 5.8: Item detail page has a 'Practise this' link."""
    from app.models import Item

    item = Item(kind="song", title="Button Test")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/items/{item.id}")
    html = resp.text

    assert "Practise this" in html
    assert f"/run/item/{item.id}?minutes=10" in html


def test_run_item_page_title(client: TestClient, db: Session) -> None:
    """SPEC 5.8: Page title says 'Free Practice' for free practice runs."""
    from app.models import Item

    item = Item(kind="song", title="Title Test")
    db.add(item)
    db.commit()

    _login(client)
    resp = client.get(f"/run/item/{item.id}")
    html = resp.text

    assert "Free Practice" in html
