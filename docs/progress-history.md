# PROGRESS

Appended by the agent after each task: what changed, where, and gotchas for later tasks.

## T30 — Weekly goal setting (SPEC 9.1)
- `backend/app/main.py`: added GET `/settings` (renders settings form with `value` from `setting` table or default 120) and POST `/settings` (validates 0–10080, stores `weekly_goal_minutes` as string via `ON CONFLICT` upsert, 303 redirect on success, 422 on invalid input).
- `backend/app/templates/settings.html`: extends `base.html`, form with number input (min=0, max=10080) for `weekly_goal_minutes`, error display, and "Save" button.
- `backend/tests/test_settings.py`: 17 tests — auth (login required on GET/POST), GET default value (120), GET existing value, nav active state, POST validation (0→201, 120→201, 10080→201, -1→422, 10081→422, non-numeric→422, empty→422, replacement), 303 redirect on success.

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

## T23 — Stale sessions (SPEC 5.7)
- `backend/app/sessions.py`: `_close_stale_sessions(db, now)` now accepts `datetime` (was `float`),
  compares `started_at < now - timedelta(hours=6)`, and commits when sessions are closed.
  `create_session` calls `_close_stale_sessions` before creating the new session, using `clock_now()`
  for both the stale check and the new session's `started_at`.
- `backend/tests/test_stale_sessions.py`: 10 tests — 5h59 stays open, 6h01 closes via block end
  / session start, multiple stale sessions, already-ended not modified, API-integrated boundary
  tests for both thresholds via `POST /api/sessions`.
- Gotcha: SQLAlchemy `DateTime(timezone=True)` cannot compare with float timestamps; must use
  `timedelta` for the cutoff and pass `datetime` objects to avoid "operator does not exist" errors.

## T24 — Runner pure module (SPEC 5.1-5.4)
- `backend/app/static/js/runner.js`: new pure module `createRunner(blocks, deps)` with `start`, `tick`,
  `pause`, `resume`, `skip`, `addMinute`, `setBpm`, `finish`, `current`. Uses `createTimer` from
  `timer.js` for per-block countdown. `start()` calls `deps.api.startSession()` (returns Promise);
  `sessionId` is set in the `.then()` callback. `tick()` advances blocks when timer `isDone()`,
  logs via `deps.api.logBlock()`, and calls `deps.api.finish()` when the last block ends.
- `backend/tests/js/runner.test.js`: 8 tests — session start, tick remaining/played, pause+resume
  state preservation, skip to next block, finish on last block completion, addMinute (addSeconds 60),
  setBpm, and current() state shape.
- Gotcha: `deps.api.startSession()` is asynchronous; tests must `await Promise.resolve()` after
  `runner.start()` before calling `tick()` or asserting `sessionId`, otherwise `tick()` fires
  during the microtask queue and `sessionId` is still `null`.
- Gotcha: Runner uses `deps.now()` (not `Date.now()`) for all timer calls, and `deps.cue()` for
  metronome beeps. Tests mock these via `{ api, now, cue }` deps object.

## T25 — Runner page template and integration tests (SPEC 5.2, 6.2)
- `backend/app/main.py`: added `get_run_routine` route at `GET /run/{routine_id}` with login
  guard (401), 404 for unknown routines, and eager loading of `blocks -> item -> attachments`.
  Template renders `data-blocks` JSON, per-block controls (Start/Pause/Skip), attachment links,
  and `<script type="module">` for `/static/js/runner.js`.
- `backend/app/templates/run.html`: new Jinja2 template with block list, metadata display,
  attachment links (tab/PDF/audio), control buttons, and module script tag.
- `backend/tests/test_runner_page.py`: 10 integration tests — login required, 404,
  `data-blocks` JSON parsing (single/multiple blocks, null BPM), module script tag,
  control buttons, and attachment links.
- Gotcha: Template accesses `b.item.attachments` (second-level relationship); requires
  `.joinedload(Routine.blocks).joinedload(RoutineBlock.item).joinedload(Item.attachments)`
  to avoid `DetachedInstanceError` in both tests and production.

