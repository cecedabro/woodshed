# PROGRESS

Appended by the agent after each task: what changed, where, and gotchas for later tasks.

## Skeleton (by hand, 2026-11-11)
- `backend/` uv project (Python 3.12): `app/main.py` `create_app(settings)` keeps engine and
  sessionmaker on `app.state`; `/healthz`, `/readyz`; `config.py` with `check_production`.
- `app/clock.py`: call `clock.now()` via `from app import clock` so tests can monkeypatch it.
- `tests/conftest.py`: fixtures `settings`, `app`, `client`, `db`; tables are truncated after each test.
- Alembic baseline `0001` is empty; the first real tables come in T01.
- Vendored: htmx 2.0.11, alphaTab 1.9.0 (render only, see docs/frontend.md §alphatab).
