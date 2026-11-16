"""Tests for GET /items/{item_id} — the item detail page (SPEC 3.4)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Item


@pytest.fixture()
def item(db: Session) -> Item:
    i = Item(
        kind="song",
        title="Stairway to the Blues",
        artist="The Woodshed Cats",
        status="polishing",
        current_bpm=120,
        original_url="https://example.com/stairway",
        notes="G key - 12 bar\nIntro: G D C\n<script>bad</script>",
    )
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def _html(client: TestClient, item_id: int) -> str:
    """Fetch the item page and return the raw HTML."""
    resp = client.get(f"/items/{item_id}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
    return resp.text


# --- Basic rendering -----------------------------------------------------------


def test_get_item_page_returns_200(client: TestClient, item: Item) -> None:
    assert client.get(f"/items/{item.id}").status_code == 200


def test_item_page_contains_title(client: TestClient, item: Item) -> None:
    html = _html(client, item.id)
    assert item.title in html


def test_item_page_contains_all_fields(client: TestClient, item: Item) -> None:
    """All non-None fields are rendered in the page."""
    html = _html(client, item.id)
    assert item.kind.capitalize() in html
    assert item.artist in html
    assert item.status.capitalize() in html
    assert str(item.current_bpm) in html
    assert item.original_url in html


# --- HTML attributes -----------------------------------------------------------


def test_original_url_has_target_and_rel(client: TestClient, item: Item) -> None:
    """External links must use target='_blank' and rel='noopener'."""
    html = _html(client, item.id)
    # Find the <a> tag with the original_url
    pattern = rf'<a[^>]*href="{re.escape(item.original_url)}"[^>]*>'
    match = re.search(pattern, html)
    assert match, f"No <a> tag found with href={item.original_url}"
    tag_text = match.group(0)
    assert 'target="_blank"' in tag_text
    assert "noopener" in tag_text


def test_item_page_has_edit_link(client: TestClient, item: Item) -> None:
    """The edit link points to /items/{id}/edit."""
    html = _html(client, item.id)
    assert f"/items/{item.id}/edit" in html
    assert 'href="/items/99999/edit"' not in html  # ensure it's the real ID


# --- Notes: escaping and newlines ---------------------------------------------


def test_notes_preserve_newlines_as_br(client: TestClient, item: Item) -> None:
    """Newlines in notes become <br> tags (2 newlines = 2 <br>s)."""
    html = _html(client, item.id)
    # Find the notes element
    notes_pattern = r'<p[^>]*class="notes"[^>]*>(.*?)</p>'
    match = re.search(notes_pattern, html, re.DOTALL)
    assert match, "No <p class='notes'> element found"
    notes_content = match.group(1)
    br_count = notes_content.count("<br>")
    # "G key - 12 bar\nIntro: G D C\n<script>bad</script>" has 2 newlines
    assert br_count == 2, f"Expected 2 <br> tags, found {br_count}"


def test_notes_html_is_escaped(client: TestClient, item: Item) -> None:
    """HTML in notes must be escaped (script tags should not execute)."""
    html = _html(client, item.id)
    notes_pattern = r'<p[^>]*class="notes"[^>]*>(.*?)</p>'
    match = re.search(notes_pattern, html, re.DOTALL)
    assert match, "No <p class='notes'> element found"
    notes_content = match.group(1)
    # The escaped version should contain &lt;script&gt;
    assert "&lt;script&gt;" in notes_content
    # A real <script> element must NOT exist inside the notes
    real_script = re.search(r"<script[^>]*>", notes_content)
    assert real_script is None, f"Unescaped <script> tag found in notes: {notes_content}"


# --- 404 handling --------------------------------------------------------------


def test_unknown_item_id_returns_404(client: TestClient) -> None:
    resp = client.get("/items/99999")
    assert resp.status_code == 404


def test_404_page_contains_styled_message(client: TestClient) -> None:
    resp = client.get("/items/99999")
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


def test_404_has_nav(client: TestClient) -> None:
    """The 404 page must still render the navigation."""
    resp = client.get("/items/99999")
    assert "<nav" in resp.text
