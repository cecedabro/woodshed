"""practice

Revision ID: b3cda3472b74
Revises: 0002
Create Date: 2026-11-15 13:12:11.023040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3cda3472b74"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "routine",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "routine_block",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("routine_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["routine_id"],
            ["routine.id"],
            name=op.f("fk_routine_block_routine_id_routine"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["item.id"],
            name=op.f("fk_routine_block_item_id_item"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("routine_id", "position", name="uq_routine_block_routine_position"),
    )

    op.create_table(
        "practice_session",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("routine_id", sa.Integer(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["routine_id"],
            ["routine.id"],
            name=op.f("fk_practice_session_routine_id_routine"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "session_block",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("planned_seconds", sa.Integer(), nullable=False),
        sa.Column("played_seconds", sa.Integer(), nullable=False),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_session.id"],
            name=op.f("fk_session_block_session_id_practice_session"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["item.id"],
            name=op.f("fk_session_block_item_id_item"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_session_block_ended_at", "session_block", ["ended_at"])
    op.create_index("ix_session_block_item_id_ended_at", "session_block", ["item_id", "ended_at"])

    op.create_table(
        "take",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("session_block_id", sa.Integer(), nullable=True),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["item.id"],
            name=op.f("fk_take_item_id_item"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_block_id"],
            ["session_block.id"],
            name=op.f("fk_take_session_block_id_session_block"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("take")
    op.drop_index("ix_session_block_item_id_ended_at", table_name="session_block")
    op.drop_index("ix_session_block_ended_at", table_name="session_block")
    op.drop_table("session_block")
    op.drop_table("practice_session")
    op.drop_table("routine_block")
    op.drop_table("routine")
