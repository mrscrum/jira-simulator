"""Add timing templates and status_category

Revision ID: 011
Revises: 010
Create Date: 2026-03-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

revision: str = "011"
down_revision: str = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_safe(table: str, column: sa.Column) -> None:
    try:
        op.add_column(table, column)
    except OperationalError:
        pass


def upgrade() -> None:
    _add_column_safe(
        "workflow_steps",
        sa.Column("status_category", sa.String(), nullable=True),
    )

    op.create_table(
        "timing_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("spread_factor", sa.Float(), nullable=False, server_default="0.33"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "timing_template_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("timing_templates.id"),
            nullable=False,
        ),
        sa.Column("issue_type", sa.String(), nullable=False),
        sa.Column("story_points", sa.Integer(), nullable=False),
        sa.Column("ct_min", sa.Float(), nullable=False),
        sa.Column("ct_q1", sa.Float(), nullable=False),
        sa.Column("ct_median", sa.Float(), nullable=False),
        sa.Column("ct_q3", sa.Float(), nullable=False),
        sa.Column("ct_max", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "template_id", "issue_type", "story_points",
            name="uq_template_type_points",
        ),
    )


def downgrade() -> None:
    op.drop_table("timing_template_entries")
    op.drop_table("timing_templates")
    op.drop_column("workflow_steps", "status_category")
