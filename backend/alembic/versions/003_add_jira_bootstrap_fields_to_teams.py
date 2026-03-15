"""Add jira bootstrap fields to teams

Revision ID: 003
Revises: 002
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "jira_bootstrapped",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "teams",
        sa.Column("jira_bootstrap_warnings", sa.String(), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("jira_bootstrapped_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teams", "jira_bootstrapped_at")
    op.drop_column("teams", "jira_bootstrap_warnings")
    op.drop_column("teams", "jira_bootstrapped")
