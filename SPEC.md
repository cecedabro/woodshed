# SPEC (human-owned — do not edit)

Requirements as testable sentences. Each section maps to tasks in `PLAN.md`.
Times are stored in UTC. "Local" means Europe/Amsterdam. A week runs Monday
00:00 to Sunday 24:00 local time. "Minutes played" always means logged seconds / 60.

## 1. Skeleton (done by hand)
- 1.1 `make check` passes: ruff, mypy, pytest with ≥ 90 % coverage, node tests, bandit.
- 1.2 `GET /healthz` → 200 `{"status": "ok"}` without touching the database.
- 1.3 Config comes from env vars (`DATABASE_URL`, `APP_PASSWORD`, `SESSION_SECRET`,
      `MEDIA_DIR`, `APP_ENV`, `LOG_LEVEL`) with local defaults.
- 1.4 With `APP_ENV=production` the app refuses to start when `APP_PASSWORD` is the
      development default or `SESSION_SECRET` is the default or shorter than 32 characters.
- 1.5 `GET /readyz` → 200 `{"status": "ready"}` when `SELECT 1` works, else 503
      `{"status": "unavailable"}`.

## 2. Login (single user)
- 2.1 `GET /login` shows a form with one password field. `POST /login` with the right
      password (constant-time compare) sets cookie `ws_session` and redirects 303 to `/`;
      a wrong password re-renders the form with status 401 and sets no cookie.
- 2.2 `ws_session` is `<expiry unix seconds>.<hex HMAC-SHA256 of the expiry with SESSION_SECRET>`,
      valid 90 days, `HttpOnly`, `SameSite=Lax`, `Path=/`, and `Secure` when `APP_ENV=production`.
      A tampered, malformed or expired cookie counts as logged out.
- 2.3 Without a valid session, HTML routes redirect 303 to `/login` and `/api/` routes
      return 401 JSON. Open without login: `/login`, `/healthz`, `/readyz`, `/static/…`,
      `/manifest.webmanifest`, `/sw.js`. One middleware enforces this, deny by default:
      a new route needs a login unless it is added to that list.
- 2.4 `POST /logout` clears the cookie and redirects 303 to `/login`.
- 2.5 After 10 failed logins within 15 minutes (whole app, not per client), `POST /login`
      returns 429 until the window passes, even with the right password.
- 2.6 Requests with a method other than GET/HEAD whose `Origin` header is present and
      is not exactly `<scheme>://<Host header>` get 403. The Host header includes the port
      when there is one (`http://localhost:8000`); behind Traefik the scheme is `https`
      (uvicorn runs with `--proxy-headers`).

## 3. Library
- 3.1 An item has: `kind` (`song` | `exercise`), `title` (1–200 chars), `artist` (optional),
      `status` (`learning` | `polishing` | `repertoire`, default `learning`), `current_bpm`
      (optional, 20–400), `original_url` (optional, must start with `http://` or `https://`),
      `notes` (optional Markdown-free plain text, max 20 000 chars), `created_at`, `updated_at`.
      From MusicBrainz (SPEC 14), all optional: `year` (1000–2100), `mbid` and
      `release_group_id` (UUIDs), `has_cover` (default false).
- 3.2 `/library` lists items grouped by status, each linking to `/items/{id}`; a filter
      `?kind=song|exercise` and a title search `?q=` (case-insensitive substring).
- 3.3 `/items/new` and `/items/{id}/edit` create and edit items with server-side
      validation; invalid input re-renders the form with status 422 and the error next to the field.
- 3.4 `/items/{id}` shows all fields, the original-recording link (opens in a new tab with
      `rel="noopener"`), notes with line breaks kept, attachments, takes and tempo history.
      An unknown id gives the styled 404 page.
