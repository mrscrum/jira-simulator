"""Engine rewrite — new columns for distribution-based simulation

Revision ID: 009
Revises: 008
Create Date: 2026-03-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

revision: str = "009"
down_revision: str = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_safe(table: str, column: sa.Column) -> None:
    """Add column, silently skip if it already exists."""
    try:
        op.add_column(table, column)
    except OperationalError:
        pass


def upgrade() -> None:
    # --- Teams: sprint capacity range and simulation config ---
    _add_column_safe(
        "teams",
        sa.Column(
            "sprint_capacity_min",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )
    _add_column_safe(
        "teams",
        sa.Column(
            "sprint_capacity_max",
            sa.Integer(),
            nullable=False,
            server_default="40",
        ),
    )
    _add_column_safe(
        "teams",
        sa.Column(
            "priority_randomization",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    _add_column_safe(
        "teams",
        sa.Column("first_sprint_start_date", sa.DateTime(), nullable=True),
    )
    _add_column_safe(
        "teams",
        sa.Column(
            "tick_duration_hours",
            sa.Float(),
            nullable=False,
            server_default="1.0",
        ),
    )

    # --- Issues: per-status distribution tracking ---
    _add_column_safe(
        "issues",
        sa.Column(
            "sampled_full_time",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    _add_column_safe(
        "issues",
        sa.Column(
            "sampled_work_time",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    _add_column_safe(
        "issues",
        sa.Column(
            "elapsed_full_time",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    _add_column_safe(
        "issues",
        sa.Column(
            "elapsed_work_time",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    _add_column_safe(
        "issues",
        sa.Column(
            "work_started",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )

    # --- Sprints: capacity target ---
    _add_column_safe(
        "sprints",
        sa.Column("capacity_target", sa.Integer(), nullable=True),
    )

    # --- TouchTimeConfig: full-time percentile columns ---
    _add_column_safe(
        "touch_time_configs",
        sa.Column("full_time_p25", sa.Float(), nullable=True),
    )
    _add_column_safe(
        "touch_time_configs",
        sa.Column("full_time_p50", sa.Float(), nullable=True),
    )
    _add_column_safe(
        "touch_time_configs",
        sa.Column("full_time_p99", sa.Float(), nullable=True),
    )

    # --- WorkflowStep: multiple roles support ---
    _add_column_safe(
        "workflow_steps",
        sa.Column("roles_json", sa.String(), nullable=True),
    )

    # --- Issues: epic support ---
    _add_column_safe(
        "issues",
        sa.Column(
            "epic_id",
            sa.Integer(),
            sa.ForeignKey("issues.id"),
            nullable=True,
        ),
    )

    # --- MoveLeftConfig: per-item-type ---
    _add_column_safe(
        "move_left_config",
        sa.Column("issue_type", sa.String(), nullable=True),
    )

    # --- Members: default WIP to 1 ---
    op.execute("UPDATE members SET max_concurrent_wip = 1")

    # --- Sprint phase cleanup: old phases → new phases ---
    op.execute(
        "UPDATE sprints SET phase = 'PLANNING' WHERE phase = 'BACKLOG_PREP'"
    )
    op.execute(
        "UPDATE sprints SET phase = 'COMPLETED' WHERE phase IN ('REVIEW', 'RETRO')"
    )


def downgrade() -> None:
    # Restore old sprint phases
    op.execute(
        "UPDATE sprints SET phase = 'BACKLOG_PREP' WHERE phase = 'PLANNING'"
    )
    op.execute(
        "UPDATE sprints SET phase = 'REVIEW' WHERE phase = 'COMPLETED'"
    )

    op.execute("UPDATE members SET max_concurrent_wip = 3")

    op.drop_column("move_left_config", "issue_type")
    op.drop_column("workflow_steps", "roles_json")
    op.drop_column("touch_time_configs", "full_time_p99")
    op.drop_column("touch_time_configs", "full_time_p50")
    op.drop_column("touch_time_configs", "full_time_p25")
    op.drop_column("sprints", "capacity_target")
    op.drop_column("issues", "work_started")
    op.drop_column("issues", "elapsed_work_time")
    op.drop_column("issues", "elapsed_full_time")
    op.drop_column("issues", "sampled_work_time")
    op.drop_column("issues", "sampled_full_time")
    op.drop_column("teams", "tick_duration_hours")
    op.drop_column("teams", "first_sprint_start_date")
    op.drop_column("teams", "priority_randomization")
    op.drop_column("teams", "sprint_capacity_max")
    op.drop_column("teams", "sprint_capacity_min")
    op.drop_column("issues", "epic_id")
