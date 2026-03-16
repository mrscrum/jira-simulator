"""Stage 4 schema — simulation engine tables and column additions

Revision ID: 008
Revises: 007
Create Date: 2026-03-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: str = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Team new columns ---
    op.add_column(
        "teams",
        sa.Column(
            "sprint_length_days",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "sprint_planning_strategy",
            sa.String(),
            nullable=False,
            server_default="capacity_fitted",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "backlog_depth_target",
            sa.Integer(),
            nullable=False,
            server_default="40",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "pause_before_planning",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "working_hours_start",
            sa.Integer(),
            nullable=False,
            server_default="9",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "working_hours_end",
            sa.Integer(),
            nullable=False,
            server_default="17",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "timezone",
            sa.String(),
            nullable=False,
            server_default="UTC",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "holidays",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
    )

    # --- Member new column ---
    op.add_column(
        "members",
        sa.Column("timezone", sa.String(), nullable=True),
    )

    # --- Sprint new columns ---
    op.add_column(
        "sprints",
        sa.Column(
            "phase",
            sa.String(),
            nullable=False,
            server_default="BACKLOG_PREP",
        ),
    )
    op.add_column(
        "sprints",
        sa.Column("sprint_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sprints",
        sa.Column("committed_points", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sprints",
        sa.Column("completed_points", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sprints",
        sa.Column(
            "carried_over_points",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "sprints",
        sa.Column("velocity", sa.Float(), nullable=True),
    )
    op.add_column(
        "sprints",
        sa.Column(
            "goal_at_risk",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )

    # --- Issue new columns ---
    op.add_column(
        "issues",
        sa.Column("backlog_priority", sa.Integer(), nullable=True),
    )
    op.add_column(
        "issues",
        sa.Column(
            "carried_over",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "issues",
        sa.Column(
            "descoped",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "issues",
        sa.Column("split_from_id", sa.Integer(), nullable=True),
    )
    # SQLite does not support ALTER ADD CONSTRAINT for foreign keys.
    # The FK is enforced at the ORM level. A batch migration could be
    # used to recreate the table, but the cost outweighs the benefit
    # for a self-referential nullable FK.

    # --- New tables ---
    op.create_table(
        "simulation_event_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default="1"
        ),
        sa.Column("probability", sa.Float(), nullable=True),
        sa.Column("params", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
    )

    op.create_table(
        "simulation_event_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("sprint_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("sim_day", sa.Integer(), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column(
            "jira_written", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"]),
    )

    op.create_table(
        "move_left_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("from_step_id", sa.Integer(), nullable=False),
        sa.Column("base_probability", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["from_step_id"], ["workflow_steps.id"]),
    )

    op.create_table(
        "move_left_targets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("move_left_config_id", sa.Integer(), nullable=False),
        sa.Column("to_step_id", sa.Integer(), nullable=False),
        sa.Column(
            "weight", sa.Float(), nullable=False, server_default="1.0"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["move_left_config_id"], ["move_left_config.id"]
        ),
        sa.ForeignKeyConstraint(["to_step_id"], ["workflow_steps.id"]),
    )

    op.create_table(
        "move_left_same_step_statuses",
        sa.Column("move_left_config_id", sa.Integer(), nullable=False),
        sa.Column("status_name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("move_left_config_id", "status_name"),
        sa.ForeignKeyConstraint(
            ["move_left_config_id"], ["move_left_config.id"]
        ),
    )

    op.create_table(
        "daily_capacity_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("total_hours", sa.Float(), nullable=False),
        sa.Column("consumed_hours", sa.Float(), nullable=False),
        sa.Column("active_wip_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
    )


def downgrade() -> None:
    op.drop_table("daily_capacity_log")
    op.drop_table("move_left_same_step_statuses")
    op.drop_table("move_left_targets")
    op.drop_table("move_left_config")
    op.drop_table("simulation_event_log")
    op.drop_table("simulation_event_config")

    op.drop_column("issues", "split_from_id")
    op.drop_column("issues", "descoped")
    op.drop_column("issues", "carried_over")
    op.drop_column("issues", "backlog_priority")

    op.drop_column("sprints", "goal_at_risk")
    op.drop_column("sprints", "velocity")
    op.drop_column("sprints", "carried_over_points")
    op.drop_column("sprints", "completed_points")
    op.drop_column("sprints", "committed_points")
    op.drop_column("sprints", "sprint_number")
    op.drop_column("sprints", "phase")

    op.drop_column("members", "timezone")

    op.drop_column("teams", "holidays")
    op.drop_column("teams", "timezone")
    op.drop_column("teams", "working_hours_end")
    op.drop_column("teams", "working_hours_start")
    op.drop_column("teams", "pause_before_planning")
    op.drop_column("teams", "backlog_depth_target")
    op.drop_column("teams", "sprint_planning_strategy")
    op.drop_column("teams", "sprint_length_days")
