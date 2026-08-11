"""Pure incremental advancement for one persisted Scrum team."""

import math
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.authoritative_slice import (
    AuthoritativeTickSliceCommit,
    SemanticCounterClaim,
)
from app.v2.domain.business_calendar import BusinessCalendar, UtcInterval
from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.deterministic_rng import DecisionOccurrence, DecisionType, visit_rng_id
from app.v2.domain.draw_source import DrawSource
from app.v2.domain.live_slice import (
    ActivityDetails,
    ActivityEventDraft,
    DraftEnvelope,
    GroundTruthDetails,
    GroundTruthRecordDraft,
    ProjectionDetails,
    ProjectionIntentDraft,
    RuntimeAdvance,
    TickSliceCommit,
)
from app.v2.domain.sampling import sample_touch, touch_bounds
from app.v2.domain.scrum_state import (
    MemberAvailabilityOverlay,
    MemberBusinessDateConsumption,
    MemberIdentity,
    ScrumStateWriteSet,
    SemanticCounterKind,
    SprintLifecycle,
    StatusVisitLifecycle,
    StatusVisitSample,
    StatusVisitSampleInput,
    StatusVisitState,
    WorkItemLifecycle,
    WorkItemState,
)
from app.v2.domain.team_blueprint import MemberBlueprint, WorkflowRouteStep

MICROSECONDS_PER_HOUR = 3_600_000_000


@dataclass(frozen=True)
class TickRequest:
    team_id: UUID
    ends_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if type(self.team_id) is not UUID:
            raise TypeError("team_id must be a UUID")
        object.__setattr__(self, "ends_at", _utc(self.ends_at, "ends_at"))
        object.__setattr__(self, "recorded_at", _utc(self.recorded_at, "recorded_at"))


@dataclass(frozen=True)
class _BusinessSegment:
    business_date: date
    start: datetime
    end: datetime

    @property
    def microseconds(self) -> int:
        return _microseconds(self.end - self.start)


@dataclass(frozen=True)
class _TickResult:
    ends_at: datetime
    visits: tuple[StatusVisitState, ...]
    work_items: tuple[WorkItemState, ...]
    samples: tuple[StatusVisitSample, ...]
    consumption: tuple[MemberBusinessDateConsumption, ...]
    claims: tuple[SemanticCounterClaim, ...]
    queue_causes: tuple["_QueueCause", ...] = ()


@dataclass(frozen=True)
class _QueueCause:
    visit_id: UUID
    reason: str
    delta_microseconds: int


@dataclass(frozen=True)
class _QueueContext:
    state: LiveTeamState
    segment: _BusinessSegment
    consumption: dict[tuple[UUID, date], int]


@dataclass(frozen=True)
class _LedgerItem:
    state: LiveTeamState
    request: TickRequest
    work: WorkItemState
    visit: StatusVisitState
    original_visit: StatusVisitState
    queue_causes: tuple[_QueueCause, ...]
    semantic_key: str
    summary: str


def calculate_scrum_tick(
    state: LiveTeamState, request: TickRequest, draws: DrawSource
) -> AuthoritativeTickSliceCommit:
    """Calculate one deterministic, persistence-ready Scrum slice."""
    _validate_request(state, request)
    aggregate = state.aggregate
    calendar = BusinessCalendar.from_blueprint(
        aggregate.blueprint.team.timezone, aggregate.blueprint.calendar
    )
    cursor = aggregate.runtime.simulation_time
    effective_end = _effective_end(state, request.ends_at)
    segments = _business_segments(state, calendar, cursor, effective_end)
    result = _advance_visits(state, effective_end, segments, calendar, draws)
    live_slice = _live_slice(state, request, result.ends_at, result)
    write_set = ScrumStateWriteSet(
        member_business_date_consumption=result.consumption,
        work_items=result.work_items,
        status_visits=result.visits,
        status_visit_samples=result.samples,
    )
    return AuthoritativeTickSliceCommit(live_slice, write_set, result.claims, ())


