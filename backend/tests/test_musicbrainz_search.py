"""Tests for the networking layer of app/musicbrainz.py (T75).

Covers ``search()``, ``fetch_url``, ``RateLimiter``, and
``MBUnavailable`` using a fake fetch function and a fake clock.
"""

from pathlib import Path

from app.config import Settings
from app.musicbrainz import (
    Candidate,
    MBUnavailable,
    RateLimiter,
    search,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---------------------------------------------------------------------------
# fetch_url – URL construction, User-Agent, encoding
# ---------------------------------------------------------------------------


def test_fetch_url_raises_MBUavailable_on_HTTP_error() -> None:
    """URLError from fetch becomes MBUnavailable."""

    from urllib.error import URLError

    def bad_fetch(url: str, ua: str, timeout: float) -> bytes:
        raise URLError("boom")

    try:
        search(
            "texas flood",
            _fetch=bad_fetch,
            limiter=RateLimiter(clock=lambda: 0),
        )
        raise AssertionError("MBUnavailable not raised")
    except MBUnavailable:
        pass


def test_fetch_url_raises_MBUavailable_on_invalid_json() -> None:
    """Invalid JSON from MusicBrainz raises MBUnavailable."""

    def json_bad_fetch(url: str, ua: str, timeout: float) -> bytes:
        return b"not json {{"

    try:
        search(
            "texas flood",
            _fetch=json_bad_fetch,
            limiter=RateLimiter(clock=lambda: 0),
        )
        raise AssertionError("MBUnavailable not raised")
    except MBUnavailable:
        pass


def test_fetch_url_raises_MBUavailable_on_rate_limit_body() -> None:
    """Rate-limit response body raises MBUnavailable."""
    rate_limited = _load("mb_rate_limited.json")

    def rate_fetch(url: str, ua: str, timeout: float) -> bytes:
        return rate_limited.encode()

    try:
        search(
            "texas flood",
            _fetch=rate_fetch,
            limiter=RateLimiter(clock=lambda: 0),
        )
        raise AssertionError("MBUnavailable not raised")
    except MBUnavailable:
        pass


def test_fetch_url_has_correct_params_and_encoding() -> None:
    """Fake fetch records the URL and can validate query params."""
    recorded: list[tuple[str, str, float]] = []

    def record_fetch(url: str, ua: str, timeout: float) -> bytes:
        recorded.append((url, ua, timeout))
        return b'{"recordings":[]}'

    limiter = RateLimiter(clock=lambda: 0)
    search(
        "Texas Flood",
        _fetch=record_fetch,
        limiter=limiter,
    )

    assert len(recorded) == 1
    url = recorded[0][0]
    assert "fmt=json" in url
    assert "limit=25" in url
    assert "query=" in url
    # query should be URL-encoded (space → %20 or +)
    assert "Texas%20Flood" in url or "Texas+Flood" in url


def test_fetch_url_sends_UserAgent_header() -> None:
    """The fake fetch receives the User-Agent from settings."""
    recorded: list[tuple[str, str, float]] = []

    def record_fetch(url: str, ua: str, timeout: float) -> bytes:
        recorded.append((url, ua, timeout))
        return b'{"recordings":[]}'

    settings = Settings(MB_USER_AGENT="my-app/2.0")
    search(
        "test",
        _fetch=record_fetch,
        settings=settings,
        limiter=RateLimiter(clock=lambda: 0),
    )

    assert recorded[0][1] == "my-app/2.0"


def test_fetch_url_uses_default_UserAgent_when_no_settings() -> None:
    """When no Settings are passed the default User-Agent is used."""
    recorded: list[tuple[str, str, float]] = []

    def record_fetch(url: str, ua: str, timeout: float) -> bytes:
        recorded.append((url, ua, timeout))
        return b'{"recordings":[]}'

    search(
        "test",
        _fetch=record_fetch,
        limiter=RateLimiter(clock=lambda: 0),
    )

    assert recorded[0][1] == "woodshed/1.0 (https://guitar.home.cedricschippers.dev)"


def test_fetch_url_uses_5s_timeout() -> None:
    """The default timeout is 5 seconds."""
    recorded: list[tuple[str, str, float]] = []

    def record_fetch(url: str, ua: str, timeout: float) -> bytes:
        recorded.append((url, ua, timeout))
        return b'{"recordings":[]}'

    search(
        "test",
        _fetch=record_fetch,
        limiter=RateLimiter(clock=lambda: 0),
    )

    assert recorded[0][2] == 5.0


# ---------------------------------------------------------------------------
# RateLimiter – fake clock, sleep recording
# ---------------------------------------------------------------------------


def test_ratelimiter_sleeps_on_rapid_second_request() -> None:
    """Two calls within one second record a sleep for the delay."""
    clock_time = [0.0]

    def fake_clock() -> float:
        return clock_time[0]

    sleeps: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    limiter = RateLimiter(clock=fake_clock, sleep=fake_sleep)

    # First call – no wait
    limiter.wait()
    assert sleeps == []

    # Advance 0.5 seconds
    clock_time[0] = 0.5
    limiter.wait()
    assert len(sleeps) == 1
    assert abs(sleeps[0] - 0.5) < 0.01  # slept for 0.5 s


def test_ratelimiter_no_sleep_when_a_full_second_passed() -> None:
    """Two calls more than one second apart do not sleep."""
    clock_time = [0.0]

    def fake_clock() -> float:
        return clock_time[0]

    sleeps: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    limiter = RateLimiter(clock=fake_clock, sleep=fake_sleep)

    limiter.wait()
    clock_time[0] = 1.1  # one full second passed
    limiter.wait()

    assert sleeps == []


def test_ratelimiter_reset_clears_state() -> None:
    """Calling reset() clears the last-request timestamp and recorded sleeps."""

    def fake_sleep(delay: float) -> None:
        pass

    limiter = RateLimiter(clock=lambda: 0, sleep=fake_sleep)
    limiter._LAST = 5.0
    limiter.sleeps = [0.5, 0.3]
    limiter.reset()
    assert limiter._LAST is None
    assert limiter.sleeps == []


def test_ratelimiter_default_is_singleton() -> None:
    """_get_default_limiter returns the same instance on repeated calls."""
    from app.musicbrainz import _get_default_limiter

    first = _get_default_limiter()
    second = _get_default_limiter()
    assert first is second


# ---------------------------------------------------------------------------
# search – end-to-end with real parse_recordings
# ---------------------------------------------------------------------------


def test_search_returns_candidates_from_real_fixture() -> None:
    """search() parses the Blackbird fixture and returns deduplicated candidates."""
    fixture = _load("mb_search_blackbird.json")

    def passthrough_fetch(url: str, ua: str, timeout: float) -> bytes:
        return fixture.encode()

    candidates = search(
        "blackbird",
        _fetch=passthrough_fetch,
        limiter=RateLimiter(clock=lambda: 0),
    )

    assert len(candidates) <= 8
    assert all(isinstance(c, Candidate) for c in candidates)


def test_search_returns_empty_list_when_no_recordings() -> None:
    """An empty fixture returns no candidates."""

    def empty_fetch(url: str, ua: str, timeout: float) -> bytes:
        return b'{"recordings": []}'

    candidates = search(
        "nothing",
        _fetch=empty_fetch,
        limiter=RateLimiter(clock=lambda: 0),
    )

    assert candidates == []
