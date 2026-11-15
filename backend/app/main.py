"""App factory. Routers are included here; keep route code in their own modules."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import router as api_router
from app.auth import get_login, post_login, post_logout
from app.config import Settings, check_production
from app.db import make_engine, make_sessionmaker
from app.item_forms import get_edit_item, get_new_item, post_edit_item, post_new_item
from app.items_service import get_item
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
                item = get_item(db, item_id)
            finally:
                db.close()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        edit_url = f"/items/{item.id}/edit"
        template = env.get_template("items_detail.html")
        return HTMLResponse(
            template.render({"item": item, "active": "items", "edit_link": edit_url})
        )

    app.add_api_route("/login", get_login, methods=["GET"])
    app.add_api_route("/login", post_login, methods=["POST"])
    app.add_api_route("/logout", post_logout, methods=["POST"])

    app.add_api_route("/items/new", get_new_item, methods=["GET"], response_model=None)
    app.add_api_route("/items/new", post_new_item, methods=["POST"], response_model=None)
    app.add_api_route("/items/{item_id}", get_item_page, methods=["GET"])
    app.add_api_route("/items/{item_id}/edit", get_edit_item, methods=["GET"], response_model=None)
    app.add_api_route(
        "/items/{item_id}/edit", post_edit_item, methods=["POST"], response_model=None
    )

    app.include_router(api_router)

    return app


app = create_app()