def _validate_request(state: LiveTeamState, request: TickRequest) -> None:
    if type(state) is not LiveTeamState or type(request) is not TickRequest:
        raise TypeError("state and request must use their exact application types")
    runtime = state.aggregate.runtime
    if request.team_id != runtime.team_id:
        raise ValueError("tick request must identify the loaded team")
    if request.ends_at < runtime.simulation_time:
        raise ValueError("tick end must not precede persisted simulation time")


def _effective_end(state: LiveTeamState, requested_end: datetime) -> datetime:
    active = tuple(
        sprint for sprint in state.scrum.sprints if sprint.lifecycle is SprintLifecycle.ACTIVE
    )
    if not active:
        return requested_end
    return min(requested_end, active[0].planned_end_at)


def _business_segments(
    state: LiveTeamState,
    calendar: BusinessCalendar,
    starts_at: datetime,
    ends_at: datetime,
) -> tuple[_BusinessSegment, ...]:
    if starts_at == ends_at:
        return ()
    first_day = calendar.business_date(starts_at)
    final_day = calendar.business_date(ends_at - timedelta.resolution)
    segments: list[_BusinessSegment] = []
    day = first_day
    while day <= final_day:
        working = calendar.working_interval(day)
        if working is not None:
            start = max(starts_at, working.start)
            end = min(ends_at, working.end)
            if start < end:
                boundaries = _availability_boundaries(state, start, end)
                segments.extend(
                    _BusinessSegment(day, left, right)
                    for left, right in zip(boundaries, boundaries[1:], strict=False)
                )
        day += timedelta(days=1)
    return tuple(segments)


def _availability_boundaries(
    state: LiveTeamState, starts_at: datetime, ends_at: datetime
) -> tuple[datetime, ...]:
    configured = tuple(
        interval
        for member in state.aggregate.blueprint.members
        for interval in member.availability
    )
    intervals = (*configured, *state.scrum.member_availability_overlays)
    boundaries = {starts_at, ends_at}
    boundaries.update(
        instant
        for interval in intervals
        for instant in (interval.starts_at, interval.ends_at)
        if starts_at < instant < ends_at
    )
    return tuple(sorted(boundaries))


def _advance_visits(
    state: LiveTeamState,
    effective_end: datetime,
    segments: tuple[_BusinessSegment, ...],
    calendar: BusinessCalendar,
    draws: DrawSource,
) -> _TickResult:
    work_by_id = {item.id: item for item in state.scrum.work_items}
    visits = {
        visit.id: visit
        for visit in state.scrum.status_visits
        if visit.lifecycle is StatusVisitLifecycle.OPEN
    }
    original = dict(visits)
    consumption = _consumption_map(state)
    queue_causes: list[_QueueCause] = []
    committed_end = effective_end
    for segment in segments:
        starting_consumption = dict(consumption)
        probe_consumption = dict(consumption)
        probe = _advance_segment(state, work_by_id, visits, probe_consumption, segment)
        boundary = _completion_boundary(state, calendar, segment, visits, probe, work_by_id)
        if boundary is None:
            context = _QueueContext(state, segment, starting_consumption)
            queue_causes.extend(_segment_queue_causes(context, visits, probe))
            visits = probe
            consumption = probe_consumption
            continue
        shortened = replace(segment, end=boundary)
        advanced = _advance_segment(state, work_by_id, visits, consumption, shortened)
        context = _QueueContext(state, shortened, starting_consumption)
        queue_causes.extend(_segment_queue_causes(context, visits, advanced))
        visits = advanced
        committed_end = boundary
        break
    result = _finish_visits(
        state, work_by_id, original, visits, consumption, committed_end, calendar, draws
    )
    return replace(result, queue_causes=_aggregate_queue_causes(queue_causes))


def _segment_queue_causes(
    context: _QueueContext,
    before: dict[UUID, StatusVisitState],
    after: dict[UUID, StatusVisitState],
) -> tuple[_QueueCause, ...]:
    causes = []
    for visit_id, original in before.items():
        advanced = after[visit_id]
        delta = advanced.queue_microseconds - original.queue_microseconds
        if delta:
            causes.append(
                _QueueCause(visit_id, _queue_reason_at(context, advanced), delta)
            )
    return tuple(causes)


