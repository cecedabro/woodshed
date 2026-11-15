"""Shared fixtures. Tests use a real Postgres (docs/testing.md), never mocks or SQLite.

Database: a `woodshed_test` database on the server of $DATABASE_URL when that is set
(the devbox has a Postgres sidecar), otherwise a throwaway server started by pgserver.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import Base

BACKEND = Path(__file__).resolve().parents[1]


def _ensure_database(url: str) -> None:
    u = make_url(url)
    admin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": u.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{u.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def db_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    base = os.environ.get("DATABASE_URL")
    if base:
        url = make_url(base).set(drivername="postgresql+psycopg", database="woodshed_test")
        rendered = url.render_as_string(hide_password=False)
        _ensure_database(rendered)
        yield rendered
        return
    import pgserver

    srv = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="stop")
    yield srv.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    srv.cleanup()


@pytest.fixture(scope="session")
def migrated(db_url: str) -> str:
    """Wipe the test database and run every migration once per test session."""
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.attributes["keep_url"] = True
    command.upgrade(cfg, "head")
    return db_url


@pytest.fixture()
def settings(migrated: str, tmp_path: Path) -> Settings:
    return Settings(DATABASE_URL=migrated, MEDIA_DIR=tmp_path / "media")


@pytest.fixture()
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    yield application
    with application.state.engine.begin() as conn:  # empty every table after each test
        names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        if names:
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    application.state.engine.dispose()


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(app: FastAPI) -> Iterator[Session]:
    """A session on the same database the app uses, for arranging data and checking side effects."""
    with app.state.sessionmaker() as session:
        yield session
