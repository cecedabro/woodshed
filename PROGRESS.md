# PROGRESS

Append 3–5 lines per task below. Older entries (T01–T61) are in `docs/progress-history.md`;
don't read that file, search it with `rg` if you need something.

## Gotchas so far
- Login: one `LoginRequiredMiddleware` in `app/auth.py` guards everything except
  `OPEN_PATHS` / `/static/`. Routes need no login dependency. The `client` fixture is
  already logged in; use `anon_client` for not-logged-in behaviour.
- `tests/test_auth_coverage.py` requests every route anonymously: a new open route must be
  added to `OPEN_PATHS` (only if SPEC 2.3 says so).
- Pages extend `base.html` and `{% import "_ui.html" as ui %}`. `ui.empty()` is a plain
  macro (`{{ }}`), `ui.section()` / `ui.group()` / `ui.row()` take a `{% call %}` block.
- The navbar `<h1>` comes from `{% block title %}`; pages have no `<h1>` of their own.
- Field errors from `ui.field(error=…)` render as `class="field-error"`.
- Runner: `data-blocks="{{ blocks_json }}"` (built by `runner_blocks()` in
  `app/routes/run.py`, each block has `start_bpm`). Tests parse it with `html.unescape`.
- Routine editor fragment: `partials/routine_blocks.html`, swapped into `#blocks`.

## By hand, 2026-11-16 (T48, T49, T54, T57, T65)
- Login middleware, logged-in test client, auth coverage test; `/attachments/{id}/download`
  removed (files are served by `/media/attachment/{id}`); wrong password → 401.
- Runner blocks built in Python with `start_bpm`; `runner.js` reads `start_bpm`.
- Routine editor add/remove + the editor page in the new design.
- Old tests that asserted old markup (raw `<input>`, `class="error"`, five nav links,
  `style.css`) now accept the new markup.

## Home page migration, 2026-11-16 (T69)
- Rewrote `backend/app/templates/home.html` to extend `base.html` and use the new UI
  macros (`ui.section`, `ui.progress`, `ui.start`, `ui.row`, `ui.empty`).
- Updated `backend/app/main.py` `home()` route: replaced `routines` context with `first`,
  `others`, and `aside_text` (computed from `goal - week_minutes` or "Goal reached").
- Updated `backend/tests/test_home.py`: replaced `primary` class assertion with `start` class
  check and added `test_home_progress_shows_of_goal` for "of 120 min".
- Removed `home.html` from `backend/tests/ui_legacy.txt`.
- Footer text uses "Weekly minutes only." (avoiding "streak" which a behavioural test
  asserts must not appear on the home page).
- All 408 tests pass, 99% coverage, `make check` clean.

## Item detail page migration, 2026-11-16 (T72)
- Rewrote `backend/app/templates/items_detail.html` to extend `base.html` and use `ui.*` macros:
  `.stack-lg` layout with `.spread` header (h2 + badges + practising button), `.split` for
  details/notes and files/tempo, `ui.section()`/`ui.group()`/`ui.row()`/`ui.empty()`.
- Changed heading from `<h1>` to `<h2>` (navbar title block provides the only `<h1>`).
- Updated `backend/app/routes/items.py`: added `has_cover=False` to template context.
- Updated `backend/tests/test_item_page.py`: notes regex from `<dd>` to `<p>`, original_url
  link regex from `<a\s+href=...>` to `<a[^>]*href=...>` to match row macro output.
- Removed `items_detail.html` from `backend/tests/ui_legacy.txt`.
- All 411 tests pass, 99% coverage, `make check` clean.

## Item page part 2: Files section and upload form (T80)
- Updated Files section in `items_detail.html`: tab rows link to `/items/{id}/tab/{att}` (was
  all to `/media/attachment/`), audio uses `<audio class="audio" controls preload="none">` in
  a padded group (not a row), PDF rows link to `/media/attachment/{att}`.
- Added per-file remove button via `ui.button()` (small, secondary, with trash icon) in a POST
  form to `/items/{id}/attachments/{att}/_delete` for each tab, pdf, and audio attachment.