def _aggregate_queue_causes(causes: list[_QueueCause]) -> tuple[_QueueCause, ...]:
    totals: dict[tuple[UUID, str], int] = {}
    for cause in causes:
        key = cause.visit_id, cause.reason
        totals[key] = totals.get(key, 0) + cause.delta_microseconds
    return tuple(
        _QueueCause(visit_id, reason, delta)
        for (visit_id, reason), delta in sorted(
            totals.items(), key=lambda item: (str(item[0][0]), item[0][1])
        )
    )


def _queue_reason_at(context: _QueueContext, visit: StatusVisitState) -> str:
    state = context.state
    identities = tuple(
        identity
        for identity in state.scrum.member_identities
        if _proficiency(
            state.aggregate.blueprint.members[identity.blueprint_index],
            visit.activity_key,
        )
        is not None
    )
    if not identities:
        return "NO_CAPABLE_MEMBER"
    available = tuple(
        identity
        for identity in identities
        if _effective_fraction(state, identity, context.segment) > 0
    )
    if not available:
        return "UNAVAILABLE"
    exhausted = all(
        _remaining_capacity(state, identity, context.segment, context.consumption) == 0
        for identity in available
    )
    return "DAILY_CAPACITY" if exhausted else "WIP_LIMIT"


def _completion_boundary(
    state: LiveTeamState,
    calendar: BusinessCalendar,
    segment: _BusinessSegment,
    before: dict[UUID, StatusVisitState],
    after: dict[UUID, StatusVisitState],
    work_by_id: dict[UUID, WorkItemState],
) -> datetime | None:
    samples = {sample.visit_id: sample for sample in state.scrum.status_visit_samples}
    used_by_member: dict[UUID, int] = {}
    candidates: list[datetime] = []
    ordered = sorted(before.values(), key=lambda item: work_by_id[item.work_item_id].simulator_rank)
    for visit in ordered:
        updated = after[visit.id]
        touch_at = _touch_completion(state, segment, visit, updated, used_by_member)
        credited = updated.credited_labor_microseconds - visit.credited_labor_microseconds
        if updated.member_id is not None:
            used_by_member[updated.member_id] = used_by_member.get(updated.member_id, 0) + credited
        if touch_at is None:
            continue
        dwell_at = _dwell_completion(calendar, segment, visit, samples[visit.id])
        completion = max(touch_at, dwell_at)
        if completion <= segment.end:
            candidates.append(completion)
    return min(candidates) if candidates else None


def _touch_completion(
    state: LiveTeamState,
    segment: _BusinessSegment,
    before: StatusVisitState,
    after: StatusVisitState,
    used_by_member: dict[UUID, int],
) -> datetime | None:
    if after.remaining_work_microseconds:
        return None
    if before.remaining_work_microseconds == 0:
        return segment.start
    if after.member_id is None:
        return None
    identity = next(item for item in state.scrum.member_identities if item.id == after.member_id)
    fraction = _effective_fraction(state, identity, segment)
    prior_labor = used_by_member.get(identity.id, 0)
    elapsed = math.ceil((prior_labor + before.remaining_work_microseconds) / fraction)
    return segment.start + timedelta(microseconds=elapsed)


def _dwell_completion(
    calendar: BusinessCalendar,
    segment: _BusinessSegment,
    visit: StatusVisitState,
    sample: StatusVisitSample,
) -> datetime:
    elapsed = calendar.elapsed(UtcInterval(visit.entered_at, segment.start)).business
    service = max(0, _microseconds(elapsed) - visit.pause_microseconds)
    required = round(sample.dwell_sampled_hours * MICROSECONDS_PER_HOUR)
    return segment.start + timedelta(microseconds=max(0, required - service))


def _advance_segment(
    state: LiveTeamState,
    work_by_id: dict[UUID, WorkItemState],
    visits: dict[UUID, StatusVisitState],
    consumption: dict[tuple[UUID, date], int],
    segment: _BusinessSegment,
) -> dict[UUID, StatusVisitState]:
    ordered = sorted(
        visits.values(), key=lambda visit: work_by_id[visit.work_item_id].simulator_rank
    )
    assigned = _assign_owners(state, ordered, segment, consumption)
    starting_consumption = dict(consumption)
    advanced: dict[UUID, StatusVisitState] = {}
    for visit in assigned:
        advanced[visit.id] = _advance_visit(
            state, visit, segment, consumption, starting_consumption
        )
    return advanced


