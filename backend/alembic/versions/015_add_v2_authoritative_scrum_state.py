"""Add authoritative v2 Scrum state.

Revision ID: 015
Revises: 014
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.v2.persistence.utc_datetime import UTCDateTime

revision: str = "015"
down_revision: str = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_SAFE_INTEGER = 2**53 - 1
MAX_COUNTER_NEXT_VALUE = 2**53
MAX_SQLITE_INTEGER = 2**63 - 1
MAX_FINITE_FLOAT = "1.7976931348623157e308"
RUN_REFERENCE = ["v2_runs.team_id", "v2_runs.id"]
NATURAL_DECISION_TYPES_SQL = (
    "('RISK_CANCELLATION_OUTCOME','RISK_MEMBER_UNAVAILABLE_OUTCOME')"
)
SPRINT_OBSERVED_CHECK = (
    "(lifecycle = 'PLANNED' AND observed_start_at IS NULL AND observed_end_at IS NULL) OR "
    "(lifecycle = 'ACTIVE' AND observed_start_at IS NOT NULL AND observed_end_at IS NULL) OR "
    "(lifecycle = 'COMPLETED' AND observed_start_at IS NOT NULL AND "
    "observed_end_at IS NOT NULL AND observed_start_at <= observed_end_at)"
)
VISIT_TIME_CHECK = (
    "(lifecycle = 'OPEN' AND closed_at IS NULL) OR "
    "(lifecycle = 'CLOSED' AND closed_at IS NOT NULL AND entered_at <= closed_at)"
)


def _integer_range(column: str, maximum: int) -> str:
    return f"typeof({column}) = 'integer' AND {column} BETWEEN 0 AND {maximum}"


VISIT_NONNEGATIVE_CHECK = " AND ".join(
    _integer_range(column, MAX_SQLITE_INTEGER)
    for column in (
        "required_work_microseconds",
        "elapsed_work_microseconds",
        "remaining_work_microseconds",
        "queue_microseconds",
        "pause_microseconds",
        "credited_labor_microseconds",
    )
)
COUNTER_SCOPE_CHECK = (
    "(kind = 'SPRINT_ORDINAL' AND scope_id = team_id AND scope_key = 'SCRUM') OR "
    "(kind = 'ITEM_SEQUENCE' AND scope_id = team_id AND scope_key IN "
    "('INITIAL_BACKLOG','SCRUM_REPLENISHMENT','KANBAN_ARRIVAL',"
    "'AGENT_CREATED','JIRA_IMPORTED')) OR "
    "(kind = 'VISIT_ORDINAL' AND scope_key = 'VISIT') OR "
    f"(kind = 'NATURAL_DECISION_OCCURRENCE' AND scope_key IN {NATURAL_DECISION_TYPES_SQL})"
)
COUNTER_OWNER_CHECK = (
    "(kind IN ('SPRINT_ORDINAL','ITEM_SEQUENCE') "
    "AND work_item_id IS NULL AND member_id IS NULL) OR "
    "(kind = 'VISIT_ORDINAL' AND scope_id = work_item_id AND work_item_id IS NOT NULL "
    "AND member_id IS NULL) OR "
    "(kind = 'NATURAL_DECISION_OCCURRENCE' AND scope_key = 'RISK_CANCELLATION_OUTCOME' "
    "AND scope_id = work_item_id AND work_item_id IS NOT NULL AND member_id IS NULL) OR "
    "(kind = 'NATURAL_DECISION_OCCURRENCE' AND scope_key = "
    "'RISK_MEMBER_UNAVAILABLE_OUTCOME' AND scope_id = member_id AND member_id IS NOT NULL "
    "AND work_item_id IS NULL)"
)
EVALUATION_OWNER_CHECK = (
    "(decision_type = 'RISK_CANCELLATION_OUTCOME' AND semantic_entity_id = work_item_id "
    "AND work_item_id IS NOT NULL AND member_id IS NULL) OR "
    "(decision_type = 'RISK_MEMBER_UNAVAILABLE_OUTCOME' AND semantic_entity_id = member_id "
    "AND member_id IS NOT NULL AND work_item_id IS NULL)"
)


def upgrade() -> None:
    op.create_index("ux_v2_runs_team_id", "v2_runs", ["team_id", "id"], unique=True)
    _create_member_identities()
    _create_member_overlays()
    _create_member_consumption()
    _create_work_items()
    _create_work_item_factors()
    _create_sprints()
    _create_sprint_scope()
    _create_status_visits()
    _create_status_visit_samples()
    _create_semantic_counters()
    _create_natural_evaluations()


def _run_foreign_key(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["team_id", "run_id"], RUN_REFERENCE, name=name, ondelete="CASCADE"
    )


def _create_member_identities() -> None:
    op.create_table(
        "v2_member_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("v2_teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("blueprint_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("team_id", "blueprint_index", name="uq_v2_members_team_index"),
        sa.UniqueConstraint("team_id", "id", name="uq_v2_members_team_id"),
        sa.CheckConstraint(
            _integer_range("blueprint_index", MAX_SAFE_INTEGER),
            name="ck_v2_members_blueprint_index",
        ),
    )


def _member_owner_foreign_key(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["team_id", "member_id"],
        ["v2_member_identities.team_id", "v2_member_identities.id"],
        name=name,
        ondelete="CASCADE",
    )


def _create_member_overlays() -> None:
    op.create_table(
        "v2_member_availability_overlays",
        *_overlay_columns(),
        _run_foreign_key("fk_v2_overlays_team_run"),
        _member_owner_foreign_key("fk_v2_overlays_team_member"),
        sa.CheckConstraint("starts_at < ends_at", name="ck_v2_overlays_interval"),
        sa.CheckConstraint("availability_fraction BETWEEN 0 AND 1", name="ck_v2_overlays_fraction"),
        sa.CheckConstraint(
            "daily_capacity_ceiling_microseconds IS NULL OR ("
            + _integer_range("daily_capacity_ceiling_microseconds", MAX_SQLITE_INTEGER)
            + ")",
            name="ck_v2_overlays_capacity_ceiling",
        ),
    )


def _overlay_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("starts_at", UTCDateTime(), nullable=False),
        sa.Column("ends_at", UTCDateTime(), nullable=False),
        sa.Column("availability_fraction", sa.Float(), nullable=False),
        sa.Column("daily_capacity_ceiling_microseconds", sa.Integer()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("provenance_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    ]


def _create_member_consumption() -> None:
    op.create_table(
        "v2_member_business_date_consumption",
        sa.Column("team_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("member_id", sa.String(36), primary_key=True),
        sa.Column("business_date", sa.Date(), primary_key=True),
        sa.Column("consumed_labor_microseconds", sa.Integer(), nullable=False),
        _run_foreign_key("fk_v2_consumption_team_run"),
        _member_owner_foreign_key("fk_v2_consumption_team_member"),
        sa.CheckConstraint(
            _integer_range("consumed_labor_microseconds", MAX_SQLITE_INTEGER),
            name="ck_v2_consumption_nonnegative",
        ),
    )


def _create_work_items() -> None:
    op.create_table(
        "v2_work_items",
        *_work_item_columns(),
        _run_foreign_key("fk_v2_work_items_team_run"),
        *_work_item_constraints(),
    )


def _work_item_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("creation_kind", sa.String(40), nullable=False),
        sa.Column("creation_sequence", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(20), nullable=False),
        sa.Column("story_points", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("relative_rank", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(20), nullable=False),
        sa.Column("current_status_key", sa.String(100), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def _work_item_constraints() -> list[sa.Constraint]:
    return [
        sa.UniqueConstraint(
            "team_id",
            "run_id",
            "creation_kind",
            "creation_sequence",
            name="uq_v2_work_items_creation",
        ),
        sa.UniqueConstraint("team_id", "run_id", "id", name="uq_v2_work_items_identity"),
        sa.CheckConstraint(
            _integer_range("creation_sequence", MAX_SAFE_INTEGER),
            name="ck_v2_work_items_creation_sequence",
        ),
        sa.CheckConstraint(
            _integer_range("relative_rank", MAX_SAFE_INTEGER),
            name="ck_v2_work_items_relative_rank",
        ),
        *_work_item_enum_constraints(),
        sa.CheckConstraint("created_at <= updated_at", name="ck_v2_work_items_times"),
    ]


def _work_item_enum_constraints() -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "creation_kind IN ('INITIAL_BACKLOG','SCRUM_REPLENISHMENT','KANBAN_ARRIVAL',"
            "'AGENT_CREATED','JIRA_IMPORTED')",
            name="ck_v2_work_items_creation_kind",
        ),
        sa.CheckConstraint(
            "issue_type IN ('STORY','BUG','TASK','SPIKE','ENABLER')",
            name="ck_v2_work_items_issue_type",
        ),
        sa.CheckConstraint("story_points IN (1,2,3,5,8,13)", name="ck_v2_work_items_story_points"),
        sa.CheckConstraint(
            "priority IN ('HIGHEST','HIGH','MEDIUM','LOW','LOWEST')",
            name="ck_v2_work_items_priority",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('BACKLOG','ACTIVE','DONE','CANCELLED')",
            name="ck_v2_work_items_lifecycle",
        ),
    ]


def _work_item_foreign_key(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["team_id", "run_id", "work_item_id"],
        ["v2_work_items.team_id", "v2_work_items.run_id", "v2_work_items.id"],
        name=name,
        ondelete="CASCADE",
    )


def _create_work_item_factors() -> None:
    op.create_table(
        "v2_work_item_factors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("work_item_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("provenance_sha256", sa.String(64), nullable=False),
        sa.Column("recorded_at", UTCDateTime(), nullable=False),
        _work_item_foreign_key("fk_v2_factors_work_item"),
        sa.UniqueConstraint(
            "team_id",
            "run_id",
            "work_item_id",
            "kind",
            name="uq_v2_factors_item_kind",
        ),
        sa.CheckConstraint(
            "kind IN ('DESCRIPTION_QUALITY','LATENT_COMPLEXITY')",
            name="ck_v2_factors_kind",
        ),
        sa.CheckConstraint("value BETWEEN 0 AND 1", name="ck_v2_factors_value"),
    )


def _create_sprints() -> None:
    op.create_table(
        "v2_sprints",
        *_sprint_columns(),
        _run_foreign_key("fk_v2_sprints_team_run"),
        *_sprint_constraints(),
    )
    op.create_index(
        "ux_v2_sprints_one_active",
        "v2_sprints",
        ["team_id", "run_id"],
        unique=True,
        sqlite_where=sa.text("lifecycle = 'ACTIVE'"),
    )


def _sprint_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(20), nullable=False),
        sa.Column("planned_start_at", UTCDateTime(), nullable=False),
        sa.Column("planned_end_at", UTCDateTime(), nullable=False),
        sa.Column("observed_start_at", UTCDateTime()),
        sa.Column("observed_end_at", UTCDateTime()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def _sprint_constraints() -> list[sa.Constraint]:
    return [
        sa.UniqueConstraint("team_id", "run_id", "ordinal", name="uq_v2_sprints_ordinal"),
        sa.UniqueConstraint("team_id", "run_id", "id", name="uq_v2_sprints_identity"),
        sa.CheckConstraint(
            _integer_range("ordinal", MAX_SAFE_INTEGER), name="ck_v2_sprints_ordinal"
        ),
        sa.CheckConstraint(
            "lifecycle IN ('PLANNED','ACTIVE','COMPLETED')",
            name="ck_v2_sprints_lifecycle",
        ),
        sa.CheckConstraint("planned_start_at < planned_end_at", name="ck_v2_sprints_planned"),
        sa.CheckConstraint(SPRINT_OBSERVED_CHECK, name="ck_v2_sprints_observed"),
        sa.CheckConstraint("created_at <= updated_at", name="ck_v2_sprints_times"),
    ]


def _create_sprint_scope() -> None:
    op.create_table(
        "v2_sprint_scope",
        *_scope_columns(),
        *_scope_constraints(),
    )
    op.create_index(
        "ux_v2_sprint_scope_current_item",
        "v2_sprint_scope",
        ["team_id", "run_id", "work_item_id"],
        unique=True,
        sqlite_where=sa.text("removed_at IS NULL"),
    )


def _scope_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("sprint_id", sa.String(36), nullable=False),
        sa.Column("work_item_id", sa.String(36), nullable=False),
        sa.Column("added_at", UTCDateTime(), nullable=False),
        sa.Column("removed_at", UTCDateTime()),
    ]


def _scope_constraints() -> list[sa.Constraint]:
    return [
        sa.ForeignKeyConstraint(
            ["team_id", "run_id", "sprint_id"],
            ["v2_sprints.team_id", "v2_sprints.run_id", "v2_sprints.id"],
            name="fk_v2_scope_sprint",
            ondelete="CASCADE",
        ),
        _work_item_foreign_key("fk_v2_scope_work_item"),
        sa.UniqueConstraint(
            "team_id",
            "run_id",
            "sprint_id",
            "work_item_id",
            name="uq_v2_scope_sprint_item",
        ),
        sa.CheckConstraint(
            "removed_at IS NULL OR added_at <= removed_at", name="ck_v2_scope_times"
        ),
    ]


def _create_status_visits() -> None:
    op.create_table(
        "v2_status_visits",
        *_visit_columns(),
        *_visit_constraints(),
    )
    op.create_index(
        "ux_v2_status_visits_one_open",
        "v2_status_visits",
        ["team_id", "run_id", "work_item_id"],
        unique=True,
        sqlite_where=sa.text("lifecycle = 'OPEN'"),
    )


def _visit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("work_item_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(20), nullable=False),
        sa.Column("status_key", sa.String(100), nullable=False),
        sa.Column("activity_key", sa.String(100), nullable=True),
        sa.Column("member_id", sa.String(36)),
        sa.Column("entered_at", UTCDateTime(), nullable=False),
        sa.Column("closed_at", UTCDateTime()),
        sa.Column("required_work_microseconds", sa.Integer(), nullable=False),
        sa.Column("elapsed_work_microseconds", sa.Integer(), nullable=False),
        sa.Column("remaining_work_microseconds", sa.Integer(), nullable=False),
        sa.Column("queue_microseconds", sa.Integer(), nullable=False),
        sa.Column("pause_microseconds", sa.Integer(), nullable=False),
        sa.Column("credited_labor_microseconds", sa.Integer(), nullable=False),
    ]


def _visit_constraints() -> list[sa.Constraint]:
    return [
        _work_item_foreign_key("fk_v2_visits_work_item"),
        _member_owner_foreign_key("fk_v2_visits_team_member"),
        *_visit_unique_constraints(),
        *_visit_check_constraints(),
    ]


def _visit_unique_constraints() -> list[sa.Constraint]:
    return [
        sa.UniqueConstraint(
            "team_id",
            "run_id",
            "work_item_id",
            "ordinal",
            name="uq_v2_visits_item_ordinal",
        ),
        sa.UniqueConstraint("team_id", "run_id", "id", name="uq_v2_visits_identity"),
        sa.UniqueConstraint(
            "team_id",
            "run_id",
            "id",
            "required_work_microseconds",
            name="uq_v2_visits_required_work",
        ),
    ]


def _visit_check_constraints() -> list[sa.Constraint]:
    return [
        sa.CheckConstraint(
            _integer_range("ordinal", MAX_SAFE_INTEGER),
            name="ck_v2_status_visits_ordinal",
        ),
        sa.CheckConstraint("lifecycle IN ('OPEN','CLOSED')", name="ck_v2_status_visits_lifecycle"),
        sa.CheckConstraint(VISIT_TIME_CHECK, name="ck_v2_status_visits_times"),
        sa.CheckConstraint(VISIT_NONNEGATIVE_CHECK, name="ck_v2_status_visits_nonnegative"),
        sa.CheckConstraint(
            "required_work_microseconds = elapsed_work_microseconds + remaining_work_microseconds",
            name="ck_v2_status_visits_work_balance",
        ),
        sa.CheckConstraint(
            "lifecycle != 'CLOSED' OR remaining_work_microseconds = 0",
            name="ck_v2_status_visits_closed_remaining",
        ),
    ]


def _create_status_visit_samples() -> None:
    op.create_table(
        "v2_status_visit_samples",
        *_sample_columns(),
        sa.ForeignKeyConstraint(
            ["team_id", "run_id", "visit_id", "required_work_microseconds"],
            [
                "v2_status_visits.team_id",
                "v2_status_visits.run_id",
                "v2_status_visits.id",
                "v2_status_visits.required_work_microseconds",
            ],
            name="fk_v2_samples_visit",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "dwell_unit_value BETWEEN 0 AND 1 AND touch_unit_value BETWEEN 0 AND 1",
            name="ck_v2_samples_unit_values",
        ),
        sa.CheckConstraint(
            f"dwell_sampled_hours BETWEEN 0 AND {MAX_FINITE_FLOAT} AND "
            f"touch_sampled_hours BETWEEN 0 AND {MAX_FINITE_FLOAT}",
            name="ck_v2_samples_hours",
        ),
        sa.CheckConstraint(
            _integer_range("required_work_microseconds", MAX_SQLITE_INTEGER),
            name="ck_v2_samples_required_work",
        ),
    )


def _sample_columns() -> list[sa.Column]:
    return [
        sa.Column("visit_id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("timing_profile", sa.String(100), nullable=False),
        sa.Column("timing_profile_version", sa.String(30), nullable=False),
        sa.Column("dwell_sampler_version", sa.String(50), nullable=False),
        sa.Column("touch_sampler_version", sa.String(50), nullable=False),
        sa.Column("dwell_parameters_json", sa.Text(), nullable=False),
        sa.Column("dwell_parameters_sha256", sa.String(64), nullable=False),
        sa.Column("touch_parameters_json", sa.Text(), nullable=False),
        sa.Column("touch_parameters_sha256", sa.String(64), nullable=False),
        sa.Column("dwell_draw_json", sa.Text(), nullable=False),
        sa.Column("dwell_draw_sha256", sa.String(64), nullable=False),
        sa.Column("touch_draw_json", sa.Text(), nullable=False),
        sa.Column("touch_draw_sha256", sa.String(64), nullable=False),
        sa.Column("dwell_unit_value", sa.Float(), nullable=False),
        sa.Column("touch_unit_value", sa.Float(), nullable=False),
        sa.Column("dwell_sampled_hours", sa.Float(), nullable=False),
        sa.Column("touch_sampled_hours", sa.Float(), nullable=False),
        sa.Column("required_work_microseconds", sa.Integer(), nullable=False),
        sa.Column("required_work_sha256", sa.String(64), nullable=False),
    ]


def _create_semantic_counters() -> None:
    op.create_table(
        "v2_semantic_counters",
        sa.Column("team_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), primary_key=True),
        sa.Column("scope_id", sa.String(36), primary_key=True),
        sa.Column("scope_key", sa.String(60), primary_key=True),
        sa.Column("work_item_id", sa.String(36), nullable=True),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column("next_value", sa.Integer(), nullable=False),
        _run_foreign_key("fk_v2_counters_team_run"),
        _work_item_foreign_key("fk_v2_counters_work_item"),
        _member_owner_foreign_key("fk_v2_counters_member"),
        sa.CheckConstraint(
            _integer_range("next_value", MAX_COUNTER_NEXT_VALUE),
            name="ck_v2_semantic_counters_next_value",
        ),
        sa.CheckConstraint(COUNTER_SCOPE_CHECK, name="ck_v2_semantic_counters_scope"),
        sa.CheckConstraint(COUNTER_OWNER_CHECK, name="ck_v2_semantic_counters_owner"),
    )


def _create_natural_evaluations() -> None:
    op.create_table(
        "v2_natural_decision_evaluations",
        *_evaluation_columns(),
        _run_foreign_key("fk_v2_evaluations_team_run"),
        _work_item_foreign_key("fk_v2_evaluations_work_item"),
        _member_owner_foreign_key("fk_v2_evaluations_member"),
        *_evaluation_constraints(),
    )


def _evaluation_constraints() -> list[sa.Constraint]:
    return [
        sa.UniqueConstraint(
            "team_id",
            "run_id",
            "decision_type",
            "semantic_entity_id",
            "business_date",
            name="uq_v2_evaluations_eligibility",
        ),
        sa.UniqueConstraint(
            "team_id",
            "run_id",
            "decision_type",
            "semantic_entity_id",
            "occurrence",
            name="uq_v2_evaluations_occurrence",
        ),
        sa.CheckConstraint(
            _integer_range("occurrence", MAX_SAFE_INTEGER),
            name="ck_v2_evaluations_occurrence",
        ),
        sa.CheckConstraint(
            f"decision_type IN {NATURAL_DECISION_TYPES_SQL}",
            name="ck_v2_evaluations_decision_type",
        ),
        sa.CheckConstraint(EVALUATION_OWNER_CHECK, name="ck_v2_evaluations_owner"),
    ]


def _evaluation_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("decision_type", sa.String(60), nullable=False),
        sa.Column("semantic_entity_id", sa.String(36), nullable=False),
        sa.Column("work_item_id", sa.String(36), nullable=True),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("occurrence", sa.Integer(), nullable=False),
        sa.Column("commit_id", sa.String(36), nullable=False),
        sa.Column("recorded_at", UTCDateTime(), nullable=False),
    ]


def downgrade() -> None:
    op.drop_table("v2_natural_decision_evaluations")
    op.drop_table("v2_semantic_counters")
    op.drop_table("v2_status_visit_samples")
    op.drop_table("v2_status_visits")
    op.drop_table("v2_sprint_scope")
    op.drop_table("v2_sprints")
    op.drop_table("v2_work_item_factors")
    op.drop_table("v2_work_items")
    op.drop_table("v2_member_business_date_consumption")
    op.drop_table("v2_member_availability_overlays")
    op.drop_table("v2_member_identities")
    op.drop_index("ux_v2_runs_team_id", table_name="v2_runs")
