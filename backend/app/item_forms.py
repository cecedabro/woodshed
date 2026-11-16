"""Item create/edit forms (SPEC 3.3).

Routes: GET/POST /items/new, GET/POST /items/{item_id}/edit.
"""

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.items_service import ItemIn, create_item, get_item, update_item
from app.templating import env, get_theme

# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

_KIND_OPTIONS = [("song", "Song"), ("exercise", "Exercise")]
_STATUS_OPTIONS = [
    ("learning", "Learning"),
    ("polishing", "Polishing"),
    ("repertoire", "Repertoire"),
]


def _render_form(
    request: Request,
    item_in: ItemIn | None,
    errors: dict[str, str] | None = None,
    *,
    edit_id: int | None = None,
) -> HTMLResponse:
    """Render the new/edit form with optional pre-filled data and field errors."""
    errors = errors or {}
    template = (
        env.get_template("items_new.html")
        if edit_id is None
        else env.get_template("items_edit.html")
    )
    context: dict[str, object] = {
        "active": "library",
        "kind_options": _KIND_OPTIONS,
        "status_options": _STATUS_OPTIONS,
        "item": item_in,
        "errors": errors,
        "mbid": "",
        "rgid": "",
        "back_url": f"/items/{edit_id}" if edit_id is not None else "/library",
        "theme": get_theme(request.app),
    }
    if edit_id is not None:
        context["edit_id"] = edit_id
    return HTMLResponse(template.render(context), status_code=422)


def _item_to_form_data(db_item) -> ItemIn:  # type: ignore[no-untyped-def]
    """Convert a persisted Item row to ItemIn for the edit form."""
    return ItemIn(
        kind=db_item.kind,
        title=db_item.title,
        artist=db_item.artist,
        status=db_item.status,
        current_bpm=db_item.current_bpm,
        original_url=db_item.original_url,
        notes=db_item.notes or None,
    )


def _format_errors(exc: ValidationError) -> dict[str, str]:
    """Convert a Pydantic ValidationError to {field: message}."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err["loc"][0] if err["loc"] else "form"
        field = str(loc)
        errors[field] = str(err["msg"])
    return errors


async def _extract_and_validate(
    request: Request,
) -> tuple[ItemIn, None] | tuple[None, dict[str, str]]:
    """Extract form data and validate with ItemIn.

    Returns ``(ItemIn, None)`` on success or ``(None, dict[str, str])`` on failure.
    """
    form = await request.form()
    raw: dict[str, str | int] = {}
    for key, value in form.items():
        if key == "current_bpm" and value:
            try:
                raw[key] = int(str(value))
            except (ValueError, TypeError):
                raw[key] = int(value)  # type: ignore[arg-type]
        elif value:
            raw[key] = str(value)
    try:
        item_in = ItemIn.model_validate(raw)
        return (item_in, None)
    except ValidationError as exc:
        return (None, _format_errors(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


async def get_new_item(request: Request) -> HTMLResponse:
    """GET /items/new -- show new item form."""
    return HTMLResponse(
        env.get_template("items_new.html").render(
            active="library",
            kind_options=_KIND_OPTIONS,
            status_options=_STATUS_OPTIONS,
            item=None,
            errors=None,
            q="",
            mbid="",
            rgid="",
            back_url="/library",
            theme=get_theme(request.app),
        )
    )


async def post_new_item(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:
    """POST /items/new -- create item."""
    data, fmt_errors = await _extract_and_validate(request)
    if fmt_errors:
        return _render_form(request, None, fmt_errors)

    assert data is not None
    item = create_item(db, data)
    db.commit()
    return RedirectResponse(url=f"/items/{item.id}", status_code=303)


async def get_edit_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """GET /items/{id}/edit -- show edit form."""
    item = get_item(db, item_id)
    if item is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not Found")
    return HTMLResponse(
        env.get_template("items_edit.html").render(
            active="library",
            kind_options=_KIND_OPTIONS,
            status_options=_STATUS_OPTIONS,
            item=_item_to_form_data(item),
            errors=None,
            edit_id=item_id,
            mbid="",
            rgid="",
            back_url=f"/items/{item_id}",
            theme=get_theme(request.app),
        )
    )


async def post_edit_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:
    """POST /items/{id}/edit -- update item."""
    item = get_item(db, item_id)
    if item is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not Found")

    data, fmt_errors = await _extract_and_validate(request)
    if fmt_errors:
        return _render_form(request, _item_to_form_data(item), fmt_errors, edit_id=item_id)

    assert data is not None
    updated = update_item(db, item_id, data)
    db.commit()
    return RedirectResponse(url=f"/items/{updated.id}", status_code=303)
