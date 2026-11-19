"""Metronome page route (SPEC 6).

Routes: GET /metronome
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import env, get_theme

router = APIRouter()


@router.get("/metronome", response_model=None)
def get_metronome(
    request: Request,
) -> HTMLResponse:
    return HTMLResponse(
        env.get_template("metronome.html").render(
            active="tuner",
            bpm=80,
            theme=get_theme(request.app),
        )
    )
