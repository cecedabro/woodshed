"""Tests for MusicBrainz lookup page (SPEC 14.1-14.3).

Routes: GET /items/lookup?title=&artist=
"""

import re
from unittest.mock import patch

from app.musicbrainz import Candidate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CANDIDATE = Candidate(
    mbid="mb-123",
    title="Test Song",
    artist="Test Artist",
    year=2020,
    length="3:45",
    release_group_id="rg-456",
    score=100,
    date="2020-01-15",
)


def _candidates(count: int = 1) -> list[Candidate]:
    return [_CANDIDATE] * count


# ---------------------------------------------------------------------------
# GET /items/lookup
# ---------------------------------------------------------------------------


def test_lookup_returns_200(client):
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=Test+Song&artist=Test+Artist")
    assert resp.status_code == 200
    assert b"Test Song" in resp.content
    assert b"Test Artist" in resp.content


def test_lookup_builds_query(client):
    """Lookup sends a combined recording+artist query to MusicBrainz."""
    with patch("app.routes.items.search", return_value=[]) as mock:
        client.get("/items/lookup?title=Foo&artist=Bar")
    call_args = mock.call_args
    query = call_args[0][0] if call_args[0] else call_args[1]["query"]
    assert 'recording:"Foo"' in query
    assert 'artist:"Bar"' in query


def test_lookup_empty_title_only(client):
    with patch("app.routes.items.search", return_value=[]) as mock:
        resp = client.get("/items/lookup?title=Only+Title")
    assert resp.status_code == 200
    call_args = mock.call_args
    query = call_args[0][0] if call_args[0] else call_args[1]["query"]
    assert "artist:" not in query


def test_lookup_empty_artist_only(client):
    with patch("app.routes.items.search", return_value=[]) as mock:
        resp = client.get("/items/lookup?artist=Only+Artist")
    assert resp.status_code == 200
    call_args = mock.call_args
    query = call_args[0][0] if call_args[0] else call_args[1]["query"]
    assert 'recording:""' in query  # build_query always includes recording clause
    assert 'artist:"Only Artist"' in query


def test_lookup_no_params_shows_blank(client):
    """Lookup with no title or artist returns empty results, no error."""
    with patch("app.routes.items.search", return_value=[]):
        resp = client.get("/items/lookup")
    assert resp.status_code == 200
    assert b"Nothing found." in resp.content


# ---------------------------------------------------------------------------
# Pre-fill links
# ---------------------------------------------------------------------------


def test_lookup_pre_fill_link_contains_title(client):
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=My+Song&artist=My+Band")
    assert re.search(rb'href="/items/new\?kind=song&amp;title=Test%20Song', resp.content)


def test_lookup_pre_fill_link_contains_artist(client):
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=My+Song&artist=My+Band")
    assert b"&amp;artist=Test%20Artist" in resp.content


def test_lookup_pre_fill_link_contains_year(client):
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=My+Song")
    assert b"&amp;year=2020" in resp.content


def test_lookup_pre_fill_link_contains_mbid(client):
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=My+Song")
    assert b"&amp;mbid=mb-123" in resp.content


def test_lookup_pre_fill_link_contains_rgid(client):
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=My+Song")
    assert b"&amp;release_group_id=rg-456" in resp.content


def test_lookup_pre_fill_link_no_original_url(client):
    """Original URL should NOT appear in pre-fill links (length is a duration, not a URL)."""
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=My+Song")
    assert b"original_url" not in resp.content


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_lookup_error_on_mb_unavailable(client):
    from app.musicbrainz import MBUnavailable

    with patch("app.routes.items.search", side_effect=MBUnavailable("timeout")):
        resp = client.get("/items/lookup?title=Test+Song")
    assert resp.status_code == 200
    assert b"MusicBrainz didn" in resp.content


def test_lookup_no_error_when_no_query(client):
    """No error message shown when lookup is hit with no params."""
    resp = client.get("/items/lookup")
    assert b"MusicBrainz didn't answer" not in resp.content


# ---------------------------------------------------------------------------
# Data attributes on result items
# ---------------------------------------------------------------------------


def test_lookup_result_has_data_attributes(client):
    with patch("app.routes.items.search", return_value=_candidates()):
        resp = client.get("/items/lookup?title=My+Song")
    assert b'data-mbid="mb-123"' in resp.content
    assert b'data-rgid="rg-456"' in resp.content
    assert b'data-title="Test Song"' in resp.content
    assert b'data-artist="Test Artist"' in resp.content
    assert b'data-year="2020"' in resp.content
    assert b'data-length="3:45"' in resp.content
