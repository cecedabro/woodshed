"""Week maths for stats (SPEC 9.4, backend.md §stats).

Pure functions: no database, no framework.
"""

from datetime import UTC, date, datetime, timedelta

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
