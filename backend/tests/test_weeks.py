"""Tests for week maths (SPEC 9.4, backend.md §stats).

Functions: ``week_start``, ``week_bounds_utc``.
"""

from datetime import datetime

from app.clock import LOCAL_TZ
from app.stats import week_bounds_utc, week_start

# ---------------------------------------------------------------------------
# week_start — boundary between Sunday and Monday (SPEC 9.4)
# ---------------------------------------------------------------------------


def test_week_start_sunday_vs_monday():
    """Sunday 23:30 and Monday 00:10 local return different Mondays."""
    # Sunday 23:30 Amsterdam (still in the previous week)
    sun = datetime(2026, 3, 29, 23, 30, tzinfo=LOCAL_TZ)
    # Monday 00:10 Amsterdam (new week starts)
    mon = datetime(2026, 3, 30, 0, 10, tzinfo=LOCAL_TZ)
    assert week_start(sun) != week_start(mon)

    # The Monday's date is the date of Monday itself.
    assert week_start(mon) == datetime(2026, 3, 30, tzinfo=LOCAL_TZ).date()


# ---------------------------------------------------------------------------
# week_bounds_utc — DST transition weeks (SPEC 9.4)
# ---------------------------------------------------------------------------


def test_week_bounds_dst_spring_2026():
    """Week containing 29 Mar 2026 (DST spring-forward) is 167 hours."""
    # 29 Mar 2026 is a Sunday.  The week starts on Monday 23 Mar.
    monday = datetime(2026, 3, 23).date()
    start_utc, end_utc = week_bounds_utc(monday)
    delta_hours = (end_utc - start_utc).total_seconds() / 3600
    assert delta_hours == 167


def test_week_bounds_dst_fall_2026():
    """Week containing 25 Oct 2026 (DST fall-back) is 169 hours."""
    # 25 Oct 2026 is a Sunday.  The week starts on Monday 19 Oct.
    monday = datetime(2026, 10, 19).date()
    start_utc, end_utc = week_bounds_utc(monday)
    delta_hours = (end_utc - start_utc).total_seconds() / 3600
    assert delta_hours == 169


# ---------------------------------------------------------------------------
# Sanity — normal (non-DST) week
# ---------------------------------------------------------------------------


def test_week_bounds_normal_week_is_168_hours():
    """A normal week without DST transition is exactly 168 hours."""
    monday = datetime(2026, 6, 1).date()  # 1 Jun 2026 is a Monday
    start_utc, end_utc = week_bounds_utc(monday)
    delta_hours = (end_utc - start_utc).total_seconds() / 3600
    assert delta_hours == 168


# ---------------------------------------------------------------------------
# week_start — normal dates
# ---------------------------------------------------------------------------


def test_week_start_returns_monday_date():
    """week_start returns the Monday's date for a Wednesday local datetime."""
    wed = datetime(2026, 3, 11, 14, 0, tzinfo=LOCAL_TZ)  # Wednesday
    assert week_start(wed) == datetime(2026, 3, 9, tzinfo=LOCAL_TZ).date()


def test_week_start_midnight_boundary():
    """Monday 00:00 belongs to the same week as Monday itself."""
    mon = datetime(2026, 3, 30, 0, 0, tzinfo=LOCAL_TZ)
    assert week_start(mon) == datetime(2026, 3, 30).date()


def test_week_start_sunday_midnight():
    """Sunday 00:00 belongs to the week that started the previous Monday."""
    sun = datetime(2026, 3, 29, 0, 0, tzinfo=LOCAL_TZ)
    assert week_start(sun) == datetime(2026, 3, 23).date()
