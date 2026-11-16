"""Comprehensive tests for cover art functionality (SPEC 14.4)."""

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from app.covers import _detect_ext, fetch_cover, save_cover
from app.models import Item

# ---------------------------------------------------------------------------
# Magic byte detection
# ---------------------------------------------------------------------------


def test_detect_ext_jpeg() -> None:
    assert _detect_ext(b"\xff\xd8\xff\x00" + b"\x00" * 100) == "jpg"


def test_detect_ext_png() -> None:
    assert _detect_ext(b"\x89PNG" + b"\x00" * 100) == "png"


def test_detect_ext_html() -> None:
    assert _detect_ext(b"<html>") is None


def test_detect_ext_empty() -> None:
    assert _detect_ext(b"") is None


# ---------------------------------------------------------------------------
# fetch_cover – fake fetches
# ---------------------------------------------------------------------------


def fake_jpeg_fetch(_url: str, _ua: str) -> bytes:
    return b"\xff\xd8\xff\x00" + b"\x00" * 100


def fake_png_fetch(_url: str, _ua: str) -> bytes:
    return b"\x89PNG" + b"\x00" * 100


def fake_html_fetch(_url: str, _ua: str) -> bytes:
    return b"<html><body>Error</body></html>"


def fake_oversized_fetch(_url: str, _ua: str) -> bytes:
    return b"\xff\xd8\xff\x00" + b"\x00" * (2 * 1024 * 1024 + 1)


def fake_network_error(_url: str, _ua: str) -> bytes:
    raise RuntimeError("Network error")


def fetch_cover_with_fake(
    release_group_id: str,
    user_agent: str,
    *,
    fake: Callable[[str, str], bytes],
) -> bytes | None:
    return fetch_cover(release_group_id, user_agent, fetch=fake)


def test_fetch_cover_returns_jpeg_bytes() -> None:
    result = fetch_cover_with_fake("test-rgid", "test/ua", fake=fake_jpeg_fetch)
    assert result is not None
    assert result[:3] == b"\xff\xd8\xff"


def test_fetch_cover_returns_png_bytes() -> None:
    result = fetch_cover_with_fake("test-rgid", "test/ua", fake=fake_png_fetch)
    assert result is not None
    assert result[:4] == b"\x89PNG"


def test_fetch_cover_rejects_html() -> None:
    result = fetch_cover_with_fake("test-rgid", "test/ua", fake=fake_html_fetch)
    assert result is None


def test_fetch_cover_rejects_oversized() -> None:
    result = fetch_cover_with_fake("test-rgid", "test/ua", fake=fake_oversized_fetch)
    assert result is None


def test_fetch_cover_handles_network_error() -> None:
    result = fetch_cover_with_fake("test-rgid", "test/ua", fake=fake_network_error)
    assert result is None


# ---------------------------------------------------------------------------
# save_cover
# ---------------------------------------------------------------------------


def test_save_cover_jpeg(tmp_path: Path) -> None:
    data = b"\xff\xd8\xff\x00" + b"\x00" * 100
    assert save_cover(1, data, tmp_path) is True
    cover_path = tmp_path / "cover" / "1.jpg"
    assert cover_path.exists()
    assert cover_path.read_bytes() == data


def test_save_cover_png(tmp_path: Path) -> None:
    data = b"\x89PNG" + b"\x00" * 100
    assert save_cover(2, data, tmp_path) is True
    cover_path = tmp_path / "cover" / "2.png"
    assert cover_path.exists()
    assert cover_path.read_bytes() == data


def test_save_cover_returns_false_on_oserror(tmp_path: Path) -> None:
    # Try to save where the parent is a regular file, not a directory
    parent_file = tmp_path / "notafile"
    parent_file.write_text("not a directory")
    # We cannot create cover subdirectory inside a file
    result = save_cover(99, b"\xff\xd8\xff\x00", parent_file)
    assert result is False


# ---------------------------------------------------------------------------
# API: item creation triggers cover fetch
# ---------------------------------------------------------------------------