- 3.5 Attachments: upload files to an item. Kind is derived from the extension:
      `tab` (`.gp`, `.gp3`, `.gp4`, `.gp5`, `.gpx`, `.musicxml`, `.xml`, `.mxl`),
      `pdf` (`.pdf`), `audio` (`.mp3`, `.m4a`, `.wav`, `.flac`, `.ogg`, `.opus`, `.webm`).
      Other extensions → 422. Max 100 MB per file → 413. An audio attachment has a label
      (e.g. "backing track 80 bpm", "drums only").
- 3.6 A tab attachment opens in `/items/{id}/tab/{attachment_id}`, rendered by alphaTab
      (vendored, no player). A PDF opens in the browser's own viewer. Audio plays in an
      `<audio controls>` element.
- 3.7 Deleting an item asks for confirmation and deletes its attachments, takes and their
      files; logged practice for that item stays (block rows keep the title they were logged with).
- 3.8 JSON API (also used by the human-owned migration check): `POST /api/items` with the
      3.1 fields → 201 with the item as JSON including `id`; `GET /api/items/{id}` → 200 JSON
      or 404; invalid input → 422.

## 4. Routines
- 4.1 A routine has a name and an ordered list of blocks. A block is an item plus
      planned minutes (1–120) and an optional BPM (20–400). A routine has 1–30 blocks.
- 4.2 `/routines` lists routines with total planned minutes; `/routines/new` and
      `/routines/{id}/edit` build them: add a block, remove it, move it up/down, all through HTMX.
- 4.3 Deleting a routine keeps its logged sessions.

## 5. Session runner and automatic logging
- 5.1 `/` (home) shows one big button per routine, the most recently practised routine
      first and largest. One tap on it starts the session and the first block's timer.
- 5.2 `/run/{routine_id}` runs blocks in order: item title, a countdown of the block's
      planned time, the metronome (see 6), the item's first tab/PDF/backing track one tap away,
      and buttons pause/resume, skip block, +1 minute, finish session.
- 5.3 When a block's countdown reaches 0 the runner plays a short cue, logs the block and
      starts the next block automatically. After the last block it shows a summary
      (blocks, minutes, BPM per block) and links back home.
- 5.4 Logging needs no typing. `POST /api/sessions` `{"routine_id"}` → 201 `{"id"}`.
      `POST /api/sessions/{id}/blocks` `{"item_id", "position", "planned_seconds",
      "played_seconds", "bpm"}` → 201. `POST /api/sessions/{id}/finish` → 200 with the summary.
      Only time actually counted (not paused) is logged as `played_seconds`.
- 5.5 `played_seconds` is clamped to 0 … (seconds since the session started + 60). A block
      with `played_seconds` < 10 is not stored (returns 200 `{"stored": false}`).
- 5.6 A session block keeps the item id and a copy of the item title, copied by the server
      from the item (the client sends only `item_id`; an unknown `item_id` gives 422). When it is stored
      with a BPM, the item's `current_bpm` becomes that BPM.
- 5.7 A session left unfinished for 6 hours counts as finished at its last block's end time.
- 5.8 Free practice: `/items/{id}` has a "Practise this" button that runs a one-block
      session for that item (default 10 minutes), logged the same way with `routine_id` null.
- 5.9 The runner requests a screen wake lock while a session runs (where the browser supports it).

## 6. Metronome (browser)
- 6.1 Web Audio clicks scheduled ahead of time (look-ahead scheduler), so timing does not
      drift when the main thread is busy. Accent on beat 1; beats per bar 2–7 (default 4).
      Beat k is at `start + k × 60/BPM`, where `start` is fixed when the metronome starts or
      the BPM changes; it keeps clicking until stopped.
- 6.2 BPM 20–400; −5/−1/+1/+5 buttons and tap tempo (average of the last 4 taps; a gap
      over 2 s restarts tapping). The start BPM of a block is the block's BPM, else the item's
      `current_bpm`, else 80. The BPM logged is the one in use when the block ends.
- 6.3 Metronome volume and on/off persist in `localStorage`; the metronome can be off
      for a block, then the logged BPM is null.

## 7. Tempo progress
- 7.1 `/items/{id}` shows the tempo history: per local day, the highest BPM logged for
      that item, oldest first, as text like "60 → 72 → 84" plus a small chart (inline SVG
      drawn server-side, no chart library).
