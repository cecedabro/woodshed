"""Helpers for check-migrations.sh. Run inside a checkout's backend/ directory.

Data goes in and comes out only through the JSON API (SPEC 3.8: POST /login,
POST /api/items, GET /api/items/{id}), so the check works across versions
whatever the table names are.

    python migcheck.py wipe
    python migcheck.py seed     # exit 3 when the item API does not exist yet
    python migcheck.py verify
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())  # the checkout's backend/, so `app` is importable

STATE = Path(os.environ.get("MEDIA_DIR", ".")) / "migcheck-item.json"
ITEM = {
    "kind": "song",
    "title": "Migcheck Blues",
    "artist": "Test",
    "status": "learning",
    "current_bpm": 72,
}


def wipe() -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import OperationalError

    url = make_url(os.environ["DATABASE_URL"])
    try:
        create_engine(url).connect().close()
    except OperationalError:  # database missing: create it from the server's default db
        admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    with create_engine(url).begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def client():  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    c.post("/login", data={"password": os.environ["APP_PASSWORD"]}, follow_redirects=False)
    return c


def seed() -> None:
    r = client().post("/api/items", json=ITEM)
    if r.status_code in (404, 405):
        print("no /api/items yet: skipping the data check")
        sys.exit(3)
    assert r.status_code == 201, f"seed failed: {r.status_code} {r.text}"
    STATE.write_text(json.dumps({"id": r.json()["id"]}))
    print(f"seeded item {r.json()['id']}")


def verify() -> None:
    item_id = json.loads(STATE.read_text())["id"]
    r = client().get(f"/api/items/{item_id}")
    assert r.status_code == 200, f"item lost after upgrade: {r.status_code} {r.text}"
    body = r.json()
    for key, value in ITEM.items():
        assert body.get(key) == value, f"{key} changed after upgrade: {body.get(key)!r}"
    print("data intact after upgrade")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "?"
    {"wipe": wipe, "seed": seed, "verify": verify}[cmd]()
