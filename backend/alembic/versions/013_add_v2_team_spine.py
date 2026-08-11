"""Add isolated v2 team persistence spine.

Revision ID: 013
Revises: 012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.v2.persistence.utc_datetime import UTCDateTime

revision: str = "013"
down_revision: str = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "v2_teams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("blueprint_sha256", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("methodology", sa.String(20), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    )
    op.create_table(
        "v2_team_blueprints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("v2_teams.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("recorded_at", UTCDateTime(), nullable=False),
    )
    op.create_table(
        "v2_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("v2_teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.UniqueConstraint("team_id", "ordinal", name="uq_v2_runs_team_ordinal"),
    )
    op.create_table(
        "v2_team_runtimes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("v2_teams.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("v2_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("simulation_time", UTCDateTime(), nullable=False),
        sa.Column("next_wake_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("v2_team_runtimes")
    op.drop_table("v2_runs")
    op.drop_table("v2_team_blueprints")
    op.drop_table("v2_teams")