- Added upload form at bottom of Files section: `enctype="multipart/form-data"`, group with
  `ui.field("file", "File", type="file")` + `ui.field("label", "Label (optional)")`, `.actions`
  with `ui.button("Upload", kind="primary", type="submit")`.
- Added `.remove-form` class (`display: inline`) to `pages.css`.
- No assertions in `test_attachments.py` checked old markup; no test updates needed.
- All 411 tests pass, 99% coverage, `make check` clean.

## Item forms migration: new + edit pages (T81)
- Created `backend/app/templates/partials/item_fields.html` with shared form sections (Song,
  Practice, Notes) using `ui.select()`, `ui.field()`, `ui.textarea()` inside `.group` divs.
  Replaced `ui.section()` calls with plain `<section>` elements since blocking macros can't
  be called with `{{ }}` inside an `{% include %}` partial.
- Rewrote `items_new.html` and `items_edit.html` to extend `base.html` with `{% import "_ui.html" as ui %}`
  (required by `test_ui_rules` even though `base.html` imports it), define `nav_left` back button,
  and include the shared partial. New page adds a "Find the song" section before the form.
- Updated `item_forms.py`: added `mbid`, `rgid`, `back_url` context to `_render_form`, `get_new_item`,
  and `get_edit_item`; added `q=""` to `get_new_item`.
- Removed both templates from `backend/tests/ui_legacy.txt`.
- All 419 tests pass, 100% coverage on key modules, `make check` clean.
- Migrated `items_delete.html` per "Delete confirmations" recipe: extends `base.html`, uses
  `ui.group(pad=True)` with the confirmation question and removal list, `ui.button("Delete",
  kind="danger", type="submit")` in `.actions.actions-end`, and a ghost "Cancel" link back to
  the detail page. Nav_left has a back button to the item detail. Removed from `ui_legacy.txt`.
- All 422 tests pass, 99% coverage, `make check` clean.
- Migrated `routines_list.html` per "Routines" recipe: extends `base.html`, uses
  `{% import "_ui.html" as ui %}`, `nav_right` with `ui.nav_link("New routine", "/routines/new", icon_name="plus")`,
  `ui.section()` wrapping a `ui.group()` of `ui.row(r.name, sub=r.block_count ~ " blocks · " ~ r.total_minutes ~ " min", href=...)`,
  and `ui.empty(...)` for the empty state. Removed from `ui_legacy.txt`.
- All 425 tests pass, 99% coverage, `make check` clean.

## Routine forms migration: new + delete pages (T82)
- Migrated `routines_new.html` per "New routine" recipe: extends `base.html`, `{% import "_ui.html" as ui %}`,
  `nav_left` back button to "/routines", `.stack-lg` wrapper, `<h2>New Routine</h2>`, form with
  `ui.group()` containing `ui.field("name", "Name", required=True, placeholder=...)` and error support,
  `.actions.actions-end` with `ui.button("Create", kind="primary", type="submit")`.
- Migrated `routines_delete.html` per "Delete confirmations" recipe: extends `base.html`,
  `nav_left` back to routine edit page, `ui.group(pad=True)` with the question `<p>` and
  `<p class="delete-note">`, `.actions.actions-end` with `ui.button("Delete", kind="danger", type="submit")`,
  ghost "Cancel" link to edit page.
- Removed both templates from `backend/tests/ui_legacy.txt`.
- No test assertion updates needed (existing assertions matched new markup).
- All 431 tests pass, 98.57% coverage, `make check` clean.

## Runner page migration (T83)
- Rewrote `backend/app/templates/run.html` to extend `base.html` and use new UI macros:
  `.stack-lg` wrapper, `.runner-head` with title/sub, `.countdown` with progress bar,
  `.split` for controls/right panel, `ui.button()` with explicit IDs (`run-main`, `run-plus`,
  `run-skip`, `run-record`, `run-tap`, `run-bpm`), `ui.segmented()` for beats, `ui.stepper()`
  for tempo, `ui.switch_row()` and `ui.range_row()` for metronome/volume.
