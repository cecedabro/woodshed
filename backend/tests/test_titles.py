"""Tests for page titles (T89).

Every page's <title> contains "Woodshed" exactly once (from the base template
suffix), and the navbar-title h1 never contains "Woodshed".  Home is the
exception: <title>Woodshed</title> with no suffix.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Item, Routine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _title(html: str) -> str:
    """Extract the content of the <title> tag."""
    start = html.index("<title>") + 7
    end = html.index("</title>")
    return html[start:end]


def _navbar_title(html: str) -> str:
    """Extract the text of the .navbar-title h1 element."""
    start = html.index('class="navbar-title"')
    h1_start = html.rindex("<h1", 0, start)
    h1_end = html.index("</h1>", start)
    inner = html[h1_start:h1_end]
    return inner.strip("<h1>").strip()


def _woodshed_count_title(html: str) -> int:
    return _title(html).count("Woodshed")


def _woodshed_count_navbar(html: str) -> int:
    return _navbar_title(html).count("Woodshed")


# ---------------------------------------------------------------------------
# Home — <title>Woodshed</title>, no suffix
# ---------------------------------------------------------------------------


def test_home_title_is_just_woodshed(client: TestClient) -> None:
    """Home has <title>Woodshed</title> (no suffix)."""
    resp = client.get("/")
    assert resp.status_code == 200
    title = _title(resp.text)
    assert title == "Woodshed"
    assert "Woodshed" in resp.text  # still present on the page


# ---------------------------------------------------------------------------
# /tuner
# ---------------------------------------------------------------------------


def test_tuner_title_has_woodshed_once(client: TestClient) -> None:
    resp = client.get("/tuner")
    assert resp.status_code == 200
    assert _woodshed_count_title(resp.text) == 1
    assert _woodshed_count_navbar(resp.text) == 0


def test_tuner_title_text(client: TestClient) -> None:
    resp = client.get("/tuner")
    assert _title(resp.text) == "Tuner · Woodshed"


# ---------------------------------------------------------------------------
# /settings
# ---------------------------------------------------------------------------


def test_settings_title_has_woodshed_once(client: TestClient) -> None:
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert _woodshed_count_title(resp.text) == 1
    assert _woodshed_count_navbar(resp.text) == 0


def test_settings_title_text(client: TestClient) -> None:
    resp = client.get("/settings")
    assert _title(resp.text) == "Settings · Woodshed"


# ---------------------------------------------------------------------------
# /items/new
# ---------------------------------------------------------------------------


def test_items_new_title_has_woodshed_once(client: TestClient) -> None:
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert _woodshed_count_title(resp.text) == 1
    assert _woodshed_count_navbar(resp.text) == 0


def test_items_new_title_text(client: TestClient) -> None:
    resp = client.get("/items/new")
    assert _title(resp.text) == "New Item · Woodshed"


# ---------------------------------------------------------------------------
# /routines/new
# ---------------------------------------------------------------------------


def test_routines_new_title_has_woodshed_once(client: TestClient) -> None:
    resp = client.get("/routines/new")
    assert resp.status_code == 200
    assert _woodshed_count_title(resp.text) == 1
    assert _woodshed_count_navbar(resp.text) == 0


def test_routines_new_title_text(client: TestClient) -> None:
    resp = client.get("/routines/new")
    assert _title(resp.text) == "New Routine · Woodshed"


# ---------------------------------------------------------------------------
# Item detail page
# ---------------------------------------------------------------------------


def _make_item(db: Session) -> Item:
    item = Item(kind="song", title="Stairway to the Blues", artist="The Cats", status="learning")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_item_detail_title_has_woodshed_once(client: TestClient, db: Session) -> None:
    item = _make_item(db)
    resp = client.get(f"/items/{item.id}")
    assert resp.status_code == 200
    assert _woodshed_count_title(resp.text) == 1
    assert _woodshed_count_navbar(resp.text) == 0


def test_item_detail_title_text(client: TestClient, db: Session) -> None:
    item = _make_item(db)
    resp = client.get(f"/items/{item.id}")
    assert _title(resp.text) == "Stairway to the Blues · Woodshed"


# ---------------------------------------------------------------------------
# Item delete page
# ---------------------------------------------------------------------------


def _make_item_for_delete(db: Session) -> Item:
    item = Item(kind="exercise", title="Blues Scale in A")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_item_delete_title_has_woodshed_once(client: TestClient, db: Session) -> None:
    item = _make_item_for_delete(db)
    resp = client.get(f"/items/{item.id}/delete")
    assert resp.status_code == 200
    assert _woodshed_count_title(resp.text) == 1
    assert _woodshed_count_navbar(resp.text) == 0


def test_item_delete_title_text(client: TestClient, db: Session) -> None:
    item = _make_item_for_delete(db)
    resp = client.get(f"/items/{item.id}/delete")
    assert "Delete Blues Scale in A" in _title(resp.text)


# ---------------------------------------------------------------------------
# Routine delete page
# ---------------------------------------------------------------------------


def _make_routine_for_delete(db: Session) -> Routine:
    routine = Routine(name="Evening Practice")
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


def test_routine_delete_title_has_woodshed_once(client: TestClient, db: Session) -> None:
    routine = _make_routine_for_delete(db)
    resp = client.get(f"/routines/{routine.id}/delete")
    assert resp.status_code == 200
    assert _woodshed_count_title(resp.text) == 1
    assert _woodshed_count_navbar(resp.text) == 0


def test_routine_delete_title_text(client: TestClient, db: Session) -> None:
    routine = _make_routine_for_delete(db)
    resp = client.get(f"/routines/{routine.id}/delete")
    assert "Delete Evening Practice" in _title(resp.text)
