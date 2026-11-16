"""Login, cookie and the deny-by-default middleware (SPEC 2.1–2.4)."""

from fastapi.testclient import TestClient

from app.config import DEV_APP_PASSWORD as TEST_PASSWORD


def test_right_password_sets_cookie(anon_client: TestClient) -> None:
    resp = anon_client.post("/login", data={"password": TEST_PASSWORD}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith("ws_session=")
    lower = cookie.lower()
    assert "httponly" in lower
    assert "samesite=lax" in lower
    assert "path=/" in lower
    assert "secure" not in lower


def test_wrong_password_401_no_cookie(anon_client: TestClient) -> None:
    resp = anon_client.post("/login", data={"password": "nope"}, follow_redirects=False)
    assert resp.status_code == 401
    assert "set-cookie" not in resp.headers


def test_anon_html_redirects_to_login(anon_client: TestClient) -> None:
    resp = anon_client.get("/library", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_anon_api_is_401_json(anon_client: TestClient) -> None:
    resp = anon_client.get("/api/items/1", follow_redirects=False)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Login required"}


def test_open_paths(anon_client: TestClient) -> None:
    assert anon_client.get("/healthz").status_code == 200
    assert anon_client.get("/login").status_code == 200


def test_tampered_cookie_is_logged_out(anon_client: TestClient) -> None:
    anon_client.cookies.set("ws_session", "9999999999.deadbeef")
    resp = anon_client.get("/", follow_redirects=False)
    assert resp.status_code == 303


def test_logged_in_client_sees_pages(client: TestClient) -> None:
    assert client.get("/library").status_code == 200


def test_logout_clears_cookie(client: TestClient) -> None:
    resp = client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert (
        'ws_session=""' in resp.headers["set-cookie"]
        or "max-age=0" in resp.headers["set-cookie"].lower()
    )
    assert client.get("/library", follow_redirects=False).status_code == 303