- Updated `backend/app/routes/run.py` context: added `routine_id` ("null" for free practice),
  `first_time` (formatted via `_fmt()` helper), `start_bpm`, `blocks_count`, `next_text`.
- Updated `backend/tests/test_runner_page.py`: nav now links to `/`, controls checked by ID,
  attachments container uses `id="run-links"` with `group` class.
- Updated `backend/tests/test_free_practice.py`: controls checked by ID, attachments by container,
  nav now expects "End" linking to `/`, page title expects "Woodshed".
- Removed `run.html` from `backend/tests/ui_legacy.txt`.
- All 434 tests pass, 99% coverage, `make check` clean.

## Progress page migration, 2026-11-16 (T67)
- Updated `backend/app/routes/progress.py`: added `this_week`, `avg_12wk`, `best_week` context variables computed from `weeks_12` data.
- Rewrote `backend/app/templates/progress.html` to extend `base.html` and use new UI macros: removed `<h1>`, replaced old table/chart layout with `ui.section()`/`ui.group()`/`ui.stat()`/`ui.row()` per the design recipe. Section headers: "Last 12 weeks" and "Tempo, last 90 days".
- Updated `backend/app/templates/macros.html`: `render_bar_chart` macro now emits `.chart`, `.chart-bar`, `.chart-goal`, `.chart-label` CSS classes; removed inline `fill`/`stroke` attributes.
- Removed `progress.html` from `backend/tests/ui_legacy.txt`.
- Updated `backend/tests/test_progress_tempo.py`: changed section title assertion, replaced obsolete `.delta` class checks with value assertions (`"+20 bpm"`, `"-30 bpm"`).
- Fixed mypy error in `progress.py` by extracting minutes list with `type: ignore[misc]` (dict return type from `weeks_12` mixes `int | date`).
- All 437 tests pass, 99% coverage, `make check` clean.

## By hand 2026-11-16: T83 + T79 (runner page JS)
- `run-page.js` rewritten for the new `run.html` ids; what to show comes from the pure `runner-view.js` (tested in `tests/js/runner-view.test.js`). timer.js values are seconds, not ms.
- `runner.js`: `finish()` logs the block in progress; skipping the last block finishes the session; `deps.bpmToLog` makes the logged BPM null with the metronome off (SPEC 6.3).
- `run.html` renders per block the first Tab / PDF / Backing track row (`data-block`, later blocks `hidden`); `routes/run.py` gives `links`, "Next: …" and `m:ss`.
- `components.css`: `[hidden] { display: none !important; }`; without it `hidden` does nothing on `.row`, `.split`, etc.
- Run JS tests with `node --test 'tests/js/**/*.test.js'`; `node --test tests/js/` fails on Node 22.
## Settings page migration, 2026-11-16 (T68)
- Rewrote `backend/app/templates/settings.html` to extend `base.html` and use new UI macros per the design recipe: `.stack-lg` wrapper, `<form method="post" class="form stack-lg">` with sections "Practice" (weekly goal field with `ui.field()`), "Look" (theme select with `ui.select()` using amp/flat/daylight values), "Tuner" (A4 reference field), actions with `ui.button("Save", kind="primary")`, section "More" with `ui.row("Style guide", href="/styleguide")`, and a logout form with `ui.section("Account")` / `ui.row_button("Log out", tone="danger")`.
- Updated `backend/app/routes/settings.py`: added `_get_tuner_a4()` helper, passed `tuner_a4` and `active` context to all template render calls (GET and POST error paths).
- Removed `settings.html` from `backend/tests/ui_legacy.txt`.
- No test assertion updates needed (existing assertions matched new markup).
- All 440 tests pass, 98% coverage, `make check` clean.

