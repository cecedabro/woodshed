"""Sessions API (SPEC 5.4–5.6, backend.md §sessions).

Endpoints:
    POST /api/sessions                   — create a session
    POST /api/sessions/{id}/blocks       — log a block
    POST /api/sessions/{id}/finish       — finish a session, return summary
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login
from app.clock import now as clock_now
from app.db import get_db
from app.models import Item, PracticeSession, SessionBlock

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    routine_id: int | None = None


class BlockLog(BaseModel):
    item_id: int | None = None
    item_title: str = Field(default="")
    position: int
    planned_seconds: int
    played_seconds: int
    bpm: int | None = None


class FinishPayload(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Helper: close stale sessions (SPEC 5.7)
# ---------------------------------------------------------------------------


def _close_stale_sessions(db: Session, now: float) -> None:
    """Mark sessions idle for >6 hours as finished at their last block end time."""
    six_hours = 6 * 3600
    stale = (
        db.execute(
            select(PracticeSession).where(
                PracticeSession.ended_at.is_(None),
                PracticeSession.started_at < now - six_hours,
            )
        )
        .scalars()
        .all()
    )
    for session in stale:
        session.ended_at = session.blocks[-1].ended_at if session.blocks else session.started_at


# ---------------------------------------------------------------------------
# POST /api/sessions — create
# ---------------------------------------------------------------------------


@router.post("/api/sessions", status_code=201)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    _login: None = Depends(require_login),
) -> dict[str, Any]:
    """Create a new practice session (SPEC 5.4)."""
    session = PracticeSession(routine_id=payload.routine_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id}


# ---------------------------------------------------------------------------
# POST /api/sessions/{id}/blocks — log a block
# ---------------------------------------------------------------------------


@router.post("/api/sessions/{session_id}/blocks")
def log_block(
    session_id: int,
    payload: BlockLog,
    db: Session = Depends(get_db),
    _login: None = Depends(require_login),
) -> dict[str, Any]:
    """Log a session block with clamping (SPEC 5.4–5.5)."""
    session = db.execute(
        select(PracticeSession)
        .where(PracticeSession.id == session_id)
        .options(selectinload(PracticeSession.blocks))
    ).scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # SPEC 5.5: clamp played_seconds to [0, elapsed_since_start + 60]
    now = clock_now()
    elapsed = (now - session.started_at).total_seconds()
    max_played = elapsed + 60
    clamped = max(0, min(payload.played_seconds, int(max_played)))

    # If < 10 seconds, don't store
    if clamped < 10:
        return {"stored": False}

    block = SessionBlock(
        session_id=session.id,
        item_id=payload.item_id,
        item_title=payload.item_title,
        position=payload.position,
        planned_seconds=payload.planned_seconds,
        played_seconds=clamped,
        bpm=payload.bpm,
        ended_at=now,
    )
    db.add(block)

    # SPEC 5.6: when stored with a BPM, update item.current_bpm
    if payload.bpm is not None and payload.item_id is not None:
        item = db.get(Item, payload.item_id)
        if item is not None:
            item.current_bpm = payload.bpm

    db.commit()

    return {
        "stored": True,
        "id": block.id,
        "played_seconds": clamped,
    }


# ---------------------------------------------------------------------------
# POST /api/sessions/{id}/finish — finish
# ---------------------------------------------------------------------------


@router.post("/api/sessions/{session_id}/finish")
def finish_session(
    session_id: int,
    db: Session = Depends(get_db),
    _login: None = Depends(require_login),
) -> dict[str, Any]:
    """Finish a session and return summary (SPEC 5.4, backend.md §sessions)."""
    session = db.execute(
        select(PracticeSession)
        .where(PracticeSession.id == session_id)
        .options(selectinload(PracticeSession.blocks))
    ).scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.ended_at = clock_now()
    db.commit()

    blocks = session.blocks
    total_seconds = sum(b.played_seconds for b in blocks)
    total_minutes = total_seconds // 60

    per_block = [
        {
            "position": b.position,
            "item_title": b.item_title,
            "planned_seconds": b.planned_seconds,
            "played_seconds": b.played_seconds,
            "bpm": b.bpm,
        }
        for b in blocks
    ]

    return {
        "blocks": len(blocks),
        "minutes": total_minutes,
        "per_block": per_block,
    }
