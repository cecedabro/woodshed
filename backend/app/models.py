"""SQLAlchemy models. Every change here needs a new Alembic migration in the same task."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
