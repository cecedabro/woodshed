"""Tests for the item / attachment / setting models and their CHECK constraints.

SPEC 3.1, docs/backend.md §model.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Attachment, Item, Setting


def test_insert_item_with_attachment_and_read_back(db: Session) -> None:
    """Insert an item with an attachment and verify all fields round-trip."""
    item = Item(
        kind="song",
        title="Heartbreaker",
        artist="Peter Green",
        status="repertoire",
        current_bpm=120,
        original_url="https://example.com/heartbreaker",
        notes="E minor blues progression",
    )
    db.add(item)
    db.flush()

    attachment = Attachment(
        item_id=item.id,
        kind="tab",
        label="Original tab",
        filename="heartbreaker.gp5",
        stored_name="a1b2c3d4-gp5",
        content_type="application/octet-stream",
        size_bytes=2048,
    )
    db.add(attachment)
    db.commit()
    db.refresh(item)

    assert item.id is not None
    assert item.kind == "song"
    assert item.title == "Heartbreaker"
    assert item.artist == "Peter Green"
    assert item.status == "repertoire"
    assert item.current_bpm == 120
    assert item.original_url == "https://example.com/heartbreaker"
    assert item.notes == "E minor blues progression"
    assert len(item.attachments) == 1

    attached = item.attachments[0]
    assert attached.kind == "tab"
    assert attached.label == "Original tab"
    assert attached.filename == "heartbreaker.gp5"
    assert attached.stored_name == "a1b2c3d4-gp5"
    assert attached.content_type == "application/octet-stream"
    assert attached.size_bytes == 2048
    assert attached.item_id == item.id


def test_item_default_status(db: Session) -> None:
    """When no status is given the default is 'learning'."""
    item = Item(kind="exercise", title="Daily warm-up")
    db.add(item)
    db.commit()
    db.refresh(item)

    assert item.status == "learning"


def test_item_notes_default_empty(db: Session) -> None:
    """When no notes are given the default is an empty string."""
    item = Item(kind="song", title="Test")
    db.add(item)
    db.commit()
    db.refresh(item)

    assert item.notes == ""


def test_invalid_kind_raises_integrity_error(db: Session) -> None:
    """A kind value outside (song, exercise) violates the CHECK constraint."""
    item = Item(kind="concert", title="Should fail")
    db.add(item)
    with pytest.raises(IntegrityError):
        db.commit()


def test_invalid_status_raises_integrity_error(db: Session) -> None:
    """A status value outside (learning, polishing, repertoire) violates the CHECK constraint."""
    item = Item(kind="song", title="Should fail", status="discarded")
    db.add(item)
    with pytest.raises(IntegrityError):
        db.commit()


def test_delete_item_cascades_to_attachments(db: Session) -> None:
    """Deleting an item removes its attachment rows (ON DELETE CASCADE)."""
    item = Item(kind="song", title="Cascade test")
    db.add(item)
    db.flush()

    for i in range(3):
        db.add(
            Attachment(
                item_id=item.id,
                kind=["tab", "pdf", "audio"][i],
                filename=f"file{i}.gp",
                stored_name=f"stored{i}",
                content_type="text/plain",
                size_bytes=100,
            )
        )
    db.commit()

    # Verify attachments exist before delete
    count = db.execute(
        text("SELECT count(*) FROM attachment WHERE item_id = :id"),
        {"id": item.id},
    ).scalar()
    assert count == 3

    db.delete(item)
    db.commit()

    count = db.execute(
        text("SELECT count(*) FROM attachment WHERE item_id = :id"),
        {"id": item.id},
    ).scalar()
    assert count == 0


def test_setting_key_is_primary_key(db: Session) -> None:
    """Settings use key as the primary key (text column)."""
    s = Setting(key="weekly_goal_minutes", value="120")
    db.add(s)
    db.commit()
    db.refresh(s)

    assert s.key == "weekly_goal_minutes"
    assert s.value == "120"

    # Update by re-inserting with the same key
    s.value = "90"
    db.commit()
    db.refresh(s)
    assert s.value == "90"
