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

## T07 — Login rate limiting (SPEC 2.5)
- `backend/app/auth.py`: extended with rate-limit helpers (`_prune_failures`, `_is_rate_limited`,
  `_record_failure`) that track timestamps on `app.state._failed_logins`. Added `get_login`,
  `post_login`, `post_logout` route handlers using `Depends(_get_settings)`. `post_login` returns
  HTTP 429 when 10+ failures occur within 15 minutes. Cookie helpers `_set_session_cookie` and
  `_clear_session_cookie` added. `Form(...)` imported from `fastapi`.
- `backend/app/main.py`: imported `get_login`, `post_login`, `post_logout` from `app.auth` and
  registered them via `app.add_api_route` (avoids wrapper functions that bypass FastAPI DI).
- `backend/app/templates/login.html`: login page with password form, "Wrong password" error display,
  and "Back to Home" link.
- `backend/tests/test_login_ratelimit.py`: 2 tests — 11th failed attempt returns 429; correct
  password succeeds after 15-minute window (verified via `clock.now` monkeypatch).
- Gotcha: `app.add_api_route` is required instead of wrapper functions — manual calls of
  `Depends`-backed handlers bypass dependency injection and crash the response serializer.

## T09 — Item service + JSON API (SPEC 3.1, 3.8)
- `backend/app/items_service.py`: Pydantic `ItemIn` model with validators for kind (song/exercise),
  title (1-200 chars, no blanks), status (learning/polishing/repertoire, default "learning"),
  current_bpm (20-400), original_url (http/https only), notes (≤20k chars). `create_item(db, data)`
  persists via `db.flush()` + `db.refresh()`. `get_item(db, id)` uses `select(Item).where(Item.id==id)`.
- `backend/app/api.py`: `POST /api/items` → 201 JSON, `GET /api/items/{id}` → 200/404. Imports
  `get_db` from `app.db`. Added `db.commit()` after `create_item` so the item survives the
  per-request session rollback.
- `backend/app/main.py`: imported and included `api_router` via `app.include_router(api_router)`.
- `backend/tests/test_api_items.py`: 18 tests — valid creation (all fields, minimal with defaults,
  http/https URLs), boundary BPM (19→422, 20→201, 400→201, 401→422), title length (""→422, 200→201,
  201→422), ftp URL→422, unknown status/kind→422, GET existing→200, GET missing→404. Count assertions
  use `.scalars().first() or 0` because empty tables return `None` from `scalar()`.
- Gotcha: The per-request `get_db` session context manager rolls back uncommitted data on exit.
  Added `db.commit()` in the POST route handler so seeded items survive for subsequent GET/migration checks.
- Gotcha: `db.execute(select(Item)).scalar()` returns `None` (not `0`) when no rows exist.
  Used `.scalars().first() or 0` in count assertions.

## T12 — /library endpoint (SPEC 3.2)
- `backend/app/items_service.py`: added `filter_items(db, *, kind=None, q=None)` using
  `func.lower(Item.title).contains()` for case-insensitive substring search, and
  `group_by_status(items)` preserving canonical order (`learning` → `polishing` → `repertoire`).
- `backend/app/main.py`: imported `filter_items`, `group_by_status`, `get_library`;
  registered `GET /library` via `app.add_api_route`. Handler reads `?kind=` and `?q=`
  query params, calls service functions, renders `library.html` with `active="library"`.
- `backend/app/templates/library.html`: new template — filter form (kind dropdown, q input,
  clear link), empty state with link to `/items/new`, grouped `<section>` sections per status
  with `<li>` items and `.kind-badge` spans linking to `/items/{id}`.
- `backend/app/static/style.css`: added `.library-filters`, `.library-empty`, `.library-group`,
  `.library-list`, `.library-item`, `.kind-badge` (scoped colors for `kind-song`/`kind-exercise`).
- `backend/tests/test_library.py`: 15 tests — 200 OK, nav active state, empty state & link,
  group rendering by status, ?kind= filtering (song/exercise), ?q= case-insensitive substring,
  combined filters, and empty status groups omitted.
- Fix: wrapped `db.scalars(stmt).all()` in `list()` to satisfy mypy strict typing.

## T14 — Attachment upload, delete, download & listing (SPEC 3.5, 3.9, 3.10)
- `backend/app/config.py`: added `MAX_ATTACHMENT_BYTES` (100 MB default) to `Settings`.
- `backend/app/main.py`: added `joinedload(Item.attachments)` to `get_item_page`; registered three routes —
  `POST /items/{item_id}/attachments` (upload with kind derivation, size check, label),
  `POST /items/{item_id}/attachments/{attachment_id}/_delete` (delete DB row + file),
  `GET /attachments/{attachment_id}/download` (serve file with Content-Disposition).
