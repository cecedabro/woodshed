"""Takes upload (SPEC 8.2).

Endpoints:
    POST /api/items/{id}/takes   — record a take
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.media import TooLarge, save_upload
from app.models import Take

router = APIRouter()


# ---------------------------------------------------------------------------
# Magic-byte sniffing
# ---------------------------------------------------------------------------

WEBM_BYTES = b"\x1a\x45\xdf\xa3"
FTYP_BYTES = b"ftyp"
OGGS_BYTES = b"OggS"


def sniff_audio(first_bytes: bytes) -> str | None:
    """Return ``"webm"`` | ``"mp4"`` | ``"ogg"`` | ``None`` by magic bytes."""
    if first_bytes[:4] == WEBM_BYTES:
        return "webm"

    # MP4: "ftyp" box at byte offset 4
    if first_bytes[4:8] == FTYP_BYTES and first_bytes[:4] != WEBM_BYTES:
        return "mp4"

    # Ogg: pages begin with "OggS"
    if first_bytes[:4] == OGGS_BYTES:
        return "ogg"

    return None


_CONTENT_TYPE_MAP: dict[str, str] = {
    "webm": "audio/webm",
    "mp4": "audio/mp4",
    "ogg": "audio/ogg",
}


# ---------------------------------------------------------------------------
# POST /api/items/{id}/takes
# ---------------------------------------------------------------------------


@router.post("/api/items/{item_id}/takes", status_code=201)
async def create_take(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    duration_seconds: int = Form(),
    bpm: int | None = Form(default=None),
    session_block_id: int | None = Form(default=None),
) -> dict[str, Any]:
    """Upload a take audio file for an item (SPEC 8.2).

    Returns 201 on success.
    """
    settings = request.app.state.settings
    # --- 1. Size gate ---
    if file.size is not None and file.size > settings.MAX_TAKE_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    # --- 2. Duration ---
    if duration_seconds < 1 or duration_seconds > 600:
        raise HTTPException(status_code=422, detail="duration_seconds must be 1-600")

    # --- 3. Magic bytes + extension check ---
    # Seek synchronously on the underlying file object
    file.file.seek(0)
    first_bytes = file.file.read(8)
    sniffed = sniff_audio(first_bytes)

    if sniffed is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported or corrupt audio format",
        )

    # Check that the file extension matches the sniffed format
    if file.filename is None:
        raise HTTPException(status_code=415, detail="File has no filename")

    ext = Path(file.filename).suffix.lstrip(".")
    if ext != sniffed:
        raise HTTPException(
            status_code=415,
            detail="File format does not match extension",
        )

    # Reset to beginning before save_upload reads the full file
    file.file.seek(0)

    # --- 4. Persist ---
    try:
        stored_name, size = save_upload(file, "takes", settings.MAX_TAKE_BYTES, settings.MEDIA_DIR)
    except TooLarge as e:
        raise HTTPException(status_code=413, detail="File too large") from e

    take = Take(
        item_id=item_id,
        session_block_id=session_block_id,
        stored_name=stored_name,
        content_type=_CONTENT_TYPE_MAP[sniffed],
        size_bytes=size,
        duration_seconds=duration_seconds,
        bpm=bpm,
    )
    db.add(take)
    db.commit()
    db.refresh(take)

    return {
        "id": take.id,
        "item_id": take.item_id,
        "stored_name": take.stored_name,
        "content_type": take.content_type,
        "size_bytes": take.size_bytes,
        "duration_seconds": take.duration_seconds,
        "bpm": take.bpm,
        "recorded_at": take.recorded_at.isoformat(),
    }
