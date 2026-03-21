"""Add story_points column to move_left_config

Revision ID: 010
Revises: 009
Create Date: 2026-03-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

revision: str = "010"
down_revision: str = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_safe(table: str, column: sa.Column) -> None:
    try:
        op.add_column(table, column)
    except OperationalError:
        pass


def upgrade() -> None:
    _add_column_safe(
        "move_left_config",
        sa.Column("story_points", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("move_left_config", "story_points")
