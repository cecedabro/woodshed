"""Shared fixtures. Tests use a real Postgres (docs/testing.md), never mocks or SQLite.

Database: a `woodshed_test_<pid>` database on the server of $DATABASE_URL when that is set
(the devbox has a Postgres sidecar), otherwise a throwaway server started by pgserver.
Each test run gets its own database, so a run that hangs or is killed can never block the
next one (they used to share one database and wait on each other's locks). The run drops
its database at the end and removes ones left behind by runs that no longer exist.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import Base

BACKEND = Path(__file__).resolve().parents[1]


TEST_DB_PREFIX = "woodshed_test_"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _admin_engine(url: str) -> Engine:
    return create_engine(
        make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT"
    )


def _create_database(url: str) -> None:
    """Create this run's database, after dropping ones left by dead runs."""
    name = make_url(url).database
    admin = _admin_engine(url)
    with admin.connect() as conn:
        names = conn.execute(
            text("SELECT datname FROM pg_database WHERE datname LIKE :p"),
            {"p": TEST_DB_PREFIX + "%"},
        ).scalars()
        for other in names:
            suffix = other.removeprefix(TEST_DB_PREFIX)
            if other == name or (suffix.isdigit() and not _pid_alive(int(suffix))):
                conn.execute(text(f'DROP DATABASE IF EXISTS "{other}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()


def _drop_database(url: str) -> None:
    admin = _admin_engine(url)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{make_url(url).database}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def db_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    base = os.environ.get("DATABASE_URL")
    if base:
        url = make_url(base).set(
            drivername="postgresql+psycopg", database=f"{TEST_DB_PREFIX}{os.getpid()}"
        )
        rendered = url.render_as_string(hide_password=False)
        _create_database(rendered)
        yield rendered
        _drop_database(rendered)
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


TEST_PASSWORD = Settings().APP_PASSWORD


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    """A logged-in client (SPEC 2.1). Use `anon_client` to test what strangers see."""
    with TestClient(app) as c:
        resp = c.post("/login", data={"password": TEST_PASSWORD}, follow_redirects=False)
        assert resp.status_code == 303, "test login failed"
        yield c


@pytest.fixture()
def anon_client(app: FastAPI) -> Iterator[TestClient]:
    """A client without a session cookie."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(app: FastAPI) -> Iterator[Session]:
    """A session on the same database the app uses, for arranging data and checking side effects."""
    with app.state.sessionmaker() as session:
        yield session
