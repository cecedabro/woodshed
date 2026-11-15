"""Tests for routine, routine_block, practice_session, session_block and take models.

SPEC 4.1–4.3, 5.1–5.8, docs/backend.md §model.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Item,
    PracticeSession,
    Routine,
    RoutineBlock,
    SessionBlock,
    Take,
)

# ---------------------------------------------------------------------------
# Routine + RoutineBlock
# ---------------------------------------------------------------------------


def test_create_routine_with_two_blocks_in_order(db: Session) -> None:
    """A routine has an ordered list of blocks (SPEC 4.1, 4.2)."""
    item_a = Item(kind="song", title="Item A")
    item_b = Item(kind="exercise", title="Item B")
    db.add_all([item_a, item_b])
    db.flush()

    routine = Routine(name="Morning warmup")
    db.add(routine)
    db.flush()

    db.add_all(
        [
            RoutineBlock(routine_id=routine.id, position=0, item_id=item_a.id, minutes=5),
            RoutineBlock(routine_id=routine.id, position=1, item_id=item_b.id, minutes=10),
        ]
    )
    db.commit()

    db.refresh(routine)
    assert routine.name == "Morning warmup"
    assert len(routine.blocks) == 2
    assert routine.blocks[0].position == 0
    assert routine.blocks[0].item.title == "Item A"
    assert routine.blocks[1].position == 1
    assert routine.blocks[1].item.title == "Item B"


def test_duplicate_routine_position_fails(db: Session) -> None:
    """Duplicate (routine_id, position) violates the unique constraint."""
    item = Item(kind="song", title="Test")
    db.add(item)
    db.flush()

    routine = Routine(name="Dup test")
    db.add(routine)
    db.flush()

    db.add_all(
        [
            RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=5),
            RoutineBlock(routine_id=routine.id, position=0, item_id=item.id, minutes=10),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()


# ---------------------------------------------------------------------------
# Routine deletion → practice_session.routine_id SET NULL (SPEC 4.3)
# ---------------------------------------------------------------------------


def test_delete_routine_sets_session_routine_id_to_null(db: Session) -> None:
    """Deleting a routine keeps its logged sessions but sets routine_id to NULL (SPEC 4.3)."""
    routine = Routine(name="To delete")
    db.add(routine)
    db.flush()

    session = PracticeSession(
        routine_id=routine.id,
        started_at=routine.created_at,
    )
    db.add(session)
    db.commit()

    session_id = session.id
    assert session.routine_id == routine.id

    db.delete(routine)
    db.commit()

    db.refresh(session)
    assert session.id == session_id
    assert session.routine_id is None


# ---------------------------------------------------------------------------
# Item deletion → takes cascade, session_block.item_id SET NULL, item_title stays
# ---------------------------------------------------------------------------


def test_delete_item_cascades_to_takes(db: Session) -> None:
    """Deleting an item removes its takes (ON DELETE CASCADE)."""
    item = Item(kind="song", title="Cascade item")
    db.add(item)
    db.flush()

    session = PracticeSession()
    db.add(session)
    db.flush()

    block = SessionBlock(
        session_id=session.id,
        item_id=item.id,
        item_title="Cascade item",
        position=0,
        planned_seconds=300,
        played_seconds=250,
    )
    db.add(block)
    db.flush()

    take = Take(
        item_id=item.id,
        session_block_id=block.id,
        stored_name="abc123.webm",
        content_type="audio/webm",
        size_bytes=1024,
        duration_seconds=250,
    )
    db.add(take)
    db.commit()

    take_count = db.execute(
        text("SELECT count(*) FROM take WHERE item_id = :id"), {"id": item.id}
    ).scalar()
    assert take_count == 1

    db.delete(item)
    db.commit()

    take_count = db.execute(
        text("SELECT count(*) FROM take WHERE item_id = :id"), {"id": item.id}
    ).scalar()
    assert take_count == 0


def test_delete_item_sets_session_block_item_id_null_but_keeps_title(db: Session) -> None:
    """Deleting an item clears session_block.item_id but keeps item_title (SPEC 3.7, 5.6)."""
    item = Item(kind="exercise", title="Deleted exercise")
    db.add(item)
    db.flush()

    session = PracticeSession()
    db.add(session)
    db.flush()

    block = SessionBlock(
        session_id=session.id,
        item_id=item.id,
        item_title="Deleted exercise",
        position=0,
        planned_seconds=600,
        played_seconds=500,
        bpm=90,
    )
    db.add(block)
    db.commit()

    block_id = block.id
    assert block.item_id == item.id
    assert block.item_title == "Deleted exercise"

    db.delete(item)
    db.commit()

    db.refresh(block)
    assert block.id == block_id
    assert block.item_id is None
    assert block.item_title == "Deleted exercise"