- `backend/app/templates/items_detail.html`: added attachment listing grouped by kind
  (tabs render via alphaTab at `/items/{id}/tab/{att_id}`, PDFs open in browser, audio uses `<audio>`),
  and a multipart upload form POSTing to `/_delete` for deletion.
- `backend/app/static/style.css`: added `.attachment-group`, `.attachment-list`, `.upload-form`,
  `.attachment-disk` styles for the attachment UI.
- `backend/tests/test_attachments.py`: 14 tests — valid upload (tab/pdf/audio + label), 422 for
  unknown extension, 413 for oversized file, 404 for missing item/attachment, download returns
  file bytes, missing disk file returns 404, delete removes DB row + file.
- Fix: model uses `filename` (not `original_name`); test file extensions must use allowed
  extensions (`.gp`, `.pdf`, `.mp3` etc.) since `.tab` is not in SPEC §3.5 extension list.
- Gotcha: `TestClient` follows redirects by default; all 303 assertions use `follow_redirects=False`.

## T10 — Media serving route `GET /media/{kind}/{id}` (SPEC 10.4)
- `backend/app/main.py`: added `get_media(kind, id, request, login)` route registered at `/media/{kind}/{id}`.
  Requires login (`require_login`). Kind map converts URL slugs ("attachment", "take") to DB models and
  filesystem dirs ("attachments", "takes"). Serves files with Range request support (206 partial,
  `Content-Range` header, `Accept-Ranges: bytes`). Missing files return 404; unknown kind returns 404.
  `Content-Disposition` uses `media.stored_name` (works for both `Attachment` and `Take`).
  Falls back to `application/octet-stream` when `media.content_type` is `None`.
- `backend/tests/test_media_serving.py`: 11 tests — serve attachment with content-type, serve take,
  range requests (first bytes, trailing bytes, open-end), error cases (unknown kind 404, unknown id 404,
  missing file 404, unauthenticated 401).
- `backend/app/main.py`: added `Depends` to FastAPI imports; fixed B904 (added `from None` to HTTPException).
- Fix: `Take` model has no `filename` attribute (only `stored_name`), so route uses `stored_name` for
  both Attachment and Take. Content-type header assertions use `startswith` because FastAPI appends
  `; charset=utf-8` to the content-type value.
- Gotcha: Auth check fires before kind/id validation, so unauthenticated requests always get 401
  regardless of whether kind/id are valid.

## T13 — Media helpers (SPEC 3.5, backend.md §media)
- `backend/app/media.py`: `kind_for_filename(name)` maps file extensions (case-insensitive) to
  attachment kind (`tab`/`pdf`/`audio` or `None`); `save_upload(upload, subdir, limit_bytes,
  media_dir)` copies the upload in 1 MiB chunks, names the file `<uuid4 hex><ext>`, and raises
  `TooLarge` (with partial file removed) when the limit is exceeded; `delete_file(media_dir,
  subdir, stored_name)` removes a stored file (missing file is not an error).
- `backend/tests/test_media.py`: 15 tests — extension mapping (all tab/pdf/audio extensions,
  uppercase `.GP5` → tab, `.exe` → None), upload within limit, exact limit OK, limit+1 raises
  TooLarge with no file left, multi-chunk upload, subdirectory creation, delete existing file,
  delete missing file (no error). Uses `tmp_path` with real files on disk.

## T15 — Delete item (SPEC 3.7)
- `backend/app/main.py`: added `get_delete_item` (GET `/items/{item_id}/delete` → confirmation page)
  and `post_delete_item` (POST `/items/{item_id}/delete` → deletes disk files, cascades DB deletes,
  303 redirect to `/library`). Imported `delete_file` from `app.media`.
- `backend/app/templates/items_delete.html`: confirmation page showing item title, kind, artist,
  attachment count with inline warning, take count with inline warning, delete/cancel buttons.
  Cancel links to `/items/{item_id}`. Form POSTs to `/_delete` (no, to `/items/{item_id}/delete`).
- `backend/tests/test_item_delete.py`: 17 tests — GET page 200, title display, attachment/take
  counts, combined counts, 404 for missing item, cancel link, delete form, item removed from DB,
  303 redirect to `/library`, unknown item → 404, attachment file deleted, take file deleted,
  all files deleted, DB cascade on attachments/takes, session block keeps `item_title` after delete.
