"""Add dysfunction detail fields and cross-team dependencies table

Revision ID: 002
Revises: 001
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Add detail columns to dysfunction_configs ---

    # Low Quality Story
    op.add_column(
        "dysfunction_configs",
        sa.Column("low_quality_ba_po_touch_min", sa.Float(), nullable=False, server_default="1.5"),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column("low_quality_ba_po_touch_max", sa.Float(), nullable=False, server_default="2.5"),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column("low_quality_dev_touch_min", sa.Float(), nullable=False, server_default="1.2"),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column("low_quality_dev_touch_max", sa.Float(), nullable=False, server_default="1.8"),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column("low_quality_qa_touch_min", sa.Float(), nullable=False, server_default="1.5"),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column("low_quality_qa_touch_max", sa.Float(), nullable=False, server_default="3.0"),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "low_quality_ba_cycle_back_pct", sa.Float(), nullable=False, server_default="0.4"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "low_quality_qa_cycle_back_pct", sa.Float(), nullable=False, server_default="0.5"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "low_quality_bug_injection_boost_pct",
            sa.Float(),
            nullable=False,
            server_default="0.3",
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "low_quality_re_estimation_boost_pct",
            sa.Float(),
            nullable=False,
            server_default="0.4",
        ),
    )

    # Mid-Sprint Scope Add
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "scope_add_capacity_tax_min_pct", sa.Float(), nullable=False, server_default="0.85"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "scope_add_capacity_tax_max_pct", sa.Float(), nullable=False, server_default="0.95"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "scope_add_touch_multiplier_min", sa.Float(), nullable=False, server_default="1.1"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "scope_add_touch_multiplier_max", sa.Float(), nullable=False, server_default="1.3"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "scope_add_tax_duration_days_min", sa.Float(), nullable=False, server_default="1.0"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "scope_add_tax_duration_days_max", sa.Float(), nullable=False, server_default="2.0"
        ),
    )

    # Blocking Dependency
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "blocking_dep_escalation_wait_hours",
            sa.Float(),
            nullable=False,
            server_default="24.0",
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "blocking_dep_blocker_focus_multiplier",
            sa.Float(),
            nullable=False,
            server_default="0.8",
        ),
    )

    # Teammate Goes Dark
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "dark_teammate_duration_days_min", sa.Float(), nullable=False, server_default="2.0"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "dark_teammate_duration_days_max", sa.Float(), nullable=False, server_default="5.0"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "dark_teammate_reassignment_ramp_pct",
            sa.Float(),
            nullable=False,
            server_default="0.7",
        ),
    )

    # Re-estimation
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "re_estimation_sp_multiplier_min", sa.Float(), nullable=False, server_default="1.5"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "re_estimation_sp_multiplier_max", sa.Float(), nullable=False, server_default="2.5"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "re_estimation_descope_probability_pct",
            sa.Float(),
            nullable=False,
            server_default="0.7",
        ),
    )

    # Bug Injection
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "bug_injection_sp_weight_1", sa.Float(), nullable=False, server_default="0.5"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "bug_injection_sp_weight_2", sa.Float(), nullable=False, server_default="0.3"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "bug_injection_sp_weight_3", sa.Float(), nullable=False, server_default="0.2"
        ),
    )
    op.add_column(
        "dysfunction_configs",
        sa.Column(
            "bug_injection_interruption_tax_multiplier",
            sa.Float(),
            nullable=False,
            server_default="1.1",
        ),
    )

    # --- Create cross_team_dependencies table ---
    op.create_table(
        "cross_team_dependencies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_team_id", sa.Integer(), nullable=False),
        sa.Column("target_team_id", sa.Integer(), nullable=False),
        sa.Column("dependency_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["target_team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_team_id",
            "target_team_id",
            "dependency_type",
            name="uq_dependency_source_target_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("cross_team_dependencies")

    detail_columns = [
        "low_quality_ba_po_touch_min",
        "low_quality_ba_po_touch_max",
        "low_quality_dev_touch_min",
        "low_quality_dev_touch_max",
        "low_quality_qa_touch_min",
        "low_quality_qa_touch_max",
        "low_quality_ba_cycle_back_pct",
        "low_quality_qa_cycle_back_pct",
        "low_quality_bug_injection_boost_pct",
        "low_quality_re_estimation_boost_pct",
        "scope_add_capacity_tax_min_pct",
        "scope_add_capacity_tax_max_pct",
        "scope_add_touch_multiplier_min",
        "scope_add_touch_multiplier_max",
        "scope_add_tax_duration_days_min",
        "scope_add_tax_duration_days_max",
        "blocking_dep_escalation_wait_hours",
        "blocking_dep_blocker_focus_multiplier",
        "dark_teammate_duration_days_min",
        "dark_teammate_duration_days_max",
        "dark_teammate_reassignment_ramp_pct",
        "re_estimation_sp_multiplier_min",
        "re_estimation_sp_multiplier_max",
        "re_estimation_descope_probability_pct",
        "bug_injection_sp_weight_1",
        "bug_injection_sp_weight_2",
        "bug_injection_sp_weight_3",
        "bug_injection_interruption_tax_multiplier",
    ]
    for column_name in detail_columns:
        op.drop_column("dysfunction_configs", column_name)
