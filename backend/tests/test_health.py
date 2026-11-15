from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_healthz_returns_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "from-env")
    monkeypatch.setenv("MEDIA_DIR", "/data/media")
    s = Settings()
    assert s.APP_PASSWORD == "from-env"
    assert str(s.MEDIA_DIR) == "/data/media"
    assert s.APP_ENV == "development"


def test_readyz_ready_when_database_answers(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_readyz_unavailable_when_database_is_down(settings: Settings) -> None:
    bad = settings.model_copy(update={"DATABASE_URL": "postgresql+psycopg://x:y@127.0.0.1:1/none"})
    with TestClient(create_app(bad)) as c:
        r = c.get("/readyz")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable"}


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({}, "APP_PASSWORD"),
        ({"APP_PASSWORD": "real-password"}, "SESSION_SECRET"),
        ({"APP_PASSWORD": "real-password", "SESSION_SECRET": "short"}, "SESSION_SECRET"),
    ],
)
def test_production_refuses_development_secrets(update: dict[str, str], message: str) -> None:
    s = Settings(APP_ENV="production").model_copy(update=update)
    with pytest.raises(RuntimeError, match=message):
        create_app(s)


def test_production_starts_with_real_secrets() -> None:
    s = Settings(APP_ENV="production", APP_PASSWORD="real-password", SESSION_SECRET="s" * 32)
    assert create_app(s).state.settings.APP_ENV == "production"


def test_clock_now_is_aware_utc() -> None:
    from app import clock

    assert clock.now().utcoffset() == timedelta(0)
