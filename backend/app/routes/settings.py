"""Settings routes (SPEC 9.1).

Routes: GET /settings, POST /settings
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from app.auth import require_login
from app.templating import env

router = APIRouter()


@router.get("/settings", response_model=None)
def get_settings(
    request: Request,
    login: None = Depends(require_login),
) -> HTMLResponse:
    with request.app.state.sessionmaker() as db:
        try:
            row = db.execute(
                text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'")
            ).scalar_one_or_none()
        finally:
            db.close()
    value = int(row) if row else 120
    return HTMLResponse(
        env.get_template("settings.html").render(
            active="settings",
            value=value,
            error=None,
        )
    )


@router.post("/settings", response_model=None)
async def post_settings(
    request: Request,
    login: None = Depends(require_login),
) -> HTMLResponse | RedirectResponse:
    from app.templating import env

    form = await request.form()
    raw = form.get("weekly_goal_minutes")
    minutes_str = raw.strip() if isinstance(raw, str) else ""
    try:
        minutes = int(minutes_str)
    except (ValueError, TypeError):
        return HTMLResponse(
            env.get_template("settings.html").render(
                active="settings",
                value="",
                error="Enter a number between 0 and 10080.",
            ),
            status_code=422,
        )
    if minutes < 0 or minutes > 10080:
        return HTMLResponse(
            env.get_template("settings.html").render(
                active="settings",
                value=minutes_str,
                error="Enter a number between 0 and 10080.",
            ),
            status_code=422,
        )
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
            db.commit()
        finally:
            db.close()
    return RedirectResponse("/settings", status_code=303)
