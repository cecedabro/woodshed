"""Tests for the item attachment upload form rendering (SPEC 3.9).

Verifies that the upload form appears unconditionally on the item detail page,
with the correct action, enctype, and file input, even when the item has no
attachments.
"""

from fastapi.testclient import TestClient
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


# ---------------------------------------------------------------------------
# Upload form rendering
# ---------------------------------------------------------------------------


class TestUploadFormRendering:
    """Attachment upload form rendering tests."""

    def test_upload_form_exists_with_no_attachments(self, client: TestClient, db: Session) -> None:
        """The upload form renders even when the item has zero attachments."""
        item = _create_item(db, title="No Attachments Song")
        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.text
        assert 'action="/items/' in html and '/attachments"' in html
        assert 'enctype="multipart/form-data"' in html
        assert 'name="file"' in html
        assert 'type="file"' in html

    def test_upload_form_exists_with_one_attachment(self, client: TestClient, db: Session) -> None:
        """The upload form renders when the item has one attachment."""
        item = _create_item(db, title="One Attachment Song")
        att = Attachment(
            item_id=item.id,
            filename="test.gp",
            stored_name="abc123.gp",
            kind="tab",
            label="My solo",
            content_type="text/plain",
            size_bytes=100,
        )
        db.add(att)
        db.commit()

        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.text
        assert 'action="/items/' in html and '/attachments"' in html
        assert 'enctype="multipart/form-data"' in html
        assert 'name="file"' in html
        assert 'type="file"' in html

    def test_upload_form_has_correct_action(self, client: TestClient, db: Session) -> None:
        """The form action points to the correct POST route."""
        item = _create_item(db, title="Action Test Song")
        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        assert f'action="/items/{item.id}/attachments"' in resp.text

    def test_upload_form_has_correct_enctype(self, client: TestClient, db: Session) -> None:
        """The form enctype is multipart/form-data."""
        item = _create_item(db, title="Enctype Test Song")
        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        assert 'enctype="multipart/form-data"' in resp.text

    def test_upload_form_has_file_input(self, client: TestClient, db: Session) -> None:
        """The form contains an <input type="file" name="file">."""
        item = _create_item(db, title="File Input Test Song")
        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        assert 'type="file"' in resp.text
        assert 'name="file"' in resp.text

    def test_upload_form_count_with_one_attachment(self, client: TestClient, db: Session) -> None:
        """The upload form appears exactly once when the item has one attachment."""
        item = _create_item(db, title="Count Test Song")
        att = Attachment(
            item_id=item.id,
            filename="test.gp",
            stored_name="xyz789.gp",
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=50,
        )
        db.add(att)
        db.commit()

        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.text
        # Count how many times the upload form action appears
        form_action = f'/items/{item.id}/attachments"'
        count = html.count(form_action)
        # Should appear exactly once (the upload form)
        # Note: attachment deletion forms use a different action path pattern
        # e.g. /items/{id}/attachments/{att.id}/_delete
        assert count == 1, (
            f"Expected exactly 1 upload form action, found {count}. "
            f"Form may be duplicated or missing."
        )

    def test_upload_form_with_no_attachments_count(self, client: TestClient, db: Session) -> None:
        """The upload form appears exactly once when the item has no attachments."""
        item = _create_item(db, title="Empty Count Test Song")
        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.text
        form_action = f'/items/{item.id}/attachments"'
        count = html.count(form_action)
        assert count == 1, (
            f"Expected exactly 1 upload form action, found {count}. "
            f"Form may be duplicated or missing."
        )

    def test_upload_form_rendered_with_audio_attachment(
        self, client: TestClient, db: Session
    ) -> None:
        """The upload form renders when item has an audio attachment."""
        item = _create_item(db, title="Audio Attachment Song")
        att = Attachment(
            item_id=item.id,
            filename="backing_track.mp3",
            stored_name="track001.mp3",
            kind="audio",
            label="Slow version",
            content_type="audio/mpeg",
            size_bytes=4096,
        )
        db.add(att)
        db.commit()

        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.text
        assert f'action="/items/{item.id}/attachments"' in html
        assert 'enctype="multipart/form-data"' in html

    def test_upload_form_rendered_with_pdf_attachment(
        self, client: TestClient, db: Session
    ) -> None:
        """The upload form renders when item has a PDF attachment."""
        item = _create_item(db, title="PDF Attachment Song")
        att = Attachment(
            item_id=item.id,
            filename="chord_chart.pdf",
            stored_name="chart001.pdf",
            kind="pdf",
            label="",
            content_type="application/pdf",
            size_bytes=256,
        )
        db.add(att)
        db.commit()

        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.text
        assert f'action="/items/{item.id}/attachments"' in html
