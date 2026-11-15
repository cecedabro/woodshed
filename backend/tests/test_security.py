"""Security middleware: headers + Origin check (SPEC 10.5, 2.6)."""

from fastapi.testclient import TestClient

EXPECTED_CSP = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob:"
)


def test_security_headers_on_html(client: TestClient) -> None:
    """SPEC 10.5: every response has the four security headers."""
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"] == EXPECTED_CSP


def test_security_headers_on_json(client: TestClient) -> None:
    """SPEC 10.5: security headers also on API / health responses."""
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"] == EXPECTED_CSP


def test_security_headers_on_404(client: TestClient) -> None:
    """SPEC 10.5: even unknown paths carry the headers."""
    r = client.get("/no/such/page")
    assert r.status_code == 404
    assert r.headers["x-frame-options"] == "DENY"


def test_foreign_origin_post_403(client: TestClient) -> None:
    """SPEC 2.6: POST with a foreign Origin gets 403."""
    r = client.post("/some-path", headers={"Origin": "https://evil.com"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Forbidden"


def test_foreign_origin_put_403(client: TestClient) -> None:
    """SPEC 2.6: PUT with a foreign Origin gets 403."""
    r = client.put("/some-path", headers={"Origin": "https://evil.com"})
    assert r.status_code == 403


def test_foreign_origin_delete_403(client: TestClient) -> None:
    """SPEC 2.6: DELETE with a foreign Origin gets 403."""
    r = client.delete("/some-path", headers={"Origin": "https://evil.com"})
    assert r.status_code == 403


def test_same_origin_post_passes(client: TestClient) -> None:
    """SPEC 2.6: POST with same-origin Origin is allowed through."""
    # TestClient defaults to http://testserver
    r = client.post("/no/such/path", headers={"Origin": "http://testserver"})
    assert r.status_code == 404


def test_no_origin_header_passes(client: TestClient) -> None:
    """SPEC 2.6: POST without an Origin header is allowed through."""
    r = client.post("/no/such/path")
    assert r.status_code == 404


def test_get_with_foreign_origin_not_blocked(client: TestClient) -> None:
    """SPEC 2.6: Origin check applies only to non-GET/HEAD methods."""
    r = client.get("/no/such/path", headers={"Origin": "https://evil.com"})
    assert r.status_code == 404


def test_head_with_foreign_origin_not_blocked(client: TestClient) -> None:
    """SPEC 2.6: HEAD requests are exempt from Origin checking."""
    r = client.head("/no/such/path", headers={"Origin": "https://evil.com"})
    assert r.status_code == 404


def test_foreign_origin_with_port_403(client: TestClient) -> None:
    """SPEC 2.6: Origin with a different port is considered foreign."""
    r = client.post("/some-path", headers={"Origin": "https://testserver:8080"})
    assert r.status_code == 403
