"""Tests for theme settings (SPEC 12.3-12.4).

Routes: GET /settings, POST /settings (theme field), GET /styleguide
"""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Setting

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


# ---------------------------------------------------------------------------
# Default theme
# ---------------------------------------------------------------------------


def test_default_theme_is_amp(client: TestClient, db: Session) -> None:
    """When no theme setting exists, the default is 'amp'."""
    _login(client)
    resp = client.get("/settings")
    assert resp.status_code == 200
    # The default 'amp' option should be selected
    assert 'value="amp"' in resp.text
    assert "selected" in resp.text


def test_default_theme_no_data_attribute(client: TestClient, db: Session) -> None:
    """When theme is 'amp' (the default), no data-theme attribute is rendered."""
    _login(client)
    resp = client.get("/settings")
    assert resp.status_code == 200
    html_tag = resp.text.split("<html")[1].split(">")[0]
    assert "data-theme" not in html_tag


# ---------------------------------------------------------------------------
# Theme persistence
# ---------------------------------------------------------------------------


def test_post_theme_saves_flat(client: TestClient, db: Session) -> None:
    """POST with theme=flat persists the setting."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "theme": "flat"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'theme'"))
    assert row == "flat"


def test_post_theme_saves_daylight(client: TestClient, db: Session) -> None:
    """POST with theme=daylight persists the setting."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "theme": "daylight"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'theme'"))
    assert row == "daylight"


def test_get_theme_shows_picked_value(client: TestClient, db: Session) -> None:
    """GET /settings shows the persisted theme value as selected."""
    _login(client)
    with db.begin():
        db.add(Setting(key="theme", value="daylight"))

    resp = client.get("/settings")
    assert resp.status_code == 200
    # daylight option should be selected
    assert "daylight" in resp.text


def test_post_theme_invalid_falls_back_to_amp(client: TestClient, db: Session) -> None:
    """POST with an invalid theme value falls back to amp."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "theme": "nonexistent"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'theme'"))
    assert row == "amp"


# ---------------------------------------------------------------------------
# data-theme attribute
# ---------------------------------------------------------------------------


def test_data_theme_flat_rendered(client: TestClient, db: Session) -> None:
    """When theme is 'flat', legacy pages render data-theme='flat'."""
    _login(client)
    with db.begin():
        db.add(Setting(key="theme", value="flat"))

    resp = client.get("/settings")
    assert resp.status_code == 200
    assert 'data-theme="flat"' in resp.text


def test_data_theme_daylight_rendered(client: TestClient, db: Session) -> None:
    """When theme is 'daylight', legacy pages render data-theme='daylight'."""
    _login(client)
    with db.begin():
        db.add(Setting(key="theme", value="daylight"))

    resp = client.get("/settings")
    assert resp.status_code == 200
    assert 'data-theme="daylight"' in resp.text


# ---------------------------------------------------------------------------
# Settings page theme selector
# ---------------------------------------------------------------------------


def test_settings_has_theme_selector(client: TestClient) -> None:
    """Settings page has a theme selector with all three options."""
    _login(client)
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert 'name="theme"' in resp.text
    assert 'value="amp"' in resp.text
    assert 'value="flat"' in resp.text
    assert 'value="daylight"' in resp.text


# ---------------------------------------------------------------------------
# Styleguide route
# ---------------------------------------------------------------------------


def test_styleguide_returns_200(client: TestClient) -> None:
    """GET /styleguide returns 200."""
    _login(client)
    resp = client.get("/styleguide")
    assert resp.status_code == 200