def _assign_owners(
    state: LiveTeamState,
    visits: list[StatusVisitState],
    segment: _BusinessSegment,
    consumption: dict[tuple[UUID, date], int],
) -> list[StatusVisitState]:
    members = {identity.id: identity for identity in state.scrum.member_identities}
    retained: dict[UUID, int] = {}
    assigned: list[StatusVisitState] = []
    for visit in visits:
        owner = visit.member_id
        if owner is not None and _can_retain(state, members[owner], visit, segment, retained):
            retained[owner] = retained.get(owner, 0) + 1
            assigned.append(visit)
        else:
            assigned.append(replace(visit, member_id=None))
    return [
        _assign_owner(state, members, visit, segment, consumption, retained)
        if visit.member_id is None
        else visit
        for visit in assigned
    ]


def _can_retain(
    state: LiveTeamState,
    identity: MemberIdentity,
    visit: StatusVisitState,
    segment: _BusinessSegment,
    retained: dict[UUID, int],
) -> bool:
    member = state.aggregate.blueprint.members[identity.blueprint_index]
    capable = _proficiency(member, visit.activity_key) is not None
    available = _available_microseconds(state, identity, segment) > 0
    return capable and available and retained.get(identity.id, 0) < member.max_concurrent_wip


def _assign_owner(
    state: LiveTeamState,
    members: dict[UUID, MemberIdentity],
    visit: StatusVisitState,
    segment: _BusinessSegment,
    consumption: dict[tuple[UUID, date], int],
    retained: dict[UUID, int],
) -> StatusVisitState:
    candidates = []
    for identity in members.values():
        member = state.aggregate.blueprint.members[identity.blueprint_index]
        proficiency = _proficiency(member, visit.activity_key)
        room = retained.get(identity.id, 0) < member.max_concurrent_wip
        has_time = _remaining_capacity(state, identity, segment, consumption) > 0
        if proficiency is not None and room and has_time:
            candidates.append((proficiency, -identity.blueprint_index, identity))
    if not candidates:
        return visit
    identity = max(candidates, key=lambda candidate: candidate[:2])[2]
    retained[identity.id] = retained.get(identity.id, 0) + 1
    return replace(visit, member_id=identity.id)


def _advance_visit(
    state: LiveTeamState,
    visit: StatusVisitState,
    segment: _BusinessSegment,
    consumption: dict[tuple[UUID, date], int],
    starting_consumption: dict[tuple[UUID, date], int],
) -> StatusVisitState:
    status = next(
        item for item in state.aggregate.blueprint.workflow.statuses if item.key == visit.status_key
    )
    if status.pauses_service_clock:
        return replace(visit, pause_microseconds=visit.pause_microseconds + segment.microseconds)
    if visit.member_id is None or visit.remaining_work_microseconds == 0:
        queue = segment.microseconds if visit.remaining_work_microseconds else 0
        return replace(visit, queue_microseconds=visit.queue_microseconds + queue)
    identity = next(item for item in state.scrum.member_identities if item.id == visit.member_id)
    available = _remaining_segment_capacity(
        state, identity, segment, consumption, starting_consumption
    )
    credited = min(available, visit.remaining_work_microseconds)
    key = (identity.id, segment.business_date)
    consumption[key] = consumption.get(key, 0) + credited
    remaining = visit.remaining_work_microseconds - credited
    queue = 0 if remaining == 0 else segment.microseconds - credited
    return replace(
        visit,
        elapsed_work_microseconds=visit.elapsed_work_microseconds + credited,
        remaining_work_microseconds=remaining,
        queue_microseconds=visit.queue_microseconds + max(0, queue),
        credited_labor_microseconds=visit.credited_labor_microseconds + credited,
    )


def _consumption_map(state: LiveTeamState) -> dict[tuple[UUID, date], int]:
    return {
        (item.member_id, item.business_date): item.consumed_labor_microseconds
        for item in state.scrum.member_business_date_consumption
    }


