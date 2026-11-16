"""Media and attachment download routes (SPEC 3.6, 6.2).

Routes: GET /attachments/{aid}/download,
        GET /media/{kind}/{id}
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.db import get_db
from app.models import Attachment, Take

router = APIRouter()


@router.get("/attachments/{attachment_id}/download", response_model=None)
def get_attachment_download(
    attachment_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    settings = request.app.state.settings
    att = db.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if att is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = settings.MEDIA_DIR / "attachments" / att.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return Response(
        content=path.read_bytes(),
        media_type=att.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
    )


@router.get("/media/{kind}/{media_id}", response_model=None)
def get_media(
    kind: str,
    media_id: int,
    request: Request,
    login: None = Depends(require_login),
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