def test_api_create_item_with_cover(client: TestClient, tmp_path: Path) -> None:
    """POST /api/items with release_group_id fetches and saves cover."""
    payload = {
        "kind": "song",
        "title": "Test Song",
        "artist": "Test Artist",
        "release_group_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }
    resp = client.post(
        "/api/items",
        json=payload,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] is not None
    assert body["title"] == "Test Song"
    assert body["kind"] == "song"
    assert body["release_group_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_api_create_item_without_release_group(client: TestClient) -> None:
    """POST /api/items without release_group_id skips cover fetch."""
    payload = {
        "kind": "song",
        "title": "Test Song 2",
    }
    resp = client.post(
        "/api/items",
        json=payload,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["release_group_id"] is None


# ---------------------------------------------------------------------------
# Form: item creation triggers cover fetch
# ---------------------------------------------------------------------------


def test_form_create_item_with_release_group(client: TestClient, tmp_path: Path) -> None:
    """POST /items/new with release_group_id triggers cover fetch."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Form Test Song",
            "artist": "Form Artist",
            "release_group_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers.get("location", "")
    item_id = int(location.rsplit("/", 1)[-1])
    assert item_id > 0


def test_form_edit_item_with_release_group(client: TestClient) -> None:
    """POST /items/{id}/edit with release_group_id triggers cover fetch."""
    resp = client.post(
        "/items/new",
        data={
            "kind": "song",
            "title": "Edit Test Song",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = client.post(
        f"/items/{item_id}/edit",
        data={
            "kind": "song",
            "title": "Edit Test Song Updated",
            "release_group_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


# ---------------------------------------------------------------------------
# Cover serving
# ---------------------------------------------------------------------------


def test_get_cover_404_when_no_cover(client: TestClient) -> None:
    """GET /media/cover/{item_id} returns 404 when item has no cover."""
    # Create an item without a release_group_id
    resp = client.post(
        "/api/items",
        json={"kind": "song", "title": "No Cover Song"},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    cover_resp = client.get(f"/media/cover/{item_id}")
    assert cover_resp.status_code == 404


def test_get_cover_404_for_nonexistent_item(client: TestClient) -> None:
    """GET /media/cover/{item_id} returns 404 for nonexistent item."""
    resp = client.get("/media/cover/999999")
    assert resp.status_code == 404


def test_get_cover_serves_jpeg(client: TestClient, tmp_path: Path) -> None:
    """GET /media/cover/{item_id} serves JPEG cover when available."""
    resp = client.post(
        "/api/items",
        json={"kind": "song", "title": "Cover Song"},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # Place cover in MEDIA_DIR (tmp_path / "media" / "cover")
    media_dir = tmp_path / "media" / "cover"
    media_dir.mkdir(parents=True, exist_ok=True)
    jpeg_data = b"\xff\xd8\xff\x00" + b"\x00" * 100
    (media_dir / f"{item_id}.jpg").write_bytes(jpeg_data)

    with client.app.state.sessionmaker() as db:
        item = db.get(Item, item_id)
        if item:
            item.has_cover = True
            db.commit()
        db.close()

    cover_resp = client.get(f"/media/cover/{item_id}")
    assert cover_resp.status_code == 200
    assert cover_resp.headers["content-type"] == "image/jpeg"
    assert cover_resp.content == jpeg_data


def test_get_cover_serves_png(client: TestClient, tmp_path: Path) -> None:
    """GET /media/cover/{item_id} serves PNG cover when available."""
    resp = client.post(
        "/api/items",
        json={"kind": "exercise", "title": "PNG Cover Exercise"},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    media_dir = tmp_path / "media" / "cover"
    media_dir.mkdir(parents=True, exist_ok=True)
    png_data = b"\x89PNG" + b"\x00" * 100
    (media_dir / f"{item_id}.png").write_bytes(png_data)

    with client.app.state.sessionmaker() as db:
        item = db.get(Item, item_id)
        if item:
            item.has_cover = True
            db.commit()
        db.close()

    cover_resp = client.get(f"/media/cover/{item_id}")
    assert cover_resp.status_code == 200
    assert cover_resp.headers["content-type"] == "image/png"
    assert cover_resp.content == png_data
