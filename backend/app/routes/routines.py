"""Routines routes (SPEC 4.1, 4.2, 4.3).

Routes: GET /routines, GET/POST /routines/new, GET /routines/{id}/edit,
        GET/POST /routines/{id}/delete,
        POST /routines/{id}/blocks, POST /routines/{id}/blocks/{block_id}/remove,
        POST /routines/{id}/blocks/{block_id}/move
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Item, Routine, RoutineBlock
from app.templating import env, get_theme

router = APIRouter()


@router.get("/routines", response_model=None)
def get_routines(
    request: Request,
) -> HTMLResponse:
    with request.app.state.sessionmaker() as db:
        try:
            rows = db.execute(
                text(
                    "SELECT r.id, r.name, "
                    "COALESCE(SUM(rb.minutes), 0) AS total_minutes, "
                    "COUNT(rb.id) AS block_count "
                    "FROM routine r "
                    "LEFT JOIN routine_block rb ON rb.routine_id = r.id "
                    "GROUP BY r.id "
                    "ORDER BY r.updated_at DESC"
                )
            ).fetchall()
        finally:
            db.close()
    routines = [
        {
            "id": row.id,
            "name": row.name,
            "total_minutes": row.total_minutes,
            "block_count": row.block_count,
        }
        for row in rows
    ]
    return HTMLResponse(
        env.get_template("routines_list.html").render(
            active="routines",
            routines=routines,
            theme=get_theme(request.app),
        )
    )


@router.get("/routines/new", response_model=None)
async def get_new_routine(
    request: Request,
) -> HTMLResponse:
    return HTMLResponse(
        env.get_template("routines_new.html").render(
            active="routines",
            routine=None,
            errors=None,
            theme=get_theme(request.app),
        )
    )


@router.post("/routines/new", response_model=None)
async def post_new_routine(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:
    form = await request.form()
    raw_name = form.get("name")
    name = raw_name.strip() if isinstance(raw_name, str) else ""
    if not name:
        return HTMLResponse(
            env.get_template("routines_new.html").render(
                active="routines",
                routine=None,
                errors={"name": "Name is required."},
                theme=get_theme(request.app),
            ),
            status_code=422,
        )
    routine = Routine(name=name)
    db.add(routine)
    db.commit()
    return RedirectResponse(url=f"/routines/{routine.id}/edit", status_code=303)


@router.get("/routines/{routine_id}/edit", response_model=None)
def get_routine_edit(
    routine_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    items = db.execute(select(Item.id, Item.title).order_by(Item.title)).all()
    return HTMLResponse(
        env.get_template("routines_edit.html").render(
            active="routines",
            items=[(i.id, i.title) for i in items],
            theme=get_theme(request.app),
            **_blocks_context(routine, db),
        )
    )


@router.get("/routines/{routine_id}/delete", response_model=None)
def get_delete_routine(
    routine_id: int,
    request: Request,
) -> HTMLResponse | RedirectResponse:
    with request.app.state.sessionmaker() as db:
        try:
            routine = db.get(Routine, routine_id)
        finally:
            db.close()
    if routine is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Routine not found")
    return HTMLResponse(
        env.get_template("routines_delete.html").render(
            active="routines",
            routine=routine,
            theme=get_theme(request.app),
        )
    )


@router.post("/routines/{routine_id}/delete", response_model=None)
def post_delete_routine(
    routine_id: int,
    request: Request,
) -> RedirectResponse:
    with request.app.state.sessionmaker() as db:
        try:
            routine = db.get(Routine, routine_id)
            if routine is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Routine not found")
            db.delete(routine)
            db.commit()
        finally:
            db.close()
    return RedirectResponse(url="/routines", status_code=303)


MAX_BLOCKS = 30


def _blocks_context(routine: Routine, db: Session) -> dict[str, Any]:
    """What `partials/routine_blocks.html` needs."""
    blocks = (
        db.execute(
            text(
                "SELECT rb.id, rb.position, rb.minutes, rb.bpm, i.title, i.kind "
                "FROM routine_block rb "
                "JOIN item i ON i.id = rb.item_id "
                "WHERE rb.routine_id = :rid "
                "ORDER BY rb.position"
            ),
            {"rid": routine.id},
        )
        .mappings()
        .fetchall()
    )
    return {
        "routine": routine,
        "base": f"/routines/{routine.id}",
        "blocks": list(blocks),
        "total_minutes": sum(b["minutes"] for b in blocks),
    }


def _render_block_list(routine: Routine, db: Session) -> str:
    """Render the block list fragment for a routine."""
    return env.get_template("partials/routine_blocks.html").render(**_blocks_context(routine, db))


def _int_or_none(raw: object) -> int | None:
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    try:
        return int(str(raw))
    except ValueError:
        raise HTTPException(status_code=422, detail="Not a whole number") from None


@router.post("/routines/{routine_id}/blocks", response_model=None)
async def post_add_block(
    routine_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Add a block at the end (SPEC 4.1, 4.2). Returns the block list fragment."""
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    form = await request.form()
    item_id = _int_or_none(form.get("item_id"))
    minutes = _int_or_none(form.get("minutes"))
    bpm = _int_or_none(form.get("bpm"))
    if item_id is None or db.get(Item, item_id) is None:
        raise HTTPException(status_code=422, detail="Choose a song or exercise")
    if minutes is None or not 1 <= minutes <= 120:
        raise HTTPException(status_code=422, detail="Minutes must be 1–120")
    if bpm is not None and not 20 <= bpm <= 400:
        raise HTTPException(status_code=422, detail="BPM must be 20–400")
    count = db.scalar(
        select(func.count()).select_from(RoutineBlock).where(RoutineBlock.routine_id == routine_id)
    )
    if (count or 0) >= MAX_BLOCKS:
        raise HTTPException(status_code=422, detail=f"A routine has at most {MAX_BLOCKS} blocks")
    db.add(
        RoutineBlock(
            routine_id=routine_id, position=count or 0, item_id=item_id, minutes=minutes, bpm=bpm
        )
    )
    db.commit()
    return HTMLResponse(_render_block_list(routine, db))


