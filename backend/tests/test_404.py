"""Styled 404 page (SPEC 10.6)."""

from fastapi.testclient import TestClient


def test_html_404_for_unknown_path(client: TestClient) -> None:
    """SPEC 10.6: unknown HTML paths render the styled 404 page."""
    r = client.get("/does/not/exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    assert "404" in r.text
    assert '<a href="/">' in r.text


def test_html_404_is_not_json(client: TestClient) -> None:
    """SPEC 10.6: unknown non-API paths return HTML even with Accept: application/json."""
    r = client.get("/does/not/exist", headers={"Accept": "application/json"})
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]


def test_api_404_is_json(client: TestClient) -> None:
    """SPEC 10.6: /api/ paths keep JSON errors."""
    r = client.get("/api/items/999999")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
