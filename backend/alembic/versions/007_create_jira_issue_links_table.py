"""Create jira_issue_links table

Revision ID: 007
Revises: 006
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jira_issue_links",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("from_issue_id", sa.Integer(), nullable=False),
        sa.Column("to_issue_id", sa.Integer(), nullable=False),
        sa.Column("link_type", sa.String(), nullable=False),
        sa.Column("jira_link_id", sa.String(), nullable=True),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="PENDING"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["from_issue_id"], ["issues.id"]),
        sa.ForeignKeyConstraint(["to_issue_id"], ["issues.id"]),
    )


def downgrade() -> None:
    op.drop_table("jira_issue_links")
