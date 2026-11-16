"""SQLAlchemy models. Every change here needs a new Alembic migration in the same task."""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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


# ---------------------------------------------------------------------------
# routine
# ---------------------------------------------------------------------------


class Routine(Base):
    __tablename__ = "routine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    blocks: Mapped[list["RoutineBlock"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", order_by="RoutineBlock.position"
    )
    sessions: Mapped[list["PracticeSession"]] = relationship(back_populates="routine")


# ---------------------------------------------------------------------------
# routine_block
# ---------------------------------------------------------------------------


class RoutineBlock(Base):
    __tablename__ = "routine_block"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    routine_id: Mapped[int] = mapped_column(Integer, ForeignKey("routine.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id", ondelete="CASCADE"))
    minutes: Mapped[int] = mapped_column(Integer)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("routine_id", "position", name="uq_routine_block_routine_position"),
    )

    routine: Mapped["Routine"] = relationship(back_populates="blocks")
    item: Mapped["Item"] = relationship(back_populates="routine_blocks")


# ---------------------------------------------------------------------------
# practice_session
# ---------------------------------------------------------------------------


class PracticeSession(Base):
    __tablename__ = "practice_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    routine_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("routine.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    routine: Mapped["Routine"] = relationship(back_populates="sessions")
    blocks: Mapped[list["SessionBlock"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# session_block
# ---------------------------------------------------------------------------


class SessionBlock(Base):
    __tablename__ = "session_block"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("practice_session.id", ondelete="CASCADE")
    )
    item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("item.id", ondelete="SET NULL"), nullable=True
    )
    item_title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)
    planned_seconds: Mapped[int] = mapped_column(Integer)
    played_seconds: Mapped[int] = mapped_column(Integer)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_session_block_ended_at", "ended_at"),
        Index("ix_session_block_item_id_ended_at", "item_id", "ended_at"),
    )

    session: Mapped["PracticeSession"] = relationship(back_populates="blocks")
    takes: Mapped[list["Take"]] = relationship(
        back_populates="session_block", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# take
# ---------------------------------------------------------------------------


class Take(Base):
    __tablename__ = "take"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id", ondelete="CASCADE"))
    session_block_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("session_block.id", ondelete="SET NULL"), nullable=True
    )
    stored_name: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String, default="")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    item: Mapped["Item"] = relationship(back_populates="takes")
    session_block: Mapped["SessionBlock"] = relationship(back_populates="takes")


# ---------------------------------------------------------------------------
# Extra relationships on Item
# ---------------------------------------------------------------------------

Item.routine_blocks = relationship(
    "RoutineBlock", back_populates="item", cascade="all, delete-orphan"
)
Item.takes = relationship("Take", back_populates="item", cascade="all, delete-orphan")
