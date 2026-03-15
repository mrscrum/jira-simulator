"""Create jira_issue_map table

Revision ID: 006
Revises: 005
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jira_issue_map",
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("jira_key", sa.String(), nullable=False),
        sa.Column("jira_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("issue_id"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"]),
        sa.UniqueConstraint("jira_key"),
    )


def downgrade() -> None:
    op.drop_table("jira_issue_map")
