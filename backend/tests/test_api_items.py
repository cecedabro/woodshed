"""Item JSON API: POST /api/items, GET /api/items/{id} (SPEC 3.1, 3.8)."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Item

# ---------------------------------------------------------------------------
# POST /api/items — success
# ---------------------------------------------------------------------------


def test_create_item_returns_201(client: TestClient) -> None:
    """SPEC 3.8: POST with valid data returns 201."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "Heartbreaker",
            "artist": "Led Zeppelin",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "song"
    assert body["title"] == "Heartbreaker"
    assert body["artist"] == "Led Zeppelin"
    assert body["status"] == "learning"
    assert body["current_bpm"] is None
    assert body["original_url"] is None
    assert body["notes"] == ""
    assert body["created_at"] is not None
    assert body["updated_at"] is not None
    assert body["id"] is not None


def test_create_item_all_fields(client: TestClient) -> None:
    """SPEC 3.1, 3.8: create with every field set."""
    r = client.post(
        "/api/items",
        json={
            "kind": "exercise",
            "title": "Blues scale in A",
            "artist": "Jamey Aebersold",
            "status": "polishing",
            "current_bpm": 120,
            "original_url": "https://example.com/scale",
            "notes": "Play slowly at first",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] is not None
    assert body["kind"] == "exercise"
    assert body["title"] == "Blues scale in A"
    assert body["artist"] == "Jamey Aebersold"
    assert body["status"] == "polishing"
    assert body["current_bpm"] == 120
    assert body["original_url"] == "https://example.com/scale"
    assert body["notes"] == "Play slowly at first"


def test_create_item_repertoire_status(client: TestClient) -> None:
    """SPEC 3.1: repertoire status is accepted."""
    r = client.post(
        "/api/items",
        json={
            "kind": "exercise",
            "title": "Major scale",
            "status": "repertoire",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "repertoire"


def test_create_item_http_url(client: TestClient) -> None:
    """SPEC 3.1: http:// URLs are accepted."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "HTTP link",
            "original_url": "http://example.com/song",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["original_url"] == "http://example.com/song"


def test_create_item_https_url(client: TestClient) -> None:
    """SPEC 3.1: https:// URLs are accepted."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "HTTPS link",
            "original_url": "https://example.com/song",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["original_url"] == "https://example.com/song"


def test_create_minimal_item_defaults(client: TestClient) -> None:
    """SPEC 3.1: minimal item uses defaults for all optional fields."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "Stairway",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["artist"] is None
    assert body["status"] == "learning"
    assert body["current_bpm"] is None
    assert body["original_url"] is None
    assert body["notes"] == ""


# ---------------------------------------------------------------------------
# POST /api/items — validation failures (422, nothing stored)
# ---------------------------------------------------------------------------


def test_empty_title_returns_422(client: TestClient, db) -> None:
    """SPEC 3.1: title \"\" is rejected."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "",
        },
    )
    assert r.status_code == 422

    count = db.execute(select(Item)).scalars().first() or 0
    assert count == 0


def test_title_201_chars_returns_422(client: TestClient, db) -> None:
    """SPEC 3.1: title with 201 characters is rejected."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "a" * 201,
        },
    )
    assert r.status_code == 422

    count = db.execute(select(Item)).scalars().first() or 0
    assert count == 0


def test_title_200_chars_passes(client: TestClient) -> None:
    """SPEC 3.1: title with exactly 200 characters is accepted."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "a" * 200,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "a" * 200


def test_bpm_19_returns_422(client: TestClient, db) -> None:
    """SPEC 3.1: BPM 19 is below the 20–400 range."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "Too slow",
            "current_bpm": 19,
        },
    )
    assert r.status_code == 422

    count = db.execute(select(Item)).scalars().first() or 0
    assert count == 0


def test_bpm_401_returns_422(client: TestClient, db) -> None:
    """SPEC 3.1: BPM 401 is above the 20–400 range."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "Too fast",
            "current_bpm": 401,
        },
    )
    assert r.status_code == 422

    count = db.execute(select(Item)).scalars().first() or 0
    assert count == 0


def test_bpm_20_passes(client: TestClient) -> None:
    """SPEC 3.1: BPM at lower bound 20 is accepted."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "Adagio",
            "current_bpm": 20,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["current_bpm"] == 20


def test_bpm_400_passes(client: TestClient) -> None:
    """SPEC 3.1: BPM at upper bound 400 is accepted."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "Presto",
            "current_bpm": 400,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["current_bpm"] == 400


def test_ftp_url_returns_422(client: TestClient, db) -> None:
    """SPEC 3.1: original_url must start with http:// or https://."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "No ftp",
            "original_url": "ftp://example.com/tab",
        },
    )
    assert r.status_code == 422

    count = db.execute(select(Item)).scalars().first() or 0
    assert count == 0


def test_unknown_status_returns_422(client: TestClient, db) -> None:
    """SPEC 3.1: status must be learning, polishing, or repertoire."""
    r = client.post(
        "/api/items",
        json={
            "kind": "song",
            "title": "Bad status",
            "status": "finished",
        },
    )
    assert r.status_code == 422

    count = db.execute(select(Item)).scalars().first() or 0
    assert count == 0


def test_unknown_kind_returns_422(client: TestClient, db) -> None:
    """SPEC 3.1: kind must be song or exercise."""
    r = client.post(
        "/api/items",
        json={
            "kind": "recording",
            "title": "Bad kind",
        },
    )
    assert r.status_code == 422

    count = db.execute(select(Item)).scalars().first() or 0
    assert count == 0


# ---------------------------------------------------------------------------
# GET /api/items/{id}
# ---------------------------------------------------------------------------


def test_get_existing_item_returns_200(client: TestClient, db) -> None:
    """SPEC 3.8: GET returns the item as JSON."""
    # Build the item via the db fixture so the API handler can see it
    item = Item(kind="song", title="The Thrill Is Gone")
    db.add(item)
    db.commit()
    db.refresh(item)

    r = client.get(f"/api/items/{item.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "The Thrill Is Gone"
    assert body["kind"] == "song"
    assert body["id"] == item.id


def test_get_nonexistent_item_returns_404(client: TestClient, db) -> None:
    """SPEC 3.8: GET with unknown id returns 404."""
    r = client.get("/api/items/99999")
    assert r.status_code == 404
