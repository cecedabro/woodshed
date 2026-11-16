"""Tests for the tab viewer page (SPEC 3.6, docs/frontend.md §alphatab).

Tests cover:
- GET /items/{id}/tab/{attachment_id} renders the tab viewer
- alphaTab script tag is present (classic script, not module)
- tab.js module script tag is present
- data-file URL points to /media/attachment/{id}
- 404 for a non-tab attachment (e.g. pdf)
- 404 for an attachment belonging to another item
- 404 for a non-existent attachment id
- 404 for a non-existent item id
"""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Attachment, Item

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(db: Session, **kwargs: Any) -> Item:
    item = Item(
        kind=kwargs.get("kind", "song"),
        title=kwargs.get("title", "Test Song"),
        status=kwargs.get("status", "learning"),
        notes="",
        **{k: v for k, v in kwargs.items() if k not in ("kind", "title", "status")},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _make_attachment(db: Session, item: Item, kind: str = "tab", **kwargs: Any) -> Attachment:
    att = Attachment(
        item_id=item.id,
        kind=kind,
        filename=kwargs.get("filename", f"test.{kind}"),
        stored_name=kwargs.get("stored_name", f"{kind}_test.bin"),
        label=kwargs.get("label", ""),
        content_type=kwargs.get("content_type", "application/octet-stream"),
        size_bytes=kwargs.get("size_bytes", 100),
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


# ---------------------------------------------------------------------------
# HTML helpers (stdlib only, no bs4)
# ---------------------------------------------------------------------------


def _html_has_class(html: str, cls: str) -> bool:
    """Check if an element with *cls* exists anywhere in the HTML."""
    return bool(re.search(rf'<[^>]+\bclass=["\'][^"\']*\b{re.escape(cls)}\b[^"\']*["\']', html))


def _html_find_attr(html: str, id_value: str) -> dict[str, str] | None:
    """Return attribute dict for the first element whose id matches."""
    escaped_id = re.escape(id_value)
    pattern = rf'<[^>]+\bid=[\'"]{escaped_id}[\'"]([^>]*?)>'
    m = re.search(pattern, html)
    if m is None:
        return None
    attr_str = m.group(1)
    attrs: dict[str, str] = {}
    for attr_match in re.finditer(r'([\w-]+)=["\']([^"\']*)["\']', attr_str):
        attrs[attr_match.group(1)] = attr_match.group(2)
    return attrs


def _html_find_script(
    html: str, *, type_: str | None = None, src_contains: str | None = None
) -> list[dict[str, str]]:
    """Return info dicts for <script> tags matching criteria."""
    results: list[dict[str, str]] = []
    # Match <script ...> or <script .../>
    for m in re.finditer(r"<script\b([^>]*?)/?>", html):
        attrs_str = m.group(1)
        attrs: dict[str, str] = {}
        for am in re.finditer(r'(\w+)=["\']([^"\']*)["\']', attrs_str):
            attrs[am.group(1)] = am.group(2)
        src = attrs.get("src", "")
        stype = attrs.get("type", "")
        if type_ is not None and stype != type_:
            continue
        if src_contains is not None and src_contains not in src:
            continue
        results.append(attrs)
    return results


def _html_find_back_link(html: str, item_id: int) -> bool:
    """Check that a link to /items/{id} exists."""
    return bool(re.search(rf'<a[^>]*href=["\']/items/{re.escape(str(item_id))}["\']', html))


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------


class TestTabViewerRendering:
    """Tab viewer page rendering tests."""

    def test_tab_viewer_returns_200(self, client: TestClient, db: Session) -> None:
        item = _make_item(db)
        att = _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        assert resp.status_code == 200

    def test_tab_viewer_contains_item_title(self, client: TestClient, db: Session) -> None:
        item = _make_item(db, title="My Blues Song")
        att = _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        assert "My Blues Song" in resp.text

    def test_tab_viewer_has_back_link(self, client: TestClient, db: Session) -> None:
        item = _make_item(db)
        att = _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        assert _html_find_back_link(resp.text, item.id), "Back link to /items/{id} not found"

    def test_tab_viewer_has_viewer_container(self, client: TestClient, db: Session) -> None:
        item = _make_item(db)
        att = _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        assert _html_has_class(resp.text, "tab-viewer"), ".tab-viewer container not found"

    def test_tab_viewer_has_alphaTab_script(self, client: TestClient, db: Session) -> None:
        """The alphaTab library is loaded via a classic (non-module) script tag."""
        item = _make_item(db)
        att = _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        scripts = _html_find_script(resp.text, src_contains="alphatab/alphaTab")
        assert len(scripts) == 1, "Expected exactly one alphaTab script tag"
        tag = scripts[0]
        assert "type" not in tag, "alphaTab script should not have type='module'"

    def test_tab_viewer_has_tab_js_module(self, client: TestClient, db: Session) -> None:
        """The tab.js glue code is loaded as an ES module."""
        item = _make_item(db)
        att = _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        scripts = _html_find_script(resp.text, type_="module", src_contains="tab.js")
        assert len(scripts) == 1, "Expected exactly one tab.js module script tag"

    def test_tab_viewer_data_file_url(self, client: TestClient, db: Session) -> None:
        """The #tab element has data-file pointing to /media/attachment/{id}."""
        item = _make_item(db)
        att = _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        attrs = _html_find_attr(resp.text, "tab")
        assert attrs is not None, "#tab element not found"
        assert attrs.get("data-file") == f"/media/attachment/{att.id}"


# ---------------------------------------------------------------------------
# 404 handling
# ---------------------------------------------------------------------------


class TestTabViewer404:
    """404 edge case tests."""

    def test_non_tab_attachment_returns_404(self, client: TestClient, db: Session) -> None:
        """A PDF attachment accessed via the tab viewer route returns 404."""
        item = _make_item(db)
        att = _make_attachment(db, item, kind="pdf")

        resp = client.get(f"/items/{item.id}/tab/{att.id}")
        assert resp.status_code == 404

    def test_non_existent_attachment_returns_404(self, client: TestClient, db: Session) -> None:
        """An attachment id that does not exist returns 404."""
        item = _make_item(db)
        _make_attachment(db, item, kind="tab")

        resp = client.get(f"/items/{item.id}/tab/99999")
        assert resp.status_code == 404

    def test_attachment_of_another_item_returns_404(self, client: TestClient, db: Session) -> None:
        """An attachment belonging to a different item returns 404."""
        item1 = _make_item(db, title="Item 1")
        item2 = _make_item(db, title="Item 2")
        tab = _make_attachment(db, item1, kind="tab")

        resp = client.get(f"/items/{item2.id}/tab/{tab.id}")
        assert resp.status_code == 404

    def test_non_existent_item_returns_404(self, client: TestClient) -> None:
        """A non-existent item id returns 404."""
        resp = client.get("/items/99999/tab/1")
        assert resp.status_code == 404

    def test_404_has_navigation(self, client: TestClient) -> None:
        """The 404 page should still render the navigation bar."""
        resp = client.get("/items/99999/tab/1")
        assert resp.status_code == 404
        assert "<nav" in resp.text
