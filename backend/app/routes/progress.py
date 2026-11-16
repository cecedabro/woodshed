"""Progress page route (SPEC 7.1, 7.2, 9.2).

Routes: GET /progress
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.auth import require_login
from app.stats import item_tempo_progress, weeks_12
from app.templating import env, get_theme

router = APIRouter()


@router.get("/progress", response_model=None)
def get_progress(
    request: Request,
    login: None = Depends(require_login),
) -> HTMLResponse:
    with request.app.state.sessionmaker() as db:
        try:
            goal_row = db.execute(
                text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'")
            ).scalar_one_or_none()
            goal = int(goal_row) if goal_row else 120
            week_data = weeks_12(db)
            tempo_items = item_tempo_progress(db)
        finally:
            db.close()

    return HTMLResponse(
        env.get_template("progress.html").render(
            active="progress",
            weeks=week_data,
            goal=goal,
            tempo_items=tempo_items,
            theme=get_theme(request.app),
        )
    )
