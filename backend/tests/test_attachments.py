"""Tests for attachment upload, listing, download, and deletion (SPEC 3.9, 3.10).

Tests cover:
- Upload valid attachments (tab, pdf, audio) and verify DB row + file on disk
- Upload with optional label
- Delete attachments (DB row + file removed)
- 422 for unsupported file extension
- 413 for file exceeding MAX_ATTACHMENT_BYTES
- 404 for non-existent item / attachment
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment, Item

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_item(db: Session, **kwargs) -> Item:
    """Create and commit an item for testing."""
    item = Item(
        kind=kwargs.get("kind", "song"),
        title=kwargs.get("title", "Test Song"),
        status=kwargs.get("status", "learning"),
        notes="",
        **{k: v for k, v in kwargs.items() if k not in ("kind", "title", "status")},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _make_file_content(size: int = 1024) -> bytes:
    """Return dummy file content of *size* bytes."""
    return b"x" * size


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class TestUploadAttachment:
    """Attachment upload tests."""

    def test_upload_tab(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        content = _make_file_content(512)

        resp = client.post(
            f"/items/{item.id}/attachments",
            files={"file": ("solo.gp", content, "text/plain")},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        att = db.scalar(select(Attachment).where(Attachment.item_id == item.id))
        assert att is not None
        assert att.kind == "tab"
        assert att.filename == "solo.gp"
        assert att.label == ""
        assert att.size_bytes == 512
        assert (settings.MEDIA_DIR / "attachments" / att.stored_name).exists()

    def test_upload_pdf(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        content = _make_file_content(256)

        resp = client.post(
            f"/items/{item.id}/attachments",
            files={"file": ("chord_chart.pdf", content, "application/pdf")},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        att = db.scalar(
            select(Attachment).where(Attachment.item_id == item.id, Attachment.kind == "pdf")
        )
        assert att is not None
        assert att.size_bytes == 256

    def test_upload_audio(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        content = _make_file_content(4096)

        resp = client.post(
            f"/items/{item.id}/attachments",
            files={"file": ("backing_track.mp3", content, "audio/mpeg")},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        att = db.scalar(
            select(Attachment).where(Attachment.item_id == item.id, Attachment.kind == "audio")
        )
        assert att is not None
        assert att.size_bytes == 4096

    def test_upload_with_label(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        content = _make_file_content(128)

        resp = client.post(
            f"/items/{item.id}/attachments",
            files={"file": ("backing_track.flac", content, "audio/flac")},
            data={"label": "Slow version"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        att = db.scalar(select(Attachment).where(Attachment.item_id == item.id))
        assert att is not None
        assert att.label == "Slow version"

    def test_upload_unknown_extension_422(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        content = _make_file_content(64)

        resp = client.post(
            f"/items/{item.id}/attachments",
            files={"file": ("data.xyz", content, "text/plain")},
            follow_redirects=False,
        )
        assert resp.status_code == 422

        att = db.scalar(select(Attachment).where(Attachment.item_id == item.id))
        assert att is None

    def test_upload_to_nonexistent_item_404(self, client: TestClient, settings) -> None:
        content = _make_file_content(64)
        resp = client.post(
            "/items/99999/attachments",
            files={"file": ("test.gp", content, "text/plain")},
            follow_redirects=False,
        )
        assert resp.status_code == 404

    def test_upload_large_file_413(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        # Use a file larger than MAX_ATTACHMENT_BYTES from settings
        # The default is 100 MB, so use 101 MB
        large_content = _make_file_content(settings.MAX_ATTACHMENT_BYTES + (1024 * 1024))

        resp = client.post(
            f"/items/{item.id}/attachments",
            files={"file": ("big.pdf", large_content, "application/pdf")},
            follow_redirects=False,
        )
        assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteAttachment:
    """Attachment deletion tests."""

    def test_delete_removes_db_and_disk(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        att = Attachment(
            item_id=item.id,
            filename="test.gp",
            stored_name="abc123.gp",
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=100,
        )
        db.add(att)
        db.commit()

        # Create the file on disk
        (settings.MEDIA_DIR / "attachments").mkdir(parents=True, exist_ok=True)
        file_path = settings.MEDIA_DIR / "attachments" / "abc123.gp"
        file_path.write_bytes(b"tab data")
        assert file_path.exists()

        resp = client.post(f"/items/{item.id}/attachments/{att.id}/_delete", follow_redirects=False)
        assert resp.status_code == 303

        assert db.scalar(select(Attachment).where(Attachment.id == att.id)) is None
        assert not file_path.exists()

    def test_delete_nonexistent_attachment_404(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(f"/items/{item.id}/attachments/99999/_delete", follow_redirects=False)
        assert resp.status_code == 404

    def test_delete_wrong_item_attachment_404(
        self, client: TestClient, db: Session, settings
    ) -> None:
        item1 = _create_item(db, title="Item 1")
        item2 = _create_item(db, title="Item 2")
        att = Attachment(
            item_id=item1.id,
            filename="test.gp",
            stored_name="def456.gp",
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=100,
        )
        db.add(att)
        db.commit()

        (settings.MEDIA_DIR / "attachments").mkdir(parents=True, exist_ok=True)
        (settings.MEDIA_DIR / "attachments" / "def456.gp").write_bytes(b"tab data")

        resp = client.post(
            f"/items/{item2.id}/attachments/{att.id}/_delete", follow_redirects=False
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_item_404(self, client: TestClient) -> None:
        resp = client.post("/items/99999/attachments/1/_delete", follow_redirects=False)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class TestDownloadAttachment:
    """Attachment download tests."""
