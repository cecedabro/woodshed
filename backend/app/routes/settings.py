"""Settings routes (SPEC 9.1, 12.3).

Routes: GET /settings, POST /settings
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.templating import env

router = APIRouter()

_THEME_OPTIONS = [("amp", "Amp"), ("flat", "Flat"), ("daylight", "Daylight")]


def _get_weekly_goal(db: Any) -> int:
    try:
        row = db.execute(
            text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'")
        ).scalar_one_or_none()
    except SQLAlchemyError:
        row = None
    return int(row) if row else 120


def _get_theme(db: Any) -> str:
    try:
        row = db.execute(text("SELECT value FROM setting WHERE key = 'theme'")).scalar_one_or_none()
    except SQLAlchemyError:
        row = None
    return row if row else "amp"


def _get_tuner_a4(db: Any) -> int:
    try:
        row = db.execute(
            text("SELECT value FROM setting WHERE key = 'tuner_a4'")
        ).scalar_one_or_none()
    except SQLAlchemyError:
        row = None
    return int(row) if row else 440


@router.get("/settings", response_model=None)
def get_settings(
    request: Request,
) -> HTMLResponse:
    with request.app.state.sessionmaker() as db:
        try:
            value = _get_weekly_goal(db)
            theme = _get_theme(db)
            tuner_a4 = _get_tuner_a4(db)
        finally:
            db.close()
    return HTMLResponse(
        env.get_template("settings.html").render(
            active="settings",
            value=value,
            theme=theme,
            theme_options=_THEME_OPTIONS,
            tuner_a4=tuner_a4,
            error=None,
        )
    )


@router.post("/settings", response_model=None)
async def post_settings(
    request: Request,
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    raw = form.get("weekly_goal_minutes")
    minutes_str = raw.strip() if isinstance(raw, str) else ""
    try:
        minutes = int(minutes_str)
    except (ValueError, TypeError):
        with request.app.state.sessionmaker() as db:
            try:
                tuner_a4 = _get_tuner_a4(db)
            finally:
                db.close()
        return HTMLResponse(
            env.get_template("settings.html").render(
                active="settings",
                value="",
                theme=_validate_theme(form),
                theme_options=_THEME_OPTIONS,
                tuner_a4=tuner_a4,
                error="Enter a number between 0 and 10080.",
            ),
            status_code=422,
        )
    if minutes < 0 or minutes > 10080:
        with request.app.state.sessionmaker() as db:
            try:
                tuner_a4 = _get_tuner_a4(db)
            finally:
                db.close()
        return HTMLResponse(
            env.get_template("settings.html").render(
                active="settings",
                value=minutes_str,
                theme=_validate_theme(form),
                theme_options=_THEME_OPTIONS,
                tuner_a4=tuner_a4,
                error="Enter a number between 0 and 10080.",
            ),
            status_code=422,
        )
    tuner_a4_str = form.get("tuner_a4", "")
    if isinstance(tuner_a4_str, str) and tuner_a4_str.strip():
        try:
            tuner_val = int(tuner_a4_str.strip())
        except (ValueError, TypeError):
            tuner_val = None
        if tuner_val is not None and (tuner_val < 430 or tuner_val > 450):
            tuner_val = None
    else:
        tuner_val = None
    with request.app.state.sessionmaker() as db:
        try:
            db.execute(
                text(
                    "INSERT INTO setting (key, value) "
                    "VALUES ('weekly_goal_minutes', :v) "
                    "ON CONFLICT (key) DO UPDATE SET value = :v"
                ),
                {"v": str(minutes)},
            )
            db.execute(
                text(
                    "INSERT INTO setting (key, value) "
                    "VALUES ('theme', :v) "
                    "ON CONFLICT (key) DO UPDATE SET value = :v"
                ),
                {"v": _validate_theme(form)},
            )
            if tuner_val is not None:
                db.execute(
                    text(
                        "INSERT INTO setting (key, value) "
                        "VALUES ('tuner_a4', :v) "
                        "ON CONFLICT (key) DO UPDATE SET value = :v"
                    ),
                    {"v": str(tuner_val)},
                )
            db.commit()
        finally:
            db.close()
    return RedirectResponse("/settings", status_code=303)


def _validate_theme(form: Any) -> str:
    raw_theme: str = form.get("theme", "amp")
    if raw_theme in {t[0] for t in _THEME_OPTIONS}:
        return raw_theme
    return "amp"
