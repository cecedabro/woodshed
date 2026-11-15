# PLAN

One task per line, smallest useful units. `accept:` exits 0 when done; the harness also
runs `make check`. Read the named doc before starting. The harness marks the boxes, not you.
The skeleton (SPEC §1) is done by hand: `/healthz`, `/readyz`, config, production guard,
test fixtures, CI.

## Round 1: models, layout, login, library
- [x] T01: Models and one migration for `item`, `attachment` and `setting` exactly as docs/backend.md §model (CHECK constraints for the enums). Write `tests/test_models_library.py`: insert an item with an attachment and read them back; an invalid `kind` and an invalid `status` raise `IntegrityError`; deleting an item deletes its attachment rows.
  accept: cd backend && uv run pytest tests/test_models_library.py -q
- [x] T02: Models and one migration for `routine`, `routine_block`, `practice_session`, `session_block` and `take` per docs/backend.md §model. Write `tests/test_models_practice.py`: a routine with two blocks in order; duplicate (routine_id, position) fails; deleting a routine sets `practice_session.routine_id` to NULL; deleting an item deletes its takes and sets `session_block.item_id` to NULL while `item_title` stays.
  accept: cd backend && uv run pytest tests/test_models_practice.py -q
- [x] T03: `app/templating.py` (one `Jinja2Templates`, filter `local_time` → "Tue 3 Nov, 19:05" in Europe/Amsterdam), `templates/base.html` with the nav of SPEC 10.1 (each page passes `active`), `static/style.css` with design tokens (docs/design.md), htmx loaded from `/static/vendor/htmx.min.js`, and a placeholder `/` page. Write `tests/test_layout.py`: `/` has all five nav links, only Home has `aria-current="page"`, htmx and style.css are linked; `local_time` for a winter and a summer UTC time.
  accept: cd backend && uv run pytest tests/test_layout.py -q
- [x] T04: Styled 404 (SPEC 10.6): unknown HTML paths render `templates/404.html` (extends base, link home) with 404; `/api/...` keeps JSON 404. Write `tests/test_404.py`.
  accept: cd backend && uv run pytest tests/test_404.py -q
- [x] T05: `app/security.py` (SPEC 10.5, 2.6): middleware adding the four headers with the exact CSP, and the Origin check (403 on POST with a foreign Origin; same origin and no Origin pass). Write `tests/test_security.py`.
  accept: cd backend && uv run pytest tests/test_security.py -q
- [x] T06: Pure cookie functions in `app/auth.py` (SPEC 2.2, docs/backend.md §auth): `sign(expiry, secret)` and `verify(cookie, secret, now)`. Write `tests/test_auth_cookie.py`: a fresh cookie verifies; wrong secret, edited expiry, edited signature, missing dot, non-numeric expiry and an expired cookie all fail.
  accept: cd backend && uv run pytest tests/test_auth_cookie.py -q
- [~] T07: Login (SPEC 2.1, 2.3, 2.4): `GET/POST /login`, `POST /logout`, `templates/login.html`, and middleware that sends HTML routes to `/login` (303) and gives `/api/` 401 JSON without a valid cookie; open paths as SPEC 2.3. Cookie attributes per 2.2 (`Secure` only in production). In `tests/conftest.py`, make `client` log in and add `anon_client`; existing tests must still pass. Write `tests/test_login.py` (right/wrong password, cookie attributes, redirect, 401 on `/api/x`, `/healthz` open, logout clears the cookie). — skipped: $ cd backend && uv run pytest tests/test_login.py -q && cd backend && uv run pytest -q  (exit 2)
  accept: cd backend && uv run pytest tests/test_login.py -q && cd backend && uv run pytest -q
- [x] T08: Login rate limit (SPEC 2.5): failed-attempt timestamps on `app.state`, time from `clock.now()`. Write `tests/test_login_ratelimit.py`: the 11th attempt inside 15 min is 429 even with the right password; after 15 min (monkeypatched clock) the right password works.
  accept: cd backend && uv run pytest tests/test_login_ratelimit.py -q
