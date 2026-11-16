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