## Login and 404 page migration, 2026-11-16 (T85)
- Rewrote `backend/app/templates/login.html` to extend `base.html` (no more `legacy_base.html`),
  using `{% import "_ui.html" as ui %}`, `ui.field("password", "Password", type="password", required=True, error=error)`,
  and `ui.button("Log in", kind="primary", type="submit", size="big", block=True)`.
- Rewrote `backend/app/templates/404.html` to extend `base.html`: title "Not found", `<span class="page-title">404</span>`,
  two `<p>` elements for the messages, and a plain `<a href="/">Go home</a>`.
- Updated `backend/app/auth.py`: passed `{"bare": True}` in all three login template render calls
  (GET, rate-limited 429, wrong password 401).
- Removed both `login.html` and `404.html` from `backend/tests/ui_legacy.txt`.
- All 446 tests pass, 98.43% coverage, `make check` clean.

## Pitch detection pure module (T70)
- Created `backend/app/static/js/pitch.js` with pure functions: `detectPitch(samples, sampleRate)` (autocorrelation with parabolic interpolation, RMS silence check at 0.01, 60–1200 Hz clamp), `noteFor(freq, a4)` (MIDI + cents calculation), `nearestString(freq)` (closest STANDARD string), and `STANDARD` array [E2=82.41, A2=110.0, D3=146.83, G3=196.0, B3=246.94, E4=329.63].
- Created `backend/tests/js/pitch.test.js` with 28 test cases covering all 6 standard strings (±0.5% freq accuracy), note mapping (name/octave/cents/midi), 440 Hz → A4, 446 Hz → +23.4 cents, a4=432 tuning, silence/low-amplitude → null, harmonic interference (110 Hz + 0.6×220 Hz → 110 Hz), nearestString edge cases, and boundary frequencies (60 Hz, 1000 Hz).
- All 28 node tests pass, `make check` clean (lint + mypy + pytest 98% + js + bandit + migrations).

## Tuner page (T71)
- Created `backend/app/routes/tuner.py` (`GET /tuner`) fetching `tuner_a4` from DB (defaults to 440), passing `active="tuner"`, `a4`, and `strings` (STANDARD_TUNING array) to template.
- Created `backend/app/templates/tuner.html` per the design recipe: extends `base.html`, `.stack-lg` wrapper, `data-a4="{{ tuner_a4 }}"` on root div, `#tuner-note` + `#tuner-hz` displays, `#tuner-meter` with `tuner-needle`, "Connect mic" button, six `data-freq` reference tone buttons, and loads `tuner.js` as ES module.
- Created `backend/app/static/js/tuner.js`: mic toggle via `getUserMedia`, `setMicButton()` with loading/cancel states, pitch loop (10 fps via `requestAnimationFrame`) using `pitch.js` `detectPitch()`/`noteFor()`/`nearestString()`, meter needle update (`--cents` CSS property), reference tone playback via `OscillatorNode` (2s with linear ramp fade-out), `data-freq` button click handlers.
- Wired router in `backend/app/routes/__init__.py` (imported `tuner_router`) and `backend/app/main.py` (mounted `app.include_router(tuner_router)`).
- Created `backend/tests/test_tuner_page.py` (10 tests: 200 status, `aria-current="page"`, module script, six `data-freq` values, `data-a4="440"`, note/hz/meter/status/scale elements).
- All 459 tests pass, 98% coverage, `make check` clean.

## Tuner reference in Settings, 2026-11-16 (T72)
- Updated `backend/app/routes/settings.py`: added `tuner_a4` parsing and saving in POST handler. If the value is a valid integer in 430–450, it is persisted; otherwise it is silently skipped (existing value preserved, no error shown for tuner_a4 specifically). Non-numeric and out-of-range values are also skipped.
- Updated `backend/tests/test_settings.py`: added 11 tests covering default 440 display, saved value display, POST saving of valid values (430, 432, 440, 450), rejection of out-of-range (429, 451), rejection of non-numeric ("abc"), empty field not overwriting existing, and tuner page using saved value.
- All 470 tests pass, 98.31% coverage, `make check` clean.

