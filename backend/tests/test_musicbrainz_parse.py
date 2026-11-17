"""Tests for the pure part of app/musicbrainz.py (T74).

Covers Candidate, build_query, and parse_recordings using the real
MusicBrainz fixtures shipped with the project.
"""

import json
from pathlib import Path

from app.musicbrainz import Candidate, build_query, parse_recordings

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_bytes().decode())


# ---------------------------------------------------------------------------
# Texas Flood fixture – one candidate after dedupe
# ---------------------------------------------------------------------------


def test_texas_flood_one_candidate_after_dedupe() -> None:
    """Texas Flood + Stevie Ray Vaughan yields exactly one candidate."""
    data = _load("mb_recording_search.json")
    results = parse_recordings(data)
    srv = [c for c in results if c.artist == "Stevie Ray Vaughan"]
    assert len(srv) == 1


def test_texas_flood_candidate_has_earliest_year() -> None:
    """The surviving candidate carries the earliest first-release-date."""
    data = _load("mb_recording_search.json")
    results = parse_recordings(data)
    srv = [c for c in results if c.artist == "Stevie Ray Vaughan"]
    assert len(srv) == 1
    assert srv[0].date == "1990"


def test_texas_flood_candidate_length_mss() -> None:
    """The surviving candidate has a m:ss length (from earliest-year recording)."""
    data = _load("mb_recording_search.json")
    results = parse_recordings(data)
    srv = [c for c in results if c.artist == "Stevie Ray Vaughan"]
    assert len(srv) == 1
    assert srv[0].length == "5:44"


def test_texas_flood_candidate_title() -> None:
    """Deduped candidate preserves the title."""
    data = _load("mb_recording_search.json")
    results = parse_recordings(data)
    srv = [c for c in results if c.artist == "Stevie Ray Vaughan"]
    assert srv[0].title == "Texas Flood"


# ---------------------------------------------------------------------------
# Blackbird fixture – at most 8, all titled Blackbird, sorted by score/date
# ---------------------------------------------------------------------------


def test_blackbird_at_most_8_candidates() -> None:
    """Blackbird search returns at most 8 candidates."""
    data = _load("mb_search_blackbird.json")
    results = parse_recordings(data)
    assert len(results) <= 8


def test_blackbird_all_titled_blackbird() -> None:
    """Every candidate from the Blackbird fixture is titled 'Blackbird'."""
    data = _load("mb_search_blackbird.json")
    results = parse_recordings(data)
    for c in results:
        assert c.title == "Blackbird"


def test_blackbird_sorted_by_score_then_date() -> None:
    """Candidates are sorted by score descending, then date ascending."""
    data = _load("mb_search_blackbird.json")
    results = parse_recordings(data)
    for i in range(len(results) - 1):
        a, b = results[i], results[i + 1]
        if a.score > b.score:
            continue
        elif a.score == b.score:
            assert a.date <= b.date, (
                f"scores equal but dates not ascending: {a.date!r} vs {b.date!r}"
            )
        else:
            raise AssertionError(f"scores out of order: {a.score} < {b.score}")


# ---------------------------------------------------------------------------
# build_query – quoting and escaping
# ---------------------------------------------------------------------------


def test_build_query_escapes_quotes_in_title() -> None:
    'build_query("Say \\"Hi\\"", None) escapes the double quotes.'
    q = build_query('Say "Hi"', None)
    assert q == r'recording:"Say \"Hi\""'


def test_build_query_includes_artist_clause() -> None:
    """With an artist the query contains  AND artist:"…"."""
    q = build_query("Texas Flood", "Stevie Ray Vaughan")
    assert ' AND artist:"Stevie Ray Vaughan"' in q


def test_build_query_no_artist_clause_when_none() -> None:
    """When artist is None there is no artist clause."""
    q = build_query("Texas Flood", None)
    assert "AND" not in q
    assert q == 'recording:"Texas Flood"'


def test_build_query_escapes_backslashes() -> None:
    """Backslashes in title are escaped."""
    q = build_query("C:\\Path", "Artist")
    assert r"C:\\Path" in q


# ---------------------------------------------------------------------------
# Candidate dataclass basics
# ---------------------------------------------------------------------------


def test_candidate_is_frozen() -> None:
    """Candidate is an immutable dataclass."""
    c = Candidate(
        mbid="abc",
        title="T",
        artist="A",
        year=2000,
        length="3:12",
        release_group_id="rg",
        score=90,
        date="2000",
    )
    try:
        c.title = "X"
    except AttributeError:
        pass
    else:
        raise AssertionError("Candidate should be immutable")
