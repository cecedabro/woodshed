"""JSON API for items (SPEC 3.8)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.items_service import ItemIn, create_item, get_item

router = APIRouter()


@router.post("/api/items", status_code=201)
def create_item_route(
    payload: ItemIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new item and return it as JSON with its id (SPEC 3.8)."""
    item = create_item(db, payload)
    db.commit()
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "artist": item.artist,
        "status": item.status,
        "current_bpm": item.current_bpm,
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
        "original_url": item.original_url,
        "notes": item.notes,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
