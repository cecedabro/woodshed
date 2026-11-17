"""MusicBrainz recording search – parsing, query building, and HTTP fetching."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Candidate:
    mbid: str
    title: str
    artist: str
    year: int | None
    length: str  # "7:12" or ""
    release_group_id: str | None
    score: int
    date: str  # first-release-date or ""


class MBUnavailable(Exception):
    pass


def build_query(title: str, artist: str | None) -> str:
    """Build a MusicBrainz recording search query.

    Backslashes and double-quotes in *title* and *artist* are escaped.
    """
    title = title.replace("\\", "\\\\").replace('"', '\\"')
    if artist:
        artist = artist.replace("\\", "\\\\").replace('"', '\\"')
        return f'recording:"{title}" AND artist:"{artist}"'
    return f'recording:"{title}"'


def parse_recordings(data: dict[str, Any]) -> list[Candidate]:
    """Parse MusicBrainz JSON and return deduplicated, sorted candidates.

    Deduplication key is (title, artist) – case-insensitive – keeping the
    earliest *first-release-date*.  Results are sorted by score (desc) then
    date (asc) and limited to 8.
    """
    recordings: list[dict[str, Any]] = data.get("recordings", [])
    if not isinstance(recordings, list):
        recordings = []

    candidates: list[Candidate] = []
    for rec in recordings:
        artist_credit = rec.get("artist-credit") or []
        artist = " ".join(
            name + (entry.get("joinphrase") or "")
            for entry in artist_credit
            if (name := entry.get("name"))
        )
        rec_mbid = rec.get("id", "")

        releases = rec.get("releases") or []
        rgid = ""
        if releases:
            rg = (releases[0] or {}).get("release-group") or {}
            rgid = rg.get("id") or ""

        frd = rec.get("first-release-date") or ""
        length_ms = rec.get("length") or 0
        score = int(rec.get("score") or 0)

        minutes = length_ms // 60000
        seconds = length_ms % 60000 // 1000
        length = f"{minutes}:{seconds:02d}" if length_ms else ""

        candidates.append(
            Candidate(
                mbid=rec_mbid,
                title=rec.get("title", ""),
                artist=artist,
                year=int(frd[:4]) if len(frd) >= 4 and frd[:4].isdigit() else None,
                length=length,
                release_group_id=rgid or None,
                score=score,
                date=frd,
            )
        )

    # Deduplicate: keep earliest date per (title, artist)
    candidates = [c for c in candidates if c.date]

    groups: dict[tuple[str, str], list[Candidate]] = {}
    for c in candidates:
        key = (c.title.lower(), c.artist.lower())
        groups.setdefault(key, []).append(c)

    result: list[Candidate] = []
    for _key, group in groups.items():
        group.sort(key=lambda c: (c.date, -c.score))
        result.append(group[0])

    # Sort by score desc, then date asc (empty strings sort last naturally)
    result.sort(key=lambda c: (-c.score, c.date))

    return result[:8]


# ---------------------------------------------------------------------------
# Rate limiter – at most one request per second for the whole app
# ---------------------------------------------------------------------------


class RateLimiter:
    """Ensures at most one MusicBrainz request per second.

    * *clock* and *sleep* are injectable so tests can verify waits
      without real time passing (SPEC 14.2).
    """

    _LAST: float | None = None

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self.sleeps: list[float] = []  # recorded sleeps for test assertions

    # -- unit-of-work --------------------------------------------------------

    def wait(self) -> None:
        """Sleep if the last request was less than one second ago."""
        now = self._clock()
        if self._LAST is not None:
            elapsed = now - self._LAST
            if elapsed < 1.0:
                delay = 1.0 - elapsed
                self._sleep(delay)
                self.sleeps.append(delay)
        self._LAST = self._clock()

    def reset(self) -> None:
        """Clear internal state (convenient for tests)."""
        self._LAST = None
        self.sleeps.clear()


# Default limiter used by ``search()`` when the caller doesn't supply one.
_default_limiter: RateLimiter | None = None


def _get_default_limiter() -> RateLimiter:
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter()
    return _default_limiter


# ---------------------------------------------------------------------------
# HTTP fetching
# ---------------------------------------------------------------------------


def fetch_url(
    url: str,
    user_agent: str,
    timeout: float = 5.0,
    _real_fetch: Callable[[str, str, float], bytes] | None = None,
) -> bytes:
    """Fetch *url* via ``urllib.request`` with the given *user_agent*.

    Raises ``MBUnavailable`` on any network or parse failure.
    """
    if _real_fetch is not None:
        try:
            return _real_fetch(url, user_agent, timeout)
        except HTTPError as exc:
            raise MBUnavailable(f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise MBUnavailable(f"Network error: {exc}") from exc

    req = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec: B310 URL is a known MusicBrainz endpoint
            return cast(bytes, resp.read())
    except HTTPError as exc:
        raise MBUnavailable(f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise MBUnavailable(f"Network error: {exc}") from exc


def _body_to_bytes(body: str | bytes) -> bytes:
    if isinstance(body, str):
        return body.encode()
    return body


# ---------------------------------------------------------------------------
# Public search API
# ---------------------------------------------------------------------------


def search(
    query: str,
    *,
    settings: Any | None = None,
    limiter: RateLimiter | None = None,
    _fetch: Callable[[str, str, float], bytes] | None = None,
) -> list[Candidate]:
    """Search MusicBrainz recordings.

    * *query* – the **escaped** query string (already built by
      ``build_query``).
    * *settings* – if ``Settings`` is passed, ``MB_USER_AGENT`` and
      ``MB_TIMEOUT`` (default 5) are taken from it; otherwise the
      function uses the built-in defaults.
    * *limiter* – rate limiter instance; defaults to the global limiter.
    * *_fetch* – injectable fetch callback for tests (hidden).

    Uses a 5-second timeout and one request per second.
    Raises ``MBUnavailable`` when the API is unreachable or returns
    invalid data (SPEC 14.2-14.3).
    """
    if limiter is None:
        limiter = _get_default_limiter()

    # Resolve user-agent
    if settings is not None and hasattr(settings, "MB_USER_AGENT"):
        user_agent = settings.MB_USER_AGENT
    else:
        user_agent = "woodshed/1.0 (https://guitar.home.cedricschippers.dev)"

    # Resolve timeout
    if settings is not None and hasattr(settings, "MB_TIMEOUT"):
        timeout = float(getattr(settings, "MB_TIMEOUT", 5))
    else:
        timeout = 5.0

    url = f"https://musicbrainz.org/ws/2/recording?fmt=json&limit=25&query={quote_plus(query)}"

    limiter.wait()

    raw = fetch_url(url, user_agent, timeout, _real_fetch=_fetch)
    body = raw.decode()

    # Detect rate-limit response from MusicBrainz
    if "rate limit" in body.lower():
        raise MBUnavailable("Rate limit exceeded by MusicBrainz")

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError) as exc:
        raise MBUnavailable("Invalid JSON from MusicBrainz") from exc

    return parse_recordings(data)
