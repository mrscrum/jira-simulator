"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("jira_project_key", sa.String(), nullable=False),
        sa.Column("jira_board_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_project_key"),
    )

    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("daily_capacity_hours", sa.Float(), nullable=False),
        sa.Column("max_concurrent_wip", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id"),
    )

    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("jira_status", sa.String(), nullable=False),
        sa.Column("role_required", sa.String(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("max_wait_hours", sa.Float(), nullable=False),
        sa.Column("wip_contribution", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "order", name="uq_workflow_order"),
        sa.UniqueConstraint("workflow_id", "jira_status", name="uq_workflow_jira_status"),
    )

    op.create_table(
        "touch_time_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_step_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(), nullable=False),
        sa.Column("story_points", sa.Integer(), nullable=False),
        sa.Column("min_hours", sa.Float(), nullable=False),
        sa.Column("max_hours", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_step_id"], ["workflow_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_step_id", "issue_type", "story_points", name="uq_step_type_points"
        ),
    )

    op.create_table(
        "dysfunction_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("low_quality_probability", sa.Float(), nullable=False),
        sa.Column("scope_creep_probability", sa.Float(), nullable=False),
        sa.Column("blocking_dependency_probability", sa.Float(), nullable=False),
        sa.Column("dark_teammate_probability", sa.Float(), nullable=False),
        sa.Column("re_estimation_probability", sa.Float(), nullable=False),
        sa.Column("bug_injection_probability", sa.Float(), nullable=False),
        sa.Column("cross_team_block_probability", sa.Float(), nullable=False),
        sa.Column("cross_team_handoff_lag_probability", sa.Float(), nullable=False),
        sa.Column("cross_team_bug_probability", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id"),
    )

    op.create_table(
        "sprints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("jira_sprint_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("goal", sa.String(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("planned_velocity", sa.Integer(), nullable=True),
        sa.Column("actual_velocity", sa.Integer(), nullable=True),
        sa.Column("scope_change_points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("jira_issue_key", sa.String(), nullable=True),
        sa.Column("jira_issue_id", sa.String(), nullable=True),
        sa.Column("issue_type", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("story_points", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("current_workflow_step_id", sa.Integer(), nullable=True),
        sa.Column("current_worker_id", sa.Integer(), nullable=True),
        sa.Column("jira_assignee_id", sa.Integer(), nullable=True),
        sa.Column("jira_reporter_id", sa.Integer(), nullable=True),
        sa.Column("touch_time_remaining_hours", sa.Float(), nullable=False),
        sa.Column("wait_time_accumulated_hours", sa.Float(), nullable=False),
        sa.Column("total_cycle_time_hours", sa.Float(), nullable=False),
        sa.Column("sprint_id", sa.Integer(), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("blocked_by_issue_id", sa.Integer(), nullable=True),
        sa.Column("dysfunction_flags", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["current_workflow_step_id"], ["workflow_steps.id"]),
        sa.ForeignKeyConstraint(["current_worker_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["jira_assignee_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["jira_reporter_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"]),
        sa.ForeignKeyConstraint(["blocked_by_issue_id"], ["issues.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_issue_key"),
    )


def downgrade() -> None:
    op.drop_table("issues")
    op.drop_table("sprints")
    op.drop_table("dysfunction_configs")
    op.drop_table("touch_time_configs")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
    op.drop_table("members")
    op.drop_table("teams")
    op.drop_table("organizations")