- [x] T09: Item service + JSON API (SPEC 3.1, 3.8) in `app/items_service.py` and `app/api.py`: pydantic `ItemIn` with every 3.1 rule, `POST /api/items` → 201, `GET /api/items/{id}` → 200/404. Write `tests/test_api_items.py`: create and read back every field; 422 for title "" and 201 chars, BPM 19 and 401, `ftp://` URL, unknown status; 20 and 400 BPM pass; nothing stored on 422.
  accept: cd backend && uv run pytest tests/test_api_items.py -q
- [x] T10: Item forms (SPEC 3.3): `/items/new` and `/items/{id}/edit` (GET form, POST → 303 to `/items/{id}`), reusing `ItemIn`; errors re-render with 422 next to the field. Write `tests/test_item_forms.py`.
  accept: cd backend && uv run pytest tests/test_item_forms.py -q
- [x] T11: Item page (SPEC 3.4, without files, takes and tempo for now): all fields, original link with `target="_blank" rel="noopener"`, notes with line breaks kept (escaped, then newlines → `<br>`), edit link, styled 404 for an unknown id. Write `tests/test_item_page.py` (including that `<script>` in notes is escaped).
  accept: cd backend && uv run pytest tests/test_item_page.py -q
- [x] T12: `/library` (SPEC 3.2): grouped learning / polishing / repertoire, `?kind=` filter, `?q=` case-insensitive title search, empty state with a link to `/items/new`. Write `tests/test_library.py`.
  accept: cd backend && uv run pytest tests/test_library.py -q
- [x] T13: `app/media.py` (docs/backend.md §media): `kind_for_filename(name)` per SPEC 3.5, `save_upload(upload, subdir, limit_bytes, media_dir) -> (stored_name, size)` copying in 1 MiB chunks and raising a `TooLarge` error (partial file removed), `delete_file(...)`. Write `tests/test_media.py` with real files under `tmp_path` (limit exact = ok, limit + 1 = TooLarge and no file left; `.GP5` upper case → tab; `.exe` → None).
  accept: cd backend && uv run pytest tests/test_media.py -q
- [x] T14: Attachments (SPEC 3.5): upload form on the item page (`POST /items/{id}/attachments`, multipart `file` + optional `label`), list on the item page grouped tab / PDF / audio, delete button. 422 for a bad extension, 413 over 100 MB (use a small limit from settings in the test: add `MAX_ATTACHMENT_BYTES` to Settings, default 100 MB). Write `tests/test_attachments.py` (row and file on disk; delete removes both).
  accept: cd backend && uv run pytest tests/test_attachments.py -q
- [x] T15: `GET /media/{kind}/{id}` (SPEC 10.4) for `attachment` and `take` rows: stored content type, Range support, 404 for unknown id or kind, 401/303 when logged out. Write `tests/test_media_serving.py` (full GET bytes equal; `Range: bytes=0-3` → 206 and 4 bytes with `Content-Range`).
  accept: cd backend && uv run pytest tests/test_media_serving.py -q
- [~] T16: Tab viewer (SPEC 3.6, docs/frontend.md §alphatab): `/items/{id}/tab/{attachment_id}` page and `static/js/tab.js`; PDF attachments link to `/media/attachment/{id}`; audio attachments get `<audio controls preload="none">`. Write `tests/test_tab_page.py` (alphaTab script and tab.js tags, `data-file` URL, 404 for a non-tab attachment). — skipped: $ cd backend && uv run pytest tests/test_tab_page.py -q && node --check backend/app/static/js/tab.js  (exit 1)
  accept: cd backend && uv run pytest tests/test_tab_page.py -q && node --check backend/app/static/js/tab.js
- [x] T17: Delete item (SPEC 3.7): a confirm page `GET /items/{id}/delete` and `POST` that deletes the item, its attachment and take files, and redirects to `/library`. Write `tests/test_item_delete.py` (files gone, logged session blocks keep `item_title`).
  accept: cd backend && uv run pytest tests/test_item_delete.py -q

