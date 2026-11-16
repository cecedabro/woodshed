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
