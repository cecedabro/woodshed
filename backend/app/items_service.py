"""Item service: pydantic models and CRUD functions (SPEC 3.1, 3.8)."""

import re
from datetime import UTC, datetime

from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Item

# ---------------------------------------------------------------------------
# Pydantic model for input validation (SPEC 3.1)
# ---------------------------------------------------------------------------

_KIND_OPTIONS = {"song", "exercise"}
_STATUS_OPTIONS = {"learning", "polishing", "repertoire"}
_URL_PATTERN = re.compile(r"^https?://")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ItemIn(BaseModel):
    kind: str
    title: str
    artist: str | None = None
    status: str = "learning"
    current_bpm: int | None = None
    year: int | None = None
    mbid: str | None = None
    release_group_id: str | None = None
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

    @field_validator("year")
    @classmethod
    def year_must_be_valid(cls, v: int | None) -> int | None:
        if v is not None and (v < 1000 or v > 2100):
            raise ValueError("year must be between 1000 and 2100")
        return v

    @field_validator("mbid")
    @classmethod
    def mbid_must_be_uuid(cls, v: str | None) -> str | None:
        if v is not None and not _UUID_PATTERN.match(v):
            raise ValueError("mbid must be a valid UUID")
        return v

    @field_validator("release_group_id")
    @classmethod
    def rgid_must_be_uuid(cls, v: str | None) -> str | None:
        if v is not None and not _UUID_PATTERN.match(v):
            raise ValueError("release_group_id must be a valid UUID")
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
        year=data.year,
        mbid=data.mbid,
        release_group_id=data.release_group_id,
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


def update_item(db: Session, item_id: int, data: ItemIn) -> Item:
    """Update an existing item with fields from *data* and return it."""
    item = db.scalar(select(Item).where(Item.id == item_id))
    if item is None:
        raise ValueError(f"Item {item_id} not found")
    item.kind = data.kind
    item.title = data.title
    item.artist = data.artist
    item.status = data.status
    item.current_bpm = data.current_bpm
    item.year = data.year
    item.mbid = data.mbid
    item.release_group_id = data.release_group_id
    item.original_url = data.original_url
    item.notes = data.notes or ""
    item.updated_at = datetime.now(UTC)
    db.flush()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Library queries (SPEC 3.2)
# ---------------------------------------------------------------------------

_STATUS_ORDER = ("learning", "polishing", "repertoire")


def filter_items(
    db: Session,
    *,
    kind: str | None = None,
    q: str | None = None,
) -> list[Item]:
    """Return items filtered by *kind* and/or case-insensitive *q* title search."""
    stmt = select(Item).order_by(Item.title)
    if kind is not None:
        stmt = stmt.where(Item.kind == kind)
    if q is not None and q.strip():
        stmt = stmt.where(func.lower(Item.title).contains(q.strip().lower()))
    return list(db.scalars(stmt).all())


def group_by_status(items: list[Item]) -> dict[str, list[Item]]:
    """Group *items* by status, preserving the canonical order.

    Returns a dict with keys ``learning``, ``polishing``, ``repertoire``
    (only statuses that have items).
    """
    groups: dict[str, list[Item]] = {}
    for item in items:
        groups.setdefault(item.status, []).append(item)
    return {k: groups[k] for k in _STATUS_ORDER if k in groups}
