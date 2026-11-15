"""App factory. Routers are included here; keep route code in their own modules."""

import logging
from pathlib import Path
from types import SimpleNamespace

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.api import router as api_router
from app.auth import get_login, post_login, post_logout, require_login
from app.config import Settings, check_production
from app.db import get_db, make_engine, make_sessionmaker
from app.item_forms import get_edit_item, get_new_item, post_edit_item, post_new_item
from app.items_service import filter_items, get_item, group_by_status
from app.media import TooLarge, delete_file, kind_for_filename, save_upload
from app.models import Attachment, Item, Routine, RoutineBlock, Take
from app.security import SecurityMiddleware
from app.sessions import router as sessions_router
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
    def home(login: None = Depends(require_login)) -> HTMLResponse:
        with app.state.sessionmaker() as db:
            try:
                rows = db.execute(
                    text(
                        "SELECT r.id, r.name, COUNT(rb.id) AS block_count, "
                        "COALESCE(SUM(rb.minutes), 0) AS total_minutes, "
                        "MAX(ps.ended_at) AS last_practised "
                        "FROM routine r "
                        "LEFT JOIN routine_block rb ON rb.routine_id = r.id "
                        "LEFT JOIN practice_session ps ON ps.routine_id = r.id "
                        "GROUP BY r.id "
                        "ORDER BY COALESCE(MAX(ps.ended_at), r.created_at) DESC"
                    )
                ).fetchall()
            finally:
                db.close()
        routines = [
            {
                "id": row.id,
                "name": row.name,
                "block_count": row.block_count,
                "total_minutes": row.total_minutes,
                "last_practised": row.last_practised,
            }
            for row in rows
        ]
        if routines:
            routines[0]["most_recent"] = True
        template = env.get_template("home.html")
        return HTMLResponse(template.render({"active": "home", "routines": routines}))

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

    def get_delete_item(item_id: int, request: Request) -> HTMLResponse:
        with app.state.sessionmaker() as db:
            try:
                item = db.scalar(
                    select(Item)
                    .where(Item.id == item_id)
                    .options(joinedload(Item.attachments), joinedload(Item.takes))  # type: ignore[attr-defined]
                )
            finally:
                db.close()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        attachment_count = len(item.attachments)
        take_count = len(item.takes)
        template = env.get_template("items_delete.html")
        return HTMLResponse(
            template.render(
                {
                    "item": item,
                    "active": "library",
                    "attachment_count": attachment_count,
                    "take_count": take_count,
                }
            )
        )

    def post_delete_item(item_id: int, request: Request) -> RedirectResponse:
        with app.state.sessionmaker() as db:
            try:
                item = db.scalar(
                    select(Item)
                    .where(Item.id == item_id)
                    .options(joinedload(Item.attachments), joinedload(Item.takes))  # type: ignore[attr-defined]
                )
                if item is None:
                    raise HTTPException(status_code=404, detail="Item not found")
                # Delete attachment files from disk before deleting DB rows
                for att in item.attachments:
                    delete_file(app.state.settings.MEDIA_DIR, "attachments", att.stored_name)
                # Delete take files from disk before deleting DB rows
                for take in item.takes:
                    delete_file(app.state.settings.MEDIA_DIR, "takes", take.stored_name)
                db.delete(item)
                db.commit()
            finally:
                db.close()
        return RedirectResponse("/library", status_code=303)

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
    app.add_api_route(
        "/items/{item_id}/delete", get_delete_item, methods=["GET"], response_model=None
    )
    app.add_api_route(
        "/items/{item_id}/delete", post_delete_item, methods=["POST"], response_model=None
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

    # ------------------------------------------------------------------
    # Routine pages (SPEC 4.1, 4.3)
    # ------------------------------------------------------------------

    def get_routines(request: Request, login: None = Depends(require_login)) -> HTMLResponse:
        with app.state.sessionmaker() as db:
            try:
                routines = db.execute(
                    text(
                        "SELECT r.id, r.name, "
                        "COALESCE(SUM(rb.minutes), 0) AS total_minutes, "
                        "COUNT(rb.id) AS block_count "
                        "FROM routine r "
                        "LEFT JOIN routine_block rb ON rb.routine_id = r.id "
                        "GROUP BY r.id "
                        "ORDER BY r.updated_at DESC"
                    )
                ).fetchall()
            finally:
                db.close()
        routines_list = [
            {
                "id": row.id,
                "name": row.name,
                "total_minutes": row.total_minutes,
                "block_count": row.block_count,
            }
            for row in routines
        ]
        template = env.get_template("routines_list.html")
        return HTMLResponse(template.render({"active": "routines", "routines": routines_list}))

    async def get_new_routine(
        request: Request,
        login: None = Depends(require_login),
    ) -> HTMLResponse:
        template = env.get_template("routines_new.html")
        return HTMLResponse(
            template.render({"active": "routines", "routine": None, "errors": None})
        )

    async def post_new_routine(
        request: Request,
        login: None = Depends(require_login),
        db: Session = Depends(get_db),
    ) -> RedirectResponse | HTMLResponse:
        form = await request.form()
        raw_name = form.get("name")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        if not name:
            template = env.get_template("routines_new.html")
            return HTMLResponse(
                template.render(
                    {"active": "routines", "routine": None, "errors": {"name": "Name is required."}}
                ),
                status_code=422,
            )
        routine = Routine(name=name)
        db.add(routine)
        db.commit()
        return RedirectResponse(url=f"/routines/{routine.id}/edit", status_code=303)

    def get_routine_edit(
        routine_id: int,
        request: Request,
        login: None = Depends(require_login),
    ) -> HTMLResponse | RedirectResponse:
        with app.state.sessionmaker() as db:
            try:
                routine = db.get(Routine, routine_id)
            finally:
                db.close()
        if routine is None:
            raise HTTPException(status_code=404, detail="Routine not found")
        template = env.get_template("routines_edit.html")
        return HTMLResponse(template.render({"active": "routines", "routine": routine}))

    def get_delete_routine(
        routine_id: int,
        request: Request,
        login: None = Depends(require_login),
    ) -> HTMLResponse | RedirectResponse:
        with app.state.sessionmaker() as db:
            try:
                routine = db.get(Routine, routine_id)
            finally:
                db.close()
        if routine is None:
            raise HTTPException(status_code=404, detail="Routine not found")
        template = env.get_template("routines_delete.html")
        return HTMLResponse(template.render({"active": "routines", "routine": routine}))

    def post_delete_routine(
        routine_id: int,
        request: Request,
        login: None = Depends(require_login),
    ) -> RedirectResponse:
        with app.state.sessionmaker() as db:
            try:
                routine = db.get(Routine, routine_id)
                if routine is None:
                    raise HTTPException(status_code=404, detail="Routine not found")
                db.delete(routine)
                db.commit()
            finally:
                db.close()
        return RedirectResponse(url="/routines", status_code=303)

    app.add_api_route("/routines", get_routines, methods=["GET"], response_model=None)
    app.add_api_route("/routines/new", get_new_routine, methods=["GET"], response_model=None)
    app.add_api_route("/routines/new", post_new_routine, methods=["POST"], response_model=None)
    app.add_api_route(
        "/routines/{routine_id}/edit",
        get_routine_edit,
        methods=["GET"],
        response_model=None,
    )
    app.add_api_route(
        "/routines/{routine_id}/delete",
        get_delete_routine,
        methods=["GET"],
        response_model=None,
    )
    app.add_api_route(
        "/routines/{routine_id}/delete",
        post_delete_routine,
        methods=["POST"],
        response_model=None,
    )

    # ------------------------------------------------------------------
    # Runner page (SPEC 5.2, 5.8)
    # ------------------------------------------------------------------

    def get_run_item(
        item_id: int,
        request: Request,
        login: None = Depends(require_login),
        minutes: int = Query(default=10),
    ) -> HTMLResponse:
        with app.state.sessionmaker() as db:
            try:
                item = db.get(Item, item_id, options=[joinedload(Item.attachments)])
                if item is None:
                    raise HTTPException(status_code=404, detail="Item not found")
            finally:
                db.close()
        blocks = [
            SimpleNamespace(
                id="free",
                item_id=item.id,
                item=item,
                minutes=minutes,
                bpm=None,
                position=0,
            )
        ]
        template = env.get_template("run.html")
        return HTMLResponse(template.render({"active": "run", "routine": None, "blocks": blocks}))

    app.add_api_route(
        "/run/item/{item_id}",
        get_run_item,
        methods=["GET"],
        response_model=None,
    )

    def get_run_routine(
        routine_id: int,
        request: Request,
        login: None = Depends(require_login),
    ) -> HTMLResponse:
        with app.state.sessionmaker() as db:
            try:
                routine = db.scalar(
                    select(Routine)
                    .where(Routine.id == routine_id)
                    .options(
                        joinedload(Routine.blocks)
                        .joinedload(RoutineBlock.item)
                        .joinedload(Item.attachments)
                    )
                )
                if routine is None:
                    raise HTTPException(status_code=404, detail="Routine not found")
                blocks = routine.blocks
            finally:
                db.close()
        template = env.get_template("run.html")
        return HTMLResponse(
            template.render({"active": "run", "routine": routine, "blocks": blocks})
        )

    app.add_api_route(
        "/run/{routine_id}",
        get_run_routine,
        methods=["GET"],
        response_model=None,
    )

    def get_media(
        kind: str, id: int, request: Request, login: None = Depends(require_login)
    ) -> Response:
        media_dir = app.state.settings.MEDIA_DIR
        kind_map = {"attachment": "attachments", "take": "takes"}
        if kind not in kind_map:
            raise HTTPException(status_code=404, detail="Unknown media kind")

        fs_kind = kind_map[kind]
        media: Attachment | Take | None = None
        if kind == "attachment":
            with app.state.sessionmaker() as db:
                try:
                    media = db.scalar(select(Attachment).where(Attachment.id == id))
                finally:
                    db.close()
        else:
            with app.state.sessionmaker() as db:
                try:
                    media = db.scalar(select(Take).where(Take.id == id))
                finally:
                    db.close()

        if media is None:
            raise HTTPException(status_code=404, detail="Media not found")

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

    app.add_api_route(
        "/media/{kind}/{id}",
        get_media,
        methods=["GET"],
        response_model=None,
    )

    # ------------------------------------------------------------------
    # Settings page (SPEC 9.1)
    # ------------------------------------------------------------------

    def get_settings(
        request: Request,
        login: None = Depends(require_login),
    ) -> HTMLResponse:
        with app.state.sessionmaker() as db:
            try:
                row = db.execute(
                    text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'")
                ).scalar_one_or_none()
            finally:
                db.close()
        value = int(row) if row else 120
        template = env.get_template("settings.html")
        return HTMLResponse(template.render({"active": "settings", "value": value, "error": None}))

    async def post_settings(
        request: Request,
        login: None = Depends(require_login),
    ) -> HTMLResponse | RedirectResponse:
        form = await request.form()
        raw = form.get("weekly_goal_minutes")
        minutes_str = raw.strip() if isinstance(raw, str) else ""
        try:
            minutes = int(minutes_str)
        except (ValueError, TypeError):
            template = env.get_template("settings.html")
            return HTMLResponse(
                template.render(
                    {
                        "active": "settings",
                        "value": "",
                        "error": "Enter a number between 0 and 10080.",
                    }
                ),
                status_code=422,
            )
        if minutes < 0 or minutes > 10080:
            template = env.get_template("settings.html")
            return HTMLResponse(
                template.render(
                    {
                        "active": "settings",
                        "value": minutes_str,
                        "error": "Enter a number between 0 and 10080.",
                    }
                ),
                status_code=422,
            )
        with app.state.sessionmaker() as db:
            try:
                db.execute(
                    text(
                        "INSERT INTO setting (key, value) "
                        "VALUES ('weekly_goal_minutes', :v) "
                        "ON CONFLICT (key) DO UPDATE SET value = :v"
                    ),
                    {"v": str(minutes)},
                )
                db.commit()
            finally:
                db.close()
        return RedirectResponse("/settings", status_code=303)

    app.add_api_route("/settings", get_settings, methods=["GET"], response_model=None)
    app.add_api_route("/settings", post_settings, methods=["POST"], response_model=None)

    app.include_router(api_router)
    app.include_router(sessions_router)

    return app


app = create_app()