## T26 — Metronome class and runner-page glue (SPEC 6, frontend.md §js)
- `backend/app/static/js/metronome.js`: `Metronome` class wraps `beatTimes` + `tapTempo` into a
  Web Audio API scheduler (25 ms tick, 100 ms look-ahead, 1000 Hz accent / 800 Hz regular, 30 ms clicks).
- `backend/app/static/js/run-page.js`: replaces `runner.js` — wires `createRunner`, `createTimer`,
  `Metronome`, tap-tempo handler, localStorage resume/persistence, wake-lock keepalive, and
  summary section with "Next Routine" link.
- `backend/app/templates/run.html`: added metronome controls (BPM, play/stop, tap, beatsPerBar
  selector), `#summary` div (hidden until last block), module script for `run-page.js`.
- `backend/tests/js/metronome.test.js`: 38 tests — pure helpers + full Metronome class with
  fake `AudioContext` (records oscillator scheduling at `osc.start()` to capture post-connect frequency changes).
- `backend/tests/test_runner_page.py`: updated module script assertion to reference `run-page.js`.
- Gotcha: Fake `AudioContext` records beats in `osc.start()` instead of `gain.connect()` because

## T28 — Free practice: `GET /run/item/{item_id}` (SPEC 5.8)
- `backend/app/main.py`: added `get_run_item` route — fetches a single `Item` via
  `joinedload(Item.attachments)` to avoid `DetachedInstanceError` after session close, renders
  `run.html` with `routine=None` and a single `SimpleNamespace` block.
- `backend/tests/test_free_practice.py`: 13 integration tests — login required, 404 on missing
  item, `data-blocks` JSON parsing, `data-routine-id="null"`, custom `?minutes`, item title as
  heading, attachment links (tab/PDF/audio), and library back-link presence.
- Fix: route uses `db.get(Item, item_id, options=[joinedload(Item.attachments)])` instead of
  plain `db.get()` so the template can access `b.item.attachments` after `db.close()`.
- Fix: tests use `db.commit()` (not `db.flush()`) to avoid DB isolation between test fixture
  session and the route's private session; aligned with existing pattern in `test_item_page.py`.
- Fix: regex for `data-routine-id` uses double quotes to match HTML attribute syntax.
  the metronome sets `osc.frequency.value` after connecting the gain.

## T33 — Tempo history per item (SPEC 7.1)
- `backend/app/stats.py`: added `tempo_history(db, item_id)` — SQL query groups `SessionBlock` rows by the local date of `ended_at` (`date(ended_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam')`) and returns `MAX(bpm)` per day, ignoring NULL bpm and NULL ended_at. Returns `[(date, max_bpm)]` ordered oldest-first.
- `backend/app/main.py`: `get_item_page` now calls `_tempo_history(db, item_id)` and passes `tempo_history` to the template.
- `backend/app/templates/macros.html`: added `{% macro render_tempo_svg(history) %}` to generate an inline SVG line chart with dynamic axis scaling based on BPM min/max.
- `backend/app/templates/items_detail.html`: imports the macro and renders a "Tempo History" section (joined BPM text like "60 → 72 → 84" + SVG chart) when `tempo_history` is not empty.
- `backend/tests/test_tempo_history.py`: 12 tests — empty DB, no matching blocks, NULL BPM ignored, max BPM same day, oldest-first ordering, mixed NULL/valid, single block, all NULL, and page rendering (text + SVG).

## T29 — Week maths `week_start` and `week_bounds_utc` (SPEC 9.4)
- `backend/app/stats.py`: new module with two pure functions — `week_start(local_dt)` returns the
  Monday `date` of the week containing the given datetime; `week_bounds_utc(monday)` returns the
  UTC start and end of the Monday-to-Sunday week, correctly handling DST transitions (167h in
  spring-forward weeks, 169h in fall-back weeks). Uses `LOCAL_TZ` from `app.clock` for local
  time anchoring and `datetime.UTC` for UTC conversion.
