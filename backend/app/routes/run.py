"""Runner routes (SPEC 5.2, 5.8).

Routes: GET /run/item/{item_id}, GET /run/{routine_id}
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Item, Routine, RoutineBlock
from app.templating import env, get_theme

router = APIRouter()


@router.get("/run/item/{item_id}", response_model=None)
def get_run_item(
    item_id: int,
    request: Request,
    minutes: int = Query(default=10),
) -> HTMLResponse:
    from types import SimpleNamespace

    with request.app.state.sessionmaker() as db:
        try:
            item = db.get(Item, item_id, options=[joinedload(Item.attachments)])
            if item is None:
                from fastapi import HTTPException

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
    return HTMLResponse(
        env.get_template("run.html").render(
            active="run",
            routine=None,
            blocks=blocks,
            theme=get_theme(request.app),
        )
    )


@router.get("/run/{routine_id}", response_model=None)
def get_run_routine(
    routine_id: int,
    request: Request,
) -> HTMLResponse:
    with request.app.state.sessionmaker() as db:
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
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Routine not found")
            blocks = routine.blocks
        finally:
            db.close()
    return HTMLResponse(
        env.get_template("run.html").render(
            active="run",
            routine=routine,
            blocks=blocks,
            theme=get_theme(request.app),
        )
    )
