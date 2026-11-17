"""Media route (SPEC 3.6, 6.2): GET /media/{kind}/{id} serves attachments and takes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.models import Attachment, Item, Take

router = APIRouter()


@router.get("/media/cover/{item_id}", response_model=None)
def get_cover(
    item_id: int,
    request: Request,
) -> Response:
    """Serve the cover image for *item_id*, or 404 if none exists (SPEC 14.4)."""
    with request.app.state.sessionmaker() as db:
        try:
            item = db.scalar(select(Item).where(Item.id == item_id))
        finally:
            db.close()

    if item is None or not item.has_cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    media_dir = request.app.state.settings.MEDIA_DIR
    for ext in ("jpg", "png"):
        path = media_dir / "cover" / f"{item_id}.{ext}"
        if path.exists():
            content = path.read_bytes()
            media_type = "image/jpeg" if ext == "jpg" else "image/png"
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f'inline; filename="{item_id}.{ext}"'},
            )

    raise HTTPException(status_code=404, detail="Cover file missing on disk")


@router.get("/media/{kind}/{media_id}", response_model=None)
def get_media(
    kind: str,
    media_id: int,
    request: Request,
) -> Response:
    kind_map = {"attachment": "attachments", "take": "takes"}
    if kind not in kind_map:
        raise HTTPException(status_code=404, detail="Unknown media kind")

    fs_kind = kind_map[kind]
    media: Attachment | Take | None = None
    if kind == "attachment":
        with request.app.state.sessionmaker() as db:
            try:
                media = db.scalar(select(Attachment).where(Attachment.id == media_id))
            finally:
                db.close()
    else:
        with request.app.state.sessionmaker() as db:
            try:
                media = db.scalar(select(Take).where(Take.id == media_id))
            finally:
                db.close()

    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    media_dir = request.app.state.settings.MEDIA_DIR
    path = media_dir / fs_kind / media.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    content = path.read_bytes()
    media_type = media.content_type or "application/octet-stream"

    range_header = request.headers.get("range")
    if range_header and range_header.startswith("bytes="):
        range_spec = range_header[6:]
        parts = range_spec.split("-", 1)
        start_str, end_str = parts[0] or "", parts[1] or ""
        try:
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else len(content) - 1
            if start < 0 or end >= len(content) or start > end:
                raise HTTPException(status_code=416, detail="Invalid range")
        except ValueError:
            raise HTTPException(status_code=416, detail="Invalid range") from None

        sub = content[start : end + 1]
        return Response(
            content=sub,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{len(content)}",
                "Content-Disposition": f'inline; filename="{media.stored_name}"',
            },
            status_code=206,
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{media.stored_name}"'},
    )
