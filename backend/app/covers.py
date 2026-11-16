"""Cover art: fetch from iTunes, save to disk, detect format by magic bytes (SPEC 14.4)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Max cover size: 2 MB (SPEC 14.4)
MAX_COVER_BYTES = 2 * 1024 * 1024

# Magic bytes for JPEG and PNG
_JPEG_SIG = b"\xff\xd8\xff"
_PNG_SIG = b"\x89PNG"


def _detect_ext(data: bytes) -> str | None:
    """Return ``'jpg'`` or ``'png'`` based on magic bytes, or ``None`` if rejected."""
    if data[:4] == _PNG_SIG:
        return "png"
    if data[:3] == _JPEG_SIG:
        return "jpg"
    # Could be HTML or something else – reject
    return None


def _fetch(url: str, user_agent: str, timeout: float = 5.0) -> bytes:
    """Default real fetch implementation using urllib."""
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    req = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec[B310]
            return resp.read()  # type: ignore[no-any-return]
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def fetch_cover(
    release_group_id: str,
    user_agent: str,
    *,
    fetch: Callable[[str, str], bytes] | None = None,
) -> bytes | None:
    """Look up cover art for *release_group_id* via iTunes Search API.

    Returns the raw image bytes on success, or ``None`` on any failure
    (no result, HTML response, oversized file, or network error).
    """
    fetch_fn = fetch or _fetch
    url = f"https://itunes.apple.com/search?term=&mbReleaseId={release_group_id}&limit=1"
    try:
        data = fetch_fn(url, user_agent)
    except Exception:
        return None

    if not data:
        return None

    ext = _detect_ext(data)
    if ext is None:
        logger.info(
            "Cover for rgid %s rejected: not JPEG/PNG (got %d bytes)",
            release_group_id,
            len(data),
        )
        return None

    if len(data) > MAX_COVER_BYTES:
        logger.info(
            "Cover for rgid %s rejected: %d bytes > %d limit",
            release_group_id,
            len(data),
            MAX_COVER_BYTES,
        )
        return None

    return data


def save_cover(
    item_id: int,
    data: bytes,
    media_dir: Path,
) -> bool:
    """Write *data* to ``media_dir/cover/{item_id}.{ext}``.

    Returns ``True`` when the file was saved successfully, ``False`` otherwise.
    Sets ``has_cover`` on *item_id* by updating the filesystem path.
    """
    ext = "jpg" if data[:3] == _JPEG_SIG else "png"
    cover_dir = media_dir / "cover"
    try:
        cover_dir.mkdir(parents=True, exist_ok=True)
        cover_path = cover_dir / f"{item_id}.{ext}"
        cover_path.write_bytes(data)
        return True
    except OSError:
        return False