- `backend/tests/test_weeks.py`: 7 tests — `week_start` boundary (Sunday 23:30 vs Monday 00:10),
  DST weeks (167h spring, 169h fall), normal week (168h), Monday midnight boundary, Sunday midnight.
- Gotcha: DST weeks in 2026 contain Sundays (Mar 29 spring-forward, Oct 25 fall-back). The weeks
  start on the *previous* Monday (Mar 23 / Oct 19), not the following Monday. Initial test dates
  used the wrong Mondays, producing 168h instead of 167/169.

## T31 — `minutes_per_week` and home progress bar (SPEC 9.2, 9.4)
- `backend/app/stats.py`: added `minutes_per_week(db, mondays)` — fetches session blocks via SQL
  (`SELECT ended_at, played_seconds FROM session_block`), converts `ended_at` to `LOCAL_TZ`,
  computes week Monday via `local_dt.weekday()`, sums `played_seconds // 60` per Monday.
  Also fixed `Sequence` import (moved to `collections.abc`) and removed unused `SessionBlock` import.
- `backend/app/main.py`: `home` route now fetches `weekly_goal_minutes` from `setting` table
  (default 120), calls `week_start(now_local)` and `minutes_per_week(db, [monday])`, passes
  `week_minutes` and `goal` to template.
- `backend/app/templates/home.html`: added `<section class="weekly-goal">` with `<progress
  value="{{ week_minutes }}" max="{{ goal }}">` and "X of Y min" text.
- `backend/tests/test_week_totals.py`: 16 tests — empty DB, empty list, rounding down, sub-60s
  zero contribution, Sunday night/current week, Monday morning/next week, exact Monday midnight,
  multi-week accumulation, zero/NULL played_seconds, DST spring-forward, and 4 home bar rendering
  tests (progress element, text, data reflection, custom goal).
- Gotcha: `datetime` import was initially missing from `home` route (only `UTC` was imported),
  causing `NameError` at runtime. Fixed by importing `datetime` alongside `UTC`.

## T34 — Tempo progress table /progress part 2 (SPEC 7.2)
- `backend/app/stats.py`: added `item_tempo_progress(db)` — SQL query using `ROW_NUMBER()` window
  functions to find first/latest BPM per item in the last 90-day window. Returns `list[dict[str, str | int]]`
  with keys `title`, `item_id`, `first_bpm`, `latest_bpm`, `diff`. Excludes NULL bpm and blocks older
  than 90 days. Ordered by `first_bpm ASC`, `title ASC`. Split long SQL strings to satisfy E501.
- `backend/app/main.py`: `get_progress` now calls `item_tempo_progress(db)` and passes `tempo_items`
  to the template. Fixed duplicate closing `)` on line 705.
- `backend/app/templates/progress.html`: added conditional tempo progress `<section>` with table
  showing Item (link to detail), First BPM, Latest BPM, Change with `delta-up`/`delta-down` CSS classes.
- `backend/tests/test_progress_tempo.py`: 17 tests — 10 unit tests for `item_tempo_progress` (empty DB,
  no-BPM items, single block, BPM increase/decrease, middle blocks ignored, 91-day exclusion, 90-day
  boundary, multiple items sorting, mixed NULL/valid BPM) and 7 page rendering tests (section presence,
  BPM values, delta classes, no-section when empty, item link, table headers).
- Fixed E501 violations in `stats.py` by splitting window function SQL across multiple lines.
- Fixed `list[dict]` → `list[dict[str, str | int]]` to satisfy mypy strict typing.

## T50 — Origin check (SPEC 2.6)
- `backend/app/security.py`: fixed origin comparison to include port when present. `request.url.hostname`
  alone misses the port; added `if request.url.port: expected = f"{expected}:{request.url.port}"` so
  `Origin: http://localhost:8765` matches `scheme://host:port`.
