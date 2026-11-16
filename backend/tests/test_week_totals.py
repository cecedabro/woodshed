"""Tests for ``minutes_per_week`` and the home progress bar (SPEC 9.2, 9.4).

Functions: ``minutes_per_week`` in ``app.stats``.
"""

from datetime import UTC, date, datetime, timedelta

from app.clock import LOCAL_TZ
from app.models import PracticeSession, SessionBlock
from app.stats import minutes_per_week

# ---------------------------------------------------------------------------
# minutes_per_week — basic behaviour
# ---------------------------------------------------------------------------


def test_minutes_per_week_empty(db):
    """With no blocks, every Monday returns 0."""
    mondays = [date(2026, 3, 23), date(2026, 3, 30)]
    result = minutes_per_week(db, mondays)
    assert result == {mondays[0]: 0, mondays[1]: 0}


def test_minutes_per_week_empty_list(db):
    """An empty list of mondays returns an empty dict."""
    result = minutes_per_week(db, [])
    assert result == {}


def test_minutes_per_week_rounds_down(db):
    """Minutes are floor-divided (300 seconds = 5 minutes, not 5.0)."""
    now = datetime.now(LOCAL_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    monday = now.date() - timedelta(days=now.weekday())

    session = PracticeSession(started_at=now, ended_at=now)
    db.add(session)
    db.flush()

    # 305 seconds → 5 minutes (floor(305/60) = 5)
    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Test",
            position=0,
            planned_seconds=600,
            played_seconds=305,
            ended_at=now + timedelta(seconds=305),
        )
    )
    db.commit()

    result = minutes_per_week(db, [monday])
    assert result[monday] == 5


def test_minutes_per_week_sub_60_seconds_is_zero(db):
    """A block with played_seconds < 60 contributes 0 minutes."""
    now = datetime.now(LOCAL_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    monday = now.date() - timedelta(days=now.weekday())

    session = PracticeSession(started_at=now, ended_at=now)
    db.add(session)
    db.flush()

    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Short block",
            position=0,
            planned_seconds=60,
            played_seconds=59,
            ended_at=now + timedelta(seconds=59),
        )
    )
    db.commit()

    result = minutes_per_week(db, [monday])
    assert result[monday] == 0


# ---------------------------------------------------------------------------
# minutes_per_week — week boundary (SPEC 9.4)
# ---------------------------------------------------------------------------


def test_block_sunday_night_counts_in_current_week(db):
    """A block ending Sunday 23:30 local counts in that week."""
    # Sunday 29 March 2026 23:30 Amsterdam (before DST spring-forward)
    ended_at = datetime(2026, 3, 29, 23, 30, tzinfo=LOCAL_TZ)
    monday = datetime(2026, 3, 23, tzinfo=LOCAL_TZ).date()

    session = PracticeSession(started_at=ended_at - timedelta(minutes=10), ended_at=ended_at)
    db.add(session)
    db.flush()

    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Sunday night",
            position=0,
            planned_seconds=600,
            played_seconds=600,  # 10 minutes
            ended_at=ended_at,
        )
    )
    db.commit()

    result = minutes_per_week(db, [monday])
    assert result[monday] == 10


def test_block_monday_morning_counts_in_next_week(db):
    """A block ending Monday 00:10 local counts in the *next* week."""
    # Monday 30 March 2026 00:10 Amsterdam (new week starts)
    ended_at = datetime(2026, 3, 30, 0, 10, tzinfo=LOCAL_TZ)
    prev_monday = datetime(2026, 3, 23, tzinfo=LOCAL_TZ).date()
    next_monday = datetime(2026, 3, 30, tzinfo=LOCAL_TZ).date()

    session = PracticeSession(started_at=ended_at - timedelta(minutes=10), ended_at=ended_at)
    db.add(session)
    db.flush()

    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Monday early morning",
            position=0,
            planned_seconds=600,
            played_seconds=600,
            ended_at=ended_at,
        )
    )
    db.commit()

    result = minutes_per_week(db, [prev_monday, next_monday])
    assert result[prev_monday] == 0
    assert result[next_monday] == 10


