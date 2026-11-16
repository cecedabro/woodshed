"""MusicBrainz recording search – pure parsing and query building."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
