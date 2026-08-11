"""SQLAlchemy mappings for authoritative v2 Scrum state."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.v2.persistence.utc_datetime import UTCDateTime

MAX_SAFE_INTEGER = 2**53 - 1
MAX_COUNTER_NEXT_VALUE = 2**53
MAX_SQLITE_INTEGER = 2**63 - 1
MAX_FINITE_FLOAT = "1.7976931348623157e308"
RUN_OWNERSHIP = ("v2_runs.team_id", "v2_runs.id")
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


def _run_foreign_key(name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["team_id", "run_id"], RUN_OWNERSHIP, name=name, ondelete="CASCADE")


def _work_owner_foreign_key(name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["team_id", "run_id", "work_item_id"],
        ["v2_work_items.team_id", "v2_work_items.run_id", "v2_work_items.id"],
        name=name,
        ondelete="CASCADE",
    )


def _member_owner_foreign_key(name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["team_id", "member_id"],
        ["v2_member_identities.team_id", "v2_member_identities.id"],
        name=name,
        ondelete="CASCADE",
    )


class V2MemberIdentityModel(Base):
    __tablename__ = "v2_member_identities"
    __table_args__ = (
        UniqueConstraint("team_id", "blueprint_index", name="uq_v2_members_team_index"),
        UniqueConstraint("team_id", "id", name="uq_v2_members_team_id"),
        CheckConstraint(
            _integer_range("blueprint_index", MAX_SAFE_INTEGER),
            name="ck_v2_members_blueprint_index",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("v2_teams.id", ondelete="CASCADE"), nullable=False
    )
    blueprint_index: Mapped[int] = mapped_column(Integer, nullable=False)


class V2MemberAvailabilityOverlayModel(Base):
    __tablename__ = "v2_member_availability_overlays"
    __table_args__ = (
        _run_foreign_key("fk_v2_overlays_team_run"),
        ForeignKeyConstraint(
            ["team_id", "member_id"],
            ["v2_member_identities.team_id", "v2_member_identities.id"],
            name="fk_v2_overlays_team_member",
            ondelete="CASCADE",
        ),
        CheckConstraint("starts_at < ends_at", name="ck_v2_overlays_interval"),
        CheckConstraint(
            "availability_fraction BETWEEN 0 AND 1",
            name="ck_v2_overlays_fraction",
        ),
        CheckConstraint(
            "daily_capacity_ceiling_microseconds IS NULL OR ("
            + _integer_range("daily_capacity_ceiling_microseconds", MAX_SQLITE_INTEGER)
            + ")",
            name="ck_v2_overlays_capacity_ceiling",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    availability_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    daily_capacity_ceiling_microseconds: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class V2MemberBusinessDateConsumptionModel(Base):
    __tablename__ = "v2_member_business_date_consumption"
    __table_args__ = (
        _run_foreign_key("fk_v2_consumption_team_run"),
        ForeignKeyConstraint(
            ["team_id", "member_id"],
            ["v2_member_identities.team_id", "v2_member_identities.id"],
            name="fk_v2_consumption_team_member",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            _integer_range("consumed_labor_microseconds", MAX_SQLITE_INTEGER),
            name="ck_v2_consumption_nonnegative",
        ),
    )

    team_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    consumed_labor_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)


class V2WorkItemModel(Base):
    __tablename__ = "v2_work_items"
    __table_args__ = (
        _run_foreign_key("fk_v2_work_items_team_run"),
        UniqueConstraint(
            "team_id",
            "run_id",
            "creation_kind",
            "creation_sequence",
            name="uq_v2_work_items_creation",
        ),
        UniqueConstraint("team_id", "run_id", "id", name="uq_v2_work_items_identity"),
        CheckConstraint(
            _integer_range("creation_sequence", MAX_SAFE_INTEGER),
            name="ck_v2_work_items_creation_sequence",
        ),
        CheckConstraint(
            _integer_range("relative_rank", MAX_SAFE_INTEGER),
            name="ck_v2_work_items_relative_rank",
        ),
        CheckConstraint(
            "creation_kind IN ('INITIAL_BACKLOG','SCRUM_REPLENISHMENT','KANBAN_ARRIVAL',"
            "'AGENT_CREATED','JIRA_IMPORTED')",
            name="ck_v2_work_items_creation_kind",
        ),
        CheckConstraint(
            "issue_type IN ('STORY','BUG','TASK','SPIKE','ENABLER')",
            name="ck_v2_work_items_issue_type",
        ),
        CheckConstraint("story_points IN (1,2,3,5,8,13)", name="ck_v2_work_items_story_points"),
        CheckConstraint(
            "priority IN ('HIGHEST','HIGH','MEDIUM','LOW','LOWEST')",
            name="ck_v2_work_items_priority",
        ),
        CheckConstraint(
            "lifecycle IN ('BACKLOG','ACTIVE','DONE','CANCELLED')",
            name="ck_v2_work_items_lifecycle",
        ),
        CheckConstraint("created_at <= updated_at", name="ck_v2_work_items_times"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    creation_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    creation_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_type: Mapped[str] = mapped_column(String(20), nullable=False)
    story_points: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    relative_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(20), nullable=False)
    current_status_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class V2WorkItemFactorModel(Base):
    __tablename__ = "v2_work_item_factors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "run_id", "work_item_id"],
            ["v2_work_items.team_id", "v2_work_items.run_id", "v2_work_items.id"],
            name="fk_v2_factors_work_item",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "team_id",
            "run_id",
            "work_item_id",
            "kind",
            name="uq_v2_factors_item_kind",
        ),
        CheckConstraint(
            "kind IN ('DESCRIPTION_QUALITY','LATENT_COMPLEXITY')",
            name="ck_v2_factors_kind",
        ),
        CheckConstraint("value BETWEEN 0 AND 1", name="ck_v2_factors_value"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    work_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class V2SprintModel(Base):
    __tablename__ = "v2_sprints"
    __table_args__ = (
        _run_foreign_key("fk_v2_sprints_team_run"),
        UniqueConstraint("team_id", "run_id", "ordinal", name="uq_v2_sprints_ordinal"),
        UniqueConstraint("team_id", "run_id", "id", name="uq_v2_sprints_identity"),
        CheckConstraint(
            _integer_range("ordinal", MAX_SAFE_INTEGER), name="ck_v2_sprints_ordinal"
        ),
        CheckConstraint(
            "lifecycle IN ('PLANNED','ACTIVE','COMPLETED')",
            name="ck_v2_sprints_lifecycle",
        ),
        CheckConstraint("planned_start_at < planned_end_at", name="ck_v2_sprints_planned"),
        CheckConstraint(SPRINT_OBSERVED_CHECK, name="ck_v2_sprints_observed"),
        CheckConstraint("created_at <= updated_at", name="ck_v2_sprints_times"),
        Index(
            "ux_v2_sprints_one_active",
            "team_id",
            "run_id",
            unique=True,
            sqlite_where=text("lifecycle = 'ACTIVE'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(20), nullable=False)
    planned_start_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    planned_end_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    observed_start_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    observed_end_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class V2SprintScopeModel(Base):
    __tablename__ = "v2_sprint_scope"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "run_id", "sprint_id"],
            ["v2_sprints.team_id", "v2_sprints.run_id", "v2_sprints.id"],
            name="fk_v2_scope_sprint",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["team_id", "run_id", "work_item_id"],
            ["v2_work_items.team_id", "v2_work_items.run_id", "v2_work_items.id"],
            name="fk_v2_scope_work_item",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "team_id",
            "run_id",
            "sprint_id",
            "work_item_id",
            name="uq_v2_scope_sprint_item",
        ),
        CheckConstraint("removed_at IS NULL OR added_at <= removed_at", name="ck_v2_scope_times"),
        Index(
            "ux_v2_sprint_scope_current_item",
            "team_id",
            "run_id",
            "work_item_id",
            unique=True,
            sqlite_where=text("removed_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sprint_id: Mapped[str] = mapped_column(String(36), nullable=False)
    work_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    added_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class V2StatusVisitModel(Base):
    __tablename__ = "v2_status_visits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "run_id", "work_item_id"],
            ["v2_work_items.team_id", "v2_work_items.run_id", "v2_work_items.id"],
            name="fk_v2_visits_work_item",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["team_id", "member_id"],
            ["v2_member_identities.team_id", "v2_member_identities.id"],
            name="fk_v2_visits_team_member",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "team_id",
            "run_id",
            "work_item_id",
            "ordinal",
            name="uq_v2_visits_item_ordinal",
        ),
        UniqueConstraint("team_id", "run_id", "id", name="uq_v2_visits_identity"),
        UniqueConstraint(
            "team_id",
            "run_id",
            "id",
            "required_work_microseconds",
            name="uq_v2_visits_required_work",
        ),
        CheckConstraint(
            _integer_range("ordinal", MAX_SAFE_INTEGER),
            name="ck_v2_status_visits_ordinal",
        ),
        CheckConstraint("lifecycle IN ('OPEN','CLOSED')", name="ck_v2_status_visits_lifecycle"),
        CheckConstraint(VISIT_TIME_CHECK, name="ck_v2_status_visits_times"),
        CheckConstraint(VISIT_NONNEGATIVE_CHECK, name="ck_v2_status_visits_nonnegative"),
        CheckConstraint(
            "required_work_microseconds = elapsed_work_microseconds + remaining_work_microseconds",
            name="ck_v2_status_visits_work_balance",
        ),
        CheckConstraint(
            "lifecycle != 'CLOSED' OR remaining_work_microseconds = 0",
            name="ck_v2_status_visits_closed_remaining",
        ),
        Index(
            "ux_v2_status_visits_one_open",
            "team_id",
            "run_id",
            "work_item_id",
            unique=True,
            sqlite_where=text("lifecycle = 'OPEN'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    work_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(20), nullable=False)
    status_key: Mapped[str] = mapped_column(String(100), nullable=False)
    activity_key: Mapped[str] = mapped_column(String(100), nullable=False)
    member_id: Mapped[str | None] = mapped_column(String(36))
    entered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    required_work_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_work_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_work_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)
    pause_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)
    credited_labor_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)


class V2StatusVisitSampleModel(Base):
    __tablename__ = "v2_status_visit_samples"
    __table_args__ = (
        ForeignKeyConstraint(
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
        CheckConstraint(
            "dwell_unit_value BETWEEN 0 AND 1 AND touch_unit_value BETWEEN 0 AND 1",
            name="ck_v2_samples_unit_values",
        ),
        CheckConstraint(
            f"dwell_sampled_hours BETWEEN 0 AND {MAX_FINITE_FLOAT} AND "
            f"touch_sampled_hours BETWEEN 0 AND {MAX_FINITE_FLOAT}",
            name="ck_v2_samples_hours",
        ),
        CheckConstraint(
            _integer_range("required_work_microseconds", MAX_SQLITE_INTEGER),
            name="ck_v2_samples_required_work",
        ),
    )

    visit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    timing_profile: Mapped[str] = mapped_column(String(100), nullable=False)
    timing_profile_version: Mapped[str] = mapped_column(String(30), nullable=False)
    dwell_sampler_version: Mapped[str] = mapped_column(String(50), nullable=False)
    touch_sampler_version: Mapped[str] = mapped_column(String(50), nullable=False)
    dwell_parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    dwell_parameters_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    touch_parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    touch_parameters_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dwell_draw_json: Mapped[str] = mapped_column(Text, nullable=False)
    dwell_draw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    touch_draw_json: Mapped[str] = mapped_column(Text, nullable=False)
    touch_draw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dwell_unit_value: Mapped[float] = mapped_column(Float, nullable=False)
    touch_unit_value: Mapped[float] = mapped_column(Float, nullable=False)
    dwell_sampled_hours: Mapped[float] = mapped_column(Float, nullable=False)
    touch_sampled_hours: Mapped[float] = mapped_column(Float, nullable=False)
    required_work_microseconds: Mapped[int] = mapped_column(Integer, nullable=False)
    required_work_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class V2SemanticCounterModel(Base):
    __tablename__ = "v2_semantic_counters"
    __table_args__ = (
        _run_foreign_key("fk_v2_counters_team_run"),
        _work_owner_foreign_key("fk_v2_counters_work_item"),
        _member_owner_foreign_key("fk_v2_counters_member"),
        CheckConstraint(
            _integer_range("next_value", MAX_COUNTER_NEXT_VALUE),
            name="ck_v2_semantic_counters_next_value",
        ),
        CheckConstraint(COUNTER_SCOPE_CHECK, name="ck_v2_semantic_counters_scope"),
        CheckConstraint(COUNTER_OWNER_CHECK, name="ck_v2_semantic_counters_owner"),
    )

    team_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(60), primary_key=True)
    work_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    member_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False)


class V2NaturalDecisionEvaluationModel(Base):
    __tablename__ = "v2_natural_decision_evaluations"
    __table_args__ = (
        _run_foreign_key("fk_v2_evaluations_team_run"),
        _work_owner_foreign_key("fk_v2_evaluations_work_item"),
        _member_owner_foreign_key("fk_v2_evaluations_member"),
        UniqueConstraint(
            "team_id",
            "run_id",
            "decision_type",
            "semantic_entity_id",
            "business_date",
            name="uq_v2_evaluations_eligibility",
        ),
        UniqueConstraint(
            "team_id",
            "run_id",
            "decision_type",
            "semantic_entity_id",
            "occurrence",
            name="uq_v2_evaluations_occurrence",
        ),
        CheckConstraint(
            _integer_range("occurrence", MAX_SAFE_INTEGER),
            name="ck_v2_evaluations_occurrence",
        ),
        CheckConstraint(
            f"decision_type IN {NATURAL_DECISION_TYPES_SQL}",
            name="ck_v2_evaluations_decision_type",
        ),
        CheckConstraint(EVALUATION_OWNER_CHECK, name="ck_v2_evaluations_owner"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(60), nullable=False)
    semantic_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    work_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    member_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    occurrence: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_id: Mapped[str] = mapped_column(String(36), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
