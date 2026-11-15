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
