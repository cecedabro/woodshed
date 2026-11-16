"""Jinja2 environment and template filters (SPEC 10.1)."""

from datetime import datetime
from html import escape
from pathlib import Path

from fastapi import FastAPI
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.clock import LOCAL_TZ

TEMPLATES_DIR = Path(__file__).resolve().parents[0] / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
    enable_async=False,
)
env.globals["enumerate"] = enumerate


def get_theme(app: FastAPI) -> str:
    """Return the current theme setting ('amp', 'flat', or 'daylight').

    Defaults to ``'amp'`` when the database is unavailable or the setting
    is missing (SPEC 12.3).
    """
    try:
        with app.state.sessionmaker() as db:
            try:
                row = db.execute(
                    text("SELECT value FROM setting WHERE key = 'theme'")
                ).scalar_one_or_none()
            finally:
                db.close()
        return row if row else "amp"
    except SQLAlchemyError:
        return "amp"


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


def notes_br(text: str) -> str:
    """Escape HTML then convert newlines to <br> tags.

    Returns a Markup object so Jinja2 does not double-escape.
    """
    escaped = escape(text, quote=True)
    return Markup(escaped.replace("\n", "<br>"))  # nosec: B704 — input is escaped above


env.filters["notes_br"] = notes_br
