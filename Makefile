SHELL := bash
.PHONY: setup fmt check jscheck run dev migrate migcheck
# Targets MUST exist and `make check` MUST pass after every task. Later tasks extend
# `check`, never weaken it.

setup:
	cd backend && uv sync

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .

check:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
	cd backend && uv run pytest -q --cov --cov-fail-under=90
	$(MAKE) -s jscheck
	cd backend && uvx bandit -q -r app -ll
	@if [ -n "$${DATABASE_URL:-}" ]; then $(MAKE) -s migcheck; fi
	@if [ -f deploy/Makefile ]; then $(MAKE) -s -C deploy validate; fi

# JS: syntax-check every file in static/js, then the node unit tests (no npm packages).
jscheck:
	@cd backend && for f in app/static/js/*.js; do [ -e "$$f" ] || continue; node --check "$$f" || exit 1; done
	cd backend && node --test --test-reporter=dot 'tests/js/**/*.test.js'

run:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev:
	cd backend && uv run python scripts/dev.py

migrate:
	cd backend && uv run alembic upgrade head

# Human-owned migration check (tests/ci/). Uses a separate, wiped database next to DATABASE_URL.
migcheck:
	@DATABASE_URL="$${DATABASE_URL%/*}/migcheck" bash tests/ci/check-migrations.sh
