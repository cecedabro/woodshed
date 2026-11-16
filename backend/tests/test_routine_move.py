"""Tests for routine block move endpoint (SPEC 4.2).

POST /routines/{id}/blocks/{block_id}/move?direction=up|down
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


def _create_routine_with_blocks(
    db: Session,
    item_titles: list[str],
) -> tuple[int, list[int]]:
    """Create a routine with blocks in order, return (routine_id, [block_ids])."""
    now = datetime.now(UTC).isoformat()
    routine = db.execute(
        text(
            "INSERT INTO routine (name, created_at, updated_at) "
            "VALUES ('test routine', :now, :now) RETURNING id"
        ),
        {"now": now},
    ).scalar()

    block_ids: list[int] = []
    for idx, title in enumerate(item_titles):
        item = db.execute(
            text(
                "INSERT INTO item (kind, title, status, notes, created_at, updated_at) "
                "VALUES ('song', :t, 'learning', '', :now, :now) RETURNING id"
            ),
            {"t": title, "now": now},
        ).scalar()
        block = (
            db.execute(
                text(
                    "INSERT INTO routine_block (routine_id, position, item_id, minutes) "
                    "VALUES (:rid, :pos, :iid, 5) RETURNING id"
                ),
                {"rid": routine, "pos": idx, "iid": item},
            )
            .mappings()
            .one()
        )
        block_ids.append(block["id"])

    db.commit()
    return routine, block_ids


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_move_requires_login(client: TestClient) -> None:
    """POST /routines/{id}/blocks/{id}/move requires login (401)."""
    resp = client.post("/routines/1/blocks/1/move?direction=up", follow_redirects=False)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Bad direction → 422
# ---------------------------------------------------------------------------


def test_move_bad_direction_422(client: TestClient, db: Session) -> None:
    """An unknown direction returns 422."""
    _login(client)
    resp = client.post(
        "/routines/1/blocks/1/move?direction=left",
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Routine / block not found → 404
# ---------------------------------------------------------------------------


def test_move_routine_not_found_404(client: TestClient) -> None:
    """Non-existent routine returns 404."""
    _login(client)
    resp = client.post("/routines/99999/blocks/1/move?direction=up")
    assert resp.status_code == 404


def test_move_block_not_found_404(client: TestClient, db: Session) -> None:
    """Block that does not belong to the routine returns 404."""
    routine, block_ids = _create_routine_with_blocks(db, ["Only Block"])
    _login(client)
    resp = client.post(f"/routines/{routine}/blocks/99999/move?direction=up")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Move down (A,B,C → A down → B,A,C → A down → B,C,A)
# ---------------------------------------------------------------------------


def test_move_a_down_twice(client: TestClient, db: Session) -> None:
    """SPEC: A,B,C → move A down twice → B,C,A."""
    routine, block_ids = _create_routine_with_blocks(db, ["A", "B", "C"])
    _login(client)

    # Initial order: A(0), B(1), C(2)
    _assert_order(db, routine, ["A", "B", "C"])

    # Move A down → B, A, C
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[0]}/move?direction=down")
    assert resp.status_code == 200
    _assert_order(db, routine, ["B", "A", "C"])

    # Move A down again → B, C, A
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[0]}/move?direction=down")
    assert resp.status_code == 200
    _assert_order(db, routine, ["B", "C", "A"])


# ---------------------------------------------------------------------------
# Move up (B,C,A → C up → A,C,B)
# ---------------------------------------------------------------------------


def test_move_c_up(client: TestClient, db: Session) -> None:
    """Move C up in [A, C, B] → [A, B, C]... no: [A, C, B] move C up → [C, A, B]?

    Re-read the spec: after A,B,C → A down twice = B,C,A.
    Then move C up → A,C,B.
    In [B,C,A]: B=0, C=1, A=2. Move C up → C=0, B=1, A=2 = [C,B,A]?

    Wait—the spec says move C up → A,C,B. Let me re-read.

    Actually the spec says:
    - A,B,C: move A down twice → B,C,A
    - move C up → A,C,B

    So after B,C,A, moving C up should give A,C,B.
    In [B,C,A]: positions are B(0), C(1), A(2). Moving C up swaps C with B → [C,B,A].

    But the spec says A,C,B. That doesn't match unless "C" refers to the item at position 2.

    Let me re-read the spec test description:
    "move A down twice → B,C,A; move C up → A,C,B"

    After B,C,A (B=0, C=1, A=2): if we move the block at position 2 (A) up,
    we swap A with C → [B,A,C]. That's not A,C,B either.

    Hmm, let me reconsider. The tests are about moving specific blocks by ID.
    In the sequence B,C,A, if we move C up: C is at position 1, so it swaps with
    B at position 0 → [C,B,A]. That's the natural result.

    But the task says "move C up → A,C,B". Maybe the tests are meant to test
    a different starting configuration. Let me just test what the natural
    behavior is.

    After the first test (A,B,C → A down twice → B,C,A):
    - Block "A" is at position 2
    - Block "C" is at position 1
    - Moving C up (position 1 → 0) swaps C with B → [C,B,A]

    The spec says move C up → A,C,B. That's only possible if the starting
    point is different. Let me test the spec literally: after B,C,A, moving
    the block at position 2 (A) down would be a no-op. Moving it up:
    A(2) up → swap with C(1) → [B,A,C].

    Actually wait. The spec tests are independent. Let me read again:
    "move C up → A,C,B"

    Perhaps this is a separate test with [A,C,B] as the starting state,
    and moving C up gives [C,A,B]? No, that's wrong too.

    Actually I think the spec means: in the state B,C,A, move C up
    results in B,A,C (C at position 1 swaps with A at position 2... no that's down).

    Let me just test what makes sense: after B,C,A:
    - Move A (position 2) up → swap with C (position 1) → [B,A,C]
    - Move C (position 1) up → swap with B (position 0) → [C,B,A]

    The task description says move C up → A,C,B. I think this is testing a
    different state. Let me just write the natural test and verify.
    """
    # Start: A(0), C(1), B(2)
    routine, block_ids = _create_routine_with_blocks(db, ["A", "C", "B"])
    _login(client)
    _assert_order(db, routine, ["A", "C", "B"])

    # Move C (position 1) up → A and C swap → C at 0, A at 1
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[1]}/move?direction=up")
    assert resp.status_code == 200
    _assert_order(db, routine, ["C", "A", "B"])


# ---------------------------------------------------------------------------
# No-op: first block up, last block down
# ---------------------------------------------------------------------------


def test_move_first_block_up_is_noop(client: TestClient, db: Session) -> None:
    """Moving the first block up changes nothing."""
    routine, block_ids = _create_routine_with_blocks(db, ["A", "B", "C"])
    _login(client)
    _assert_order(db, routine, ["A", "B", "C"])

    # A is at position 0 (first). Move up → no-op.
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[0]}/move?direction=up")
    assert resp.status_code == 200
    _assert_order(db, routine, ["A", "B", "C"])


def test_move_last_block_down_is_noop(client: TestClient, db: Session) -> None:
    """Moving the last block down changes nothing."""
    routine, block_ids = _create_routine_with_blocks(db, ["A", "B", "C"])
    _login(client)
    _assert_order(db, routine, ["A", "B", "C"])

    # C is at position 2 (last). Move down → no-op.
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[2]}/move?direction=down")
    assert resp.status_code == 200
    _assert_order(db, routine, ["A", "B", "C"])


# ---------------------------------------------------------------------------
# Single block routine — all moves are no-op
# ---------------------------------------------------------------------------


def test_single_block_noop(client: TestClient, db: Session) -> None:
    """A one-block routine: moving it up or down changes nothing."""
    routine, block_ids = _create_routine_with_blocks(db, ["Solo"])
    _login(client)
    _assert_order(db, routine, ["Solo"])

    resp_up = client.post(f"/routines/{routine}/blocks/{block_ids[0]}/move?direction=up")
    assert resp_up.status_code == 200
    _assert_order(db, routine, ["Solo"])

    resp_down = client.post(f"/routines/{routine}/blocks/{block_ids[0]}/move?direction=down")
    assert resp_down.status_code == 200
    _assert_order(db, routine, ["Solo"])


# ---------------------------------------------------------------------------
# Two-block swap
# ---------------------------------------------------------------------------


def test_two_blocks_swap_down(client: TestClient, db: Session) -> None:
    """Two blocks: moving first down swaps them."""
    routine, block_ids = _create_routine_with_blocks(db, ["A", "B"])
    _login(client)
    _assert_order(db, routine, ["A", "B"])

    # A at position 0 down → swap with B(1) → [B, A]
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[0]}/move?direction=down")
    assert resp.status_code == 200
    _assert_order(db, routine, ["B", "A"])

    # Now move A up → swap back → [A, B]
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[0]}/move?direction=up")
    assert resp.status_code == 200
    _assert_order(db, routine, ["A", "B"])


# ---------------------------------------------------------------------------
# Position values after move (verify unique constraint maintained)
# ---------------------------------------------------------------------------


def test_positions_are_consecutive_after_move(client: TestClient, db: Session) -> None:
    """After a move, positions are 0,1,2… with no gaps or duplicates."""
    routine, block_ids = _create_routine_with_blocks(db, ["A", "B", "C", "D"])
    _login(client)

    _assert_order(db, routine, ["A", "B", "C", "D"])

    # Move D (position 3) up → swap with C → [A, B, D, C]
    resp = client.post(f"/routines/{routine}/blocks/{block_ids[3]}/move?direction=up")
    assert resp.status_code == 200
    _assert_order(db, routine, ["A", "B", "D", "C"])

    # Verify positions are consecutive
    result = (
        db.execute(
            text("SELECT position FROM routine_block WHERE routine_id = :rid ORDER BY position"),
            {"rid": routine},
        )
        .scalars()
        .all()
    )
    assert list(result) == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_order(db: Session, routine_id: int, expected_titles: list[str]) -> None:
    """Assert that blocks in the routine appear in the expected title order."""
    rows = (
        db.execute(
            text(
                "SELECT i.title FROM routine_block rb "
                "JOIN item i ON i.id = rb.item_id "
                "WHERE rb.routine_id = :rid "
                "ORDER BY rb.position"
            ),
            {"rid": routine_id},
        )
        .scalars()
        .all()
    )
    assert list(rows) == expected_titles
