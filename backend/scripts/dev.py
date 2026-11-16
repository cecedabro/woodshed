#!/usr/bin/env python3
"""Dev entry-point: start pgserver, migrate, seed, run uvicorn.

Usage (via ``make dev``):

    python scripts/dev.py

The seed function is also importable for tests:

    from scripts.dev import seed_db
"""

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[1]
DEV_DB_DIR = BACKEND / ".devdb"


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def seed_db(db: Session) -> None:
    """Insert deterministic seed data (idempotent).

    Creates 3 routines, 8 items (blues/rock), and 10 weeks of practice
    sessions with steadily rising BPMs.  Calling this function twice does
    not duplicate rows.
    """
    from datetime import datetime, timedelta

    from app.clock import LOCAL_TZ
    from app.models import (
        Item,
        PracticeSession,
        Routine,
        RoutineBlock,
        SessionBlock,
    )
    from app.stats import week_bounds_utc

    # --- Items (8 blues / rock songs + exercises) -------------------------

    items_data = [
        ("song", "Stormy Monday", "Tyrone Davis"),
        ("song", "Sweet Home Chicago", "Robert Johnson"),
        ("song", "Crossfire", "Ray Charles"),
        ("song", "Killing Floor", "Howlin' Wolf"),
        ("exercise", "E-minor pentatonic drill", None),
        ("exercise", "12-bar blues turnaround", None),
        ("exercise", "Shuffle right-hand pattern", None),
        ("exercise", "Blues scale speed run", None),
    ]

    item_id_map: dict[str, int] = {}
    for kind, title, artist in items_data:
        stmt = text("SELECT id FROM item WHERE title = :t").bindparams(t=title)
        row = db.execute(stmt).scalar_one_or_none()
        if row is not None:
            item_id_map[title] = row
            continue
        item = Item(kind=kind, title=title, artist=artist)
        db.add(item)
        db.flush()
        item_id_map[title] = item.id

    # --- Routines (3) -----------------------------------------------------

    routines_data = [
        (
            "Morning blues warmup",
            [
                (0, "E-minor pentatonic drill", 5, 80),
                (1, "Stormy Monday", 10, 90),
                (2, "12-bar blues turnaround", 5, 100),
            ],
        ),
        (
            "Rock session",
            [
                (0, "Shuffle right-hand pattern", 5, 110),
                (1, "Sweet Home Chicago", 10, 120),
                (2, "Crossfire", 10, 130),
            ],
        ),
        (
            "Evening practice",
            [
                (0, "Blues scale speed run", 10, 100),
                (1, "Killing Floor", 10, 110),
            ],
        ),
    ]

    routine_id_map: dict[str, int] = {}
    for routine_name, _ in routines_data:
        stmt = text("SELECT id FROM routine WHERE name = :n").bindparams(n=routine_name)
        row = db.execute(stmt).scalar_one_or_none()
        if row is not None:
            routine_id_map[routine_name] = row
            continue
        routine = Routine(name=routine_name)
        db.add(routine)
        db.flush()
        routine_id_map[routine_name] = routine.id

    db.commit()

    # Ensure all blocks exist (idempotent by checking routine_id + position)
    for routine_name, blocks_data in routines_data:
        routine_id = routine_id_map[routine_name]
        for position, item_title, minutes, bpm in blocks_data:
            stmt = text(
                "SELECT id FROM routine_block WHERE routine_id = :rid AND position = :pos"
            ).bindparams(rid=routine_id, pos=position)
            row = db.execute(stmt).scalar_one_or_none()
            if row is not None:
                continue
            item_id = item_id_map[item_title]
            db.add(
                RoutineBlock(
                    routine_id=routine_id,
                    position=position,
                    item_id=item_id,
                    minutes=minutes,
                    bpm=bpm,
                )
            )
    db.commit()

    # --- 10 weeks of practice sessions -----------------------------------

    now_local = datetime.now(LOCAL_TZ)
    base_monday = now_local.date() - timedelta(days=now_local.weekday()) - timedelta(weeks=9)

    bpm_increment = 2

    for week_idx in range(10):
        monday = base_monday + timedelta(weeks=week_idx)
        _week_start_utc, _week_end_utc = week_bounds_utc(monday)

        day_offset = week_idx % 5
        practice_day = monday + timedelta(days=day_offset)

        for routine_name, blocks_data in routines_data:
            routine_id = routine_id_map[routine_name]
            total_minutes = sum(b[2] for b in blocks_data)

            session_started = datetime.combine(
                practice_day,
                datetime.min.time().replace(hour=18),
                tzinfo=LOCAL_TZ,
            )
            session_ended = session_started + timedelta(minutes=total_minutes)

            # Check if session already exists for this routine + day
            stmt = text(
                "SELECT id FROM practice_session "
                "WHERE routine_id = :rid "
                "  AND started_at >= :start AND started_at < :end"
            ).bindparams(
                rid=routine_id,
                start=session_started,
                end=session_started + timedelta(days=1),
            )
            row = db.execute(stmt).scalar_one_or_none()

            if row is not None:
                session = db.get(PracticeSession, row)
            else:
                session = PracticeSession(
                    routine_id=routine_id,
                    started_at=session_started,
                    ended_at=session_ended,
                )
                db.add(session)
                db.flush()

            for block_pos, item_title, minutes, block_bpm in blocks_data:
                item_id = item_id_map[item_title]
                planned_seconds = minutes * 60
                played_seconds = int(planned_seconds * 0.9)
                current_bpm = block_bpm + (bpm_increment * week_idx)

                block_ended = session_started + timedelta(minutes=block_pos * minutes + minutes)

                stmt = text(
                    "SELECT id FROM session_block WHERE session_id = :sid AND position = :pos"
                ).bindparams(sid=session.id, pos=block_pos)
                row = db.execute(stmt).scalar_one_or_none()

                if row is not None:
                    block = db.get(SessionBlock, row)
                    block.bpm = current_bpm
                    block.played_seconds = played_seconds
                    continue

                db.add(
                    SessionBlock(
                        session_id=session.id,
                        item_id=item_id,
                        item_title=item_title,
                        position=block_pos,
                        planned_seconds=planned_seconds,
                        played_seconds=played_seconds,
                        bpm=current_bpm,
                        ended_at=block_ended,
                    )
                )

    db.commit()