def _remaining_capacity(
    state: LiveTeamState,
    identity: MemberIdentity,
    segment: _BusinessSegment,
    consumption: dict[tuple[UUID, date], int],
) -> int:
    available = _available_microseconds(state, identity, segment)
    ceiling = _daily_ceiling(state, identity, segment)
    consumed = consumption.get((identity.id, segment.business_date), 0)
    return max(0, min(available, ceiling - consumed))


def _remaining_segment_capacity(
    state: LiveTeamState,
    identity: MemberIdentity,
    segment: _BusinessSegment,
    consumption: dict[tuple[UUID, date], int],
    starting_consumption: dict[tuple[UUID, date], int],
) -> int:
    key = (identity.id, segment.business_date)
    consumed = consumption.get(key, 0)
    used_in_segment = consumed - starting_consumption.get(key, 0)
    available = _available_microseconds(state, identity, segment) - used_in_segment
    ceiling = _daily_ceiling(state, identity, segment) - consumed
    return max(0, min(available, ceiling))


def _available_microseconds(
    state: LiveTeamState, identity: MemberIdentity, segment: _BusinessSegment
) -> int:
    fraction = _effective_fraction(state, identity, segment)
    return round(segment.microseconds * fraction)


def _daily_ceiling(
    state: LiveTeamState, identity: MemberIdentity, segment: _BusinessSegment
) -> int:
    member = state.aggregate.blueprint.members[identity.blueprint_index]
    ceilings = [round(member.daily_capacity_hours * MICROSECONDS_PER_HOUR)]
    for interval in member.availability:
        if _active(interval, segment):
            ceilings.append(round(interval.daily_capacity_hours_override * MICROSECONDS_PER_HOUR))
    for overlay in _member_overlays(state, identity.id):
        if _active(overlay, segment) and overlay.daily_capacity_ceiling_microseconds is not None:
            ceilings.append(overlay.daily_capacity_ceiling_microseconds)
    return round(min(ceilings) * _effective_fraction(state, identity, segment))


def _effective_fraction(
    state: LiveTeamState, identity: MemberIdentity, segment: _BusinessSegment
) -> float:
    member = state.aggregate.blueprint.members[identity.blueprint_index]
    intervals = (*member.availability, *_member_overlays(state, identity.id))
    fractions = [
        interval.availability_fraction
        for interval in intervals
        if _active(interval, segment)
    ]
    return min((1.0, *fractions))


def _active(interval: object, segment: _BusinessSegment) -> bool:
    return interval.starts_at <= segment.start < interval.ends_at


def _member_overlays(
    state: LiveTeamState, member_id: UUID
) -> tuple[MemberAvailabilityOverlay, ...]:
    return tuple(
        overlay
        for overlay in state.scrum.member_availability_overlays
        if overlay.member_id == member_id
    )


def _proficiency(member: MemberBlueprint, activity: str | None) -> float | None:
    return next(
        (
            responsibility.proficiency
            for responsibility in member.responsibilities
            if responsibility.activity == activity
        ),
        None,
    )


def _finish_visits(
    state: LiveTeamState,
    work_by_id: dict[UUID, WorkItemState],
    original: dict[UUID, StatusVisitState],
    visits: dict[UUID, StatusVisitState],
    consumption: dict[tuple[UUID, date], int],
    effective_end: datetime,
    calendar: BusinessCalendar,
    draws: DrawSource,
) -> _TickResult:
    changed: list[StatusVisitState] = []
    work_changes: list[WorkItemState] = []
    samples: list[StatusVisitSample] = []
    claims: list[SemanticCounterClaim] = []
    sample_by_visit = {sample.visit_id: sample for sample in state.scrum.status_visit_samples}
    for visit in visits.values():
        if _is_complete(visit, sample_by_visit[visit.id], effective_end, calendar):
            closed = replace(visit, lifecycle=StatusVisitLifecycle.CLOSED, closed_at=effective_end)
            changed.append(closed)
            transition = _transition(state, work_by_id[visit.work_item_id], closed, draws)
            work_changes.append(transition[0])
            if transition[1] is not None:
                changed.append(transition[1])
                samples.append(transition[2])
                claims.append(transition[3])
        elif visit != original[visit.id]:
            changed.append(visit)
    consumption_changes = _consumption_changes(state, consumption)
    return _TickResult(
        effective_end,
        tuple(changed),
        tuple(work_changes),
        tuple(samples),
        consumption_changes,
        tuple(claims),
    )


