"""Tests for Item year, mbid, release_group_id, has_cover fields (SPEC 3.1, 3.8).

Routes tested: GET/POST /items/new, GET/POST /items/{item_id}/edit,
                GET /api/items/{item_id}.
"""

import re

from sqlalchemy import select

from app.models import Item

ERROR = re.compile(rb'class="(?:field-)?error"')


# ---------------------------------------------------------------------------
# Form rendering: GET /items/new
# ---------------------------------------------------------------------------


def test_get_new_item_has_year_field(client) -> None:
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert b'name="year"' in resp.content


def test_get_new_item_year_is_visible_input(client) -> None:
    """Year must be a visible input, not hidden."""
    resp = client.get("/items/new")
    # Hidden inputs use type="hidden", not a visible text/number input
    assert re.search(rb'<input[^>]*name="year"[^>]*type="number"', resp.content)


def test_get_new_item_has_hidden_mbid(client) -> None:
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert b'name="mbid"' in resp.content
    assert b'type="hidden"' in resp.content


def test_get_new_item_has_hidden_release_group_id(client) -> None:
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert b'name="release_group_id"' in resp.content
    assert b'type="hidden"' in resp.content


# ---------------------------------------------------------------------------
# API: POST /items/new with new fields
# ---------------------------------------------------------------------------


def test_post_new_item_accepts_year(client, db) -> None:
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Born in Chicago",
            "artist": "Muddy Waters",
            "year": 1954,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db.scalar(select(Item).where(Item.title == "Born in Chicago"))
    assert item is not None
    assert item.year == 1954


def test_post_new_item_accepts_mbids(client, db) -> None:
    """Valid UUIDs for mbid and release_group_id are accepted."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Crossroads",
            "artist": "Robert Johnson",
            "year": 1937,
            "mbid": "97abde02-a497-43bd-8f26-83c936ed51b7",
            "release_group_id": "f9a49394-6d6c-4f9e-8f6e-5d3f2e1a0b9c",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db.scalar(select(Item).where(Item.title == "Crossroads"))
    assert item is not None
    assert item.mbid == "97abde02-a497-43bd-8f26-83c936ed51b7"
    assert item.release_group_id == "f9a49394-6d6c-4f9e-8f6e-5d3f2e1a0b9c"


def test_post_new_item_all_mb_fields_together(client, db) -> None:
    """All four fields can be set simultaneously."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "exercise",
            "title": "Bach Invention 1",
            "year": 1720,
            "mbid": "a03a59ef-5f18-3091-a3d9-a1b1c0a4e4f2",
            "release_group_id": "b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db.scalar(select(Item).where(Item.title == "Bach Invention 1"))
    assert item is not None
    assert item.year == 1720
    assert item.mbid == "a03a59ef-5f18-3091-a3d9-a1b1c0a4e4f2"
    assert item.release_group_id == "b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3"
    assert item.has_cover is False


