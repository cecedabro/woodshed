"""The one place that reads the clock.

Use it as `from app import clock` and call `clock.now()` (not `from app.clock import now`),
so tests can `monkeypatch.setattr("app.clock.now", lambda: FIXED)`.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Amsterdam")


def now() -> datetime:
    """Current time, timezone-aware UTC."""
    return datetime.now(UTC)
