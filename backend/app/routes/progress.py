"""Progress page route (SPEC 7.1, 7.2, 9.2).

Routes: GET /progress
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.stats import item_tempo_progress, weeks_12
from app.templating import env, get_theme

router = APIRouter()


@router.get("/progress", response_model=None)
def get_progress(
    request: Request,
) -> HTMLResponse:
    with request.app.state.sessionmaker() as db:
        try:
            goal_row = db.execute(
                text("SELECT value FROM setting WHERE key = 'weekly_goal_minutes'")
            ).scalar_one_or_none()
            goal = int(goal_row) if goal_row else 120
            week_data = weeks_12(db)
            tempo_items = item_tempo_progress(db)

            minutes_list: list[int] = [w["minutes"] for w in week_data]  # type: ignore[misc]
            this_week = minutes_list[-1] if minutes_list else 0
            avg_12wk = round(sum(minutes_list) / 12) if minutes_list else 0
            best_week = max(minutes_list) if minutes_list else 0
        finally:
            db.close()

    return HTMLResponse(
        env.get_template("progress.html").render(
            active="progress",
            weeks=week_data,
            goal=goal,
            tempo_items=tempo_items,
            theme=get_theme(request.app),
            this_week=this_week,
            avg_12wk=avg_12wk,
            best_week=best_week,
        )
    )
