"""Tests for /library (SPEC 3.2).

Groups items by status, supports ?kind= and ?q= filters, shows empty state.
"""

from fastapi.testclient import TestClient


def _html(client: TestClient, path: str = "/library") -> str:
    """Fetch the library page and return the raw HTML."""
    resp = client.get(path)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
    return resp.text


# --- Basic rendering ---------------------------------------------------------


def test_get_library_returns_200(client: TestClient) -> None:
    """SPEC 3.2: GET /library returns 200."""
    resp = client.get("/library")
    assert resp.status_code == 200


def test_library_has_nav(client: TestClient) -> None:
    """SPEC 10.1: Library page includes navigation."""
    html = _html(client)
    assert "<nav" in html


def test_library_nav_active_library(client: TestClient) -> None:
    """SPEC 10.1: The Library nav link has aria-current='page'."""
    html = _html(client)
    assert 'aria-current="page"' in html
    assert 'href="/library"' in html


# --- Empty state --------------------------------------------------------------


def test_library_shows_empty_when_no_items(client: TestClient) -> None:
    """SPEC 3.2: Empty library shows a message."""
    html = _html(client)
    assert "No items" in html


def test_library_empty_links_to_new_item(client: TestClient) -> None:
    """SPEC 3.2: Empty state links to /items/new."""
    html = _html(client)
    assert 'href="/items/new"' in html


# --- Grouped by status --------------------------------------------------------


def test_library_groups_items_by_status(client: TestClient, db) -> None:
    """SPEC 3.2: Items are grouped by status (learning, polishing, repertoire)."""
    from app.models import Item

    db.add(Item(kind="song", title="Zebra Song", status="learning"))
    db.add(Item(kind="exercise", title="Blues Drill", status="polishing"))
    db.add(Item(kind="song", title="Gypsy Queen", status="repertoire"))
    db.commit()

    html = _html(client)

    assert "Learning" in html
    assert "Polishing" in html
    assert "Repertoire" in html


def test_library_learning_section_shows_learning_items(client: TestClient, db) -> None:
    """SPEC 3.2: The learning section only shows learning items."""
    from app.models import Item

    db.add(Item(kind="song", title="Zebra Song", status="learning"))
    db.add(Item(kind="song", title="Abandoned Song", status="polishing"))
    db.commit()

    html = _html(client)

    assert "Zebra Song" in html
    assert "Abandoned Song" in html


def test_library_omits_empty_status_groups(client: TestClient, db) -> None:
    """SPEC 3.2: Status groups with no items are not rendered."""
    from app.models import Item

    db.add(Item(kind="song", title="Only Learning", status="learning"))
    db.commit()

    html = _html(client)

    assert "Learning" in html
    assert "Polishing" not in html
    assert "Repertoire" not in html


# --- Kind filtering -----------------------------------------------------------


def test_library_filter_by_kind(client: TestClient, db) -> None:
    """SPEC 3.2: ?kind=song filters to songs only."""
    from app.models import Item

    db.add(Item(kind="song", title="Blues Song"))
    db.add(Item(kind="exercise", title="Blues Drill"))
    db.commit()

    html = _html(client, "/library?kind=song")

    assert "Blues Song" in html
    assert "Blues Drill" not in html


def test_library_filter_by_kind_exercise(client: TestClient, db) -> None:
    """SPEC 3.2: ?kind=exercise filters to exercises only."""
    from app.models import Item

    db.add(Item(kind="song", title="Blues Song"))
    db.add(Item(kind="exercise", title="Blues Drill"))
    db.commit()

    html = _html(client, "/library?kind=exercise")

    assert "Blues Song" not in html
    assert "Blues Drill" in html


def test_library_filter_by_kind_hides_empty_groups(client: TestClient, db) -> None:
    """SPEC 3.2: ?kind=song hides non-song status groups."""
    from app.models import Item

    db.add(Item(kind="exercise", title="Drill", status="learning"))
    db.add(Item(kind="song", title="Song", status="repertoire"))
    db.commit()

    html = _html(client, "/library?kind=song")

    assert "Song" in html
    assert "Drill" not in html
    assert "Learning" not in html
    assert "Repertoire" in html


# --- Title search -------------------------------------------------------------


def test_library_search_by_title(client: TestClient, db) -> None:
    """SPEC 3.2: ?q= matches titles case-insensitively."""
    from app.models import Item

    db.add(Item(kind="song", title="Zebra Crossing"))
    db.add(Item(kind="song", title="Morning Sun"))
    db.commit()

    html = _html(client, "/library?q=zebra")

    assert "Zebra Crossing" in html
    assert "Morning Sun" not in html


def test_library_search_case_insensitive(client: TestClient, db) -> None:
    """SPEC 3.2: ?q= is case insensitive."""
    from app.models import Item

    db.add(Item(kind="song", title="Zebra Crossing"))
    db.commit()

    html = _html(client, "/library?q=zebra")
    assert "Zebra Crossing" in html

    html2 = _html(client, "/library?q=ZEBRA")
    assert "Zebra Crossing" in html2

    html3 = _html(client, "/library?q=ZeBra")
    assert "Zebra Crossing" in html3


def test_library_search_substring(client: TestClient, db) -> None:
    """SPEC 3.2: ?q= matches substrings."""
    from app.models import Item

    db.add(Item(kind="song", title="Blues in the Night"))
    db.add(Item(kind="song", title="Night Rider"))
    db.add(Item(kind="song", title="Morning Sun"))
    db.commit()

    html = _html(client, "/library?q=night")

    assert "Blues in the Night" in html
    assert "Night Rider" in html
    assert "Morning Sun" not in html


# --- Combined filters ---------------------------------------------------------


def test_library_combined_kind_and_search(client: TestClient, db) -> None:
    """SPEC 3.2: ?kind= and ?q= work together."""
    from app.models import Item

    db.add(Item(kind="song", title="Zebra Crossing"))
    db.add(Item(kind="song", title="Blues Song"))
    db.add(Item(kind="exercise", title="Zebra Drill"))
    db.commit()

    html = _html(client, "/library?kind=song&q=zebra")

    assert "Zebra Crossing" in html
    assert "Blues Song" not in html
    assert "Zebra Drill" not in html
