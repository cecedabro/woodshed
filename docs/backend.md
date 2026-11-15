# Backend

FastAPI app in `backend/`. Prescriptive for code; look and feel is in
`docs/frontend.md` and `docs/design.md`.

## Allowed dependencies
Runtime: fastapi, uvicorn[standard], sqlalchemy>=2, alembic, psycopg[binary], pydantic>=2,
pydantic-settings, jinja2, python-multipart. Dev: httpx, pytest, pytest-cov, ruff, mypy,
pgserver. Use the standard library for everything else (`hmac`, `hashlib`, `zoneinfo`,
`uuid`, `shutil`, `struct`, `zlib`). Add nothing else.

## Layout (inside `backend/app/`, suggested; split a module when it passes ~300 lines)
```
main.py        create_app(): settings, engine, middleware, routers. Nothing else.
config.py      Settings (env) + check_production()            [exists]
db.py          make_engine, make_sessionmaker, get_db          [exists]
models.py      SQLAlchemy models (§model)
clock.py       now() -> aware UTC datetime; the one place that reads the clock
templating.py  the Jinja2Templates instance and filters (local_time, minutes, ...)
auth.py        cookie sign/verify, login/logout routes, login-required middleware
security.py    security headers + Origin check middleware
items.py       library pages; api.py JSON API; attachments.py; media.py (files on disk)
routines.py    routine pages; sessions.py runner page + logging API
stats.py       weekly totals, tempo history (pure functions + queries)
takes.py       recording upload, list, compare; settings.py /settings
pwa.py         manifest + service worker routes
```

## App factory rules
- `create_app(settings)` builds everything from `settings`; no module-level engine or
  settings. Routes get the DB with `Depends(get_db)` and settings via `request.app.state.settings`.
- Time: call `app.clock.now()` (or a dependency wrapping it), never `datetime.now()`
  directly, so tests can monkeypatch one place. Rate limits keep their state on `app.state`
  so each test app starts clean.

## §model
One migration per task that changes models. Names are fixed (the tests and later tasks use them):
```
item            id, kind (song|exercise), title, artist?, status (learning|polishing|repertoire),
                current_bpm?, original_url?, notes (text, default ''), created_at, updated_at
attachment      id, item_id → item ON DELETE CASCADE, kind (tab|pdf|audio), label (default ''),
                filename (original name), stored_name (uuid + ext), content_type, size_bytes, created_at
routine         id, name, created_at, updated_at
routine_block   id, routine_id → routine CASCADE, position, item_id → item CASCADE, minutes, bpm?
                unique (routine_id, position)
practice_session id, routine_id? → routine SET NULL, started_at, ended_at?
session_block   id, session_id → practice_session CASCADE, item_id? → item SET NULL, item_title,
                position, planned_seconds, played_seconds, bpm?, ended_at
take            id, item_id → item CASCADE, session_block_id? → session_block SET NULL,
                stored_name, content_type, size_bytes, duration_seconds, bpm?, note (default ''),
                recorded_at
setting         key (pk, text), value (text)
```
Enums are `String` columns with a `CHECK` constraint (simpler migrations than PG enums).
Timestamps are `DateTime(timezone=True)`. Index `session_block(ended_at)` and
`session_block(item_id, ended_at)`. Validation of ranges (SPEC 3.1, 4.1) is in pydantic
models in Python, not only in the database.

## §auth (SPEC 2)
- `sign(expiry: int, secret: str) -> str` and `verify(cookie: str, secret: str, now: int) -> bool`
  are pure functions. Compare with `hmac.compare_digest`.
- Middleware order: security headers outermost, then Origin check, then login check.
- The failed-login window is a list of timestamps on `app.state`; prune entries older than 15 min.

## §media (SPEC 3.5, 8.2, 10.4)
- Files live in `MEDIA_DIR/attachments/` and `MEDIA_DIR/takes/`, named `<uuid4 hex><ext>`.
  Create the directories on first write. Never use the client's filename on disk.
- Save uploads by copying the `UploadFile` in 1 MiB chunks and stop with 413 as soon as the
  limit is passed (delete the partial file). Also reject early when `Content-Length` is too big.
- Serve with `FileResponse(path, media_type=row.content_type)`; Starlette answers `Range`
  requests with 206. Look the row up by id; never build a path from user input.
- Deleting a row deletes its file in the same request (after the commit; a missing file is fine).

## §sessions (SPEC 5)
- `played_seconds` comes from the browser; the server clamps it (SPEC 5.5).
- `finish` sets `ended_at` and returns `{"blocks": n, "minutes": m, "per_block": [...]}`.
- Stale sessions (SPEC 5.7) are closed lazily: a helper `close_stale_sessions(db, now)` runs
  at the start of the home page and of `POST /api/sessions`.

## §stats (SPEC 7, 9)
- Put week maths in pure functions: `week_start(local_dt) -> date` (Monday), and
  `week_bounds_utc(monday: date) -> (start_utc, end_utc)` via `zoneinfo.ZoneInfo("Europe/Amsterdam")`.
- Weekly minutes = sum of `session_block.played_seconds` with `ended_at` in the week / 60,
  rounded down.
- Tempo history = per local day, `max(bpm)` of that item's blocks with a BPM.
- Charts are inline SVG built in Python (a function returning markup, rendered with `|safe`
  only for that trusted output). No chart library.

## Testing
See `docs/testing.md`. Use the fixtures in `backend/tests/conftest.py` (`client`, `db`,
`settings`, `app`). Every endpoint: one success and one failure path, with side effects
checked in the database and, for files, on disk under `settings.MEDIA_DIR`.
