"""JSON API for items (SPEC 3.8)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings
from app.covers import fetch_cover, save_cover
from app.db import get_db
from app.items_service import ItemIn, create_item, get_item

router = APIRouter()


def _try_fetch_cover(payload: ItemIn, settings: Settings) -> None:
    """Attempt to fetch cover art in the background; never raise."""
    if not payload.release_group_id:
        return
    data = fetch_cover(payload.release_group_id, settings.MB_USER_AGENT)
    if data is None:
        return
    # We need the item id, but we haven't committed yet.
    # The item will get an id after commit below; cover fetch happens post-commit in caller.


@router.post("/api/items", status_code=201)
def create_item_route(
    payload: ItemIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(lambda: Settings()),
) -> dict[str, Any]:
    """Create a new item and return it as JSON with its id (SPEC 3.8)."""
    item = create_item(db, payload)
    db.commit()

    # Trigger cover fetch after commit so item.id is available.
    if payload.release_group_id:
        try:
            data = fetch_cover(payload.release_group_id, settings.MB_USER_AGENT)
            if data is not None:
                saved = save_cover(item.id, data, settings.MEDIA_DIR)
                if saved:
                    item.has_cover = True
                    db.commit()
        except Exception:
            pass  # Never roll back item creation (SPEC 14.4)

    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "artist": item.artist,
        "status": item.status,
        "current_bpm": item.current_bpm,
        "year": item.year,
        "mbid": item.mbid,
        "release_group_id": item.release_group_id,
        "has_cover": item.has_cover,
        "original_url": item.original_url,
        "notes": item.notes,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


@router.get("/api/items/{item_id}")
def get_item_route(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the item as JSON, or 404 if not found (SPEC 3.8)."""
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "artist": item.artist,
        "status": item.status,
        "current_bpm": item.current_bpm,
        "year": item.year,
        "mbid": item.mbid,
        "release_group_id": item.release_group_id,
        "has_cover": item.has_cover,
        "original_url": item.original_url,
        "notes": item.notes,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
