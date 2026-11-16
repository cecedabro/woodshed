"""Media helpers: file-kind detection, safe upload, and deletion (SPEC 3.5, backend.md §media)."""

import uuid
from pathlib import Path
from typing import Any

_CHUNK_SIZE = 1 * 1024 * 1024  # 1 MiB


# ---------------------------------------------------------------------------
# Extension → attachment kind mapping
# ---------------------------------------------------------------------------

_TAB_EXTS = {".gp", ".gp3", ".gp4", ".gp5", ".gpx", ".musicxml", ".xml", ".mxl"}
_PDF_EXTS = {".pdf"}
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".webm"}

_ALL_KNOWN: dict[str, str] = {}
for _e in _TAB_EXTS:
    _ALL_KNOWN[_e] = "tab"
for _e in _PDF_EXTS:
    _ALL_KNOWN[_e] = "pdf"
for _e in _AUDIO_EXTS:
    _ALL_KNOWN[_e] = "audio"


def kind_for_filename(name: str) -> str | None:
    """Derive attachment kind from the file extension (case-insensitive).

    Returns ``"tab"``, ``"pdf"``, ``"audio"``, or ``None`` for unknown
    extensions.  This mirrors SPEC §3.5 extension lists.
    """
    ext = Path(name).suffix.lower()
    return _ALL_KNOWN.get(ext)


# ---------------------------------------------------------------------------
# Upload / deletion helpers
# ---------------------------------------------------------------------------


class TooLarge(Exception):
    """Raised when the uploaded data exceeds *limit_bytes*.

    The partial file on disk is already removed by ``save_upload``.
    """

    pass


def save_upload(upload: Any, subdir: str, limit_bytes: int, media_dir: Path) -> tuple[str, int]:
    """Copy *upload* (an ``UploadFile``) into ``media_dir/<subdir>/``.

    * Files are named ``<uuid4 hex><ext>`` — never the client filename.
    * Bytes are copied in 1 MiB chunks.
    * As soon as the total bytes written would exceed *limit_bytes* the
      transfer is aborted and the partial file is removed; ``TooLarge`` is
      raised.
    * The target directory (``media_dir / subdir``) is created on first write.

    Returns ``(stored_name, size)`` on success.
    """
    ext = Path(upload.filename).suffix if upload.filename else ""
    stored_name = f"{uuid.uuid4().hex}{ext}"
    target = media_dir / subdir / stored_name

    # Ensure the directory exists (SPEC: "create the directories on first write")
    target.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    try:
        with open(target, "wb") as f:
            while True:
                chunk = upload.file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit_bytes:
                    f.write(chunk)
                    raise TooLarge(f"Upload {total} bytes exceeds limit {limit_bytes}")
                f.write(chunk)
    except Exception:
        # Clean up partial file on any failure
        if target.exists():
            target.unlink()
        raise

    return (stored_name, total)


def delete_file(media_dir: Path, subdir: str, stored_name: str) -> None:
    """Delete a stored file.  A missing file is not an error (SPEC §media)."""
    path = media_dir / subdir / stored_name
    if path.exists():
        path.unlink()
