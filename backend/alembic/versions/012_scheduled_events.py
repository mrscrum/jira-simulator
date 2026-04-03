"""Add scheduled events, audit log, precomputation runs, and sprint cadence

Revision ID: 012
Revises: 011
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

revision: str = "012"
down_revision: str = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_safe(table: str, column: sa.Column) -> None:
    """Add a column, ignoring if it already exists (idempotent for SQLite)."""
    try:
        op.add_column(table, column)
    except OperationalError:
        pass


def upgrade() -> None:
    # -- New table: scheduled_events --
    op.create_table(
        "scheduled_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("sprint_id", sa.Integer(), sa.ForeignKey("sprints.id"), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("sim_tick", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_reason", sa.String(), nullable=True),
        sa.Column("modified_at", sa.DateTime(), nullable=True),
        sa.Column("original_payload", sa.JSON(), nullable=True),
        sa.Column("original_scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_scheduled_events_batch_id",
        "scheduled_events",
        ["batch_id"],
    )
    op.create_index(
        "ix_scheduled_events_dispatch_lookup",
        "scheduled_events",
        ["team_id", "sprint_id", "status", "scheduled_at"],
    )

    # -- New table: precomputation_runs --
    op.create_table(
        "precomputation_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(), nullable=False, unique=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("sprint_id", sa.Integer(), sa.ForeignKey("sprints.id"), nullable=False),
        sa.Column("rng_seed", sa.Integer(), nullable=False),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("total_ticks", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("superseded_by", sa.Integer(), sa.ForeignKey("precomputation_runs.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # -- New table: event_audit_log --
    op.create_table(
        "event_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scheduled_event_id", sa.Integer(), sa.ForeignKey("scheduled_events.id"), nullable=False),
        sa.Column("jira_queue_entry_id", sa.String(), sa.ForeignKey("jira_write_queue.id"), nullable=True),
        sa.Column("expected_at", sa.DateTime(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verification_status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("alert_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_event_audit_log_verification",
        "event_audit_log",
        ["verification_status", "expected_at"],
    )

    # -- Add sprint cadence columns to teams --
    _add_column_safe("teams", sa.Column("sprint_cadence_rule", sa.String(), nullable=True))
    _add_column_safe("teams", sa.Column("sprint_cadence_time", sa.String(), nullable=True))
    _add_column_safe("teams", sa.Column("sprint_auto_schedule", sa.Boolean(), nullable=False, server_default="true"))

    # -- Add scheduled_event_id to jira_write_queue --
    # Note: using _add_column_safe for idempotency on SQLite test databases.
    # On PostgreSQL this is a normal ALTER TABLE ADD COLUMN.
    _add_column_safe(
        "jira_write_queue",
        sa.Column("scheduled_event_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("event_audit_log")
    op.drop_table("precomputation_runs")
    op.drop_table("scheduled_events")
