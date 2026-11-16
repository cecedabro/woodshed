"""Items routes (SPEC 3.1–3.5).

Routes: GET /library, GET/POST /items/new, GET /items/{id},
        GET/POST /items/{id}/edit, GET/POST /items/{id}/delete,
        POST /items/{id}/attachments,
        POST /items/{id}/attachments/{aid}/_delete
"""

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.items_service import filter_items, get_item, group_by_status
from app.media import TooLarge, delete_file, kind_for_filename, save_upload
from app.models import Attachment, Item
from app.stats import tempo_history
from app.templating import env, get_theme

router = APIRouter()


@router.get("/items/new", response_model=None)
async def get_new_item_page(request: Request) -> HTMLResponse:
    return await get_new_item(request)


@router.post("/items/new", response_model=None)
async def post_new_item_page(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:
    return await post_new_item(request, db=db)


@router.get("/library", response_model=None)
def get_library(request: Request) -> HTMLResponse:
    kind = request.query_params.get("kind")
    q = request.query_params.get("q")
    with request.app.state.sessionmaker() as db:
        try:
            items = filter_items(db, kind=kind, q=q)
            groups = group_by_status(items)
        finally:
            db.close()
    return HTMLResponse(
        env.get_template("library.html").render(
            active="library",
            groups=groups,
            kind_filter=kind,
            q=q,
            theme=get_theme(request.app),
        )
    )


@router.get("/items/{item_id}", response_model=None)
def get_item_page(request: Request, item_id: int) -> HTMLResponse | RedirectResponse:
    with request.app.state.sessionmaker() as db:
        try:
            item = db.scalar(
                select(Item).where(Item.id == item_id).options(joinedload(Item.attachments))
            )
            tempo = tempo_history(db, item_id)
        finally:
            db.close()
    if not item:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Item not found")
    edit_url = f"/items/{item.id}/edit"
    return HTMLResponse(
        env.get_template("items_detail.html").render(
            item=item,
            active="items",
            edit_link=edit_url,
            tempo_history=tempo,
            theme=get_theme(request.app),
        )
    )


@router.get("/items/{item_id}/delete", response_model=None)
def get_delete_item(request: Request, item_id: int) -> HTMLResponse | RedirectResponse:
    with request.app.state.sessionmaker() as db:
        try:
            item = db.scalar(
                select(Item)
                .where(Item.id == item_id)
                .options(joinedload(Item.attachments), joinedload(Item.takes))  # type: ignore[attr-defined]
            )
        finally:
            db.close()
    if item is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Item not found")
    return HTMLResponse(
        env.get_template("items_delete.html").render(
            active="library",
            item=item,
            attachment_count=len(item.attachments),
            take_count=len(item.takes),
            theme=get_theme(request.app),
        )
    )


@router.post("/items/{item_id}/delete", response_model=None)
def post_delete_item(request: Request, item_id: int) -> RedirectResponse:
    settings = request.app.state.settings
    with request.app.state.sessionmaker() as db:
        try:
            item = db.scalar(
                select(Item)
                .where(Item.id == item_id)
                .options(joinedload(Item.attachments), joinedload(Item.takes))  # type: ignore[attr-defined]
            )
            if item is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Item not found")
            for att in item.attachments:
                delete_file(settings.MEDIA_DIR, "attachments", att.stored_name)
            for take in item.takes:
                delete_file(settings.MEDIA_DIR, "takes", take.stored_name)
            db.delete(item)
            db.commit()
        finally:
            db.close()
    return RedirectResponse("/library", status_code=303)


@router.post("/items/{item_id}/attachments", response_model=None)
def post_upload_attachment(
    request: Request,
    item_id: int,
    file: UploadFile,
    label: str | None = Form(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = request.app.state.settings
    try:
        item = get_item(db, item_id)
        if item is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Item not found")
        max_bytes = settings.MAX_ATTACHMENT_BYTES
        kind = kind_for_filename(file.filename or "")
        if kind is None:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail="File type not allowed. Accepted: tabs, PDFs, and audio files.",
            )
        stored_name, size = save_upload(file, "attachments", max_bytes, settings.MEDIA_DIR)
        att = Attachment(
            item_id=item.id,
            filename=file.filename or "",
            stored_name=stored_name,
            kind=kind,
            label=label or "",
            content_type=file.content_type or "",
            size_bytes=size,
        )
        db.add(att)
        db.commit()
    except TooLarge as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return RedirectResponse(f"/items/{item_id}", status_code=303)


@router.get("/items/{item_id}/tab/{attachment_id}", response_model=None)
def get_tab_viewer(
    request: Request, item_id: int, attachment_id: int
) -> HTMLResponse | RedirectResponse:
    with request.app.state.sessionmaker() as db:
        try:
            item = db.scalar(
                select(Item).where(Item.id == item_id).options(joinedload(Item.attachments))
            )
            if item is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Item not found")
            att = db.scalar(
                select(Attachment).where(
                    Attachment.id == attachment_id, Attachment.item_id == item_id
                )
            )
            if att is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Attachment not found")
            if att.kind != "tab":
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Not a tab attachment")
        finally:
            db.close()
    return HTMLResponse(
        env.get_template("items_tab.html").render(
            active="items",
            attachment=att,
            item=item,
            theme=get_theme(request.app),
        )
    )


@router.post("/items/{item_id}/attachments/{attachment_id}/_delete", response_model=None)
def post_delete_attachment(request: Request, item_id: int, attachment_id: int) -> RedirectResponse:
    settings = request.app.state.settings
    with request.app.state.sessionmaker() as db:
        try:
            item = get_item(db, item_id)
            if item is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Attachment not found")
            att = db.scalar(
                select(Attachment).where(
                    Attachment.id == attachment_id, Attachment.item_id == item_id
                )
            )
            if att is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Attachment not found")
            delete_file(settings.MEDIA_DIR, "attachments", att.stored_name)
            db.delete(att)
            db.commit()
        finally:
            db.close()
    return RedirectResponse(f"/items/{item_id}", status_code=303)


# ---------------------------------------------------------------------------
# Item forms (item_forms.py)
# ---------------------------------------------------------------------------
from app.item_forms import get_edit_item, get_new_item, post_edit_item, post_new_item  # noqa: E402


@router.get("/items/{item_id}/edit", response_model=None)
async def get_edit_item_page(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    return await get_edit_item(request, item_id, db=db)


@router.post("/items/{item_id}/edit", response_model=None)
async def post_edit_item_page(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:
    return await post_edit_item(request, item_id, db=db)
