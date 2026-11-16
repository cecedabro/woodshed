"""App factory. Routers are included here; keep route code in their own modules."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import Scope

from app.api import router as api_router
from app.auth import LoginRequiredMiddleware, get_login, post_login, post_logout
from app.clock import LOCAL_TZ
from app.config import Settings, check_production
from app.db import make_engine, make_sessionmaker
from app.routes import (
    items_router,
    media_router,
    progress_router,
    pwa_router,
    routines_router,
    run_router,
    settings_router,
)
from app.security import SecurityMiddleware
from app.sessions import router as sessions_router
from app.stats import minutes_per_week, week_start
from app.templating import env, get_theme


class RevalidatingStaticFiles(StaticFiles):
    """Static files that browsers re-check on every use (`Cache-Control: no-cache`).

    Without a Cache-Control header browsers guess how long a file stays fresh, so after a
    deploy a phone could keep running old JS/CSS for hours. With no-cache they send the
    ETag back and get a cheap 304 when nothing changed. URL versioning would not cover
    ES-module imports (`import "./runner.js"`), this does.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    check_production(settings)
    logging.basicConfig(level=settings.LOG_LEVEL.upper())

    app = FastAPI(title="woodshed", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.engine = make_engine(settings.DATABASE_URL)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    STATIC_DIR = Path(__file__).resolve().parents[0] / "static"
    app.mount("/static", RevalidatingStaticFiles(directory=str(STATIC_DIR)), name="static")

    # Added last = outermost: security headers also land on login redirects.
    app.add_middleware(LoginRequiredMiddleware)
    app.add_middleware(SecurityMiddleware)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                {"detail": "Not Found"},
                status_code=404,
            )
        template = env.get_template("404.html")
        return HTMLResponse(
            template.render({"active": None, "theme": get_theme(request.app)}),
            status_code=404,
        )

    @app.get("/")
    def home() -> HTMLResponse:
        from datetime import datetime

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

                # Weekly goal and progress (SPEC 9.2)
                goal_row = db.execute(
                    text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'")
                ).scalar_one_or_none()
                goal = int(goal_row) if goal_row else 120

                now_local = datetime.now(LOCAL_TZ)
                this_monday = week_start(now_local)
                week_mins = minutes_per_week(db, [this_monday])
                week_minutes = week_mins.get(this_monday, 0)
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
        return HTMLResponse(
            template.render(
                {
                    "active": "home",
                    "routines": routines,
                    "week_minutes": week_minutes,
                    "goal": goal,
                    "theme": get_theme(app),
                }
            )
        )

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

    @app.get("/styleguide", response_model=None)
    def styleguide(
        request: Request,
    ) -> HTMLResponse:
        return HTMLResponse(
            env.get_template("styleguide.html").render(
                active=None,
                theme=get_theme(app),
            )
        )

    app.add_api_route("/login", get_login, methods=["GET"])
    app.add_api_route("/login", post_login, methods=["POST"])
    app.add_api_route("/logout", post_logout, methods=["POST"])

    app.include_router(items_router)
    app.include_router(media_router)
    app.include_router(progress_router)
    app.include_router(pwa_router)
    app.include_router(routines_router)
    app.include_router(run_router)
    app.include_router(settings_router)
    app.include_router(api_router)
    app.include_router(sessions_router)

    return app


app = create_app()
