"""Add atomic v2 live-slice ledgers and runtime versioning.

Revision ID: 014
Revises: 013
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.v2.persistence.utc_datetime import UTCDateTime

revision: str = "014"
down_revision: str = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _add_runtime_version()
    _create_activity_events()
    _create_ground_truth_records()
    _create_projection_intents()


def _add_runtime_version() -> None:
    with op.batch_alter_table("v2_team_runtimes") as batch:
        batch.add_column(sa.Column("version", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE v2_team_runtimes SET version = 0"))
    with op.batch_alter_table("v2_team_runtimes", recreate="always") as batch:
        batch.alter_column("version", existing_type=sa.Integer(), nullable=False)


def _envelope_columns() -> list[sa.Column]:
    return [
        sa.Column("append_sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("semantic_key", sa.String(255), nullable=False),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("v2_teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("v2_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_id", sa.String(36), nullable=False),
        sa.Column("transaction_sequence", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("occurred_at", UTCDateTime(), nullable=False),
        sa.Column("recorded_at", UTCDateTime(), nullable=False),
        sa.Column("canonical_payload", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
    ]


def _envelope_constraints(table_key: str) -> list[sa.Constraint]:
    return [
        sa.UniqueConstraint("id", name=f"uq_v2_{table_key}_id"),
        sa.UniqueConstraint("semantic_key", name=f"uq_v2_{table_key}_semantic_key"),
        sa.CheckConstraint(
            "transaction_sequence >= 0", name=f"ck_v2_{table_key}_transaction_sequence"
        ),
    ]


def _create_activity_events() -> None:
    columns = [
        *_envelope_columns(),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
    ]
    constraints = [
        *_envelope_constraints("activity_events"),
        sa.CheckConstraint("aggregate_version >= 0", name="ck_v2_activity_aggregate_version"),
    ]
    op.create_table("v2_activity_events", *columns, *constraints, sqlite_autoincrement=True)
    _create_append_indexes("activity", "v2_activity_events")


def _create_ground_truth_records() -> None:
    columns = [
        *_envelope_columns(),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("provenance_type", sa.String(50), nullable=False),
    ]
    constraints = _envelope_constraints("ground_truth_records")
    op.create_table("v2_ground_truth_records", *columns, *constraints, sqlite_autoincrement=True)
    _create_append_indexes("ground_truth", "v2_ground_truth_records")


def _create_projection_intents() -> None:
    columns = [
        *_envelope_columns(),
        sa.Column("target_kind", sa.String(50), nullable=False),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    ]
    constraints = [
        *_envelope_constraints("projection_intents"),
        sa.CheckConstraint("aggregate_version >= 0", name="ck_v2_projection_aggregate_version"),
        sa.CheckConstraint("status = 'PENDING'", name="ck_v2_projection_pending"),
    ]
    op.create_table("v2_projection_intents", *columns, *constraints, sqlite_autoincrement=True)
    _create_append_indexes("projection", "v2_projection_intents")
    op.create_index(
        "ix_v2_projection_pending",
        "v2_projection_intents",
        ["team_id", "status", "append_sequence"],
    )


def _create_append_indexes(index_key: str, table_name: str) -> None:
    op.create_index(
        f"ix_v2_{index_key}_team_append", table_name, ["team_id", "append_sequence"]
    )
    op.create_index(
        f"ix_v2_{index_key}_team_run_append",
        table_name,
        ["team_id", "run_id", "append_sequence"],
    )


def downgrade() -> None:
    op.drop_table("v2_projection_intents")
    op.drop_table("v2_ground_truth_records")
    op.drop_table("v2_activity_events")
    with op.batch_alter_table("v2_team_runtimes", recreate="always") as batch:
        batch.drop_column("version")