@router.post("/routines/{routine_id}/blocks/{block_id}/remove", response_model=None)
def post_remove_block(
    routine_id: int,
    block_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Remove a block; later blocks move up so positions stay 0..n-1."""
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    block = db.scalar(
        select(RoutineBlock).where(
            RoutineBlock.id == block_id, RoutineBlock.routine_id == routine_id
        )
    )
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found in routine")
    removed_at = block.position
    db.delete(block)
    db.flush()
    later = db.scalars(
        select(RoutineBlock)
        .where(RoutineBlock.routine_id == routine_id, RoutineBlock.position > removed_at)
        .order_by(RoutineBlock.position)
    ).all()
    for b in later:  # ascending, so each target position is already free
        b.position -= 1
        db.flush()
    db.commit()
    return HTMLResponse(_render_block_list(routine, db))


@router.post("/routines/{routine_id}/blocks/{block_id}/move", response_model=None)
def post_move_block(
    routine_id: int,
    block_id: int,
    request: Request,
    direction: str = Query(..., pattern="^(up|down)$"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Move a block up or down within a routine (SPEC 4.2).

    Swaps positions with the adjacent block. Moving the first block up or
    the last block down is a no-op.  The unique (routine_id, position)
    constraint is preserved by swapping in two steps.
    """
    # Find the routine
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")

    # Find the block to move
    row = (
        db.execute(
            text("SELECT id, position FROM routine_block WHERE id = :bid AND routine_id = :rid"),
            {"bid": block_id, "rid": routine_id},
        )
        .mappings()
        .first()
    )

    if row is None:
        raise HTTPException(status_code=404, detail="Block not found in routine")

    current_position = row["position"]

    # Determine target position
    target_position = current_position - 1 if direction == "up" else current_position + 1

    # Check if there's an adjacent block to swap with
    adjacent = (
        db.execute(
            text("SELECT id FROM routine_block WHERE routine_id = :rid AND position = :pos"),
            {"rid": routine_id, "pos": target_position},
        )
        .mappings()
        .first()
    )

    if adjacent is None:
        # No adjacent block: first up or last down — no-op
        fragment = _render_block_list(routine, db)
        return HTMLResponse(fragment)

    # Swap positions (two-step to preserve unique constraint)
    # Step 1: move current block to a temp position
    temp_position = -1
    db.execute(
        text("UPDATE routine_block SET position = :tp WHERE id = :bid AND routine_id = :rid"),
        {"tp": temp_position, "bid": block_id, "rid": routine_id},
    )
    db.commit()

    # Step 2: move adjacent block to current position
    db.execute(
        text("UPDATE routine_block SET position = :cp WHERE id = :aid AND routine_id = :rid"),
        {"cp": current_position, "aid": adjacent["id"], "rid": routine_id},
    )
    db.commit()

    # Step 3: move current block to adjacent position
    db.execute(
        text("UPDATE routine_block SET position = :ap WHERE id = :bid AND routine_id = :rid"),
        {"ap": target_position, "bid": block_id, "rid": routine_id},
    )
    db.commit()

    fragment = _render_block_list(routine, db)
    return HTMLResponse(fragment)
