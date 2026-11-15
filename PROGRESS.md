# PROGRESS

Appended by the agent after each task: what changed, where, and gotchas for later tasks.

## Skeleton (by hand, 2026-11-11)
- `backend/` uv project (Python 3.12): `app/main.py` `create_app(settings)` keeps engine and
  sessionmaker on `app.state`; `/healthz`, `/readyz`; `config.py` with `check_production`.
- `app/clock.py`: call `clock.now()` via `from app import clock` so tests can monkeypatch it.
- `tests/conftest.py`: fixtures `settings`, `app`, `client`, `db`; tables are truncated after each test.
- Alembic baseline `0001` is empty; the first real tables come in T01.
- Vendored: htmx 2.0.11, alphaTab 1.9.0 (render only, see docs/frontend.md §alphatab).

## T01 — Models and one migration (2026-11-15)
- `backend/app/models.py`: added `Item`, `Attachment`, `Setting` models with `Mapped` types,
  CHECK constraints (`kind`, `status`, `attachment.kind`), cascade delete on attachments.
- `backend/alembic/versions/0002_item_attachment_setting.py`: manual migration creating
  `item`, `attachment`, `setting` tables with CHECK constraints and FK.
- `backend/tests/test_models_library.py`: 7 tests covering insert+read-back, defaults,
  CHECK constraint violations (IntegrityError), cascade delete, and setting updates.
- `backend/tests/conftest.py`: fixed `migrated` fixture — added `cfg.attributes["keep_url"] = True`
  so `env.py` does not overwrite the test DB URL with `$DATABASE_URL` env var.
- Gotcha: `env.py:12-13` unconditionally reads `$DATABASE_URL` from the environment; the
  `migrated` fixture must set `keep_url` to point Alembic at the test DB.

## T02 — Models and one migration (2026-11-15)
- `backend/app/models.py`: added `Routine`, `RoutineBlock`, `PracticeSession`, `SessionBlock`,
  `Take` models. `RoutineBlock` has a `UniqueConstraint` on `(routine_id, position)`.
  `PracticeSession.routine_id` and `SessionBlock.item_id` use `SET NULL` on delete.
  `Take.session_block_id` uses `SET NULL` on delete. `SessionBlock` has indexes on `ended_at`
  and `(item_id, ended_at)`. Added `Item.routine_blocks` and `Item.takes` relationships via
  late binding (string-based `relationship()`).
- `backend/alembic/versions/b3cda3472b74_practice.py`: migration creating all five tables with
  correct FK directions, constraints, indexes, and cascade/SET NULL rules.
- `backend/tests/test_models_practice.py`: 5 tests — routine with two ordered blocks, duplicate
  (routine_id, position) raises IntegrityError, deleting a routine sets session.routine_id to NULL,
  deleting an item cascades to takes, and deleting an item sets session_block.item_id to NULL while
  keeping item_title intact.

## T04 — Styled 404 (SPEC 10.6)
- `backend/app/main.py`: registered a 404 exception handler (`not_found_handler`) that checks the
  request path — `/api/...` paths return JSON 404, all other unknown paths render `404.html` with
  status 404. Imports updated with `HTTPException`, `Request`, `Response`.
- `backend/app/templates/404.html`: extends `base.html`, shows "404" heading, "Page not found" text,
  and a "Back to Home" link pointing to `/`.
- `backend/tests/test_404.py`: 3 tests — HTML 404 for unknown paths (asserts 404 status, HTML content,
  home link present), HTML 404 even with Accept: application/json, JSON 404 for `/api/` paths.

## T05 — Security headers + Origin check (SPEC 10.5, 2.6)
- `backend/app/security.py`: `SecurityMiddleware` (Starlette `BaseHTTPMiddleware`) adds four headers
  (`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, exact
  CSP) to every response, and returns 403 for non-GET/HEAD requests with a foreign `Origin` header.
  Cross-origin check compares `Origin` against `{scheme}://{hostname}`.
- `backend/app/main.py`: imported `SecurityMiddleware` and registered it via `app.add_middleware()`.
- `backend/tests/test_security.py`: 11 tests — headers on HTML/JSON/404 responses, 403 on POST/PUT/DELETE
  with foreign Origin, pass on same-origin Origin, pass without Origin header, GET/HEAD exempt from check,
  port mismatch treated as foreign.
- Gotcha: `TestClient` defaults to `http://testserver` (not `https`), so same-origin Origin in tests
  must be `http://testserver`.

## T06 — Pure cookie sign/verify (SPEC 2.2, docs/backend.md §auth)
- `backend/app/auth.py`: pure functions `sign(expiry, secret) -> str` and `verify(cookie, secret, now) -> bool`.
  Cookie format is `<expiry_unix>.<hex HMAC-SHA256>`; `sign` computes HMAC over `f"{expiry}."`,
  `verify` splits on `.`, rejects non-2-part or expired cookies, and uses `hmac.compare_digest`.
- `backend/tests/test_auth_cookie.py`: 7 tests — fresh cookie verifies; wrong secret, edited expiry,
  edited signature, missing dot, non-numeric expiry and expired cookie all fail.
- Gotcha: `verify` splits on `"."` expecting exactly 2 parts (expiry + signature); the HMAC data
  includes the trailing dot so tampering with expiry changes the HMAC and is detected.
