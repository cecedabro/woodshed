"""SQLAlchemy models. Every change here needs a new Alembic migration in the same task."""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# item
# ---------------------------------------------------------------------------


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(
        String,
        CheckConstraint("kind IN ('song', 'exercise')", name="ck_item_kind"),
    )
    title: Mapped[str] = mapped_column(String(200))
    artist: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String,
        CheckConstraint(
            "status IN ('learning', 'polishing', 'repertoire')",
            name="ck_item_status",
        ),
        default="learning",
    )
    current_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_url: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# attachment
# ---------------------------------------------------------------------------


class Attachment(Base):
    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(
        String,
        CheckConstraint("kind IN ('tab', 'pdf', 'audio')", name="ck_attachment_kind"),
    )
    label: Mapped[str] = mapped_column(String, default="")
    filename: Mapped[str] = mapped_column(String)
    stored_name: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    item: Mapped["Item"] = relationship(back_populates="attachments")


# ---------------------------------------------------------------------------
# setting
# ---------------------------------------------------------------------------


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