- 7.2 `/progress` lists every item practised with a BPM in the last 90 days with its
      first and latest BPM in that window and the difference ("+24 bpm").

## 8. Recorded takes
- 8.1 The runner and `/items/{id}` have one record button. Recording uses `MediaRecorder`
      with the first supported type of `audio/webm;codecs=opus`, `audio/mp4`, `audio/ogg;codecs=opus`,
      and stops automatically after 10 minutes.
- 8.2 `POST /api/items/{id}/takes` (multipart: `file`, `duration_seconds`, optional `bpm`,
      optional `session_block_id`) stores the file under `MEDIA_DIR` and returns 201. Allowed:
      `audio/webm`, `audio/mp4`, `audio/ogg` (parameters ignored), and the bytes must match
      (`1A45DFA3` WebM, `ftyp` at offset 4 MP4, `OggS` Ogg); otherwise 415. Over 25 MB → 413.
      `duration_seconds` 1–600, else 422.
- 8.3 `/items/{id}` lists takes newest first with date, duration, BPM and a player; a take
      can get a one-line note and can be deleted (file removed too).
- 8.4 Compare: pick two takes of the same item → `/items/{id}/compare?a=&b=` shows both
      players side by side with their dates and BPMs, older one left.

## 9. Weekly goal and progress
- 9.1 One weekly goal in minutes (default 120), set on `/settings`, 0–10 080.
- 9.2 `/` shows this week's minutes played against the goal as a progress bar with text
      ("75 of 120 min"); `/progress` shows the last 12 weeks as bars with the goal line.
- 9.3 There are no daily streaks anywhere in the app.
- 9.4 Week totals use each block's end time in local time: a block ending Sunday 23:30
      local counts in that week, one ending Monday 00:10 local in the next. Daylight-saving
      weeks are handled.

## 10. Pages, PWA and security
- 10.1 Every page extends one layout (`base.html`, see SPEC 12) with nav: Home `/`, Library
       `/library`, Routines `/routines`, Tuner `/tuner`, Progress `/progress`, and Settings
       `/settings` (sidebar on wide screens, gear button on Home on phones); the current one
       has `aria-current="page"`. The nav bar title is the page's only `<h1>`.
- 10.2 Usable at 360 px wide (no horizontal scroll) and on an iPad on a music stand: the
       runner's timer and BPM are readable from 1.5 m and its buttons are ≥ 48 px.
- 10.3 `GET /manifest.webmanifest` (`application/manifest+json`): name "Woodshed",
       `display: standalone`, `start_url: /`, theme colour, icons 192 and 512 px PNG plus
       `apple-touch-icon` 180 px. `GET /sw.js` is a service worker that caches only `/static/`
       files (never pages, API responses or media).
- 10.4 Media files are served only to a logged-in user through `/media/{kind}/{id}`
       (`kind` is `attachment`, `take` or `cover`; for `cover` the id is the item id), with
       the stored content type and HTTP Range support (206 for a range request), so audio
       seeking works in Safari.