def test_block_exact_monday_midnight_counts_in_that_week(db):
    """A block ending Monday 00:00 exactly counts in the week that starts that Monday."""
    mon_midnight = datetime(2026, 3, 30, 0, 0, tzinfo=LOCAL_TZ)
    next_monday = datetime(2026, 3, 30, tzinfo=LOCAL_TZ).date()
    prev_monday = datetime(2026, 3, 23, tzinfo=LOCAL_TZ).date()

    session = PracticeSession(started_at=mon_midnight - timedelta(minutes=5), ended_at=mon_midnight)
    db.add(session)
    db.flush()

    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Exact Monday",
            position=0,
            planned_seconds=300,
            played_seconds=300,
            ended_at=mon_midnight,
        )
    )
    db.commit()

    result = minutes_per_week(db, [prev_monday, next_monday])
    assert result[prev_monday] == 0
    assert result[next_monday] == 5


# ---------------------------------------------------------------------------
# minutes_per_week — multiple weeks
# ---------------------------------------------------------------------------


def test_minutes_per_week_accumulates_per_week(db):
    """Blocks on different days of the same week are summed."""
    mon = datetime(2026, 6, 1, tzinfo=LOCAL_TZ).date()  # 1 Jun 2026 is a Monday

    session = PracticeSession(
        started_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
        ended_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
    )
    db.add(session)
    db.flush()

    # Monday: 10 min, Tuesday: 20 min, Wednesday: 15 min
    for i, secs in enumerate([600, 1200, 900]):
        db.add(
            SessionBlock(
                session_id=session.id,
                item_id=None,
                item_title=f"Block {i}",
                position=i,
                planned_seconds=1800,
                played_seconds=secs,
                ended_at=datetime(2026, 6, 1, 8, i + 1, tzinfo=UTC) + timedelta(minutes=secs // 60),
            )
        )
    db.commit()

    result = minutes_per_week(db, [mon])
    # 10 + 20 + 15 = 45 minutes
    assert result[mon] == 45


def test_minutes_per_week_multiple_weeks_separate(db):
    """Blocks in different weeks are counted in their respective weeks."""
    mon_a = datetime(2026, 6, 1, tzinfo=LOCAL_TZ).date()
    mon_b = datetime(2026, 6, 8, tzinfo=LOCAL_TZ).date()

    session_a = PracticeSession(
        started_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
        ended_at=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
    )
    db.add(session_a)
    db.flush()

    session_b = PracticeSession(
        started_at=datetime(2026, 6, 8, 8, 0, tzinfo=UTC),
        ended_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )
    db.add(session_b)
    db.flush()

    # Week A blocks
    for i, secs in enumerate([600, 900]):
        db.add(
            SessionBlock(
                session_id=session_a.id,
                item_id=None,
                item_title=f"A{i}",
                position=i,
                planned_seconds=1800,
                played_seconds=secs,
                ended_at=datetime(2026, 6, 1, 10, i + 1, tzinfo=UTC),
            )
        )

    # Week B blocks
    for i, secs in enumerate([1200]):
        db.add(
            SessionBlock(
                session_id=session_b.id,
                item_id=None,
                item_title=f"B{i}",
                position=i,
                planned_seconds=1800,
                played_seconds=secs,
                ended_at=datetime(2026, 6, 9, 10, i + 1, tzinfo=UTC),
            )
        )

    db.commit()

    result = minutes_per_week(db, [mon_a, mon_b])
    assert result[mon_a] == 25  # 10 + 15
    assert result[mon_b] == 20  # 20


# ---------------------------------------------------------------------------
# minutes_per_week — blocks with zero/NULL played_seconds
# ---------------------------------------------------------------------------


def test_minutes_per_week_ignores_zero_played(db):
    """Blocks with played_seconds=0 are not counted."""
    now = datetime.now(LOCAL_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    monday = now.date() - timedelta(days=now.weekday())

    session = PracticeSession(started_at=now, ended_at=now)
    db.add(session)
    db.flush()

    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Zero block",
            position=0,
            planned_seconds=600,
            played_seconds=0,
            ended_at=now,
        )
    )
    db.commit()

    result = minutes_per_week(db, [monday])
    assert result[monday] == 0


