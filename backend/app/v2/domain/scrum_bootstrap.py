"""Deterministic construction of the first persisted Scrum runtime state."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    item_rng_id,
    member_rng_id,
    sprint_rng_id,
    visit_rng_id,
)
from app.v2.domain.draw_source import DrawSource
from app.v2.domain.sampling import sample_touch, touch_bounds
from app.v2.domain.scrum_state import (
    MemberIdentity,
    ScrumStateWriteSet,
    SprintLifecycle,
    SprintScopeEntry,
    SprintState,
    StatusVisitLifecycle,
    StatusVisitSample,
    StatusVisitSampleInput,
    StatusVisitState,
    WorkItemLifecycle,
    WorkItemState,
    WorkPriority,
)
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint, WorkflowRouteStep
from app.v2.domain.team_runtime import PersistedTeamAggregate

MICROSECONDS_PER_HOUR = 3_600_000_000
INITIAL_SPRINT_ORDINAL = 0
INITIAL_VISIT_ORDINAL = 0


def build_initial_scrum_state(
    aggregate: PersistedTeamAggregate, started_at: datetime, draws: DrawSource
) -> ScrumStateWriteSet:
    """Build the first complete deterministic state for one persisted team run."""
    started = _utc(started_at)
    members = _member_identities(aggregate)
    work_items = _ranked_backlog(aggregate, started, draws)
    sprint = _active_sprint(aggregate, started)
    selected_ids = _selected_scope_ids(aggregate, sprint.id, work_items, draws)
    active_work, visits, samples = _activate_selected_work(
        aggregate, started, members, work_items, selected_ids, draws
    )
    scope = _scope_entries(aggregate, sprint.id, selected_ids, started)
    return ScrumStateWriteSet(
        member_identities=members,
        work_items=active_work,
        sprints=(sprint,),
        sprint_scope=scope,
        status_visits=visits,
        status_visit_samples=samples,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("started_at must be aware")
    return value.astimezone(UTC)


def _member_identities(aggregate: PersistedTeamAggregate) -> tuple[MemberIdentity, ...]:
    return tuple(
        MemberIdentity(member_rng_id(aggregate.team.id, index), aggregate.team.id, index)
        for index, _member in enumerate(aggregate.blueprint.members)
    )


def _ranked_backlog(
    aggregate: PersistedTeamAggregate, started_at: datetime, draws: DrawSource
) -> tuple[WorkItemState, ...]:
    return tuple(
        _backlog_item(aggregate, started_at, draws, sequence)
        for sequence in range(aggregate.blueprint.backlog.target_depth)
    )


def _backlog_item(
    aggregate: PersistedTeamAggregate, started_at: datetime, draws: DrawSource, sequence: int
) -> WorkItemState:
    item_id = item_rng_id(aggregate.team.id, CreationKind.INITIAL_BACKLOG, sequence)
    issue_type = _weighted_value(
        aggregate.blueprint.backlog.issue_type_weights.root,
        draws.draw(DecisionOccurrence(item_id, DecisionType.BACKLOG_ISSUE_TYPE, 0)).unit_value,
    )
    points_draw = draws.draw(DecisionOccurrence(item_id, DecisionType.BACKLOG_STORY_POINTS, 0))
    story_points = int(
        _weighted_value(
            aggregate.blueprint.backlog.story_point_weights.root, points_draw.unit_value
        )
    )
    priority = WorkPriority(
        _weighted_value(
            aggregate.blueprint.backlog.priority_weights.root,
            draws.draw(DecisionOccurrence(item_id, DecisionType.BACKLOG_PRIORITY, 0)).unit_value,
        )
    )
    initial_status = _route_for(aggregate.blueprint, issue_type).steps[0].status_key
    return WorkItemState(
        item_id,
        aggregate.team.id,
        aggregate.runtime.run_id,
        CreationKind.INITIAL_BACKLOG,
        sequence,
        issue_type,
        story_points,
        priority,
        sequence,
        WorkItemLifecycle.BACKLOG,
        initial_status,
        started_at,
        started_at,
    )


def _weighted_value(weights: object, unit_value: float) -> str:
    if not hasattr(weights, "items"):
        raise TypeError("weights must be a mapping")
    pairs = tuple(weights.items())
    total = sum(value for _key, value in pairs)
    threshold = unit_value * total
    cumulative = 0.0
    for key, value in pairs:
        cumulative += value
        if threshold < cumulative:
            return key
    return pairs[-1][0]


def _active_sprint(aggregate: PersistedTeamAggregate, started_at: datetime) -> SprintState:
    scrum = aggregate.blueprint.scrum
    planned_start = scrum.first_boundary
    planned_end = planned_start + timedelta(days=scrum.cadence_days)
    return SprintState(
        sprint_rng_id(aggregate.team.id, INITIAL_SPRINT_ORDINAL),
        aggregate.team.id,
        aggregate.runtime.run_id,
        INITIAL_SPRINT_ORDINAL,
        SprintLifecycle.ACTIVE,
        planned_start,
        planned_end,
        started_at,
        None,
        started_at,
        started_at,
    )


def _selected_scope_ids(
    aggregate: PersistedTeamAggregate,
    sprint_id: UUID,
    work_items: tuple[WorkItemState, ...],
    draws: DrawSource,
) -> frozenset[UUID]:
    scrum = aggregate.blueprint.scrum
    draw = draws.draw(DecisionOccurrence(sprint_id, DecisionType.SCRUM_CAPACITY_TARGET, 0))
    capacity = scrum.capacity_min_points + int(
        draw.unit_value * (scrum.capacity_max_points - scrum.capacity_min_points + 1)
    )
    selected: list[UUID] = []
    used_points = 0
    for item in sorted(work_items, key=lambda candidate: candidate.simulator_rank):
        if used_points + item.story_points <= capacity:
            selected.append(item.id)
            used_points += item.story_points
    return frozenset(selected)


def _activate_selected_work(
    aggregate: PersistedTeamAggregate,
    started_at: datetime,
    members: tuple[MemberIdentity, ...],
    work_items: tuple[WorkItemState, ...],
    selected_ids: frozenset[UUID],
    draws: DrawSource,
) -> tuple[tuple[WorkItemState, ...], tuple[StatusVisitState, ...], tuple[StatusVisitSample, ...]]:
    activated: list[WorkItemState] = []
    visits: list[StatusVisitState] = []
    samples: list[StatusVisitSample] = []
    for item in work_items:
        if item.id not in selected_ids:
            activated.append(item)
            continue
        active_item, visit, sample = _activate_item(aggregate, started_at, members, item, draws)
        activated.append(active_item)
        if visit is not None and sample is not None:
            visits.append(visit)
            samples.append(sample)
    return tuple(activated), tuple(visits), tuple(samples)


def _activate_item(
    aggregate: PersistedTeamAggregate,
    started_at: datetime,
    members: tuple[MemberIdentity, ...],
    item: WorkItemState,
    draws: DrawSource,
) -> tuple[WorkItemState, StatusVisitState | None, StatusVisitSample | None]:
    route = _route_for(aggregate.blueprint, item.issue_type)
    timed_step = next(
        (step for step in route.steps if _is_timed_step(aggregate.blueprint, step)), None
    )
    if timed_step is None:
        terminal_status = route.steps[-1].status_key
        return _active_item(item, terminal_status, WorkItemLifecycle.DONE, started_at), None, None
    active_item = _active_item(item, timed_step.status_key, WorkItemLifecycle.ACTIVE, started_at)
    visit = _timed_visit(aggregate, started_at, members, active_item, timed_step, draws)
    sample = _status_sample(aggregate.blueprint, active_item, visit, draws)
    return active_item, visit, sample


def _is_timed_step(blueprint: ResolvedTeamBlueprint, step: WorkflowRouteStep) -> bool:
    status = next(status for status in blueprint.workflow.statuses if status.key == step.status_key)
    return status.consumes_capacity and step.required_activity is not None


def _active_item(
    item: WorkItemState, status_key: str, lifecycle: WorkItemLifecycle, started_at: datetime
) -> WorkItemState:
    return WorkItemState(
        item.id,
        item.team_id,
        item.run_id,
        item.creation_kind,
        item.creation_sequence,
        item.issue_type,
        item.story_points,
        item.priority,
        item.relative_rank,
        lifecycle,
        status_key,
        item.created_at,
        started_at,
    )


def _timed_visit(
    aggregate: PersistedTeamAggregate,
    started_at: datetime,
    members: tuple[MemberIdentity, ...],
    item: WorkItemState,
    step: WorkflowRouteStep,
    draws: DrawSource,
) -> StatusVisitState:
    visit_id = visit_rng_id(item.id, INITIAL_VISIT_ORDINAL)
    touch_draw = draws.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_TOUCH, 0))
    required = _sampled_microseconds(
        aggregate.blueprint, item, step.status_key, touch_draw.unit_value
    )
    return StatusVisitState(
        visit_id,
        item.team_id,
        item.run_id,
        item.id,
        INITIAL_VISIT_ORDINAL,
        StatusVisitLifecycle.OPEN,
        step.status_key,
        step.required_activity,
        _member_for_activity(aggregate.blueprint, members, step.required_activity),
        started_at,
        None,
        required,
        0,
        required,
        0,
        0,
        0,
    )


def _sampled_microseconds(
    blueprint: ResolvedTeamBlueprint, item: WorkItemState, status_key: str, unit_value: float
) -> int:
    entry = next(
        entry
        for entry in blueprint.timing.entries
        if (entry.status_key, entry.issue_type, entry.story_points)
        == (status_key, item.issue_type, item.story_points)
    )
    sampled_hours = sample_touch(touch_bounds(entry), unit_value).sampled_hours
    numerator, denominator = sampled_hours.as_integer_ratio()
    rounded, remainder = divmod(numerator * MICROSECONDS_PER_HOUR, denominator)
    if remainder * 2 > denominator or (remainder * 2 == denominator and rounded % 2):
        rounded += 1
    return rounded


def _member_for_activity(
    blueprint: ResolvedTeamBlueprint, members: tuple[MemberIdentity, ...], activity: str | None
) -> UUID:
    if activity is None:
        raise ValueError("timed route steps must require an activity")
    for identity in members:
        responsibilities = blueprint.members[identity.blueprint_index].responsibilities
        if activity in {responsibility.activity for responsibility in responsibilities}:
            return identity.id
    raise ValueError("timed route activity must have a persisted member")


def _status_sample(
    blueprint: ResolvedTeamBlueprint,
    item: WorkItemState,
    visit: StatusVisitState,
    draws: DrawSource,
) -> StatusVisitSample:
    dwell = draws.draw(DecisionOccurrence(visit.id, DecisionType.STATUS_DWELL, 0))
    touch = draws.draw(DecisionOccurrence(visit.id, DecisionType.STATUS_TOUCH, 0))
    return StatusVisitSample.create(StatusVisitSampleInput(blueprint, item, visit, dwell, touch))


def _scope_entries(
    aggregate: PersistedTeamAggregate,
    sprint_id: UUID,
    selected_ids: frozenset[UUID],
    started_at: datetime,
) -> tuple[SprintScopeEntry, ...]:
    return tuple(
        SprintScopeEntry(
            semantic_uuid(f"sprint-scope/{sprint_id}/{item_id}"),
            aggregate.team.id,
            aggregate.runtime.run_id,
            sprint_id,
            item_id,
            started_at,
            None,
        )
        for item_id in sorted(selected_ids)
    )


def _route_for(blueprint: ResolvedTeamBlueprint, issue_type: str):
    return next(route for route in blueprint.workflow.routes if route.issue_type == issue_type)
