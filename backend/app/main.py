"""App factory. Routers are included here; keep route code in their own modules."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import router as api_router
from app.auth import LoginRequiredMiddleware, get_login, post_login, post_logout
from app.clock import LOCAL_TZ
from app.config import Settings, check_production
from app.db import make_engine, make_sessionmaker
from app.routes import (
    items_router,
    media_router,
    metronome_router,
    progress_router,
    routines_router,
    run_router,
    settings_router,
    takes_router,
    tuner_router,
)
from app.security import SecurityMiddleware
from app.sessions import router as sessions_router
from app.stats import minutes_per_week, week_start
from app.templating import env, get_theme


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
                        "SELECT r.id, r.name, "
                        "COALESCE(sub.block_count, 0) AS block_count, "
                        "COALESCE(sub.total_minutes, 0) AS total_minutes, "
                        "sub.last_practised "
                        "FROM routine r "
                        "LEFT JOIN ("
                        "  SELECT rb.routine_id, "
                        "    COUNT(*) AS block_count, "
                        "    COALESCE(SUM(rb.minutes), 0) AS total_minutes, "
                        "    (SELECT MAX(ps.ended_at) FROM practice_session ps "
                        "     WHERE ps.routine_id = rb.routine_id) AS last_practised "
                        "  FROM routine_block rb "
                        "  GROUP BY rb.routine_id"
                        ") sub ON sub.routine_id = r.id "
                        "ORDER BY COALESCE(sub.last_practised, r.created_at) DESC"
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
                "n_blocks": row.block_count,
                "minutes": row.total_minutes,
            }
            for row in rows
        ]
        if routines:
            first = routines.pop(0)
            others = routines
        else:
            first = None
            others = []

        if goal > 0:
            remaining = goal - week_minutes
            aside_text = "Goal reached" if remaining <= 0 else f"{remaining} to go"
        else:
            aside_text = None

        template = env.get_template("home.html")
        return HTMLResponse(
            template.render(
                {
                    "active": "home",
                    "first": first,
                    "others": others,
                    "week_minutes": week_minutes,
                    "goal": goal,
                    "aside_text": aside_text,
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
    app.include_router(routines_router)
    app.include_router(run_router)
    app.include_router(settings_router)
    app.include_router(metronome_router)
    app.include_router(tuner_router)
    app.include_router(api_router)
    app.include_router(sessions_router)
    app.include_router(takes_router)

    return app


app = create_app()