- 10.5 Every response has `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
       `X-Frame-Options: DENY` and `Content-Security-Policy: default-src 'self';
       style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:`.
       Templates contain no inline `<script>` code.
- 10.6 Unknown URLs give a styled 404 page; `/api/` paths keep JSON errors.

## 11. Build and deploy
- 11.1 The root `Dockerfile` (human-owned) builds one image that runs on port 8000 as
       uid 10001 with a read-only root filesystem; `/tmp` and `MEDIA_DIR` are the only writable paths.
- 11.2 CI runs `make check` on every PR and push to `main` and `agent/**` (`ci.yml`, human-owned).
- 11.3 Every push to `main` that passes the checks is a release: next version `vX.Y.Z`
       (patch +1; `[minor]`/`[major]` in the commit message bumps more; first is `v0.1.0`),
       images `ghcr.io/cecedabro/woodshed:X.Y.Z` and `:sha-<short>`, then the git tag.
       `[skip release]` skips it.
- 11.4 The image smoke test (`image.yml`, `tests/ci/smoke-image.sh`, human-owned) passes.
- 11.5 The migration check (`migrations.yml`, `tests/ci/check-migrations.sh`, human-owned) passes.
- 11.6 `deploy/` holds draft Kustomize manifests (namespace `woodshed`) that pass
       `kustomize build | kubeconform -strict`; see `docs/deployment.md`.

## 12. Look and design system
- 12.1 Classic-iOS look in the valve-amp colours: a nav bar on top, grouped rounded lists with
       thin separators and chevrons, segmented controls and switches, a tab bar at the bottom
       on phones and a sidebar on screens ≥ 900 px (Mac, iPad landscape). docs/design.md has
       the components and a recipe per page.
- 12.2 All colours, fonts and sizes live in `static/css/tokens.css`. Components live in
       `static/css/components.css` and `templates/_ui.html` (macros). Pages use the macros;
       page layout extras go in `static/css/pages.css` using tokens only.
       `tests/test_ui_rules.py` enforces this.
- 12.3 Themes `amp` (default), `flat` (no gloss) and `daylight` (light). Chosen in Settings
       (setting `theme`), applied on every page as `<html data-theme="…">` (none for `amp`).
- 12.4 `/styleguide` (logged in) shows every component in the current theme.

## 13. Tuner
- 13.1 `/tuner`: a "Start tuner" button asks for the microphone. Then it shows the detected
       note with octave (e.g. A₂), the frequency, and a needle from −50 to +50 cents. Within
       ±5 cents it shows "In tune" in the `ok` colour. "Stop" (and hiding the page) releases
       the microphone. Before start, and on silence, it says "Play a string".
- 13.2 Pitch detection runs in the browser only (autocorrelation on Web Audio time-domain
       samples, 60–1200 Hz). Nothing is recorded, stored or uploaded.
- 13.3 Reference A4 is 440 Hz by default, 430–450 in Settings (setting `tuner_a4`).
- 13.4 Six buttons for standard tuning (E2 A2 D3 G3 B3 E4) play a 2-second reference tone
       for that string; the string nearest to the detected pitch is highlighted.

## 14. Adding songs from MusicBrainz
- 14.1 `/items/new` starts with "Find the song": Title and Artist (optional) fields. Searching
       (on submit, and 500 ms after typing stops) loads up to 8 results without leaving the
       page: title, artist, year, length (m:ss). Each result links to `/items/new` with the
       form pre-filled (kind song, title, artist, year, original link
       `https://musicbrainz.org/recording/<mbid>`, plus hidden `mbid` and `release_group_id`).
       "Not listed? Fill it in yourself" is always there.
- 14.2 The server asks `https://musicbrainz.org/ws/2/recording` (`fmt=json`, `limit=25`) with
       query `recording:"<title>"` plus ` AND artist:"<artist>"` when given (quotes and
       backslashes escaped), the User-Agent from `MB_USER_AGENT`, a 5 s timeout, and at most
       one request per second for the whole app (it waits rather than fails). Results are
       deduplicated on (title, artist) ignoring case, keeping the earliest first-release date;
       sorted by score, then date; first 8 shown.
- 14.3 When MusicBrainz fails or is slow, the results area says "MusicBrainz didn't answer.
       Fill in the song yourself." and the form still works. No results: "Nothing found."
- 14.4 Saving an item with a `release_group_id` and no cover fetches
       `https://coverartarchive.org/release-group/<id>/front-250` (5 s timeout, redirects
       followed, max 2 MB, must be JPEG or PNG by magic bytes; anything else means no cover),
       stores it as `MEDIA_DIR/covers/<item_id>.<ext>` and serves it at
       `/media/cover/<item_id>`. Library rows and the item page show it; without a cover they
       show nothing extra.
- 14.5 Only song metadata and cover art are fetched: never tabs, audio or lyrics.