- Fix: `Item.takes` is added via late binding at module level (models.py:238); mypy doesn't see it
  on class instances. Added `# type: ignore[attr-defined]` on `joinedload(Item.takes)` calls in
  main.py:172,198. Mypy strict rejects unused `# type: ignore` comments.

## T18 — Routine CRUD pages (SPEC 4.1, 4.3)
- `backend/app/main.py`: six route handlers — `get_routines`, `get_new_routine`, `post_new_routine`,
  `get_routine_edit`, `get_delete_routine`, `post_delete_routine`. Auth via `login: None = Depends(require_login)`
  on GET routes; POST creates `Routine` with `db.add+flush+refresh` then 303 redirects to `/routines/{id}/edit`.
- `backend/app/templates/routines_list.html`: table with name, items count, `total_minutes` (SQL SUM),
  updated_at, action links. Empty state with create link.
- `backend/app/templates/routines_new.html`, `routines_delete.html`, `routines_edit.html` (stub).
- `backend/app/static/style.css`: `.routines-table`, `.btn-danger`, `.btn-inline`, `.routine-empty` styles.
- `backend/tests/test_routines.py`: 26 tests — auth, list rendering, creation, deletion, session
  preservation (SPEC 4.3: deleting routine keeps sessions with `routine_id` NULL).
- Gotcha: SQLAlchemy `expire_on_commit=False` keeps deleted objects in identity map; tests call
  `db.expunge(routine)` before `db.get()`. `TestClient.post()` follows redirects; 303 checks
  use `follow_redirects=False`. `Request.form()` values can be `UploadFile | str`; `.strip()`
  guarded with `isinstance(raw_name, str)`.

## T20 — Timer pure module (SPEC 5.2, frontend.md §js)
- `backend/app/static/js/timer.js`: pure module `createTimer(plannedSeconds)` returning an object
  with `start(now)`, `pause(now)`, `resume(now)`, `addSeconds(n)`, `remaining(now)`, `played(now)`,
  `isDone(now)`, `isRunning()`. Pausing freezes both remaining and played; resume continues
  decrementing remaining from the paused value. `remaining` clamped to 0 (never negative).
- `backend/tests/js/timer.test.js`: 10 tests — remaining/played while running, pause excludes
  time, resume continues from pause point, addSeconds(60), isDone at exactly 0, remaining never
  negative, completed timer stays at 0, played only counts actual running time, initial not-started
  state, pause-then-addSeconds interaction.

## T21 — Metronome pure module (SPEC 6, frontend.md §js)
- `backend/app/static/js/metronome.js`: pure module with `clampBpm(bpm)` (round, clamp 20-400),
  `beatTimes(startTime, bpm, beatsPerBar, fromBeat, untilTime)` returning `[{time, beat, accent}]`
  arrays, and `tapTempo(tapsMs)` (average BPM from last 4 taps, gap >2s restarts, null if <2 taps).
- `backend/tests/js/metronome.test.js`: 25 tests — clampBpm rounding/clamping boundaries,
  120 BPM at 0.5s spacing, beatsPerBar 4/3 accent patterns, fromBeat/untilTime windows,
  tapTempo 500ms intervals→120, 2.5s gap restart, fewer-than-2 taps→null, 2000ms gap no-restart.

## T22 — Sessions API router and tests (SPEC 5.5, 5.6, 5.7)
- `backend/app/sessions.py`: new router with three endpoints — `POST /api/sessions` (create session,
  auto-populate routine total_minutes), `POST /api/sessions/{id}/blocks` (log block with clamping to
  [0, elapsed+60], skip persist if clamped value <10s, update item.current_bpm),
  `POST /api/sessions/{id}/finish` (return blocks count, minutes, per_block array).
  All endpoints enforce `require_login` via `Depends`.
- `backend/app/main.py`: imported `sessions_router` and registered via `app.include_router`.
- `backend/tests/test_sessions_api.py`: 9 tests — create session (routine + no routine),
  log block (stored, clamped, <10s skipped, BPM update), finish (summary, 404), unauthenticated 401.
- Gotcha: `TestClient` calls must happen after `db.commit()` to avoid 404s on created resources.
  `PracticeSession.started_at` must be set explicitly in fixtures to match mocked `clock_now()`,
  otherwise `elapsed_since_start` clamping pushes blocks below 10s threshold.
- Gotcha: `base_time` was redefined inside the `with` block, shadowing the outer `base_time`;
  the `base_time` used by `_block_elapsed` in the test was wrong, causing a false clamping failure.
