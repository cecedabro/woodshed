"""Routines routes (SPEC 4.1, 4.3).

Routes: GET /routines, GET/POST /routines/new, GET /routines/{id}/edit,
        GET/POST /routines/{id}/delete
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_login
from app.db import get_db
from app.models import Routine
from app.templating import env

router = APIRouter()


@router.get("/routines", response_model=None)
def get_routines(
    request: Request,
    login: None = Depends(require_login),
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
        )
    )


@router.get("/routines/new", response_model=None)
async def get_new_routine(
    request: Request,
    login: None = Depends(require_login),
) -> HTMLResponse:
    return HTMLResponse(
        env.get_template("routines_new.html").render(
            active="routines",
            routine=None,
            errors=None,
        )
    )


@router.post("/routines/new", response_model=None)
async def post_new_routine(
    request: Request,
    login: None = Depends(require_login),
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
    login: None = Depends(require_login),
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
        env.get_template("routines_edit.html").render(
            active="routines",
            routine=routine,
        )
    )


@router.get("/routines/{routine_id}/delete", response_model=None)
def get_delete_routine(
    routine_id: int,
    request: Request,
    login: None = Depends(require_login),
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
        )
    )


@router.post("/routines/{routine_id}/delete", response_model=None)
def post_delete_routine(
    routine_id: int,
    request: Request,
    login: None = Depends(require_login),
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