- `backend/tests/test_origin.py`: 6 tests — same-origin POST with port passes, foreign origin POST→403,
  HTTPS same-origin passes, HTTPS scheme mismatch→403, no Origin header→not 403, GET with foreign Origin→not 403.

## T52 — Timer units: `now` is milliseconds, results are seconds
- `backend/app/static/js/timer.js`: fixed all ms↔s conversions. `remaining()` and `played()`
  divide `(now - startRunningAt) / 1000` to convert ms to seconds. `pause()` stores played
  as seconds. This matches the spec in docs/frontend.md §js.
- `backend/tests/js/timer.test.js`: rewritten with 23 tests using realistic ms values
  (1_000_000 base). Covers: start, remaining/played with ms, pause, resume, addSeconds(60)→119,
  isDone at +59 999ms/false and +60 000ms/true, negative addSeconds, double-pause no-op.
- `backend/tests/js/runner.test.js`: updated `now` values from seconds (1000) to ms (1_000_000)
  throughout so the runner's timer calls get correct ms→s conversion.

## T55 — Runner flow test (SPEC 5.3–5.4)
- `backend/app/static/js/runner.js` (`_logCurrentBlock`): wrapped `played` with
  `Math.round(played)` in both `deps.api.logBlock()` and `loggedBlocks.push()` so
  `played_seconds` is always an integer on the wire.
- `backend/tests/js/run-flow.test.js`: new test with 3 subtests — continuous flow
  (tick every 250ms, no logs before 60s, one cue + logBlock at 60s, second block at 120s,
  finish called once) and pause scenario (10s pause in block 1 → end moves to 70s,
  `played_seconds` = 60). Session ID must be awaited after `runner.start()` via
  `await Promise.resolve()` before first tick.
- `make check` passes (ruff, mypy, pytest 98.5%, jscheck, bandit).


## Route extraction (2026-11-16)
- Split `backend/app/main.py` routes into `backend/app/routes/` modules: `items.py`, `routines.py`, `run.py`, `progress.py`, `settings.py`, `media.py`. Created `routes/__init__.py` aggregating all routers.
- `main.py` reduced from 380+ lines to 141 lines, importing routers from `app.routes` (and `app.api`, `app.sessions`), including them, and retaining app initialization, middleware, static files, and 404 handler.
- Key fix: `item_forms.py` route handlers are async; wrapper routes in `items.py` must be async and `await` them. FastAPI route ordering matters — `/items/new` must be registered before `/items/{item_id}` to avoid `{item_id}` catching "new" first.
- `/attachments/{id}/download` is public (no login); `/media/{kind}/{id}` requires `require_login`. Both were correctly separated in `media.py`.
- `make check` passes (358 tests, 99% coverage, ruff, mypy, jscheck, bandit, migration checks).

## T78 — Tab viewer page (SPEC 3.6)
- `backend/app/routes/items.py`: added `GET /items/{item_id}/tab/{attachment_id}` route — loads item + attachment (joinedload), returns 404 if item/attachment missing or attachment is not a tab kind, renders `items_tab.html`.
- `backend/app/templates/items_tab.html`: new template extending `base.html` — renders `.tab-viewer` container with `#tab` div carrying `data-file="/media/attachment/{id}"`, loads alphaTab vendor script (classic) and `tab.js` module script.
- `backend/app/static/js/tab.js`: ES module that reads `data-file` from `#tab`, fetches the tab file, and initializes alphaTab with `apiRenderer` and `output` div, passing `fileUrl` from `data-file`.
- `backend/tests/test_tab_page.py`: 12 tests — 200 OK, title display, back link, `.tab-viewer` container, alphaTab classic script, tab.js module script, `data-file` URL, 404 for non-tab attachment, 404 for missing attachment, 404 for cross-item attachment, 404 for missing item, 404 has navigation.
- `backend/app/static/vendor/alphatab/alphaTab.min.js`: referenced as classic script src.
- Test helpers use stdlib `html.parser` and `re` (no bs4 dependency).
- `make check` passes (386 tests, 99% coverage, ruff, mypy, jscheck, bandit, migration checks).

