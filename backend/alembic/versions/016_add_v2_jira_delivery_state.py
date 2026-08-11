"""Add retryable v2 Jira delivery state.

Revision ID: 016
Revises: 015
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.v2.persistence.utc_datetime import UTCDateTime

revision: str = "016"
down_revision: str = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "v2_jira_delivery_receipts",
        sa.Column(
            "intent_id",
            sa.String(36),
            sa.ForeignKey("v2_projection_intents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", UTCDateTime(), nullable=True),
        sa.Column("last_attempt_at", UTCDateTime(), nullable=False),
        sa.Column("delivered_at", UTCDateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "state IN ('RETRYABLE','DELIVERED')", name="ck_v2_jira_receipts_state"
        ),
        sa.CheckConstraint("attempts >= 1", name="ck_v2_jira_receipts_attempts"),
        sa.CheckConstraint(
            "(state = 'RETRYABLE' AND next_attempt_at IS NOT NULL "
            "AND delivered_at IS NULL AND last_error IS NOT NULL) OR "
            "(state = 'DELIVERED' AND next_attempt_at IS NULL "
            "AND delivered_at IS NOT NULL AND last_error IS NULL)",
            name="ck_v2_jira_receipts_shape",
        ),
    )
    op.create_index(
        "ix_v2_jira_receipts_due",
        "v2_jira_delivery_receipts",
        ["state", "next_attempt_at"],
    )
    op.create_table(
        "v2_jira_resource_mappings",
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("v2_teams.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("internal_kind", sa.String(30), primary_key=True),
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("jira_id", sa.String(100), nullable=False),
        sa.Column("jira_key", sa.String(100), nullable=True),
        sa.UniqueConstraint(
            "team_id",
            "internal_kind",
            "jira_id",
            name="uq_v2_jira_mappings_provider_id",
        ),
        sa.UniqueConstraint(
            "team_id",
            "internal_kind",
            "jira_key",
            name="uq_v2_jira_mappings_provider_key",
        ),
    )
    op.create_index(
        "ix_v2_jira_mappings_provider_id",
        "v2_jira_resource_mappings",
        ["internal_kind", "jira_id"],
    )


def downgrade() -> None:
    op.drop_table("v2_jira_resource_mappings")
    op.drop_table("v2_jira_delivery_receipts")