def _is_complete(
    visit: StatusVisitState,
    sample: StatusVisitSample,
    effective_end: datetime,
    calendar: BusinessCalendar,
) -> bool:
    if visit.remaining_work_microseconds:
        return False
    business = calendar.elapsed(UtcInterval(visit.entered_at, effective_end)).business
    service_microseconds = max(0, _microseconds(business) - visit.pause_microseconds)
    dwell_microseconds = round(sample.dwell_sampled_hours * MICROSECONDS_PER_HOUR)
    return service_microseconds >= dwell_microseconds


def _transition(
    state: LiveTeamState,
    work: WorkItemState,
    closed: StatusVisitState,
    draws: DrawSource,
) -> tuple[
    WorkItemState,
    StatusVisitState | None,
    StatusVisitSample | None,
    SemanticCounterClaim | None,
]:
    route = next(
        route
        for route in state.aggregate.blueprint.workflow.routes
        if route.issue_type == work.issue_type
    )
    position = next(
        index for index, step in enumerate(route.steps) if step.status_key == closed.status_key
    )
    later_steps = route.steps[position + 1 :]
    timed = next((step for step in later_steps if _timed(state, step)), None)
    if timed is None:
        terminal = later_steps[-1]
        return replace(
            work,
            lifecycle=WorkItemLifecycle.DONE,
            current_status_key=terminal.status_key,
            updated_at=closed.closed_at,
        ), None, None, None
    counter = next(
        item
        for item in state.scrum.semantic_counters
        if item.scope.kind is SemanticCounterKind.VISIT_ORDINAL
        and item.scope.scope_id == work.id
    )
    next_work = replace(work, current_status_key=timed.status_key, updated_at=closed.closed_at)
    visit, sample = _new_timed_visit(state, next_work, timed, counter.next_value, draws)
    claim = SemanticCounterClaim(counter.scope, counter.next_value, 1)
    return next_work, visit, sample, claim


def _timed(state: LiveTeamState, step: WorkflowRouteStep) -> bool:
    status = next(
        item for item in state.aggregate.blueprint.workflow.statuses if item.key == step.status_key
    )
    return status.consumes_capacity and step.required_activity is not None


def _new_timed_visit(
    state: LiveTeamState,
    work: WorkItemState,
    step: WorkflowRouteStep,
    ordinal: int,
    draws: DrawSource,
) -> tuple[StatusVisitState, StatusVisitSample]:
    visit_id = visit_rng_id(work.id, ordinal)
    touch_draw = draws.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_TOUCH, 0))
    entry = next(
        item
        for item in state.aggregate.blueprint.timing.entries
        if (item.status_key, item.issue_type, item.story_points)
        == (step.status_key, work.issue_type, work.story_points)
    )
    required = round(
        sample_touch(touch_bounds(entry), touch_draw.unit_value).sampled_hours
        * MICROSECONDS_PER_HOUR
    )
    visit = StatusVisitState(
        visit_id,
        work.team_id,
        work.run_id,
        work.id,
        ordinal,
        StatusVisitLifecycle.OPEN,
        step.status_key,
        step.required_activity,
        None,
        work.updated_at,
        None,
        required,
        0,
        required,
        0,
        0,
        0,
    )
    dwell_draw = draws.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_DWELL, 0))
    sample = StatusVisitSample.create(
        StatusVisitSampleInput(state.aggregate.blueprint, work, visit, dwell_draw, touch_draw)
    )
    return visit, sample


def _consumption_changes(
    state: LiveTeamState, values: dict[tuple[UUID, date], int]
) -> tuple[MemberBusinessDateConsumption, ...]:
    original = _consumption_map(state)
    return tuple(
        MemberBusinessDateConsumption(
            state.aggregate.runtime.team_id,
            state.aggregate.runtime.run_id,
            member_id,
            business_date,
            consumed,
        )
        for (member_id, business_date), consumed in sorted(
            values.items(), key=lambda item: (item[0][1], str(item[0][0]))
        )
        if original.get((member_id, business_date)) != consumed
    )


