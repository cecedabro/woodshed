"""Runner routes (SPEC 5.2, 5.8).

Routes: GET /run/item/{item_id}, GET /run/{routine_id}
"""

import json
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Item, Routine, RoutineBlock
from app.templating import env, get_theme

router = APIRouter()

DEFAULT_BPM = 80


def _fmt(seconds: int) -> str:
    """Countdown text, "m:ss" (runner-view.js formatTime does the same in the browser)."""
    return f"{seconds // 60}:{seconds % 60:02d}"


LINK_KINDS = (("tab", "Tab"), ("pdf", "PDF"), ("audio", "Backing track"))


def runner_links(blocks: Any) -> list[dict[str, Any]]:
    """Per block, the item's first tab / PDF / backing track (SPEC 5.2), in that order.

    `block` is the block's position in the run; the page shows only the current block's links.
    """
    links = []
    for index, b in enumerate(blocks):
        for kind, label in LINK_KINDS:
            att = next((a for a in b.item.attachments if a.kind == kind), None)
            if att is None:
                continue
            if kind == "tab":
                href = f"/items/{b.item_id}/tab/{att.id}"
            else:
                href = f"/media/attachment/{att.id}"
            links.append(
                {"block": index, "label": label, "sub": att.label or att.filename, "href": href}
            )
    return links


def _next_text(blocks: Any) -> str:
    return f"Next: {blocks[1].item.title}" if len(blocks) > 1 else "Last block"


def runner_blocks(blocks: Any) -> list[dict[str, Any]]:
    """The runner's block list (SPEC 6.2): start BPM is the block's, else the item's, else 80."""
    return [
        {
            "item_id": b.item_id,
            "title": b.item.title,
            "planned_seconds": b.minutes * 60,
            "start_bpm": b.bpm or b.item.current_bpm or DEFAULT_BPM,
        }
        for b in blocks
    ]


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
    _first_time = _fmt(minutes * 60)
    start_bpm = runner_blocks(blocks)[0]["start_bpm"]
    blocks_count = len(blocks)
    next_text = _next_text(blocks)
    return HTMLResponse(
        env.get_template("run.html").render(
            active="run",
            routine=None,
            routine_id="null",
            blocks=blocks,
            blocks_count=blocks_count,
            first_time=_first_time,
            next_text=next_text,
            blocks_json=json.dumps(runner_blocks(blocks)),
            start_bpm=start_bpm,
            links=runner_links(blocks),
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
    _first_time = _fmt(blocks[0].minutes * 60)
    start_bpm = runner_blocks(blocks)[0]["start_bpm"]
    blocks_count = len(blocks)
    next_text = _next_text(blocks)
    return HTMLResponse(
        env.get_template("run.html").render(
            active="run",
            routine=routine,
            routine_id=str(routine.id),
            blocks=blocks,
            blocks_count=blocks_count,
            first_time=_first_time,
            next_text=next_text,
            blocks_json=json.dumps(runner_blocks(blocks)),
            start_bpm=start_bpm,
            links=runner_links(blocks),
            theme=get_theme(request.app),
        )
    )
