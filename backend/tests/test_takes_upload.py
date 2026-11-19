"""Tests for take upload (SPEC 8.2).

Tests cover:
- Upload valid takes (webm, mp4, ogg) and verify DB row + file on disk
- 413 for file exceeding MAX_TAKE_BYTES
- 415 for unsupported/corrupt magic bytes
- 415 for wrong sniffed extension vs actual upload extension
- 422 for duration_seconds < 1 and > 600
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item, Take

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


# Magic-byte payloads matching what sniff_audio expects
_WEBM = b"\x1a\x45\xdf\xa3" + b"padding_webm"
_MP4 = b"\x00\x00\x00\x18ftyp" + b"padding_mp4"
_OGG = b"OggS" + b"padding_ogg"
_GARBAGE = b"\x00\x00\x00\x00\x00\x00\x00\x00"


# ---------------------------------------------------------------------------
# Upload — success (201)
# ---------------------------------------------------------------------------


class TestUploadTakeSuccess:
    """Valid takes should return 201 and store DB row + file."""

    def test_upload_webm(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("riff_duet.webm", _WEBM, "audio/webm")},
            data={"duration_seconds": 45, "bpm": 96},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["item_id"] == item.id
        assert body["content_type"] == "audio/webm"
        assert body["size_bytes"] == len(_WEBM)
        assert body["duration_seconds"] == 45
        assert body["bpm"] == 96
        assert body["id"] is not None

        take = db.scalar(select(Take).where(Take.id == body["id"]))
        assert take is not None
        assert take.duration_seconds == 45
        assert take.bpm == 96
        assert take.content_type == "audio/webm"
        assert (settings.MEDIA_DIR / "takes" / take.stored_name).exists()

    def test_upload_mp4(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("solo_backing.mp4", _MP4, "audio/mp4")},
            data={"duration_seconds": 120},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["content_type"] == "audio/mp4"
        assert body["duration_seconds"] == 120

        take = db.scalar(select(Take).where(Take.id == body["id"]))
        assert take is not None
        assert (settings.MEDIA_DIR / "takes" / take.stored_name).exists()

    def test_upload_ogg(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("blues_progression.ogg", _OGG, "audio/ogg")},
            data={"duration_seconds": 300},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["content_type"] == "audio/ogg"
        assert body["duration_seconds"] == 300

        take = db.scalar(select(Take).where(Take.id == body["id"]))
        assert take is not None
        assert (settings.MEDIA_DIR / "takes" / take.stored_name).exists()


# ---------------------------------------------------------------------------
# Too-large files (413)
# ---------------------------------------------------------------------------


class TestUploadTakeTooLarge:
    """Files exceeding MAX_TAKE_BYTES must return 413."""

    def test_exceeds_max_take_bytes_413(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        # Use a file larger than MAX_TAKE_BYTES (25 MB)
        large_content = b"x" * (settings.MAX_TAKE_BYTES + 1024 * 1024)

        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("huge_take.webm", large_content, "audio/webm")},
            data={"duration_seconds": 60},
        )
        assert resp.status_code == 413

        count = db.scalar(select(Take))
        assert count is None


# ---------------------------------------------------------------------------
# Unrecognized magic bytes (415)
# ---------------------------------------------------------------------------


class TestUploadTakeBadBytes:
    """Files with garbage magic bytes must return 415."""

    def test_garbage_bytes_415(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("junk.webm", _GARBAGE, "audio/webm")},
            data={"duration_seconds": 30},
        )
        assert resp.status_code == 415
        assert "Unsupported" in resp.json()["detail"]

    def test_empty_file_bytes_415(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("empty.webm", b"", "audio/webm")},
            data={"duration_seconds": 30},
        )
        assert resp.status_code == 415


# ---------------------------------------------------------------------------
# Wrong sniffed extension vs upload filename extension (415)
# ---------------------------------------------------------------------------


class TestUploadTakeExtensionMismatch:
    """Sniffed format must match the file extension."""

    def test_webm_body_mp4_filename_415(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("riff.mp4", _WEBM, "audio/webm")},
            data={"duration_seconds": 30},
        )
        assert resp.status_code == 415

    def test_mp4_body_ogg_filename_415(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("solo.ogg", _MP4, "audio/mp4")},
            data={"duration_seconds": 30},
        )
        assert resp.status_code == 415


# ---------------------------------------------------------------------------
# Invalid duration_seconds (422)
# ---------------------------------------------------------------------------


class TestUploadTakeDuration:
    """duration_seconds must be 1-600."""

    def test_duration_zero_422(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("bad.webm", _WEBM, "audio/webm")},
            data={"duration_seconds": 0},
        )
        assert resp.status_code == 422

    def test_duration_601_422(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("too_long.webm", _WEBM, "audio/webm")},
            data={"duration_seconds": 601},
        )
        assert resp.status_code == 422

    def test_duration_minus_one_422(self, client: TestClient, db: Session) -> None:
        item = _create_item(db)
        resp = client.post(
            f"/api/items/{item.id}/takes",
            files={"file": ("short.webm", _WEBM, "audio/webm")},
            data={"duration_seconds": -1},
        )
        assert resp.status_code == 422
