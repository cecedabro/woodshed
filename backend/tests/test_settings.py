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
    assert 'type="number"' in resp.text
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
# Tuner A4 reference (SPEC 13.3)
# ---------------------------------------------------------------------------


def test_settings_shows_default_440_for_tuner_a4(client: TestClient) -> None:
    """When no tuner_a4 setting exists, the form shows 440."""
    _login(client)
    resp = client.get("/settings")
    assert 'name="tuner_a4"' in resp.text
    assert "440" in resp.text


def test_settings_shows_saved_tuner_a4(client: TestClient, db: Session) -> None:
    """When a tuner_a4 value is stored, the form shows it."""
    _login(client)
    with db.begin():
        db.add(Setting(key="tuner_a4", value="432"))
        db.commit()

    resp = client.get("/settings")
    assert "432" in resp.text


def test_post_settings_saves_valid_tuner_a4(client: TestClient, db: Session) -> None:
    """Valid tuner_a4 (430–450) is saved."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": "432"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    assert row == "432"


def test_post_settings_saves_440_tuner_a4(client: TestClient, db: Session) -> None:
    """440 is a valid tuner_a4 and is saved."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": "440"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    assert row == "440"


def test_post_settings_saves_450_tuner_a4(client: TestClient, db: Session) -> None:
    """450 (upper bound) is valid and saved."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": "450"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    assert row == "450"


def test_post_settings_saves_430_tuner_a4(client: TestClient, db: Session) -> None:
    """430 (lower bound) is valid and saved."""
    _login(client)
    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": "430"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    assert row == "430"


def test_post_settings_rejects_tuner_a4_below_430(client: TestClient, db: Session) -> None:
    """tuner_a4 below 430 is not saved."""
    _login(client)
    # First set a valid value
    with db.begin():
        db.add(Setting(key="tuner_a4", value="440"))
        db.commit()

    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": "429"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    # Must remain at the old value (440), 429 must NOT have been saved
    assert row == "440"


def test_post_settings_rejects_tuner_a4_above_450(client: TestClient, db: Session) -> None:
    """tuner_a4 above 450 is not saved."""
    _login(client)
    with db.begin():
        db.add(Setting(key="tuner_a4", value="440"))
        db.commit()

    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": "451"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    assert row == "440"


def test_post_settings_rejects_non_numeric_tuner_a4(client: TestClient, db: Session) -> None:
    """Non-numeric tuner_a4 is not saved."""
    _login(client)
    with db.begin():
        db.add(Setting(key="tuner_a4", value="440"))
        db.commit()

    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": "abc"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    assert row == "440"


def test_post_settings_empty_tuner_a4_does_not_overwrite(client: TestClient, db: Session) -> None:
    """Empty tuner_a4 field does not overwrite existing value."""
    _login(client)
    with db.begin():
        db.add(Setting(key="tuner_a4", value="432"))
        db.commit()

    resp = client.post(
        "/settings",
        data={"weekly_goal_minutes": "120", "tuner_a4": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with db.begin():
        row = db.scalar(text("SELECT value FROM setting WHERE key = 'tuner_a4'"))
    assert row == "432"


def test_tuner_page_uses_saved_tuner_a4(client: TestClient, db: Session) -> None:
    """Tuner page shows the saved tuner_a4 value in data-a4."""
    with db.begin():
        db.add(Setting(key="tuner_a4", value="432"))
        db.commit()

    resp = client.get("/tuner")
    assert 'data-a4="432"' in resp.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
