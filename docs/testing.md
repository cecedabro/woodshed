# Testing (read this: you write the tests)

The harness decides a task is done by running its `accept:` command and `make check`.
You write those tests. A weak test that passes without proving the behaviour is a
**failed task**: it defeats the only safety the loop has.

## The one rule
Every test asserts a behaviour named in `SPEC.md`, with a concrete expected value.

## Required
- **Assert on values, not truthiness.** `assert r.status_code == 201 and r.json()["title"] == "Heartbreaker"`,
  never `assert r.json()`.
- **One success and one failure path per endpoint** (bad input → 422 and nothing stored;
  not logged in → 303/401).
- **Check side effects.** After a POST, query the database (`db` fixture) for the exact rows.
  After an upload, check the file exists under `settings.MEDIA_DIR` with the right bytes;
  after a delete, check row and file are gone.
- **Real Postgres.** Never mock the database or use SQLite. `backend/tests/conftest.py`
  gives you a migrated database (`woodshed_test` on `$DATABASE_URL`'s server, or a pgserver)
  and empties every table after each test.
- **Boundaries** from SPEC: 20 and 400 BPM pass, 19 and 401 fail; 25 MB passes, 25 MB + 1 byte
  is 413; `played_seconds` 9 is not stored, 10 is; the 15-minute login window.
- **Time** comes from `app.clock.now()`; in tests `monkeypatch.setattr("app.clock.now", lambda: FIXED)`.
  Build datetimes as `datetime(2026, 3, 29, 1, 30, tzinfo=UTC) + timedelta(...)`. Never
  `now.replace(day=now.day + 1)`; it crashes at month ends. Pick fixed dates around the
  DST changes (last Sunday of March and of October) for week tests.
- **Login.** Once login exists (PLAN T07), the `client` fixture is logged in; use
  `anon_client` for logged-out tests.

## JS tests
`backend/tests/js/<module>.test.js`, run by `node --test`. Import the pure module directly
(`import { createTimer } from "../../app/static/js/timer.js"`), pass `now` values in
milliseconds, and assert exact numbers (`assert.equal(t.played(31_000), 30)`). Fakes for
`api`/`cue` are plain objects that record calls; assert on the recorded payloads.

## Banned (these count as not done)
- No assertion, `assert True`, or only `assert response`.
- Only checking that something "doesn't raise".
- Asserting that a mock was called instead of the observable result (JS fakes recording
  the payload sent to the API are fine: that payload is the observable result).
- `skip`/`xfail`/`.skip`/`.todo` to get green. If you can't make it pass, stop.

## Shape
Arrange–Act–Assert, one behaviour per test, descriptive names
(`test_block_under_ten_seconds_is_not_stored`). The whole suite must stay fast (< 60 s).
