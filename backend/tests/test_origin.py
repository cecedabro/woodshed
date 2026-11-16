"""Origin check (SPEC 2.6): compare Origin with scheme://host[:port]."""

from fastapi.testclient import TestClient


def test_same_origin_post_with_port_passes(app) -> None:
    """SPEC 2.6: POST with matching origin (including port) is allowed."""
    c = TestClient(app, base_url="http://localhost:8765")
    r = c.post("/some-path", headers={"Origin": "http://localhost:8765"})
    assert r.status_code != 403


def test_foreign_origin_post_blocked(app) -> None:
    """SPEC 2.6: POST with a foreign origin gets 403."""
    c = TestClient(app, base_url="http://localhost:8765")
    r = c.post("/some-path", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_https_same_origin_passes(app) -> None:
    """SPEC 2.6: POST with matching HTTPS origin is allowed."""
    c = TestClient(app, base_url="https://guitar.example")
    r = c.post("/some-path", headers={"Origin": "https://guitar.example"})
    assert r.status_code != 403


def test_https_scheme_mismatch_blocked(app) -> None:
    """SPEC 2.6: HTTP origin when scheme is HTTPS gets 403."""
    c = TestClient(app, base_url="https://guitar.example")
    r = c.post("/some-path", headers={"Origin": "http://guitar.example"})
    assert r.status_code == 403


def test_no_origin_header_passes(app) -> None:
    """SPEC 2.6: POST without Origin header is allowed through."""
    c = TestClient(app, base_url="http://localhost:8765")
    r = c.post("/some-path")
    assert r.status_code != 403


def test_get_with_foreign_origin_not_blocked(app) -> None:
    """SPEC 2.6: Origin check does not apply to GET."""
    c = TestClient(app, base_url="http://localhost:8765")
    r = c.get("/some-path", headers={"Origin": "http://evil.example"})
    assert r.status_code != 403