# ---------------------------------------------------------------------------
# Database bootstrap helpers
# ---------------------------------------------------------------------------


def _ensure_dev_database(db_url: str) -> str:
    """Ensure the .devdb database exists; return the connection URL."""
    u = make_url(db_url)
    admin = __import__("sqlalchemy").create_engine(
        u.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": u.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{u.database}"'))
    admin.dispose()
    return db_url


def _ensure_pgserver() -> tuple[str, object]:
    """Start pgserver on a .devdb directory, return (db_url, server)."""
    DEV_DB_DIR.mkdir(parents=True, exist_ok=True)
    import pgserver

    srv = pgserver.get_server(str(DEV_DB_DIR), cleanup_mode="stop")
    uri = srv.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    return uri, srv


def _run_migrations(db_url: str) -> None:
    """Run every Alembic migration up to head."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.attributes["keep_url"] = True
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Start pgserver, migrate, seed, and run uvicorn on :8000."""
    db_url, srv = _ensure_pgserver()
    _ensure_dev_database(db_url)
    _run_migrations(db_url)

    settings = Settings(DATABASE_URL=db_url)
    app = create_app(settings)

    # Seed on the same engine
    with app.state.engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.commit()
    with app.state.sessionmaker() as session:
        seed_db(session)

    print("Starting uvicorn on :8000 …")

    try:
        import uvicorn

        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
        )
    except KeyboardInterrupt:
        print("\nShutting down …")
        srv.cleanup()


if __name__ == "__main__":
    main()
