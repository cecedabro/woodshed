"""Every route needs a login unless SPEC 2.3 lists it as open (deny by default)."""

import re

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import is_open_path
from app.models import Base


def _api_routes(routes: list, prefix: str = "") -> list[tuple[str, set[str]]]:
    """(path, methods) of every route, also inside included routers (FastAPI ≥ 0.16x wraps them)."""
    found: list[tuple[str, set[str]]] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append((prefix + route.path, set(route.methods)))
        elif hasattr(route, "include_context"):
            ctx = route.include_context
            found += _api_routes(ctx.included_router.routes, prefix + ctx.prefix)
    return found


def _row_counts(db: Session) -> dict[str, int]:
    return {
        t.name: db.execute(text(f'SELECT COUNT(*) FROM "{t.name}"')).scalar_one()
        for t in Base.metadata.sorted_tables
    }


def test_every_closed_route_needs_login(app: FastAPI, anon_client: TestClient, db: Session) -> None:
    routes = _api_routes(list(app.routes))
    assert len(routes) > 20, "route discovery broke"
    before = _row_counts(db)
    checked = 0
    for route_path, methods in routes:
        path = re.sub(r"\{[^}]+\}", "1", route_path)
        if is_open_path(path):
            continue
        method = sorted(methods)[0]
        resp = anon_client.request(method, path, follow_redirects=False)
        if path.startswith("/api/"):
            assert resp.status_code == 401, f"{method} {route_path}: {resp.status_code}"
        else:
            assert resp.status_code == 303, f"{method} {route_path}: {resp.status_code}"
            assert resp.headers["location"] == "/login", f"{method} {route_path}"
        checked += 1
    assert checked > 20
    db.expire_all()
    assert _row_counts(db) == before, "an anonymous request changed the database"


def test_unknown_path_needs_login_too(anon_client: TestClient) -> None:
    resp = anon_client.get("/no-such-page", follow_redirects=False)
    assert resp.status_code == 303


def test_open_paths_are_exactly_spec_2_3() -> None:
    for path in ["/login", "/healthz", "/readyz", "/static/css/tokens.css", "/sw.js"]:
        assert is_open_path(path)
    for path in ["/", "/library", "/api/items", "/media/attachment/1", "/loginx", "/static"]:
        assert not is_open_path(path)
