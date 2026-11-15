"""Week maths for stats (SPEC 9.4, backend.md §stats).

Pure functions: no database, no framework.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clock import LOCAL_TZ


def week_start(local_dt: datetime) -> date:
    """Return the Monday of the week containing *local_dt* (in local time).

    A week runs Monday 00:00 to Sunday 24:00 local time (SPEC 9.4).
    """
    local = local_dt.astimezone(LOCAL_TZ) if local_dt.tzinfo is not None else local_dt
    return local.date() - timedelta(days=local.weekday())


def week_bounds_utc(monday: date) -> tuple[datetime, datetime]:
    """Return the UTC start and end of the week starting on *monday*.

    *monday* is a local-time date (Europe/Amsterdam).  The returned
    datetimes are UTC-aware.  The end boundary is midnight of the
    following Sunday (i.e. one week later).
    """
    start_local = datetime.combine(monday, datetime.min.time(), tzinfo=LOCAL_TZ)
    sunday = monday + timedelta(days=6)
    end_local = datetime.combine(sunday, datetime.min.time(), tzinfo=LOCAL_TZ) + timedelta(hours=24)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def minutes_per_week(db: Session, mondays: Sequence[date]) -> dict[date, int]:
    """Return total played minutes for each week whose Monday is in *mondays*.

    Minutes are rounded down (floor division by 60).  A block belongs to the
    week whose Monday is determined by converting ``ended_at`` to local time
    first (SPEC 9.4).
    """
    if not mondays:
        return {}

    monday_set = set(mondays)

    # Fetch all session blocks with non-zero played_seconds and a valid ended_at.
    rows = db.execute(
        text(
            "SELECT ended_at, played_seconds "
            "FROM session_block "
            "WHERE ended_at IS NOT NULL AND played_seconds > 0"
        )
    ).fetchall()

    # Build a lookup: monday -> total minutes.
    totals: dict[date, int] = {m: 0 for m in mondays}

    for row in rows:
        ended_at = row[0]
        played_seconds = row[1]

        # Convert to local time and find the week's Monday.
        local_dt = ended_at.astimezone(LOCAL_TZ)
        monday = local_dt.date() - timedelta(days=local_dt.weekday())

        if monday in monday_set:
            totals[monday] += played_seconds // 60

    return totals


def tempo_history(db: Session, item_id: int) -> list[tuple[date, int]]:
    """Return per-day maximum BPM for *item_id*, oldest first (SPEC 7.1).

    Groups ``SessionBlock`` rows by the local date of ``ended_at`` and
    returns ``(date, max_bpm)`` tuples, ignoring NULL bpm values.
    """
    rows = db.execute(
        text(
            "SELECT date(ended_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam') "
            "AS day, MAX(bpm) AS bpm "
            "FROM session_block "
            "WHERE item_id = :item_id "
            "  AND ended_at IS NOT NULL "
            "  AND bpm IS NOT NULL "
            "GROUP BY day "
            "ORDER BY day ASC"
        ),
        {"item_id": item_id},
    ).fetchall()

    return [(row[0], row[1]) for row in rows]


def item_tempo_progress(db: Session) -> list[dict[str, str | int]]:
    """Return items practised with a BPM in the last 90 days (SPEC 7.2).

    For each item, returns the first BPM (from the earliest block in the
    window), the latest BPM (from the latest block), and the difference.

    Returns ``[(title, item_id, first_bpm, latest_bpm, diff)]`` ordered
    by ``first_bpm ASC`` then ``title ASC``.
    """
    rows = db.execute(
        text(
            "WITH filtered AS ("
            "  SELECT sb.item_id, sb.bpm, sb.ended_at, sb.id, "
            "    ROW_NUMBER() OVER ("
            "      PARTITION BY sb.item_id "
            "      ORDER BY sb.ended_at ASC, sb.id ASC"
            "    ) AS rn_asc, "
            "    ROW_NUMBER() OVER ("
            "      PARTITION BY sb.item_id "
            "      ORDER BY sb.ended_at DESC, sb.id DESC"
            "    ) AS rn_desc "
            "  FROM session_block sb "
            "  WHERE sb.bpm IS NOT NULL "
            "    AND sb.ended_at > NOW() - INTERVAL '90 days' "
            "), "
            "first_bpm AS ("
            "  SELECT item_id, bpm AS first_bpm "
            "  FROM filtered WHERE rn_asc = 1 "
            "), "
            "latest_bpm AS ("
            "  SELECT item_id, bpm AS latest_bpm "
            "  FROM filtered WHERE rn_desc = 1 "
            ") "
            "SELECT i.title, i.id, fb.first_bpm, lb.latest_bpm, "
            "       (lb.latest_bpm - fb.first_bpm) AS diff "
            "FROM first_bpm fb "
            "JOIN latest_bpm lb ON fb.item_id = lb.item_id "
            "JOIN item i ON i.id = fb.item_id "
            "ORDER BY fb.first_bpm ASC, i.title ASC"
        )
    ).fetchall()

    return [
        {
            "title": row[0],
            "item_id": row[1],
            "first_bpm": row[2],
            "latest_bpm": row[3],
            "diff": row[4],
        }
        for row in rows
    ]


def weeks_12(db: Session) -> list[dict[str, int | date]]:
    """Return the last 12 weeks of data for the /progress page.

    Returns a list of dicts with keys ``monday``, ``minutes``, ordered
    oldest-first (the oldest week is index 0).
    """
    now = datetime.now(LOCAL_TZ)
    this_monday = week_start(now)

    # Build the 12 mondays (oldest first).
    mondays = [this_monday - timedelta(weeks=11 - i) for i in range(12)]

    totals = minutes_per_week(db, mondays)

    return [{"monday": m, "minutes": totals.get(m, 0)} for m in mondays]
