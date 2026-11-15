"""Jinja2 environment and template filters (SPEC 10.1)."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.clock import LOCAL_TZ

TEMPLATES_DIR = Path(__file__).resolve().parents[0] / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
    enable_async=False,
)


def local_time(dt: datetime) -> str:
    """Render a datetime in Europe/Amsterdam as 'Tue 3 Nov, 19:05'.

    If *dt* is naive, assume it is already local time.
    """
    local = dt.astimezone(LOCAL_TZ) if dt.tzinfo is not None else dt

    day_abbr = local.strftime("%a")
    day = local.day
    mon = local.strftime("%b")
    hour = local.strftime("%H")
    minute = local.strftime("%M")
    return f"{day_abbr} {day} {mon}, {hour}:{minute}"


env.filters["local_time"] = local_time
