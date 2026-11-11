#!/usr/bin/env bash
# Human-owned migration check (SPEC 11.5). The agent may not edit tests/.
# Needs DATABASE_URL pointing at a throwaway Postgres database: this script WIPES it.
# Run from the repo root: DATABASE_URL=... bash tests/ci/check-migrations.sh
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL to a throwaway Postgres database}"
ROOT=$(pwd)
HELPER="$ROOT/tests/ci/migcheck.py"
export APP_ENV=development APP_PASSWORD=migcheck-password
MEDIA_DIR=$(mktemp -d)
export MEDIA_DIR

step() { printf '\n== %s\n' "$*"; }
# run <checkout> <cmd...>: run a command in that checkout's backend with its own deps
run() { local dir=$1; shift; (cd "$dir/backend" && uv run --frozen -q "$@"); }
# seed_or_skip <checkout>: exit code 3 from seed means "no item API yet", which is fine early on
seed_or_skip() {
  local rc=0
  run "$1" python "$HELPER" seed || rc=$?
  if [ "$rc" -eq 3 ]; then return 1; fi
  if [ "$rc" -ne 0 ]; then exit "$rc"; fi
}

step "one migration head"
heads=$(run "$ROOT" alembic heads | grep -c . || true)
if [ "$heads" -ne 1 ]; then
  echo "expected exactly 1 alembic head, found $heads (merge the branches)"; exit 1
fi

step "upgrade an empty database to head"
run "$ROOT" python "$HELPER" wipe
run "$ROOT" alembic upgrade head

step "models match the migrations (alembic check)"
run "$ROOT" alembic check

step "upgrade head again is a no-op"
run "$ROOT" alembic upgrade head

step "downgrade to base and back up"
run "$ROOT" alembic downgrade base
run "$ROOT" alembic upgrade head

step "existing data survives upgrading to head"
run "$ROOT" python "$HELPER" wipe
run "$ROOT" alembic upgrade head
if seed_or_skip "$ROOT"; then
  run "$ROOT" alembic upgrade head
  run "$ROOT" python "$HELPER" verify
fi

prev=$(git -C "$ROOT" tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -n1)
if [ -z "$prev" ]; then
  step "no previous release tag: skipping the upgrade-from-release check"
  exit 0
fi

step "upgrade from the last release ($prev) with its data"
old=$(mktemp -d)
trap 'git -C "$ROOT" worktree remove --force "$old" >/dev/null 2>&1 || true' EXIT
git -C "$ROOT" worktree add -q --detach "$old" "$prev"
run "$ROOT" python "$HELPER" wipe
run "$old" alembic upgrade head
if seed_or_skip "$old"; then
  run "$ROOT" alembic upgrade head
  run "$ROOT" python "$HELPER" verify
fi

step "all migration checks passed"