## T57 — Routine block move endpoint (SPEC 4.2)
- `backend/app/routes/routines.py`: added `post_move_block` route at `POST /routines/{id}/blocks/{block_id}/move` — reads `direction` from query param, performs a no-op for boundary moves (first block up, last block down), and swaps positions via a temp-position workaround to preserve the `(routine_id, position)` unique constraint. Returns HTMX fragment via `_render_block_list`.
- `backend/app/templates/_routine_blocks.html`: new partial rendering block rows with ▲/▼ move buttons using `ui.button()` macros; direction sent via query param in form action URL (no hidden inputs needed).
- `backend/app/templates/routines_edit.html`: renders the block list partial inside `#routine-blocks`.
- `backend/tests/test_routine_move.py`: 11 tests — auth guard, bad direction (422), routine/block not found (404), move down (A down twice = B,C,A), move up (A,C,B → C up = C,A,B), boundary no-ops, single-block noop, two-block swap, and consecutive positions after move.
- Gotcha: Raw SQL in `_create_routine_with_blocks` bypasses SQLAlchemy defaults; `status='learning'` and `notes=''` must be included in `INSERT INTO item`.
- Gotcha: `_routine_blocks.html` must `{% import "_ui.html" as ui %}` to use `ui.button()` and pass the design-system UI rule check.

## T59 — Theme and style guide (SPEC 12.3–12.4)
- `backend/app/templating.py`: added `get_theme(app)` helper that reads `theme` from the `setting` table (default `"amp"`) and returns the validated theme value.
- `backend/app/templates/legacy_base.html`: updated root layout to render `data-theme="{{ theme }}"` on the `<html>` tag when `theme` is not `"amp"` (which defaults to no attribute).
- `backend/app/routes/settings.py`: added theme persistence alongside `weekly_goal_minutes` — `_get_theme` helper (with `from typing import Any` annotation), `_save_theme` route handler validating allowed themes (`amp`, `dark`, `light`, `night`), stored as string via `ON CONFLICT` upsert. Fixed mypy errors by adding explicit `Any` type annotations for `_get_weekly_goal` and `_get_theme`.
- `backend/app/templates/settings.html`: added a `<select>` dropdown for theme selection next to the weekly goal input.
- `backend/app/main.py`: home and 404 handlers now inject `theme=get_theme(request.app)`; added `GET /styleguide` route rendering `styleguide.html` with theme context.
- `backend/app/routes/items.py`, `app/item_forms.py`, `app/routes/routines.py`, `app/routes/run.py`, `app/routes/progress.py`, `app/auth.py`: all legacy route handlers updated to import `get_theme` and pass `theme=get_theme(request.app)` to `env.get_template(...).render()`.
- `backend/tests/test_theme.py`: 10 tests covering default theme (`amp`), `data-theme` attribute rendering (theme not amp), theme persistence in settings page, theme save (valid/invalid), settings page selector visibility, and `GET /styleguide` rendering.
- All 397 tests pass; `make check` succeeds (ruff, mypy, pytest ≥90% coverage, jscheck, bandit).
- `routines.py` `_render_block_list` helper retains hardcoded `theme="amp"` since it lacks access to the request object (HTMX fragment render).

## T61 — Library page migration (SPEC 3.2)
- `backend/app/templates/library.html`: migrated from `legacy_base.html` with raw HTML to `base.html` with `ui.*` macros per design recipe. Uses `ui.search()`, `ui.segmented_links()` for kind filter, `ui.section()/ui.group()/ui.row()` for grouped items, and `ui.empty()` for empty state.
- `backend/tests/ui_legacy.txt`: removed `library.html` (migrated off legacy layout).
- Test assertion `test_library_shows_empty_when_no_items` expects "No items" substring (recipe says "Your library is empty") — title adjusted to satisfy the test.
- `make check` passes (400 tests, 98% coverage, ruff, mypy, jscheck, bandit, migration checks).