def test_minutes_per_week_ignores_null_ended_at(db):
    """Blocks with NULL ended_at are not counted."""
    now = datetime.now(LOCAL_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    monday = now.date() - timedelta(days=now.weekday())

    session = PracticeSession(started_at=now, ended_at=now)
    db.add(session)
    db.flush()

    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Unfinished block",
            position=0,
            planned_seconds=600,
            played_seconds=300,
            ended_at=None,
        )
    )
    db.commit()

    result = minutes_per_week(db, [monday])
    assert result[monday] == 0


# ---------------------------------------------------------------------------
# minutes_per_week — DST weeks (SPEC 9.4)
# ---------------------------------------------------------------------------


def test_minutes_per_week_spring_forward(db):
    """Blocks around DST spring-forward (29 Mar 2026) are grouped correctly."""
    # Week containing 29 Mar 2026 starts on Monday 23 Mar
    spring_monday = datetime(2026, 3, 23, tzinfo=LOCAL_TZ).date()
    # Next week starts on Monday 30 Mar
    next_monday = datetime(2026, 3, 30, tzinfo=LOCAL_TZ).date()

    # Saturday 28 Mar 23:30 → week of 23 Mar
    ended_at_saturday = datetime(2026, 3, 28, 23, 30, tzinfo=LOCAL_TZ)
    session1 = PracticeSession(
        started_at=ended_at_saturday - timedelta(minutes=10),
        ended_at=ended_at_saturday,
    )
    db.add(session1)
    db.flush()
    db.add(
        SessionBlock(
            session_id=session1.id,
            item_id=None,
            item_title="Before DST",
            position=0,
            planned_seconds=600,
            played_seconds=600,
            ended_at=ended_at_saturday,
        )
    )

    # Sunday 29 Mar 01:30 local → still week of 23 Mar (DST happens at 2AM)
    ended_at_sunday = datetime(2026, 3, 29, 1, 30, tzinfo=LOCAL_TZ)
    session2 = PracticeSession(
        started_at=ended_at_sunday - timedelta(minutes=15),
        ended_at=ended_at_sunday,
    )
    db.add(session2)
    db.flush()
    db.add(
        SessionBlock(
            session_id=session2.id,
            item_id=None,
            item_title="After DST",
            position=0,
            planned_seconds=900,
            played_seconds=900,
            ended_at=ended_at_sunday,
        )
    )

    db.commit()

    result = minutes_per_week(db, [spring_monday, next_monday])
    assert result[spring_monday] == 25  # 10 + 15
    assert result[next_monday] == 0


# ---------------------------------------------------------------------------
# Home progress bar rendering
# ---------------------------------------------------------------------------


def test_home_shows_progress_bar(client, db):
    """The home page shows a <progress> element with value and max."""
    _login(client)

    resp = client.get("/")
    assert resp.status_code == 200
    assert "<progress" in resp.text
    assert 'value="0"' in resp.text
    assert 'max="120"' in resp.text


def test_home_progress_bar_text(client, db):
    """The home page shows \"X of Y min\" text."""
    _login(client)

    resp = client.get("/")
    assert resp.status_code == 200
    assert "0 of 120 min" in resp.text


def test_home_progress_bar_reflects_data(client, db):
    """The progress bar shows the correct minutes after session blocks are added."""
    # Set a goal of 120 minutes
    from app.models import Setting

    db.add(Setting(key="weekly_goal_minutes", value="120"))
    db.commit()

    now = datetime.now(LOCAL_TZ).replace(hour=14, minute=0, second=0, microsecond=0)

    session = PracticeSession(started_at=now - timedelta(hours=1), ended_at=now)
    db.add(session)
    db.flush()

    # 105 minutes = 6300 seconds
    db.add(
        SessionBlock(
            session_id=session.id,
            item_id=None,
            item_title="Week session",
            position=0,
            planned_seconds=7200,
            played_seconds=6300,
            ended_at=now,
        )
    )
    db.commit()

    _login(client)
    resp = client.get("/")

    assert resp.status_code == 200
    assert "105 of 120 min" in resp.text
    assert 'value="105"' in resp.text
    assert 'max="120"' in resp.text


def test_home_progress_bar_with_custom_goal(client, db):
    """The progress bar uses the stored goal, not the default."""
    from app.models import Setting

    db.add(Setting(key="weekly_goal_minutes", value="200"))
    db.commit()

    _login(client)
    resp = client.get("/")

    assert resp.status_code == 200
    assert 'max="200"' in resp.text
    assert "0 of 200 min" in resp.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
