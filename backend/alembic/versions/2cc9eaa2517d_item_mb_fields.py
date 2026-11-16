"""item_mb_fields

Revision ID: 2cc9eaa2517d
Revises: b3cda3472b74
Create Date: 2026-11-16 17:30:29.785443
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2cc9eaa2517d"
down_revision: str | None = "b3cda3472b74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "item",
        sa.Column("year", sa.Integer(), nullable=True),
    )
    op.add_column(
        "item",
        sa.Column("mbid", sa.String(), nullable=True),
    )
    op.add_column(
        "item",
        sa.Column("release_group_id", sa.String(), nullable=True),
    )
    op.add_column(
        "item",
        sa.Column("has_cover", sa.Boolean(), nullable=False, server_default="f"),
    )


def downgrade() -> None:
    op.drop_column("item", "has_cover")
    op.drop_column("item", "release_group_id")
    op.drop_column("item", "mbid")
    op.drop_column("item", "year")