## Round 2: routines, runner, metronome
- [x] T18: Routine service + pages (SPEC 4.1, 4.3): `/routines` list with total planned minutes, `/routines/new` (name only, then go to the editor), delete with confirm. Validation per 4.1. Write `tests/test_routines.py`.
  accept: cd backend && uv run pytest tests/test_routines.py -q
- [~] T19: Routine editor (SPEC 4.2) at `/routines/{id}/edit` with HTMX: add a block (item select, minutes, optional BPM), remove, move up/down; each action returns the updated block list fragment; positions stay 0..n-1 without gaps. Write `tests/test_routine_editor.py` (move first block down twice → order; remove middle → positions renumbered; 31st block → 422). — skipped: agent made no changes
  accept: cd backend && uv run pytest tests/test_routine_editor.py -q
- [x] T20: `static/js/timer.js` per docs/frontend.md §js. Write `tests/js/timer.test.js`: remaining and played while running, pause excludes time, resume, addSeconds(60), isDone exactly at 0, remaining never negative.
  accept: cd backend && node --test tests/js/timer.test.js
- [x] T21: `static/js/metronome.js` pure functions `clampBpm`, `beatTimes`, `tapTempo` per §js (the `Metronome` class comes in T26). Write `tests/js/metronome.test.js`: 120 BPM beats at 0.5 s spacing; accents every 4th beat and every 3rd with beatsPerBar 3; `fromBeat`/`untilTime` windows; taps at 500 ms intervals → 120; a 2.5 s gap restarts; fewer than 2 taps → null; clamp 10 → 20, 999 → 400.
  accept: cd backend && node --test tests/js/metronome.test.js
- [x] T22: Sessions API (SPEC 5.4–5.6, docs/backend.md §sessions) in `app/sessions.py`. Write `tests/test_sessions_api.py`: create; log a block (row values); clamp to elapsed + 60 (monkeypatched clock); 9 s → `{"stored": false}`; logging with a BPM updates `item.current_bpm`; finish returns the summary; 404 for an unknown session; logged out → 401.
  accept: cd backend && uv run pytest tests/test_sessions_api.py -q
