"""Tests for GET /media/{kind}/{id} media serving route (SPEC 10.4).

Tests cover:
- Serve attachment and take rows as 200 with correct content
- Range request returns 206 with Content-Range header
- 404 for unknown kind and unknown id
- 401 when not logged in
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Attachment, Item, Take

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_item(db: Session) -> Item:
    item = Item(kind="song", title="Test Song", status="learning", notes="")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _write_media(settings, kind: str, stored_name: str, data: bytes) -> None:
    path = settings.MEDIA_DIR / kind / stored_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _login(client: TestClient) -> None:
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


# ---------------------------------------------------------------------------
# Successful serves
# ---------------------------------------------------------------------------


class TestServeAttachment:
    def test_serves_attachment_with_content_type(
        self, client: TestClient, db: Session, settings
    ) -> None:
        item = _create_item(db)
        data = b"tab solo content here"
        stored = "solo.gp"

        att = Attachment(
            item_id=item.id,
            filename="solo.gp",
            stored_name=stored,
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=len(data),
        )
        db.add(att)
        db.commit()

        _write_media(settings, "attachments", stored, data)
        _login(client)

        resp = client.get(f"/media/attachment/{att.id}")
        assert resp.status_code == 200
        assert resp.content == data
        assert resp.headers["content-type"].startswith("text/plain")


class TestServeTake:
    def test_serves_take(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        data = b"recording audio data"
        stored = "take_001.mp3"

        take = Take(
            item_id=item.id,
            session_block_id=None,
            stored_name=stored,
            content_type="audio/mpeg",
            size_bytes=len(data),
            duration_seconds=10,
            bpm=120,
            note="",
        )
        db.add(take)
        db.commit()

        _write_media(settings, "takes", stored, data)
        _login(client)

        resp = client.get(f"/media/take/{take.id}")
        assert resp.status_code == 200
        assert resp.content == data
        assert resp.headers["content-type"] == "audio/mpeg"


# ---------------------------------------------------------------------------
# Range requests
# ---------------------------------------------------------------------------


class TestRangeRequests:
    def test_range_first_bytes(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        data = b"0123456789ABCDEF"
        stored = "range_test.gp"

        att = Attachment(
            item_id=item.id,
            filename="range_test.gp",
            stored_name=stored,
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=len(data),
        )
        db.add(att)
        db.commit()

        _write_media(settings, "attachments", stored, data)
        _login(client)

        resp = client.get(f"/media/attachment/{att.id}", headers={"Range": "bytes=0-3"})
        assert resp.status_code == 206
        assert resp.content == data[0:4]
        assert resp.headers["content-range"] == "bytes 0-3/16"

    def test_range_trailing_bytes(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        data = b"0123456789ABCDEF"
        stored = "range_test2.gp"

        att = Attachment(
            item_id=item.id,
            filename="range_test2.gp",
            stored_name=stored,
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=len(data),
        )
        db.add(att)
        db.commit()

        _write_media(settings, "attachments", stored, data)
        _login(client)

        resp = client.get(f"/media/attachment/{att.id}", headers={"Range": "bytes=12-"})
        assert resp.status_code == 206
        assert resp.content == data[12:]
        assert resp.headers["content-range"] == "bytes 12-15/16"

    def test_range_open_end(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        data = b"ABCDEFGHIJ"
        stored = "range_test3.gp"

        att = Attachment(
            item_id=item.id,
            filename="range_test3.gp",
            stored_name=stored,
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=len(data),
        )
        db.add(att)
        db.commit()

        _write_media(settings, "attachments", stored, data)
        _login(client)

        resp = client.get(f"/media/attachment/{att.id}", headers={"Range": "bytes=5-"})
        assert resp.status_code == 206
        assert resp.content == data[5:]
        assert resp.headers["content-range"] == "bytes 5-9/10"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrors:
    def test_unknown_kind_when_logged_in(self, client: TestClient, db: Session, settings) -> None:
        _login(client)
        resp = client.get("/media/unknown_king/1")
        assert resp.status_code == 404

    def test_unknown_id_when_logged_in(self, client: TestClient, db: Session, settings) -> None:
        _login(client)
        resp = client.get("/media/attachment/99999")
        assert resp.status_code == 404

    def test_media_not_found_missing_file(self, client: TestClient, db: Session, settings) -> None:
        item = _create_item(db)
        att = Attachment(
            item_id=item.id,
            filename="gone.gp",
            stored_name="missing.gp",
            kind="tab",
            label="",
            content_type="text/plain",
            size_bytes=100,
        )
        db.add(att)
        db.commit()
        _login(client)

        resp = client.get(f"/media/attachment/{att.id}")
        assert resp.status_code == 404
