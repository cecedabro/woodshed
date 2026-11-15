"""App factory. Routers are included here; keep route code in their own modules."""

import logging
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.api import router as api_router
from app.auth import get_login, post_login, post_logout
from app.config import Settings, check_production
from app.db import make_engine, make_sessionmaker
from app.item_forms import get_edit_item, get_new_item, post_edit_item, post_new_item
from app.items_service import filter_items, get_item, group_by_status
from app.media import TooLarge, delete_file, kind_for_filename, save_upload
from app.models import Attachment, Item
from app.security import SecurityMiddleware
from app.templating import env


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    check_production(settings)
    logging.basicConfig(level=settings.LOG_LEVEL.upper())

    app = FastAPI(title="woodshed", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.engine = make_engine(settings.DATABASE_URL)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    STATIC_DIR = Path(__file__).resolve().parents[0] / "static"
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.add_middleware(SecurityMiddleware)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                {"detail": "Not Found"},
                status_code=404,
            )
        template = env.get_template("404.html")
        return HTMLResponse(template.render({"active": None}), status_code=404)

    @app.get("/")
    def home() -> HTMLResponse:
        template = env.get_template("home.html")
        return HTMLResponse(template.render({"active": "home"}))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        try:
            with app.state.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready"})

    def get_item_page(item_id: int, request: Request) -> HTMLResponse:
        with app.state.sessionmaker() as db:
            try:
                item = db.scalar(
                    select(Item).where(Item.id == item_id).options(joinedload(Item.attachments))
                )
            finally:
                db.close()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        edit_url = f"/items/{item.id}/edit"
        template = env.get_template("items_detail.html")
        return HTMLResponse(
            template.render({"item": item, "active": "items", "edit_link": edit_url})
        )

    def get_library(request: Request) -> HTMLResponse:
        kind = request.query_params.get("kind")
        q = request.query_params.get("q")
        with app.state.sessionmaker() as db:
            try:
                items = filter_items(db, kind=kind, q=q)
                groups = group_by_status(items)
            finally:
                db.close()
        template = env.get_template("library.html")
        return HTMLResponse(
            template.render(
                {
                    "active": "library",
                    "groups": groups,
                    "kind_filter": kind,
                    "q": q,
                }
            )
        )

    def post_upload_attachment(
        item_id: int,
        file: UploadFile,
        label: str | None = Form(None),
    ) -> RedirectResponse:
        with app.state.sessionmaker() as db:
            try:
                item = get_item(db, item_id)
                if item is None:
                    raise HTTPException(status_code=404, detail="Item not found")
                settings = app.state.settings
                max_bytes = settings.MAX_ATTACHMENT_BYTES
                if file.size is not None and file.size > max_bytes:
                    raise TooLarge(file.size, max_bytes)
                kind = kind_for_filename(file.filename or "")
                if kind is None:
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
                raise HTTPException(status_code=413, detail=str(exc)) from exc
            finally:
                db.close()
        return RedirectResponse(f"/items/{item_id}", status_code=303)

    def post_delete_attachment(
        item_id: int,
        attachment_id: int,
    ) -> RedirectResponse:
        with app.state.sessionmaker() as db:
            try:
                item = get_item(db, item_id)
                if item is None:
                    raise HTTPException(status_code=404, detail="Item not found")
                att = db.scalar(
                    select(Attachment).where(
                        Attachment.id == attachment_id, Attachment.item_id == item_id
                    )
                )
                if att is None:
                    raise HTTPException(status_code=404, detail="Attachment not found")
                delete_file(app.state.settings.MEDIA_DIR, "attachments", att.stored_name)
                db.delete(att)
                db.commit()
            finally:
                db.close()
        return RedirectResponse(f"/items/{item_id}", status_code=303)

    app.add_api_route("/login", get_login, methods=["GET"])
    app.add_api_route("/login", post_login, methods=["POST"])
    app.add_api_route("/logout", post_logout, methods=["POST"])

    app.add_api_route("/library", get_library, methods=["GET"], response_model=None)
    app.add_api_route("/items/new", get_new_item, methods=["GET"], response_model=None)
    app.add_api_route("/items/new", post_new_item, methods=["POST"], response_model=None)
    app.add_api_route("/items/{item_id}", get_item_page, methods=["GET"])
    app.add_api_route("/items/{item_id}/edit", get_edit_item, methods=["GET"], response_model=None)
    app.add_api_route(
        "/items/{item_id}/edit", post_edit_item, methods=["POST"], response_model=None
    )

    def get_attachment_download(attachment_id: int) -> Response:
        with app.state.sessionmaker() as db:
            try:
                att = db.scalar(select(Attachment).where(Attachment.id == attachment_id))
                if att is None:
                    raise HTTPException(status_code=404, detail="Attachment not found")
                path = app.state.settings.MEDIA_DIR / "attachments" / att.stored_name
                if not path.exists():
                    raise HTTPException(status_code=404, detail="File not found on disk")
            finally:
                db.close()
        return Response(
            content=path.read_bytes(),
            media_type=att.content_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
        )

    app.add_api_route(
        "/attachments/{attachment_id}/download",
        get_attachment_download,
        methods=["GET"],
        response_model=None,
    )
    app.add_api_route(
        "/items/{item_id}/attachments",
        post_upload_attachment,
        methods=["POST"],
        response_model=None,
    )
    app.add_api_route(
        "/items/{item_id}/attachments/{attachment_id}/_delete",
        post_delete_attachment,
        methods=["POST"],
        response_model=None,
    )

    app.include_router(api_router)

    return app


app = create_app()