- [x] T23: `close_stale_sessions(db, now)` (SPEC 5.7), called by `POST /api/sessions` and the home page. Write `tests/test_stale_sessions.py` (5 h 59 min open stays open, 6 h 1 min gets `ended_at` = its last block's `ended_at`, or `started_at` when it has no blocks).
  accept: cd backend && uv run pytest tests/test_stale_sessions.py -q
- [ ] T24: `static/js/runner.js` `createRunner` per §js with fake `api`, `now` and `cue`. Write `tests/js/runner.test.js`: start calls startSession; a finished block logs exact `played_seconds` and moves on; skip logs a partial block; setBpm changes the logged BPM; pause time is not logged; the last block triggers finish once.
  accept: cd backend && node --test tests/js/runner.test.js
- [ ] T25: Runner page `/run/{routine_id}` (SPEC 5.2): server renders blocks as JSON in `data-blocks` (item_id, title, planned_seconds, start BPM per SPEC 6.2) and, per block, links to the item's first tab, PDF and audio attachment; controls as real buttons with labels. Write `tests/test_runner_page.py` (parse `data-blocks` JSON and assert values; 404 for an unknown routine; module script tags).
  accept: cd backend && uv run pytest tests/test_runner_page.py -q
- [ ] T26: `Metronome` class (§js look-ahead pattern) and `static/js/run-page.js` glue: start on the first tap, tick every 250 ms, update the countdown, BPM buttons and tap tempo, beats-per-bar select, metronome on/off and volume in `localStorage` (SPEC 6.3), cue sound, wake lock (SPEC 5.9), summary view after finish. Add a test to `tests/js/metronome.test.js` for the class with a fake AudioContext (clicks scheduled at the `beatTimes` times).
  accept: cd backend && node --test tests/js/metronome.test.js && node --check app/static/js/run-page.js
- [ ] T27: Home page (SPEC 5.1): one big start button per routine, the most recently practised first (then newest), linking to `/run/{id}?autostart=1`; run-page.js starts immediately on `autostart=1` after the first user gesture-capable tap (the button itself is that tap: navigate, then show one large "Start" if the browser blocks audio). Empty state links to create a routine. Write `tests/test_home.py` (order by last session).
  accept: cd backend && uv run pytest tests/test_home.py -q
- [ ] T28: Free practice (SPEC 5.8): "Practise this" on `/items/{id}` opens `/run/item/{id}?minutes=10` with one block; sessions created with `routine_id` null. Write `tests/test_free_practice.py`.
  accept: cd backend && uv run pytest tests/test_free_practice.py -q

## Round 3: progress, goal, takes
- [ ] T29: `app/stats.py` week maths (SPEC 9.4, docs/backend.md §stats): `week_start`, `week_bounds_utc`. Write `tests/test_weeks.py`: Sunday 23:30 vs Monday 00:10 local; the weeks containing 29 Mar 2026 and 25 Oct 2026 (DST) are 167 and 169 hours long.
  accept: cd backend && uv run pytest tests/test_weeks.py -q
- [ ] T30: Weekly goal (SPEC 9.1): `setting` row `weekly_goal_minutes`, default 120; `/settings` form (0–10080, else 422). Write `tests/test_settings.py`.
  accept: cd backend && uv run pytest tests/test_settings.py -q
- [ ] T31: `minutes_per_week(db, mondays)` and the home progress bar (SPEC 9.2): `<progress>` with value and max plus "75 of 120 min". Write `tests/test_week_totals.py` with blocks around a week boundary (exact minutes, rounding down).
  accept: cd backend && uv run pytest tests/test_week_totals.py -q
- [ ] T32: `/progress` part 1 (SPEC 9.2, 9.3): last 12 weeks as an inline SVG bar chart with the goal line, plus a text table for screen readers. Write `tests/test_progress_weeks.py` (12 bars, the right heights relative to the max, an empty week is 0; the words "streak" and "day in a row" appear nowhere on `/` or `/progress`).
  accept: cd backend && uv run pytest tests/test_progress_weeks.py -q
- [ ] T33: Tempo history (SPEC 7.1): `tempo_history(db, item_id)` → [(local date, max bpm)], the text "60 → 72 → 84" and a small inline SVG line on `/items/{id}`. Write `tests/test_tempo_history.py` (two blocks on one day → max; null BPMs ignored; order oldest first).
  accept: cd backend && uv run pytest tests/test_tempo_history.py -q
- [ ] T34: `/progress` part 2 (SPEC 7.2): table of items with a BPM in the last 90 days, first and latest BPM and "+24 bpm". Write `tests/test_progress_tempo.py` (91-day-old block excluded).
  accept: cd backend && uv run pytest tests/test_progress_tempo.py -q
- [ ] T35: Takes upload (SPEC 8.2) in `app/takes.py`: `sniff_audio(first_bytes) -> "webm"|"mp4"|"ogg"|None`, `POST /api/items/{id}/takes`. Add `MAX_TAKE_BYTES` (default 25 MB) to Settings. Write `tests/test_takes_upload.py` (each of the three formats with crafted header bytes → 201, row + file; wrong bytes → 415; declared mp4 with WebM bytes → 415; too big → 413; duration 0 and 601 → 422).
  accept: cd backend && uv run pytest tests/test_takes_upload.py -q
- [ ] T36: `static/js/recorder.js` `pickMimeType` + glue (SPEC 8.1): one record button (on the runner and the item page) that toggles recording, shows elapsed time, stops at 600 s and uploads with the current BPM and block. Write `tests/js/recorder.test.js` (Safari-like support → `audio/mp4`; nothing supported → "").
  accept: cd backend && node --test tests/js/recorder.test.js && node --check app/static/js/recorder.js
- [ ] T37: Takes on the item page (SPEC 8.3): newest first with local date, duration, BPM, `<audio controls preload="none">`, an HTMX one-line note, delete (row and file). Write `tests/test_takes_list.py`.
  accept: cd backend && uv run pytest tests/test_takes_list.py -q
- [ ] T38: Compare (SPEC 8.4): checkboxes on the takes list submit to `/items/{id}/compare?a=&b=`; older take left. 404 when a take belongs to another item. Write `tests/test_compare.py`.
  accept: cd backend && uv run pytest tests/test_compare.py -q

## Round 4: home-screen app, polish, release, deploy
- [ ] T39: Icons and manifest (SPEC 10.3, docs/frontend.md §pwa): `backend/scripts/make_icons.py` (stdlib PNG writer) and the generated `static/icons/icon-192.png`, `icon-512.png`, `apple-touch-icon.png` (180); `GET /manifest.webmanifest`; head tags in `base.html`. Write `tests/test_manifest.py` (JSON fields, content type, PNG sizes read from the IHDR chunk).
  accept: cd backend && uv run pytest tests/test_manifest.py -q
- [ ] T40: `GET /sw.js` (SPEC 10.3): served from the root with a JS content type and `Service-Worker-Allowed: /`; caches only `/static/` (cache-first), everything else goes to the network; registered from `static/js/app.js`. Write `tests/test_sw.py`.
  accept: cd backend && uv run pytest tests/test_sw.py -q && node --check backend/app/static/sw.js
- [ ] T41: Accessibility pass (SPEC 10.2): `tests/test_a11y.py` parses every page (logged in, with seed rows) with `html.parser` and checks: one `<h1>`, every input/select/textarea has a label, every button has text or `aria-label`, `<html lang="en">`, no inline `<script>` code or `on*=` attributes. Fix what fails.
  accept: cd backend && uv run pytest tests/test_a11y.py -q
- [ ] T42: `make dev` (`backend/scripts/dev.py`): starts pgserver in `backend/.devdb/`, migrates, seeds 3 routines, 8 items (blues/rock), 10 weeks of sessions with rising BPMs, and runs uvicorn on :8000. Put the seed in a function and write `tests/test_dev_seed.py` that calls it on the test database and checks the counts.
  accept: cd backend && uv run pytest tests/test_dev_seed.py -q
- [ ] T43: `backend/scripts/next_version.py` (stdlib only, SPEC 11.3): from tag names and the commit message print the next version. Write `tests/test_next_version.py` (no tags → v0.1.0; ignores non-`vX.Y.Z` tags; `[minor]` resets patch; `[major]` resets both).
  accept: cd backend && uv run pytest tests/test_next_version.py -q
- [ ] T44: `.github/workflows/release.yml` per docs/deployment.md (on push to main; `permissions: contents: write, packages: write`; concurrency `release` without cancel; jobs `uses:` ci.yml, migrations.yml and image.yml, then build-and-push with pinned docker actions and the tag; skip on `[skip release]`).
  accept: uvx --from actionlint-py actionlint .github/workflows/release.yml
- [ ] T45: `deploy/` part 1 per docs/deployment.md: `Makefile` (validate), `kustomization.yaml`, `namespace.yaml`, `app.yaml` (Deployment with both initContainers, probes, security context, resources, `/tmp` emptyDir, media PVC mount at `/data`, image marker; Service; PVC `woodshed-media`).
  accept: make -C deploy validate
- [ ] T46: `deploy/` part 2: `postgres.yaml` (StatefulSet + Service per the table), `ingress.yaml`, and `secret.example.yaml` with `REPLACE_ME` values (not in the kustomization).
  accept: make -C deploy validate && grep -q REPLACE_ME deploy/secret.example.yaml
- [ ] T47: README "Using it" and "Deploying" sections: every page in one line, `make dev`, how a merge becomes a release, env vars and secrets. Short; do not change other sections.
  accept: grep -q "## Deploying" README.md && grep -q "make dev" README.md

## Later (not for the loop yet)
- Resurface pieces not played in N days.
- Loop a section and slow down backing tracks.
- Watched folder on the homelab that ingests files and makes a guitar-free stem with Demucs.
- alphaTab playback (soundfont) and a cursor that follows the metronome.