def _live_slice(
    state: LiveTeamState,
    request: TickRequest,
    effective_end: datetime,
    result: _TickResult,
) -> TickSliceCommit:
    runtime = state.aggregate.runtime
    commit_id = semantic_uuid(
        f"scrum-tick/{runtime.team_id}/{runtime.run_id}/{runtime.version}/{effective_end.isoformat()}"
    )
    ledger_request = TickRequest(request.team_id, effective_end, request.recorded_at)
    activity, truth, projection = _ledger_drafts(state, ledger_request, result)
    return TickSliceCommit(
        commit_id,
        runtime.team_id,
        runtime.run_id,
        runtime.version,
        RuntimeAdvance(runtime.state, effective_end, effective_end),
        activity,
        truth,
        projection,
        request.recorded_at,
    )


def _ledger_drafts(
    state: LiveTeamState, request: TickRequest, result: _TickResult
) -> tuple[
    tuple[ActivityEventDraft, ...],
    tuple[GroundTruthRecordDraft, ...],
    tuple[ProjectionIntentDraft, ...],
]:
    work_changes = {item.id: item for item in result.work_items}
    work_by_id = {item.id: item for item in state.scrum.work_items}
    original_visits = {item.id: item for item in state.scrum.status_visits}
    queue_causes = {
        visit_id: tuple(cause for cause in result.queue_causes if cause.visit_id == visit_id)
        for visit_id in original_visits
    }
    activity = []
    truth = []
    projection = []
    for visit in result.visits:
        if visit.ordinal > 0 and visit.lifecycle is StatusVisitLifecycle.OPEN:
            continue
        work = work_changes.get(visit.work_item_id, work_by_id[visit.work_item_id])
        key = _ledger_key(state, visit, request.ends_at)
        ledger_item = _LedgerItem(
            state,
            request,
            work,
            visit,
            original_visits[visit.id],
            queue_causes[visit.id],
            key,
            _summary(state, work, visit),
        )
        activity.append(_activity_draft(ledger_item))
        truth.append(_ground_truth_draft(ledger_item))
        if work.id in work_changes:
            projection.append(_projection_draft(ledger_item))
    return tuple(activity), tuple(truth), tuple(projection)


def _activity_draft(item: _LedgerItem) -> ActivityEventDraft:
    envelope = DraftEnvelope(
        item.semantic_key, "1.0", item.request.ends_at, {"summary": item.summary}
    )
    details = ActivityDetails(
        "ISSUE_UPDATED",
        "ISSUE",
        item.work.id,
        item.state.aggregate.runtime.version + 1,
    )
    return ActivityEventDraft.create(envelope, details)


def _ground_truth_draft(item: _LedgerItem) -> GroundTruthRecordDraft:
    original = item.original_visit
    touch_delta = item.visit.credited_labor_microseconds - original.credited_labor_microseconds
    causal_member = item.visit.member_id or original.member_id
    calendar = BusinessCalendar.from_blueprint(
        item.state.aggregate.blueprint.team.timezone,
        item.state.aggregate.blueprint.calendar,
    )
    business_delta = calendar.elapsed(
        UtcInterval(item.state.aggregate.runtime.simulation_time, item.request.ends_at)
    ).business
    payload = {
        "work_item_id": str(item.work.id),
        "reason": _causal_reason(item),
        "member_id": None if causal_member is None else str(causal_member),
        "status": item.work.current_status_key,
        "business_delta_microseconds": _microseconds(business_delta),
        "queue_delta_microseconds": item.visit.queue_microseconds - original.queue_microseconds,
        "queue_causes": [
            {
                "reason": cause.reason,
                "queue_delta_microseconds": cause.delta_microseconds,
            }
            for cause in item.queue_causes
        ],
        "pause_delta_microseconds": item.visit.pause_microseconds - original.pause_microseconds,
        "touch_delta_microseconds": touch_delta,
        "remaining_before_microseconds": original.remaining_work_microseconds,
        "remaining_after_microseconds": item.visit.remaining_work_microseconds,
        "timing_context": _timing_context(item),
    }
    envelope = DraftEnvelope(item.semantic_key, "1.0", item.request.ends_at, payload)
    return GroundTruthRecordDraft.create(
        envelope, GroundTruthDetails("ISSUE_STATE", "SIMULATOR_V2")
    )


