"""Tests for DELETE item feature (SPEC 3.7).

Routes: GET /items/{id}/delete, POST /items/{id}/delete.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment, Item, Take


def _html(client: TestClient, path: str) -> str:
    """Fetch a page and return the raw HTML."""
    resp = client.get(path)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
    return resp.text


# ---------------------------------------------------------------------------
# GET /items/{id}/delete — confirmation page
# ---------------------------------------------------------------------------


def test_get_delete_returns_200(client: TestClient, db: Session) -> None:
    """SPEC 3.7: GET /items/{id}/delete returns 200."""
    item = Item(kind="song", title="Cross Road Blues")
    db.add(item)
    db.commit()
    resp = client.get(f"/items/{item.id}/delete")
    assert resp.status_code == 200


def test_delete_page_shows_item_title(client: TestClient, db: Session) -> None:
    """SPEC 3.7: Confirmation page displays the item title."""
    item = Item(kind="song", title="Stormy Monday")
    db.add(item)
    db.commit()
    html = _html(client, f"/items/{item.id}/delete")
    assert "Stormy Monday" in html
    assert "Are you sure you want to delete" in html


def test_delete_page_shows_no_attachments(client: TestClient, db: Session) -> None:
    """SPEC 3.7: No attachment/li if zero attachments."""
    item = Item(kind="exercise", title="Blues Scale")
    db.add(item)
    db.commit()
    html = _html(client, f"/items/{item.id}/delete")
    assert "attachment" not in html.lower()


def test_delete_page_shows_attachment_count(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """SPEC 3.7: Confirmation page lists attachment count."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "attachments").mkdir()
    att_path = media_dir / "attachments" / "test.gp"
    att_path.write_bytes(b"tab")
    item = Item(kind="song", title="Pride and Joy")
    db.add(item)
    db.commit()
    db.refresh(item)
    att = Attachment(
        item_id=item.id,
        kind="tab",
        label="Main tab",
        filename="test.gp",
        stored_name="test.gp",
        content_type="application/octet-stream",
        size_bytes=5,
    )
    db.add(att)
    db.commit()
    html = _html(client, f"/items/{item.id}/delete")
    assert "1 attachment" in html


def test_delete_page_shows_take_count(client: TestClient, db: Session, tmp_path: Path) -> None:
    """SPEC 3.7: Confirmation page lists take count."""
    item = Item(kind="song", title="Mannish Boy")
    db.add(item)
    db.commit()
    db.refresh(item)
    take = Take(
        item_id=item.id,
        stored_name="take1.wav",
        content_type="audio/wav",
        size_bytes=100,
        duration_seconds=30,
    )
    db.add(take)
    db.commit()
    html = _html(client, f"/items/{item.id}/delete")
    assert "1 recording" in html


def test_delete_page_shows_both_counts(client: TestClient, db: Session) -> None:
    """SPEC 3.7: Page shows both attachment and take counts."""
    item = Item(kind="song", title="House of the Rising Sun")
    db.add(item)
    db.commit()
    db.refresh(item)
    att = Attachment(
        item_id=item.id,
        kind="tab",
        label="Tab",
        filename="tab.gp",
        stored_name="tab.gp",
        content_type="application/octet-stream",
        size_bytes=5,
    )
    db.add(att)
    take = Take(
        item_id=item.id,
        stored_name="take1.mp3",
        content_type="audio/mpeg",
        size_bytes=500,
        duration_seconds=60,
    )
    db.add(take)
    db.commit()
    html = _html(client, f"/items/{item.id}/delete")
    assert "1 attachment" in html
    assert "1 recording" in html


def test_delete_page_not_found(client: TestClient) -> None:
    """SPEC 3.7: Non-existent item returns 404."""
    resp = client.get("/items/99999/delete")
    assert resp.status_code == 404


def test_delete_page_has_cancel_button(client: TestClient, db: Session) -> None:
    """SPEC 3.7: Confirmation page has a cancel link back to the detail page."""
    item = Item(kind="song", title="Cross Road Blues")
    db.add(item)
    db.commit()
    html = _html(client, f"/items/{item.id}/delete")
    assert f'href="/items/{item.id}"' in html


def test_delete_page_has_delete_form(client: TestClient, db: Session) -> None:
    """SPEC 3.7: Confirmation page has a POST form to delete."""
    item = Item(kind="song", title="Cross Road Blues")
    db.add(item)
    db.commit()
    html = _html(client, f"/items/{item.id}/delete")
    assert f'action="/items/{item.id}/delete"' in html


# ---------------------------------------------------------------------------
# POST /items/{id}/delete — actual deletion
# ---------------------------------------------------------------------------


def test_post_delete_removes_item(client: TestClient, db: Session) -> None:
    """SPEC 3.7: POST /items/{id}/delete removes the item from the DB."""
    item = Item(kind="song", title="Sweet Little sixteen")
    db.add(item)
    db.commit()
    item_id = item.id
    client.post(f"/items/{item_id}/delete", follow_redirects=False)
    result = db.scalar(select(Item).where(Item.id == item_id))
    assert result is None