def test_post_new_item_year_boundaries(client, db) -> None:
    """Year 1000 and 2100 are both accepted."""
    for year_val in [1000, 2100]:
        item_title = f"Year test {year_val}"
        resp = client.post(
            "/items/new",
            data={
                "kind": "song",
                "title": item_title,
                "year": year_val,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303, f"year={year_val} should be accepted"
        item = db.scalar(select(Item).where(Item.title == item_title))
        assert item is not None
        assert item.year == year_val


def test_post_new_item_year_zero_rejected(client, db) -> None:
    """Year 0 is below the valid range."""
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Year Zero", "year": 0},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"year" in resp.content.lower()


def test_post_new_item_year_999_rejected(client, db) -> None:
    """Year 999 is below the valid range (minimum 1000)."""
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Year 999", "year": 999},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"year" in resp.content.lower()


def test_post_new_item_year_2101_rejected(client, db) -> None:
    """Year 2101 is above the valid range (maximum 2100)."""
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Year 2101", "year": 2101},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"year" in resp.content.lower()


def test_post_new_item_year_10000_rejected(client, db) -> None:
    """Year 10000 is way above the valid range."""
    resp = client.post(
        "/items/new",
        data={"kind": "song", "title": "Year 10k", "year": 10000},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"year" in resp.content.lower()


def test_post_new_item_rejects_invalid_mbid(client, db) -> None:
    """mbid that is not a valid UUID must be rejected."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Bad Mbid",
            "mbid": "not-a-uuid",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"mbid" in resp.content.lower()


def test_post_new_item_rejects_partial_mbid(client, db) -> None:
    """mbid missing dashes is not a valid UUID."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Partial Mbid",
            "mbid": "97abde02a49743bd8f2683c936ed51b7",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"mbid" in resp.content.lower()


def test_post_new_item_rejects_invalid_release_group_id(client, db) -> None:
    """release_group_id that is not a valid UUID must be rejected."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Bad Rgid",
            "release_group_id": "not-a-uuid",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"release_group_id" in resp.content.lower()


def test_post_new_item_empty_mbid_ignored(client, db) -> None:
    """Empty mbid field (not sent) should not cause validation errors."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "No Mbid",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db.scalar(select(Item).where(Item.title == "No Mbid"))
    assert item is not None
    assert item.mbid is None


def test_post_new_item_empty_year_ignored(client, db) -> None:
    """Empty year field (not sent) should not cause validation errors."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "No Year",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db.scalar(select(Item).where(Item.title == "No Year"))
    assert item is not None
    assert item.year is None


# ---------------------------------------------------------------------------
# Edit form: GET /items/{id}/edit
# ---------------------------------------------------------------------------


def test_get_edit_item_populates_year(client, db) -> None:
    item = Item(kind="song", title="Edit Year Test", year=1969)
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/items/{item.id}/edit")
    assert resp.status_code == 200
    assert b"1969" in resp.content


def test_get_edit_item_populates_mbid(client, db) -> None:
    item = Item(kind="song", title="Edit Mbid Test", mbid="a03a59ef-5f18-3091-a3d9-a1b1c0a4e4f2")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/items/{item.id}/edit")
    assert resp.status_code == 200
    assert b"a03a59ef-5f18-3091-a3d9-a1b1c0a4e4f2" in resp.content


def test_get_edit_item_populates_release_group_id(client, db) -> None:
    item = Item(
        kind="song", title="Edit Rgid Test", release_group_id="b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3"
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/items/{item.id}/edit")
    assert resp.status_code == 200
    assert b"b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3" in resp.content


# ---------------------------------------------------------------------------
# Edit form: POST /items/{id}/edit
# ---------------------------------------------------------------------------


def test_post_edit_item_updates_year(client, db) -> None:
    item = Item(kind="song", title="Before Year", year=1950)
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(
        f"/items/{item.id}/edit",
        data={
            "kind": "song",
            "title": "Before Year",
            "year": 1965,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db.expire_all()
    updated = db.scalar(select(Item).where(Item.id == item.id))
    assert updated.year == 1965


def test_post_edit_item_updates_mbid(client, db) -> None:
    item = Item(kind="song", title="Before Mbid", mbid="a03a59ef-5f18-3091-a3d9-a1b1c0a4e4f2")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(
        f"/items/{item.id}/edit",
        data={
            "kind": "song",
            "title": "Before Mbid",
            "mbid": "b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db.expire_all()
    updated = db.scalar(select(Item).where(Item.id == item.id))
    assert updated.mbid == "b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3"


def test_post_edit_item_rejects_bad_year(client, db) -> None:
    item = Item(kind="song", title="Edit Year Error")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(
        f"/items/{item.id}/edit",
        data={
            "kind": "song",
            "title": "Edit Year Error",
            "year": 999,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"year" in resp.content.lower()


def test_post_edit_item_rejects_bad_mbid(client, db) -> None:
    item = Item(kind="song", title="Edit Mbid Error")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(
        f"/items/{item.id}/edit",
        data={
            "kind": "song",
            "title": "Edit Mbid Error",
            "mbid": "not-a-uuid",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert b"mbid" in resp.content.lower()


# ---------------------------------------------------------------------------
# API: GET /api/items/{item_id}
# ---------------------------------------------------------------------------


def test_api_item_returns_year(client, db) -> None:
    item = Item(kind="song", title="API Year", year=1971)
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/api/items/{item.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 1971


def test_api_item_returns_mbids(client, db) -> None:
    item = Item(
        kind="song",
        title="API Mbid",
        mbid="a03a59ef-5f18-3091-a3d9-a1b1c0a4e4f2",
        release_group_id="b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3",
        has_cover=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/api/items/{item.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mbid"] == "a03a59ef-5f18-3091-a3d9-a1b1c0a4e4f2"
    assert data["release_group_id"] == "b14b60a8-6a29-4102-b4ea-b2c2d1b5f5a3"
    assert data["has_cover"] is True


def test_api_item_nulls_for_missing_fields(client, db) -> None:
    item = Item(kind="song", title="API Null Test")
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.get(f"/api/items/{item.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] is None
    assert data["mbid"] is None
    assert data["release_group_id"] is None
    assert data["has_cover"] is False
