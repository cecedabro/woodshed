"""Tests for weekly goal settings (SPEC 9.1).

Routes: GET /settings, POST /settings
"""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Setting

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------


def test_get_settings_returns_200(client: TestClient) -> None:
    """GET /settings returns 200 with a form."""
    _login(client)
    resp = client.get("/settings")
    assert resp.status_code == 200


def test_settings_page_has_nav(client: TestClient) -> None:
    """SPEC 10.1: Settings page nav has active='settings'."""
    _login(client)
    resp = client.get("/settings")
    assert 'aria-current="page"' in resp.text
    assert 'href="/settings"' in resp.text


def test_settings_default_120_when_no_value(client: TestClient) -> None:
    """When no setting exists, the form defaults to 120 (SPEC 9.1)."""
    _login(client)
    resp = client.get("/settings")
    assert "120" in resp.text


def test_settings_shows_existing_value(client: TestClient, db: Session) -> None:
    """When a value is stored, the form shows it."""
    _login(client)
    with db.begin():
        db.add(Setting(key="weekly_goal_minutes", value="200"))
        db.commit()

    resp = client.get("/settings")
    assert "200" in resp.text


def test_settings_page_has_form(client: TestClient) -> None:
    """Settings page has a form with a numeric input named weekly_goal_minutes."""
    _login(client)
    resp = client.get("/settings")
    assert '<input type="number"' in resp.text
    assert 'name="weekly_goal_minutes"' in resp.text


# ---------------------------------------------------------------------------
# POST /settings — validation (SPEC 9.1)
# ---------------------------------------------------------------------------


def test_post_settings_accepts_valid_range(client: TestClient, db: Session) -> None:
    """0 is a valid weekly goal."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "0"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'"))
    assert row == "0"


def test_post_settings_accepts_120(client: TestClient, db: Session) -> None:
    """120 is a valid weekly goal (SPEC default)."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'"))
    assert row == "120"


def test_post_settings_accepts_10080(client: TestClient, db: Session) -> None:
    """10080 is the max and is valid (7 * 24 * 60 = total minutes in a week)."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "10080"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'"))
    assert row == "10080"


def test_post_settings_422_below_zero(client: TestClient) -> None:
    """Negative values return 422."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "-1"},
        follow_redirects=False,
    )
    assert resp.status_code == 422


def test_post_settings_422_above_max(client: TestClient) -> None:
    """Values above 10080 return 422 (SPEC 9.1: 0-10080)."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "10081"},
        follow_redirects=False,
    )
    assert resp.status_code == 422


def test_post_settings_422_non_numeric(client: TestClient) -> None:
    """Non-numeric input returns 422."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "abc"},
        follow_redirects=False,
    )
    assert resp.status_code == 422


def test_post_settings_422_empty(client: TestClient) -> None:
    """Empty input returns 422."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 422


def test_post_settings_replaces_existing_value(client: TestClient, db: Session) -> None:
    """POST replaces the existing weekly_goal_minutes value."""
    _login(client)
    with db.begin():
        db.add(Setting(key="weekly_goal_minutes", value="50"))

    client.post("/settings", data={"weekly_goal_minutes": "300"})

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'"))
    assert row == "300"


def test_post_settings_redirects_to_settings(client: TestClient) -> None:
    """POST /settings redirects to /settings on success."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "180"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings"


def test_post_settings_422_shows_error(client: TestClient) -> None:
    """422 response contains an error message."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "99999"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert (
        "error" in resp.text.lower()
        or "invalid" in resp.text.lower()
        or "goal" in resp.text.lower()
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