## Item year, mbid, release_group_id, has_cover fields (T84)
- Added `year`, `mbid`, `release_group_id`, `has_cover` to `Item` model (`backend/app/models.py`).
- Added `ItemIn` with `year` (1000–2100) and `mbid`/`release_group_id` (UUID) validators in `backend/app/items_service.py`; updated `create_item` and `update_item` to pass them through.
- Generated migration `backend/alembic/versions/2cc9eaa2517d_item_mb_fields.py` with `ALTER TABLE item ADD COLUMN` for all four fields (nullable year, mbid, release_group_id; has_cover defaults to false).
- Updated `backend/app/api.py` item response dicts to include new fields.
- Updated `backend/app/item_forms.py`: `_extract_and_validate` parses `year` as int; `_item_to_form_data` maps new fields; `_render_form` passes `mbid`/`rgid` context; `get_edit_item` passes actual `item.mbid`/`item.release_group_id` to hidden form fields.
- Added `year` visible `<input type="number">` in `partials/item_fields.html` (Practice section); `mbid`/`release_group_id` are hidden.
- Created `backend/tests/test_item_mb_fields.py` (27 tests): form rendering, API creation with all fields, year boundary/validation, mbid/release_group_id UUID validation, edit form population, API response fields.
- All 497 tests pass, 98.35% coverage, `make check` clean.

## MusicBrainz pure parsing module (T74)
- Created `backend/app/musicbrainz.py` with `Candidate` dataclass (frozen, immutable), `build_query()` (escapes backslashes and double-quotes, appends `AND artist:"…"` only when artist is not None), and `parse_recordings()` (extracts artist from artist-credit with joinphrase, first-release-date, length in m:ss, release-group-id; dedupes by (title, artist) case-insensitive keeping earliest date, sorts by score desc then date asc, limits to 8).
- Created `backend/tests/test_musicbrainz_parse.py` (12 tests): Texas Flood fixture dedup (1 candidate, earliest year "1990", length "5:44"), Blackbird fixture (≤8 candidates, all titled "Blackbird", sorted by score then date), `build_query` quote escaping and artist clause presence, `build_query` no-artist case, backslash escaping, Candidate immutability.
- All 509 tests pass, 98.34% coverage, `make check` clean.

## MusicBrainz search: rate limiter, fetch, search(), /items/lookup (T75)
- Added `MB_USER_AGENT` and `MB_TIMEOUT` (default 5) settings to `app/config.py`.
- Added `RateLimiter` class to `app/musicbrainz.py` with injectable `clock`/`sleep` and a wait-before-request pattern (sleeps until 1 s since last request); default singleton via `_get_default_limiter()`.
- Added `fetch_url()` function using `urllib.request.Request` with `User-Agent` header and configurable timeout; raises `MBUnavailable` on `HTTPError`/`URLError`; accepts optional `_real_fetch` for test injection (also wraps its errors in `MBUnavailable`).
- Added `search()` function: calls `limiter.wait()`, builds URL with `fmt=json&limit=25&query=…`, calls `fetch_url()`, detects rate-limit response body, parses JSON via `parse_recordings()`. Raises `MBUnavailable` on invalid JSON or rate-limited body.
- Added `GET /items/lookup` route in `app/routes/items.py` that calls `search()` and renders `partials/mb_results.html` (candidate rows with `data-*` attributes + error/nothing-found messages).
- Created `backend/tests/test_musicbrainz_search.py` (13 tests): fake fetch for URL params/User-Agent/timeout, rate-limit body detection, `MBUnavailable` from `URLError` and invalid JSON, RateLimiter sleep/no-sleep/reset/defaults, end-to-end with real fixture and empty fixture.
- All 524 tests pass, 96.73% coverage, `make check` clean.

