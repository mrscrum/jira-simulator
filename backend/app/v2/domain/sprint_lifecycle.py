"""Pure fixed-boundary Scrum lifecycle transitions."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.authoritative_slice import (
    EligibleNaturalDecisionClaim,
    SemanticCounterClaim,
)
from app.v2.domain.business_calendar import BusinessCalendar, CadenceRule, cadence_boundary
from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.deterministic_rng import DecisionOccurrence, DecisionType, sprint_rng_id
from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.live_slice import (
    ActivityDetails,
    ActivityEventDraft,
    DraftEnvelope,
    GroundTruthDetails,
    GroundTruthRecordDraft,
    ProjectionDetails,
    ProjectionIntentDraft,
)
from app.v2.domain.scrum_bootstrap import (
    _activate_selected_work,
    _selected_scope_ids,
)
from app.v2.domain.scrum_state import (
    ScrumStateWriteSet,
    SemanticCounterKind,
    SemanticCounterScope,
    SprintLifecycle,
    SprintScopeEntry,
    SprintState,
    StatusVisitSample,
    StatusVisitState,
    WorkItemLifecycle,
    WorkItemState,
)


@dataclass(frozen=True)
class SprintTransition:
    state: ScrumStateWriteSet
    activity: tuple[ActivityEventDraft, ...]
    ground_truth: tuple[GroundTruthRecordDraft, ...]
    projection_intents: tuple[ProjectionIntentDraft, ...]
    counter_claims: tuple[SemanticCounterClaim, ...]
    natural_decision_claims: tuple[EligibleNaturalDecisionClaim, ...]


@dataclass(frozen=True)
class _PlannedScope:
    work_items: tuple[WorkItemState, ...]
    scope: tuple[SprintScopeEntry, ...]
    visits: tuple[StatusVisitState, ...]
    samples: tuple[StatusVisitSample, ...]
    claims: tuple[SemanticCounterClaim, ...]


@dataclass(frozen=True)
class _PlanningContext:
    state: LiveTeamState
    sprint_id: UUID
    selected_ids: tuple[UUID, ...]
    boundary: datetime
    draws: SeededDrawSource


@dataclass(frozen=True)
class _ScopeContext:
    state: LiveTeamState
    sprint_id: UUID
    work_item_ids: tuple[UUID, ...]
    boundary: datetime


@dataclass(frozen=True)
class _TransitionContext:
    state: LiveTeamState
    write_set: ScrumStateWriteSet
    claims: tuple[SemanticCounterClaim, ...]
    previous: SprintState
    current: SprintState
    boundary: datetime


def cross_sprint_boundary(state: LiveTeamState, boundary: datetime) -> SprintTransition:
    """Activate or roll one sprint exactly at its persisted fixed boundary."""
    instant = _utc(boundary)
    planned = next(
        (
            sprint
            for sprint in state.scrum.sprints
            if sprint.lifecycle is SprintLifecycle.PLANNED and sprint.planned_start_at == instant
        ),
        None,
    )
    if planned is not None:
        return _activate_planned_sprint(state, planned, instant)
    active = next(
        (
            sprint
            for sprint in state.scrum.sprints
            if sprint.lifecycle is SprintLifecycle.ACTIVE and sprint.planned_end_at == instant
        ),
        None,
    )
    if active is not None:
        return _roll_active_sprint(state, active, instant)
    return _empty_transition()


def _activate_planned_sprint(
    state: LiveTeamState, sprint: SprintState, boundary: datetime
) -> SprintTransition:
    draws = SeededDrawSource(state.aggregate)
    selected = _selected_scope_ids(state.aggregate, sprint.id, state.scrum.work_items, draws)
    ordered = tuple(
        item.id
        for item in sorted(state.scrum.work_items, key=lambda item: item.simulator_rank)
        if item.id in selected
    )
    plan = _planned_scope(_PlanningContext(state, sprint.id, ordered, boundary, draws))
    activated = replace(
        sprint,
        lifecycle=SprintLifecycle.ACTIVE,
        observed_start_at=boundary,
        updated_at=boundary,
    )
    write_set = ScrumStateWriteSet(
        work_items=plan.work_items,
        sprints=(activated,),
        sprint_scope=plan.scope,
        status_visits=plan.visits,
        status_visit_samples=plan.samples,
    )
    context = _TransitionContext(state, write_set, plan.claims, sprint, activated, boundary)
    return _activation_transition(context)


def _roll_active_sprint(
    state: LiveTeamState, sprint: SprintState, boundary: datetime
) -> SprintTransition:
    successor, sprint_claim = _successor(state, sprint, boundary)
    carry_ids = _carryover_ids(state, sprint.id)
    backlog_ids = _ranked_backlog_ids(state, successor.id, carry_ids)
    plan = _planned_scope(
        _PlanningContext(
            state, successor.id, backlog_ids, boundary, SeededDrawSource(state.aggregate)
        )
    )
    completed = _completed_sprint(sprint, boundary)
    closed_scope = tuple(
        replace(entry, removed_at=boundary)
        for entry in state.scrum.sprint_scope
        if entry.sprint_id == sprint.id and entry.removed_at is None
    )
    successor_scope = _scope_entries(
        _ScopeContext(state, successor.id, (*carry_ids, *backlog_ids), boundary)
    )
    write_set = ScrumStateWriteSet(
        work_items=plan.work_items,
        sprints=(completed, successor),
        sprint_scope=(*closed_scope, *successor_scope),
        status_visits=plan.visits,
        status_visit_samples=plan.samples,
    )
    claims = (sprint_claim, *plan.claims)
    context = _TransitionContext(state, write_set, claims, sprint, successor, boundary)
    return _rollover_transition(context)


def _completed_sprint(sprint: SprintState, boundary: datetime) -> SprintState:
    return replace(
        sprint,
        lifecycle=SprintLifecycle.COMPLETED,
        observed_end_at=boundary,
        updated_at=boundary,
    )


def _successor(
    state: LiveTeamState, sprint: SprintState, boundary: datetime
) -> tuple[SprintState, SemanticCounterClaim]:
    scope = SemanticCounterScope(SemanticCounterKind.SPRINT_ORDINAL, sprint.team_id, "SCRUM")
    counter = next(item for item in state.scrum.semantic_counters if item.scope == scope)
    calendar = BusinessCalendar.from_blueprint(
        state.aggregate.blueprint.team.timezone, state.aggregate.blueprint.calendar
    )
    rule = CadenceRule(
        state.aggregate.blueprint.scrum.first_boundary,
        state.aggregate.blueprint.scrum.cadence_days,
    )
    ordinal = counter.next_value
    successor = SprintState(
        sprint_rng_id(sprint.team_id, ordinal),
        sprint.team_id,
        sprint.run_id,
        ordinal,
        SprintLifecycle.ACTIVE,
        cadence_boundary(calendar, rule, ordinal),
        cadence_boundary(calendar, rule, ordinal + 1),
        boundary,
        None,
        boundary,
        boundary,
    )
    return successor, SemanticCounterClaim(scope, ordinal, 1)


def _carryover_ids(state: LiveTeamState, sprint_id: UUID) -> tuple[UUID, ...]:
    work_by_id = {item.id: item for item in state.scrum.work_items}
    return tuple(
        entry.work_item_id
        for entry in state.scrum.sprint_scope
        if entry.sprint_id == sprint_id
        and entry.removed_at is None
        and work_by_id[entry.work_item_id].lifecycle is WorkItemLifecycle.ACTIVE
    )


def _ranked_backlog_ids(
    state: LiveTeamState, sprint_id: UUID, carry_ids: tuple[UUID, ...]
) -> tuple[UUID, ...]:
    work_by_id = {item.id: item for item in state.scrum.work_items}
    used = sum(work_by_id[item_id].story_points for item_id in carry_ids)
    scrum = state.aggregate.blueprint.scrum
    draw = SeededDrawSource(state.aggregate).draw(
        DecisionOccurrence(sprint_id, DecisionType.SCRUM_CAPACITY_TARGET, 0)
    )
    target = scrum.capacity_min_points + int(
        draw.unit_value * (scrum.capacity_max_points - scrum.capacity_min_points + 1)
    )
    selected: list[UUID] = []
    for item in sorted(state.scrum.work_items, key=lambda candidate: candidate.simulator_rank):
        if item.lifecycle is not WorkItemLifecycle.BACKLOG:
            continue
        if used >= scrum.capacity_min_points and used + item.story_points > target:
            break
        selected.append(item.id)
        used += item.story_points
    return tuple(selected)


def _planned_scope(context: _PlanningContext) -> _PlannedScope:
    state = context.state
    selected = frozenset(context.selected_ids)
    work, visits, samples = _activate_selected_work(
        state.aggregate,
        context.boundary,
        state.scrum.member_identities,
        state.scrum.work_items,
        selected,
        context.draws,
    )
    changed_work = tuple(item for item in work if item.id in selected)
    scope = _scope_entries(
        _ScopeContext(state, context.sprint_id, context.selected_ids, context.boundary)
    )
    claims = tuple(_visit_claim(state, visit.work_item_id, visit.ordinal) for visit in visits)
    return _PlannedScope(changed_work, scope, visits, samples, claims)


def _visit_claim(state: LiveTeamState, work_item_id: UUID, ordinal: int) -> SemanticCounterClaim:
    scope = SemanticCounterScope(SemanticCounterKind.VISIT_ORDINAL, work_item_id, "VISIT")
    counter = next(item for item in state.scrum.semantic_counters if item.scope == scope)
    return SemanticCounterClaim(scope, counter.next_value, 1)


def _scope_entries(context: _ScopeContext) -> tuple[SprintScopeEntry, ...]:
    state = context.state
    return tuple(
        SprintScopeEntry(
            semantic_uuid(f"sprint-scope/{context.sprint_id}/{item_id}"),
            state.aggregate.runtime.team_id,
            state.aggregate.runtime.run_id,
            context.sprint_id,
            item_id,
            context.boundary,
            None,
        )
        for item_id in context.work_item_ids
    )


def _activation_transition(context: _TransitionContext) -> SprintTransition:
    activity = (_activity(context, "SPRINT_STARTED"),)
    truth = (_ground_truth(context),)
    intents = _build_projection_intents(context, ("CREATE_SPRINT", "SCOPE_SPRINT", "START_SPRINT"))
    return SprintTransition(context.write_set, activity, truth, intents, context.claims, ())


def _rollover_transition(context: _TransitionContext) -> SprintTransition:
    activity = (_activity(context, "SPRINT_ROLLED_OVER"),)
    truth = (_ground_truth(context),)
    operations = ("COMPLETE_SPRINT", "CREATE_SPRINT", "SCOPE_SPRINT", "START_SPRINT")
    intents = _build_projection_intents(context, operations)
    return SprintTransition(context.write_set, activity, truth, intents, context.claims, ())


def _activity(context: _TransitionContext, event_type: str) -> ActivityEventDraft:
    sprint = context.current
    key = _boundary_key(context.state, sprint.ordinal, "activity")
    envelope = DraftEnvelope(key, "1.0", context.boundary, {"sprint_id": str(sprint.id)})
    details = ActivityDetails(
        event_type, "SPRINT", sprint.id, context.state.aggregate.runtime.version + 1
    )
    return ActivityEventDraft.create(envelope, details)


def _ground_truth(context: _TransitionContext) -> GroundTruthRecordDraft:
    state = context.state
    key = _boundary_key(state, context.current.ordinal, "ground-truth")
    payload = {
        "boundary": context.boundary.isoformat(),
        "previous_sprint_id": str(context.previous.id),
        "current_sprint_id": str(context.current.id),
        "carryover_policy": state.aggregate.blueprint.scrum.carryover_policy_version,
    }
    return GroundTruthRecordDraft.create(
        DraftEnvelope(key, "1.0", context.boundary, payload),
        GroundTruthDetails("SPRINT_BOUNDARY", "SIMULATOR_V2"),
    )


def _build_projection_intents(
    context: _TransitionContext, operations: tuple[str, ...]
) -> tuple[ProjectionIntentDraft, ...]:
    state = context.state
    intents: list[ProjectionIntentDraft] = []
    for operation in operations:
        dependency = [] if not intents else [intents[-1].semantic_key]
        sprint = context.previous if operation == "COMPLETE_SPRINT" else context.current
        key = _boundary_key(state, context.current.ordinal, operation.lower())
        envelope = DraftEnvelope(
            key,
            "1.0",
            context.boundary,
            {"sprint_id": str(sprint.id), "depends_on": dependency},
        )
        details = ProjectionDetails(
            "JIRA", operation, sprint.id, state.aggregate.runtime.version + 1, "PENDING"
        )
        intents.append(ProjectionIntentDraft.create(envelope, details))
    return tuple(intents)


def _boundary_key(state: LiveTeamState, ordinal: int, suffix: str) -> str:
    runtime = state.aggregate.runtime
    return f"sprint-boundary/{runtime.team_id}/{runtime.run_id}/{ordinal}/{suffix}"


def _empty_transition() -> SprintTransition:
    return SprintTransition(ScrumStateWriteSet(), (), (), (), (), ())


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("boundary must be aware")
    return value.astimezone(UTC)