def test_post_delete_redirects_to_library(client: TestClient, db: Session) -> None:
    """SPEC 3.7: Deletion redirects to /library."""
    item = Item(kind="song", title="Rock Island Line")
    db.add(item)
    db.commit()
    resp = client.post(f"/items/{item.id}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/library"


def test_post_delete_unknown_item(client: TestClient) -> None:
    """SPEC 3.7: Deleting a non-existent item returns 404."""
    resp = client.post("/items/99999/delete", follow_redirects=False)
    assert resp.status_code == 404


def test_post_delete_removes_attachment_file(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """SPEC 3.7: Deleting item removes attachment files from disk."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "attachments").mkdir()
    stored = "attached.gp"
    (media_dir / "attachments" / stored).write_bytes(b"tab data")
    item = Item(kind="song", title="Red House")
    db.add(item)
    db.commit()
    db.refresh(item)
    att = Attachment(
        item_id=item.id,
        kind="tab",
        label="Main",
        filename=stored,
        stored_name=stored,
        content_type="application/octet-stream",
        size_bytes=10,
    )
    db.add(att)
    db.commit()
    item_id = item.id
    client.post(f"/items/{item_id}/delete", follow_redirects=False)
    assert not (media_dir / "attachments" / stored).exists()


def test_post_delete_removes_take_file(client: TestClient, db: Session, tmp_path: Path) -> None:
    """SPEC 3.7: Deleting item removes take files from disk."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "takes").mkdir()
    stored = "recording.wav"
    (media_dir / "takes" / stored).write_bytes(b"audio data")
    item = Item(kind="song", title="Bummed")
    db.add(item)
    db.commit()
    db.refresh(item)
    take = Take(
        item_id=item.id,
        stored_name=stored,
        content_type="audio/wav",
        size_bytes=100,
        duration_seconds=240,
    )
    db.add(take)
    db.commit()
    item_id = item.id
    client.post(f"/items/{item_id}/delete", follow_redirects=False)
    assert not (media_dir / "takes" / stored).exists()


def test_post_delete_removes_all_files(client: TestClient, db: Session, tmp_path: Path) -> None:
    """SPEC 3.7: Deleting item with both attachments and takes removes all files."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "attachments").mkdir()
    (media_dir / "takes").mkdir()
    (media_dir / "attachments" / "a.gp").write_bytes(b"a")
    (media_dir / "attachments" / "b.pdf").write_bytes(b"b")
    (media_dir / "takes" / "t1.wav").write_bytes(b"t1")
    (media_dir / "takes" / "t2.wav").write_bytes(b"t2")
    item = Item(kind="song", title="Wang Dang Doodle")
    db.add(item)
    db.commit()
    db.refresh(item)
    for name in ("a.gp", "b.pdf"):
        db.add(
            Attachment(
                item_id=item.id,
                kind="tab" if name.endswith(".gp") else "pdf",
                label="",
                filename=name,
                stored_name=name,
                content_type="application/octet-stream",
                size_bytes=1,
            )
        )
    for name in ("t1.wav", "t2.wav"):
        db.add(
            Take(
                item_id=item.id,
                stored_name=name,
                content_type="audio/wav",
                size_bytes=5,
                duration_seconds=60,
            )
        )
    db.commit()
    client.post(f"/items/{item.id}/delete", follow_redirects=False)
    assert not (media_dir / "attachments" / "a.gp").exists()
    assert not (media_dir / "attachments" / "b.pdf").exists()
    assert not (media_dir / "takes" / "t1.wav").exists()
    assert not (media_dir / "takes" / "t2.wav").exists()


def test_post_delete_cascades_attachments_and_takes_from_db(
    client: TestClient, db: Session
) -> None:
    """SPEC 3.7: Delete cascades away attachments and takes from DB."""
    item = Item(kind="song", title="I Put a Spell on You")
    db.add(item)
    db.commit()
    db.refresh(item)
    att = Attachment(
        item_id=item.id,
        kind="tab",
        label="",
        filename="x.gp",
        stored_name="x.gp",
        content_type="application/octet-stream",
        size_bytes=5,
    )
    db.add(att)
    take = Take(
        item_id=item.id,
        stored_name="y.wav",
        content_type="audio/wav",
        size_bytes=10,
        duration_seconds=120,
    )
    db.add(take)
    db.commit()
    client.post(f"/items/{item.id}/delete", follow_redirects=False)
    assert db.scalar(select(Attachment)) is None
    assert db.scalar(select(Take)) is None


def test_session_block_keeps_item_title_after_delete(client: TestClient, db: Session) -> None:
    """SPEC 3.7: Logged session blocks retain item_title after item deletion."""
    from app.models import PracticeSession, SessionBlock

    item = Item(kind="song", title="The Thrill Is Gone")
    db.add(item)
    db.commit()
    session = PracticeSession()
    block = SessionBlock(
        session=session,
        item_id=item.id,
        item_title="The Thrill Is Gone",
        position=0,
        planned_seconds=600,
        played_seconds=500,
    )
    db.add(block)
    db.commit()
    item_id = item.id
    client.post(f"/items/{item_id}/delete", follow_redirects=False)
    saved_block = db.scalar(
        select(SessionBlock).where(SessionBlock.item_title == "The Thrill Is Gone")
    )
    assert saved_block is not None
    assert saved_block.item_title == "The Thrill Is Gone"
