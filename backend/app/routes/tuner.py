"""Tuner page route (SPEC 13.1, 13.4).

Routes: GET /tuner
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.templating import env, get_theme

router = APIRouter()

STANDARD_TUNING = [
    ("E2", 82.41),
    ("A2", 110.0),
    ("D3", 146.83),
    ("G3", 196.0),
    ("B3", 246.94),
    ("E4", 329.63),
]


def _get_tuner_a4(db: Session) -> int:
    try:
        from sqlalchemy import text

        row = db.execute(
            text("SELECT value FROM setting WHERE key = 'tuner_a4'")
        ).scalar_one_or_none()
    except Exception:
        row = None
    return int(row) if row else 440


@router.get("/tuner", response_model=None)
def get_tuner(
    request: Request,
) -> HTMLResponse:
    with request.app.state.sessionmaker() as db:
        try:
            a4 = _get_tuner_a4(db)
        finally:
            db.close()

    return HTMLResponse(
        env.get_template("tuner.html").render(
            active="tuner",
            a4=a4,
            strings=STANDARD_TUNING,
            theme=get_theme(request.app),
        )
    )
