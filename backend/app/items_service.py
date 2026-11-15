"""Item service: pydantic models and CRUD functions (SPEC 3.1, 3.8)."""

import re
from datetime import UTC, datetime

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item

# ---------------------------------------------------------------------------
# Pydantic model for input validation (SPEC 3.1)
# ---------------------------------------------------------------------------

_KIND_OPTIONS = {"song", "exercise"}
_STATUS_OPTIONS = {"learning", "polishing", "repertoire"}
_URL_PATTERN = re.compile(r"^https?://")


class ItemIn(BaseModel):
    kind: str
    title: str
    artist: str | None = None
    status: str = "learning"
    current_bpm: int | None = None
    original_url: str | None = None
    notes: str | None = None

    @field_validator("kind")
    @classmethod
    def kind_must_be_valid(cls, v: str) -> str:
        if v not in _KIND_OPTIONS:
            raise ValueError("kind must be 'song' or 'exercise'")
        return v

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title must be 1-200 characters")
        if len(v) > 200:
            raise ValueError("title must be 1-200 characters")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in _STATUS_OPTIONS:
            raise ValueError("status must be 'learning', 'polishing' or 'repertoire'")
        return v

    @field_validator("current_bpm")
    @classmethod
    def bpm_must_be_in_range(cls, v: int | None) -> int | None:
        if v is not None and (v < 20 or v > 400):
            raise ValueError("current_bpm must be between 20 and 400")
        return v

    @field_validator("original_url")
    @classmethod
    def url_must_be_http(cls, v: str | None) -> str | None:
        if v is not None and not _URL_PATTERN.match(v):
            raise ValueError("original_url must start with http:// or https://")
        return v

    @field_validator("notes")
    @classmethod
    def notes_must_not_be_too_long(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 20000:
            raise ValueError("notes must be at most 20 000 characters")
        return v


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


def create_item(db: Session, data: ItemIn) -> Item:
    """Persist *data* as a new :class:`~app.models.Item` and return it."""
    now = datetime.now(UTC)
    item = Item(
        kind=data.kind,
        title=data.title,
        artist=data.artist,
        status=data.status,
        current_bpm=data.current_bpm,
        original_url=data.original_url,
        notes=data.notes or "",
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: int) -> Item | None:
    """Return the item with *item_id*, or ``None``."""
    return db.scalar(select(Item).where(Item.id == item_id))
