"""Routine editor: list, add and remove blocks (SPEC 4.1, 4.2)."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item, Routine, RoutineBlock


def _setup(db: Session) -> tuple[int, list[int]]:
    routine = Routine(name="Evening")
    items = [Item(kind="song", title=t) for t in ("Alpha", "Bravo", "Charlie")]
    db.add_all([routine, *items])
    db.commit()
    return routine.id, [i.id for i in items]


def _titles(db: Session, rid: int) -> list[tuple[int, str]]:
    db.expire_all()
    rows = db.execute(
        select(RoutineBlock.position, Item.title)
        .join(Item, Item.id == RoutineBlock.item_id)
        .where(RoutineBlock.routine_id == rid)
        .order_by(RoutineBlock.position)
    ).all()
    return [(r.position, r.title) for r in rows]


def _add(client: TestClient, rid: int, item_id: int, minutes: str = "5", bpm: str = ""):
    return client.post(
        f"/routines/{rid}/blocks", data={"item_id": str(item_id), "minutes": minutes, "bpm": bpm}
    )


def test_editor_lists_existing_blocks(client: TestClient, db: Session) -> None:
    rid, ids = _setup(db)
    db.add(RoutineBlock(routine_id=rid, position=0, item_id=ids[0], minutes=7, bpm=90))
    db.commit()
    resp = client.get(f"/routines/{rid}/edit")
    assert resp.status_code == 200
    assert "Alpha" in resp.text
    assert "7 min · 90 bpm" in resp.text
    assert 'id="blocks"' in resp.text
    assert f'hx-post="/routines/{rid}/blocks"' in resp.text


def test_add_three_then_remove_middle(client: TestClient, db: Session) -> None:
    rid, ids = _setup(db)
    for item_id in ids:
        resp = _add(client, rid, item_id)
        assert resp.status_code == 200
    assert _titles(db, rid) == [(0, "Alpha"), (1, "Bravo"), (2, "Charlie")]
    assert "Charlie" in resp.text and "15 min in total" in resp.text

    middle = db.scalar(
        select(RoutineBlock.id).where(RoutineBlock.routine_id == rid, RoutineBlock.position == 1)
    )
    resp = client.post(f"/routines/{rid}/blocks/{middle}/remove")
    assert resp.status_code == 200
    assert "Bravo" not in resp.text
    assert _titles(db, rid) == [(0, "Alpha"), (1, "Charlie")]


def test_add_with_bpm(client: TestClient, db: Session) -> None:
    rid, ids = _setup(db)
    assert _add(client, rid, ids[0], minutes="10", bpm="120").status_code == 200
    block = db.scalar(select(RoutineBlock).where(RoutineBlock.routine_id == rid))
    assert block is not None and (block.minutes, block.bpm) == (10, 120)


def test_31st_block_is_422(client: TestClient, db: Session) -> None:
    rid, ids = _setup(db)
    db.add_all(
        RoutineBlock(routine_id=rid, position=p, item_id=ids[0], minutes=1) for p in range(30)
    )
    db.commit()
    assert _add(client, rid, ids[1]).status_code == 422
    assert len(_titles(db, rid)) == 30


def test_bad_values_are_422(client: TestClient, db: Session) -> None:
    rid, ids = _setup(db)
    assert _add(client, rid, ids[0], minutes="0").status_code == 422
    assert _add(client, rid, ids[0], minutes="121").status_code == 422
    assert _add(client, rid, ids[0], bpm="19").status_code == 422
    assert _add(client, rid, ids[0], minutes="abc").status_code == 422
    assert _add(client, rid, 99999).status_code == 422
    assert _titles(db, rid) == []


def test_block_of_another_routine_is_404(client: TestClient, db: Session) -> None:
    rid, ids = _setup(db)
    other = Routine(name="Other")
    db.add(other)
    db.flush()
    block = RoutineBlock(routine_id=other.id, position=0, item_id=ids[0], minutes=5)
    db.add(block)
    db.commit()
    assert client.post(f"/routines/{rid}/blocks/{block.id}/remove").status_code == 404
    assert len(_titles(db, other.id)) == 1


def test_unknown_routine_is_404(client: TestClient, db: Session) -> None:
    _, ids = _setup(db)
    assert _add(client, 99999, ids[0]).status_code == 404
    assert client.get("/routines/99999/edit").status_code == 404