def _causal_reason(item: _LedgerItem) -> str:
    if item.work.current_status_key != item.visit.status_key:
        return "TRANSITIONED"
    original = item.original_visit
    if item.visit.remaining_work_microseconds == 0:
        return "DWELLING"
    touch_delta = item.visit.credited_labor_microseconds - original.credited_labor_microseconds
    if touch_delta:
        return "PROGRESSED"
    if item.queue_causes:
        return item.queue_causes[0].reason
    return "DWELLING"


def _causal_segment(item: _LedgerItem) -> _BusinessSegment:
    state = item.state
    calendar = BusinessCalendar.from_blueprint(
        state.aggregate.blueprint.team.timezone, state.aggregate.blueprint.calendar
    )
    instant = item.request.ends_at - timedelta.resolution
    business_date = calendar.business_date(instant)
    working = calendar.working_interval(business_date)
    if working is None:
        return _BusinessSegment(business_date, instant, item.request.ends_at)
    start = max(state.aggregate.runtime.simulation_time, working.start)
    return _BusinessSegment(business_date, start, item.request.ends_at)


def _timing_context(item: _LedgerItem) -> dict[str, object]:
    sample = next(
        value
        for value in item.state.scrum.status_visit_samples
        if value.visit_id == item.original_visit.id
    )
    member_id = item.visit.member_id or item.original_visit.member_id
    member = None
    if member_id is not None:
        identity = next(
            value for value in item.state.scrum.member_identities if value.id == member_id
        )
        member = item.state.aggregate.blueprint.members[identity.blueprint_index]
    segment = _causal_segment(item)
    return {
        "activity": item.original_visit.activity_key,
        "dwell_sampled_hours": sample.dwell_sampled_hours,
        "touch_sampled_hours": sample.touch_sampled_hours,
        "required_work_microseconds": sample.required_work_microseconds,
        "daily_capacity_hours": None if member is None else member.daily_capacity_hours,
        "max_concurrent_wip": None if member is None else member.max_concurrent_wip,
        "availability_fraction": (
            None if member_id is None else _effective_fraction(item.state, identity, segment)
        ),
        "effective_daily_capacity_microseconds": (
            None if member_id is None else _daily_ceiling(item.state, identity, segment)
        ),
    }


def _projection_draft(item: _LedgerItem) -> ProjectionIntentDraft:
    payload = {"issue_id": str(item.work.id), "status": item.work.current_status_key}
    envelope = DraftEnvelope(item.semantic_key, "1.0", item.request.ends_at, payload)
    details = ProjectionDetails(
        "JIRA",
        "TRANSITION_ISSUE",
        item.work.id,
        item.state.aggregate.runtime.version + 1,
        "PENDING",
    )
    return ProjectionIntentDraft.create(envelope, details)


def _summary(state: LiveTeamState, work: WorkItemState, visit: StatusVisitState) -> str:
    if work.current_status_key != visit.status_key:
        status = next(
            item
            for item in state.aggregate.blueprint.workflow.statuses
            if item.key == work.current_status_key
        )
        return f"{work.issue_type.title()} moved to {status.jira_name}"
    if visit.member_id is None:
        return f"{work.issue_type.title()} is queued for {visit.activity_key}"
    return f"{work.issue_type.title()} progressed in {visit.status_key}"


def _ledger_key(state: LiveTeamState, visit: StatusVisitState, ends_at: datetime) -> str:
    runtime = state.aggregate.runtime
    return (
        f"scrum-tick/{runtime.team_id}/{runtime.run_id}/{runtime.version}/"
        f"{visit.work_item_id}/{visit.ordinal}/{ends_at.isoformat()}"
    )


def _utc(value: datetime, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be an aware datetime")
    return value.astimezone(UTC)


def _microseconds(duration: timedelta) -> int:
    return duration // timedelta.resolution
