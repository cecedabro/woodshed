# AGENTS.md — woodshed

Read this first, every task. Then read the area doc for the task (table below)
and the part of `SPEC.md` the task names.

You are a local model working one small task at a time with no human to ask.
Prefer the boring, explicit option. When unsure about **code**, follow the area
doc. When unsure about **look and feel**, you decide (see `docs/design.md`).

## What this builds
A self-hosted guitar practice organiser for one person (blues, classic and
psychedelic rock). It does not listen or score; it gives structure and keeps the
log. A routine is a list of blocks (item + minutes); the runner times each block
with a built-in metronome, moves on by itself and logs what was played. Plus a
library of songs/exercises with tabs, backing tracks and notes, tempo progress per
item, recorded takes, and a weekly goal. Runs on a k3s homelab at
`https://guitar.home.cedricschippers.dev`, used on a MacBook, an iPad and a phone
as a home-screen web app.

Principles (they decide close calls):
- One tap from opening the app to playing.
- Logging comes from the timer. The user never types in practice time.
- Progress is weekly totals. **No daily streaks**, anywhere.
- No scraping or downloading of tabs/audio; the user uploads his own files.

## Repository layout
| Path | What | Doc |
| --- | --- | --- |
| `backend/app/` | FastAPI app: routes, models, services, templates, static | `docs/backend.md`, `docs/frontend.md` |
| `backend/app/static/js/` | Browser JS as ES modules: pure logic + thin DOM glue | `docs/frontend.md` §js |
| `backend/app/static/vendor/` | htmx 2.0.11 and alphaTab 1.9.0, vendored by hand. **Do not edit.** | `docs/frontend.md` §vendor |
| `backend/tests/` | Your tests (pytest) and `tests/js/` (node:test) | `docs/testing.md` |
| `backend/alembic/` | Migrations | `docs/backend.md` §model |
| `tests/ci/`, `.github/workflows/`, `Dockerfile` | Human-owned CI checks. **Do not edit.** | `docs/deployment.md` |
| `deploy/` | Draft Kustomize manifests (later round) | `docs/deployment.md` |
| `SPEC.md`, `PLAN.md`, `AGENTS.md`, `docs/` | The human's instructions. **Do not edit.** | — |
| `PROGRESS.md` | You append to this after each task | — |

## How you are judged (the loop)
After you stop, the harness runs the task's `accept:` command and then
`make check`. The task counts as done only if both exit 0. Then it commits.
If they fail, your work is thrown away and the task is retried with the error.
So: **run the accept command and `make check` yourself before you stop, and fix what fails.**

## Rules
- There is no human to answer questions. Never ask for confirmation or "would you like me to continue". Decide the simplest option, do the task, and note the choice in `PROGRESS.md`.
- Change only what the task needs. Do not start other tasks.
- Stay inside the repo. You may not touch `/tmp` or any path outside it; such commands
  are rejected. For scratch files use `.agent/tmp/` (git-ignored).
- Never edit `tests/` (the root one), `docs/`, `SPEC.md`, `PLAN.md`, `AGENTS.md`, the
  vendored files, or anything listed in `.agent-protected`. The harness rejects such
  changes. If a human-owned check seems wrong, satisfy it and note the concern in `PROGRESS.md`.
- You write the code **and its tests**. Read `docs/testing.md`: weak tests that pass
  trivially count as a failed task. Tests assert real behaviour from `SPEC.md`.
- Add a dependency only if the area doc allows it. No npm packages at all.
- No secrets in the repo. Config comes from env vars with safe local defaults.
- After each task, append 3–5 lines to `PROGRESS.md`: what you changed, where, and
  anything the next task must know (a new env var, route, fixture, gotcha).

## Fixed technical decisions (do not revisit)
- Python 3.12, FastAPI, SQLAlchemy 2 (typed `Mapped[...]` models), Alembic, Postgres, `uv`.
- Server-rendered Jinja2 + HTMX. No SPA, no build step, no inline `<script>`.
- JS is plain ES modules in `static/js/`, loaded with `<script type="module">`. Logic that
  can be pure (timer, metronome scheduling, tap tempo, MIME choice) is pure and unit-tested with `node --test`.
- Tabs render with the vendored alphaTab; PDFs use the browser's viewer; audio uses `<audio>`.
- Uploads and recordings are files under `MEDIA_DIR` (a Longhorn volume in production);
  the database stores only their metadata.
- Times are UTC in code and storage; pages show Europe/Amsterdam.
- One user. Login is a password + signed cookie (SPEC §2); no user table.

## Design system (not your call)
The look is fixed: `docs/design.md` has the components (`templates/_ui.html` macros,
`static/css/components.css`, `static/css/tokens.css`) and a recipe for every page. Compose
pages from the macros; extra layout goes in `static/css/pages.css` with tokens only.
`backend/tests/test_ui_rules.py` checks this. Never edit the design files listed as human-owned.

## You decide
Internal module structure inside `backend/app/`, names of functions, wording on pages
where the recipe leaves it open.

## Commands
- `make setup` — `uv sync` (Python 3.12 is downloaded by uv if missing).
- `make check` — ruff, ruff format check, mypy (strict, `app/`), pytest with ≥ 90 % coverage,
  `node --check` + `node --test` for JS, bandit, the migration check when `DATABASE_URL` is set,
  and `deploy/` validation once it exists. Must pass after every task.
- `make fmt` — autoformat. Run before `make check`.
- `make migcheck` — the migration check. If you change `app/models.py`, add a new Alembic
  migration in the same task (`cd backend && uv run alembic revision --autogenerate -m "..."`,
  then read and tidy it); never edit an old one.
- `make dev` — preview server with seed data (exists after a later task).
- Offline docs are in `~/docs/` (fastapi, sqlalchemy, alembic, jinja, htmx, python).
  Search with `rg -i <term> ~/docs/<name>`; never read a whole file.