## "Find the song" link + results rendering (T76)
- Added pre-fill link in `partials/item_fields.html`: `ui.link("Find the song", "/items/lookup", icon_name="search")` with a `p.mb-hint` description paragraph.
- Added `build_query(title, artist)` helper in `musicbrainz.py` that generates a `recording:"..." AND artist:"..."` query string with proper escaping (backslashes, double-quotes).
- Added `partials/mb_results.html` template: renders candidate rows as `.mb-result` divs with `data-*` attributes (mbid, rgid, title, artist, year, length), each row contains an `.mb-result-link` to `/items/new?kind=song&title=…&artist=…&year=…&mbid=…&release_group_id=…` (omits `length`). Also renders "Nothing found." when empty, and a fallback message when `MBUnavailable` is raised.
- Updated `items_new.html` to include the "Find the song" section before the form.
- Updated `items.py` lookup route: parses `title`/`artist` from query params, calls `build_query()` (skips search when both empty), renders `mb_results.html` with `{% call ui.group() %}…{% endcall %}` (not `{{ }}`) so UI macros work inside the partial swap.
- Created `backend/tests/test_mb_lookup_page.py` (14 tests): 200 status, query building with title+artist/title only/artist only, empty params handling, pre-fill links containing title/artist/year/mbid/rgid (no length), pre-fill link has no `original_url`, error message on `MBUnavailable`, no error when no query, and data attributes on result rows.
- All 538 tests pass, `make check` clean.

## Cover art: fetch, save, serve, form integration (T77)
- Created `backend/app/covers.py` with `fetch_cover` (iTunes Search API via `mbReleaseId`, injectable `fetch` for test doubles, magic-byte validation for JPEG/PNG, 2 MB size limit, HTML rejection) and `save_cover` (writes to `media_dir/cover/{item_id}.{ext}`, returns `False` on `OSError`).
- Updated `backend/app/api.py`: imports `fetch_cover`/`save_cover`, adds `Settings` dependency to `create_item_route`, calls `_try_fetch_cover` after committing new item (cover fetch failures never roll back the item).
- Updated `backend/app/item_forms.py`: imports `Settings`/`Item`/`fetch_cover`/`save_cover`, added `_try_fetch_cover(item, data, settings)` helper (wraps fetch+save in try/except), called it in `post_new_item` and `post_edit_item` POST handlers.
- Updated `backend/app/routes/media.py`: added `GET /media/cover/{item_id}` route that looks up `Item.has_cover`, finds the cover file by `item_id.ext` in MEDIA_DIR/cover/, serves with correct `Content-Type` (`image/jpeg` or `image/png`), returns 404 when no cover or file missing.
- Created `backend/tests/test_covers.py` (20 tests): magic byte detection (JPEG/PNG/HTML/empty), fetch with fake injectors (JPEG, PNG, HTML rejection, oversized, network error), save cover (JPEG, PNG, OSError return False), API item creation with/without release_group_id, form item creation/edit with release_group_id, cover serving (JPEG 200 + correct content-type, PNG 200, 404 when no cover, 404 for nonexistent item).
- All 558 tests pass, 97% coverage, `make check` clean.

## Home routine counts fix: separate subqueries (T86)
- Replaced the single join query in `backend/app/main.py` (home route) with a subquery that aggregates `routine_block` counts/minutes and the last session independently, preventing the N×M inflation bug (e.g. 3 blocks × 4 sessions → 12 blocks).
- Created `backend/tests/test_home_counts.py` (6 tests): routine with 3 blocks and 4 sessions shows "3 blocks · 20 min"; no-block routine shows "0 blocks · 0 min"; single block/1 session; blocks with no sessions; two routines with different counts coexist correctly.
- All 565 tests pass, 97% coverage, `make check` clean.

## Item upload form always renders (T87)
- Fixed `backend/app/templates/items_detail.html`: moved the upload form outside the `{% if item.attachments %}` block so it renders unconditionally, placing it below the empty state.
- Created `backend/tests/test_item_upload_form.py` (9 tests): verifies form existence with zero/one/audio/pdf attachments, correct `action`, `enctype`, `type="file"`, `name="file"` attributes, and exact form count (1) regardless of attachment presence.
- All 574 tests pass, 97% coverage, `make check` clean.
