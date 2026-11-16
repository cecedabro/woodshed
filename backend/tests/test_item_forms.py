"""Tests for item create/edit forms (SPEC 3.3).

Routes: GET/POST /items/new, GET/POST /items/{item_id}/edit.
"""

import re

from sqlalchemy import select

from app.models import Item

# A field error: `class="error"` on the old layout, `class="field-error"` in the design system.
ERROR = re.compile(rb'class="(?:field-)?error"')

# ---------------------------------------------------------------------------
# GET /items/new
# ---------------------------------------------------------------------------


def test_get_new_item_returns_200(client):
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert b"New Item" in resp.content
    assert b'name="kind"' in resp.content
    assert b'name="title"' in resp.content
    assert b'name="artist"' in resp.content
    assert b'name="status"' in resp.content
    assert b'name="current_bpm"' in resp.content
    assert b'name="original_url"' in resp.content
    assert b'name="notes"' in resp.content


def test_get_new_item_has_kind_options(client):
    resp = client.get("/items/new")
    assert b"song" in resp.content
    assert b"exercise" in resp.content


def test_get_new_item_has_status_options(client):
    resp = client.get("/items/new")
    assert b"learning" in resp.content
    assert b"polishing" in resp.content
    assert b"repertoire" in resp.content


def test_get_new_item_no_error_spans(client):
    resp = client.get("/items/new")
    assert not ERROR.search(resp.content)


# ---------------------------------------------------------------------------
# POST /items/new
# ---------------------------------------------------------------------------


def test_post_new_item_success(client, db):
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Sweet Home Chicago",
            "artist": "Robert Johnson",
            "status": "repertoire",
            "current_bpm": 120,
            "original_url": "https://example.com",
            "notes": "In E",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/items/" in resp.headers["location"]

    item = db.scalar(select(Item).where(Item.title == "Sweet Home Chicago"))
    assert item is not None
    assert item.kind == "song"
    assert item.artist == "Robert Johnson"
    assert item.status == "repertoire"
    assert item.current_bpm == 120
    assert item.original_url == "https://example.com"
    assert item.notes == "In E"


def test_post_new_item_defaults(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "exercise", "title": "Metronome drill"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    item = db.scalar(select(Item).where(Item.title == "Metronome drill"))
    assert item is not None
    assert item.status == "learning"
    assert item.artist is None
    assert item.current_bpm is None
    assert item.original_url is None
    assert item.notes == ""


def test_post_new_item_rejects_empty_title(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "", "artist": "X"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert ERROR.search(resp.content)
    assert b"title" in resp.content.lower()
    assert db.scalar(select(Item)) is None


def test_post_new_item_rejects_blank_title(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "   ", "artist": "X"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"title" in resp.content.lower()


def test_post_new_item_rejects_long_title(client, db):
    long_title = "A" * 201
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": long_title},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"title" in resp.content.lower()


def test_post_new_item_rejects_bpm_19(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Test", "current_bpm": 19},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"current_bpm" in resp.content.lower()


def test_post_new_item_rejects_bpm_401(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Test", "current_bpm": 401},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"current_bpm" in resp.content.lower()


def test_post_new_item_accepts_bpm_20(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Test", "current_bpm": 20},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db.scalar(select(Item).where(Item.title == "Test"))
    assert item is not None
    assert item.current_bpm == 20


def test_post_new_item_accepts_bpm_400(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Test", "current_bpm": 400},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db.scalar(select(Item).where(Item.title == "Test"))
    assert item is not None
    assert item.current_bpm == 400


def test_post_new_item_rejects_ftp_url(client, db):
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Test",
            "original_url": "ftp://example.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"original_url" in resp.content.lower()


def test_post_new_item_rejects_invalid_kind(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "drum", "title": "Test"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"kind" in resp.content.lower()


def test_post_new_item_rejects_invalid_status(client, db):
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Test",
            "status": "abandoned",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"status" in resp.content.lower()


def test_post_new_item_error_next_to_field(client, db):
    resp = client.post(
        "/items/new",
        data={"kind": "bad", "title": "   ", "status": "bad"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    # Each field error span should be inside the field div
    # Check that "error" class appears alongside the field
    # We check that the response contains the error message near the field
    assert len(ERROR.findall(resp.content)) >= 3  # kind, title, status + selects


# ---------------------------------------------------------------------------
# GET /items/{id}/edit
# ---------------------------------------------------------------------------


def test_get_edit_item_404(client):
    resp = client.get("/items/99999/edit")
    assert resp.status_code == 404


def test_get_edit_item_populated(client, db):
    item = Item(
        kind="song",
        title="Crossroads",
        artist="Eric Clapton",
        status="polishing",
        current_bpm=160,
        original_url="https://example.com/crossroads",
        notes="In A",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/items/{item.id}/edit")
    assert resp.status_code == 200
    assert b"Edit Item" in resp.content
    assert b"Crossroads" in resp.content
    assert b"Eric Clapton" in resp.content
    assert b'value="polishing"' in resp.content
    assert b'value="160"' in resp.content


def test_get_edit_item_reuses_same_template_kind(client, db):
    item = Item(kind="exercise", title="Scale 1", status="learning")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/items/{item.id}/edit")
    assert resp.status_code == 200
    # Edit form should have the same fields
    assert b'name="kind"' in resp.content
    assert b'name="title"' in resp.content


# ---------------------------------------------------------------------------
# POST /items/{id}/edit
# ---------------------------------------------------------------------------


def test_post_edit_item_success(client, db):
    item = Item(kind="song", title="Before", artist="Old")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(
        f"/items/{item.id}/edit",
        data={
            "kind": "exercise",
            "title": "After",
            "artist": "New",
            "status": "repertoire",
            "current_bpm": 100,
            "original_url": "https://new.example.com",
            "notes": "Updated notes",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert f"/items/{item.id}" in resp.headers["location"]

    db.expire_all()
    updated = db.scalar(select(Item).where(Item.id == item.id))
    assert updated is not None
    assert updated.kind == "exercise"
    assert updated.title == "After"
    assert updated.artist == "New"
    assert updated.status == "repertoire"
    assert updated.current_bpm == 100
    assert updated.original_url == "https://new.example.com"
    assert updated.notes == "Updated notes"


def test_post_edit_item_preserves_missing_optional_fields(client, db):
    item = Item(
        kind="song",
        title="Test",
        artist="Origin",
        status="learning",
        current_bpm=80,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(
        f"/items/{item.id}/edit",
        data={
            "kind": "song",
            "title": "Test",
            # artist, current_bpm, original_url, notes omitted
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db.expire_all()
    updated = db.scalar(select(Item).where(Item.id == item.id))
    assert updated.artist is None  # form field empty -> None via _extract_and_validate
    assert updated.current_bpm is None  # form field empty -> None


def test_post_edit_item_rejects_bad_title(client, db):
    item = Item(kind="song", title="Test")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(
        f"/items/{item.id}/edit",
        data={"kind": "song", "title": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"title" in resp.content.lower()


def test_post_edit_item_404(client, db):
    resp = client.post(
        "/items/99999/edit",
        data={"kind": "song", "title": "X"},
        follow_redirects=False,
    )
    assert resp.status_code == 404
