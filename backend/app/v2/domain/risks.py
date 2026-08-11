"""Versioned causal risk policy for one pragmatic live Scrum tick."""

import json
import math
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.authoritative_slice import (
    EligibleNaturalDecisionClaim,
    SemanticCounterClaim,
)
from app.v2.domain.business_calendar import BusinessCalendar
from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
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
)
from app.v2.domain.sampling import sample_touch, touch_bounds
from app.v2.domain.scrum_state import (
    FactorKind,
    MemberAvailabilityOverlay,
    ScrumStateWriteSet,
    SemanticCounterKind,
    StatusVisitLifecycle,
    StatusVisitSample,
    StatusVisitSampleInput,
    StatusVisitState,
    WorkItemLifecycle,
    WorkItemState,
)
from app.v2.domain.team_blueprint import RiskRule, WorkflowRouteStep

MICROSECONDS_PER_HOUR = 3_600_000_000
SUPPORTED_REVIEW_STATUSES = frozenset({"CODE_REVIEW", "QA", "PO_REVIEW"})


@dataclass(frozen=True)
class RiskEvaluation:
    state: ScrumStateWriteSet
    activity: tuple[ActivityEventDraft, ...]
    ground_truth: tuple[GroundTruthRecordDraft, ...]
    projection_intents: tuple[ProjectionIntentDraft, ...]
    counter_claims: tuple[SemanticCounterClaim, ...]
    natural_decision_claims: tuple[EligibleNaturalDecisionClaim, ...]


@dataclass(frozen=True)
class _RiskRecords:
    state: ScrumStateWriteSet = ScrumStateWriteSet()
    activity: tuple[ActivityEventDraft, ...] = ()
    ground_truth: tuple[GroundTruthRecordDraft, ...] = ()
    projection_intents: tuple[ProjectionIntentDraft, ...] = ()
    counter_claims: tuple[SemanticCounterClaim, ...] = ()
    natural_decision_claims: tuple[EligibleNaturalDecisionClaim, ...] = ()


@dataclass(frozen=True)
class _DecisionEvidence:
    rule: RiskRule
    entity_id: UUID
    occurred_at: datetime
    factors: dict[str, float]
    probability: float
    draw: float | None
    outcome: bool
    eligible_people: tuple[UUID, ...]
    wait_delta_microseconds: int
    progress_delta_microseconds: int
    cause: str
    jira_intent: dict[str, object] | None


@dataclass(frozen=True)
class _RiskContext:
    state: LiveTeamState
    as_of: datetime
    draws: DrawSource
    rule: RiskRule


@dataclass(frozen=True)
class _EvidenceBatch:
    evidence: _DecisionEvidence
    event_type: str
    projection: ProjectionIntentDraft | None = None
    state: ScrumStateWriteSet = ScrumStateWriteSet()
    counter_claims: tuple[SemanticCounterClaim, ...] = ()
    natural_claims: tuple[EligibleNaturalDecisionClaim, ...] = ()


@dataclass(frozen=True)
class _NaturalDecisionRequest:
    state: LiveTeamState
    entity_id: UUID
    decision_type: DecisionType
    business_date: date


def evaluate_due_risks(state: LiveTeamState, as_of: datetime, draws: DrawSource) -> RiskEvaluation:
    """Evaluate only configured rules whose persisted trigger is due."""
    instant = _utc(as_of)
    records = _RiskRecords()
    handlers = {
        "LONG_STAY": _long_stay,
        "REVIEW_REJECTION": _review_rejection,
        "CANCELLATION": _cancellation,
        "EXTERNAL_DEPENDENCY": _external_dependency,
        "MEMBER_UNAVAILABLE": _member_unavailability,
    }
    for rule in state.aggregate.blueprint.risks.rules:
        handler = handlers.get(rule.key)
        if handler is not None:
            records = _merge_records(records, handler(_RiskContext(state, instant, draws, rule)))
    return RiskEvaluation(
        records.state,
        records.activity,
        records.ground_truth,
        records.projection_intents,
        records.counter_claims,
        records.natural_decision_claims,
    )


def _long_stay(context: _RiskContext) -> _RiskRecords:
    state, as_of, rule = context.state, context.as_of, context.rule
    if rule.trigger != "STATUS_AGED":
        return _RiskRecords()
    samples = {sample.visit_id: sample for sample in state.scrum.status_visit_samples}
    records = _RiskRecords()
    for visit in _open_visits(state):
        sample = samples[visit.id]
        multiplier = _number(rule, "threshold_multiplier", 1.0)
        threshold = round(sample.dwell_sampled_hours * multiplier * MICROSECONDS_PER_HOUR)
        if not _threshold_crossed(context, visit, threshold):
            continue
        evidence = _DecisionEvidence(
            rule,
            visit.work_item_id,
            as_of,
            {},
            1.0,
            None,
            True,
            _eligible_people(state, visit),
            0,
            0,
            "sampled dwell threshold crossed",
            None,
        )
        records = _merge_records(
            records,
            _evidence_records(state, _EvidenceBatch(evidence, "LONG_STAY_DETECTED")),
        )
    return records


def _review_rejection(context: _RiskContext) -> _RiskRecords:
    state, as_of, rule = context.state, context.as_of, context.rule
    if rule.trigger != "STATUS_EXITED":
        return _RiskRecords()
    records = _RiskRecords()
    for visit in state.scrum.status_visits:
        if not _review_due(state, visit, as_of):
            continue
        records = _merge_records(
            records, _review_records(context, _work(state, visit.work_item_id), visit)
        )
    return records


def _review_records(
    context: _RiskContext, work: WorkItemState, review: StatusVisitState
) -> _RiskRecords:
    state, as_of, draws, rule = context.state, context.as_of, context.draws, context.rule
    draw = draws.draw(DecisionOccurrence(review.id, DecisionType.RISK_REVIEW_REJECTION_OUTCOME, 0))
    factors = _factors(state, work, review)
    probability = _probability(rule, factors)
    outcome = draw.unit_value < probability
    target = _text(rule, "return_status")
    _require_earlier_step(state, work, (review.status_key, target))
    people = _eligible_people_for_activity(state, _route_step(state, work, target))
    projection = _transition_intent(context, work.id, target) if outcome else None
    evidence = _DecisionEvidence(
        rule,
        review.id,
        as_of,
        factors,
        probability,
        draw.unit_value,
        outcome,
        people,
        0,
        0,
        "configured review rejection decision",
        _intent_payload(projection),
    )
    if not outcome:
        return _RiskRecords()
    returned_work = replace(
        work,
        lifecycle=WorkItemLifecycle.ACTIVE,
        current_status_key=target,
        updated_at=as_of,
    )
    returned_visit, sample, claim = _returned_visit(context, returned_work)
    risk_state = ScrumStateWriteSet(
        work_items=(returned_work,),
        status_visits=(returned_visit,),
        status_visit_samples=(sample,),
    )
    batch = _EvidenceBatch(evidence, "REVIEW_REJECTED", projection, risk_state, (claim,))
    return _evidence_records(state, batch)


def _cancellation(context: _RiskContext) -> _RiskRecords:
    state, as_of, rule = context.state, context.as_of, context.rule
    boundary = _workday_boundary(state, as_of)
    if rule.trigger != "WORKDAY_STARTED" or boundary is None:
        return _RiskRecords()
    records = _RiskRecords()
    for work in state.scrum.work_items:
        if work.lifecycle is not WorkItemLifecycle.ACTIVE:
            continue
        records = _merge_records(records, _cancellation_records(context, work, boundary))
    return records


def _cancellation_records(
    context: _RiskContext,
    work: WorkItemState,
    boundary: datetime,
) -> _RiskRecords:
    state, draws, rule = context.state, context.draws, context.rule
    claim, eligible = _natural_claim(
        _NaturalDecisionRequest(
            state, work.id, DecisionType.RISK_CANCELLATION_OUTCOME, boundary.date()
        )
    )
    draw = draws.draw(eligible.decision)
    visit = _work_visit(state, work.id)
    factors = _factors(state, work, visit)
    probability = _probability(rule, factors)
    outcome = draw.unit_value < probability
    target = _text(rule, "target_status")
    projection = (
        _transition_intent(replace(context, as_of=boundary), work.id, target) if outcome else None
    )
    evidence = _DecisionEvidence(
        rule,
        work.id,
        boundary,
        factors,
        probability,
        draw.unit_value,
        outcome,
        _eligible_people(state, visit),
        0,
        0,
        "workday cancellation decision",
        _intent_payload(projection),
    )
    risk_state = ScrumStateWriteSet()
    if not outcome:
        return _RiskRecords(counter_claims=(claim,), natural_decision_claims=(eligible,))
    cancelled = replace(
        work,
        lifecycle=WorkItemLifecycle.CANCELLED,
        current_status_key=target,
        updated_at=boundary,
    )
    closed = replace(
        visit,
        lifecycle=StatusVisitLifecycle.CLOSED,
        member_id=None,
        closed_at=boundary,
        elapsed_work_microseconds=visit.required_work_microseconds,
        remaining_work_microseconds=0,
    )
    risk_state = ScrumStateWriteSet(work_items=(cancelled,), status_visits=(closed,))
    return _evidence_records(
        state,
        _EvidenceBatch(
            evidence,
            "ISSUE_CANCELLED",
            projection,
            risk_state,
            (claim,),
            (eligible,),
        ),
    )


def _external_dependency(context: _RiskContext) -> _RiskRecords:
    state, rule = context.state, context.rule
    if rule.trigger != "STATUS_ENTERED":
        return _RiskRecords()
    records = _RiskRecords()
    for visit in _open_visits(state):
        outcome = _dependency_records(context, visit)
        records = _merge_records(records, outcome)
    return records


def _dependency_records(context: _RiskContext, visit: StatusVisitState) -> _RiskRecords:
    state, as_of, draws, rule = context.state, context.as_of, context.draws, context.rule
    total_wait = round(_number(rule, "wait_hours") * MICROSECONDS_PER_HOUR)
    remaining = max(0, total_wait - visit.pause_microseconds)
    cursor = state.aggregate.runtime.simulation_time
    if visit.entered_at > cursor or remaining == 0 or as_of <= cursor:
        return _RiskRecords()
    draw = draws.draw(
        DecisionOccurrence(visit.id, DecisionType.RISK_EXTERNAL_DEPENDENCY_OUTCOME, 0)
    )
    work = _work(state, visit.work_item_id)
    factors = _factors(state, work, visit)
    probability = _probability(rule, factors)
    outcome = draw.unit_value < probability
    delta = min(remaining, _microseconds(as_of - cursor)) if outcome else 0
    if not outcome or delta == 0:
        return _RiskRecords()
    blocked = replace(
        visit,
        member_id=None,
        queue_microseconds=visit.queue_microseconds + delta,
        pause_microseconds=visit.pause_microseconds + delta,
    )
    evidence = _DecisionEvidence(
        rule,
        visit.id,
        cursor,
        factors,
        probability,
        draw.unit_value,
        outcome,
        _eligible_people(state, visit),
        delta,
        0,
        "external dependency paused visit progress",
        None,
    )
    risk_state = ScrumStateWriteSet(status_visits=(blocked,)) if outcome else ScrumStateWriteSet()
    batch = _EvidenceBatch(evidence, "EXTERNAL_DEPENDENCY_STARTED", state=risk_state)
    return _evidence_records(state, batch)


def _member_unavailability(context: _RiskContext) -> _RiskRecords:
    state, as_of, rule = context.state, context.as_of, context.rule
    boundary = _workday_boundary(state, as_of)
    if rule.trigger != "WORKDAY_STARTED" or boundary is None:
        return _RiskRecords()
    member_ids = tuple(
        sorted(
            {visit.member_id for visit in _open_visits(state) if visit.member_id is not None},
            key=str,
        )
    )
    records = _RiskRecords()
    for member_id in member_ids:
        outcome = _unavailability_records(context, member_id, boundary)
        records = _merge_records(records, outcome)
    return records


def _unavailability_records(
    context: _RiskContext,
    member_id: UUID,
    boundary: datetime,
) -> _RiskRecords:
    state, draws, rule = context.state, context.draws, context.rule
    claim, eligible = _natural_claim(
        _NaturalDecisionRequest(
            state, member_id, DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME, boundary.date()
        )
    )
    draw = draws.draw(eligible.decision)
    factors = _member_factors(state, member_id)
    probability = _probability(rule, factors)
    outcome = draw.unit_value < probability
    duration = _duration_days(context, member_id, eligible.decision.occurrence)
    overlay = (
        _unavailability_overlay(replace(context, as_of=boundary), member_id, duration)
        if outcome
        else None
    )
    evidence = _DecisionEvidence(
        rule,
        member_id,
        boundary,
        factors,
        probability,
        draw.unit_value,
        outcome,
        (member_id,),
        0,
        0,
        "member availability decision",
        None,
    )
    risk_state = (
        ScrumStateWriteSet(member_availability_overlays=(overlay,))
        if overlay is not None
        else ScrumStateWriteSet()
    )
    if not outcome:
        return _RiskRecords(counter_claims=(claim,), natural_decision_claims=(eligible,))
    return _evidence_records(
        state,
        _EvidenceBatch(
            evidence,
            "MEMBER_BECAME_UNAVAILABLE",
            state=risk_state,
            counter_claims=(claim,),
            natural_claims=(eligible,),
        ),
    )


def _evidence_records(state: LiveTeamState, batch: _EvidenceBatch) -> _RiskRecords:
    evidence = batch.evidence
    key = _risk_key(state, evidence)
    payload = _evidence_payload(state, evidence)
    envelope = DraftEnvelope(key, "1.0", evidence.occurred_at, payload)
    activity = ActivityEventDraft.create(
        DraftEnvelope(
            key,
            "1.0",
            evidence.occurred_at,
            {"summary": _fallback_summary(evidence)},
        ),
        ActivityDetails(batch.event_type, "RISK", evidence.entity_id, _aggregate_version(state)),
    )
    truth = GroundTruthRecordDraft.create(
        envelope,
        GroundTruthDetails("RISK_EVALUATION", "SIMULATOR_V2"),
    )
    activities = () if batch.event_type == "RISK_EVALUATED" else (activity,)
    projections = () if batch.projection is None else (batch.projection,)
    return _RiskRecords(
        batch.state,
        activities,
        (truth,),
        projections,
        batch.counter_claims,
        batch.natural_claims,
    )


def _evidence_payload(state: LiveTeamState, evidence: _DecisionEvidence) -> dict[str, object]:
    rule = evidence.rule
    return {
        "risk": rule.key,
        "configuration": {
            "algorithm": state.aggregate.blueprint.risks.algorithm_version,
            "profile": state.aggregate.blueprint.risks.profile_name,
            "profile_version": state.aggregate.blueprint.risks.profile_version,
            "trigger": rule.trigger,
            "base_probability": rule.base_probability,
            "coefficients": dict(rule.coefficients.items()),
            "clamp": {"min": rule.clamp.min, "max": rule.clamp.max},
            "mechanical_parameters": dict(rule.mechanical_parameters.items()),
        },
        "factors": evidence.factors,
        "probability": evidence.probability,
        "draw": evidence.draw,
        "outcome": evidence.outcome,
        "eligible_people": [str(item) for item in evidence.eligible_people],
        "wait_delta_microseconds": evidence.wait_delta_microseconds,
        "progress_delta_microseconds": evidence.progress_delta_microseconds,
        "cause": evidence.cause,
        "jira_intent": evidence.jira_intent,
    }


def _merge_records(left: _RiskRecords, right: _RiskRecords) -> _RiskRecords:
    return _RiskRecords(
        _merge_write_sets(left.state, right.state),
        (*left.activity, *right.activity),
        (*left.ground_truth, *right.ground_truth),
        (*left.projection_intents, *right.projection_intents),
        (*left.counter_claims, *right.counter_claims),
        (*left.natural_decision_claims, *right.natural_decision_claims),
    )


def _merge_write_sets(left: ScrumStateWriteSet, right: ScrumStateWriteSet) -> ScrumStateWriteSet:
    values = {}
    for name in left.__dataclass_fields__:
        records = {_identity(item): item for item in getattr(left, name)}
        records.update({_identity(item): item for item in getattr(right, name)})
        values[name] = tuple(records.values())
    return ScrumStateWriteSet(**values)


def _identity(value: object) -> object:
    if hasattr(value, "id"):
        return value.id
    if hasattr(value, "visit_id"):
        return value.visit_id
    if hasattr(value, "scope"):
        return value.scope
    raise TypeError("risk state row has no persistence identity")


def _natural_claim(
    request: _NaturalDecisionRequest,
) -> tuple[SemanticCounterClaim, EligibleNaturalDecisionClaim]:
    state = request.state
    counter = next(
        item
        for item in state.scrum.semantic_counters
        if item.scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE
        and item.scope.scope_id == request.entity_id
        and item.scope.scope_key == request.decision_type.value
    )
    decision = DecisionOccurrence(request.entity_id, request.decision_type, counter.next_value)
    return (
        SemanticCounterClaim(counter.scope, counter.next_value, 1),
        EligibleNaturalDecisionClaim(decision, request.business_date),
    )


def _returned_visit(
    context: _RiskContext, work: WorkItemState
) -> tuple[StatusVisitState, StatusVisitSample, SemanticCounterClaim]:
    state, as_of, draws = context.state, context.as_of, context.draws
    counter = next(
        item
        for item in state.scrum.semantic_counters
        if item.scope.kind is SemanticCounterKind.VISIT_ORDINAL and item.scope.scope_id == work.id
    )
    step = _route_step(state, work, work.current_status_key)
    visit_id = visit_rng_id(work.id, counter.next_value)
    touch = draws.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_TOUCH, 0))
    entry = next(
        item
        for item in state.aggregate.blueprint.timing.entries
        if (item.status_key, item.issue_type, item.story_points)
        == (step.status_key, work.issue_type, work.story_points)
    )
    required = round(
        sample_touch(touch_bounds(entry), touch.unit_value).sampled_hours * MICROSECONDS_PER_HOUR
    )
    visit = StatusVisitState(
        visit_id,
        work.team_id,
        work.run_id,
        work.id,
        counter.next_value,
        StatusVisitLifecycle.OPEN,
        step.status_key,
        step.required_activity,
        None,
        as_of,
        None,
        required,
        0,
        required,
        0,
        0,
        0,
    )
    dwell = draws.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_DWELL, 0))
    sample = StatusVisitSample.create(
        StatusVisitSampleInput(state.aggregate.blueprint, work, visit, dwell, touch)
    )
    return visit, sample, SemanticCounterClaim(counter.scope, counter.next_value, 1)


def _unavailability_overlay(
    context: _RiskContext,
    member_id: UUID,
    duration_days: int,
) -> MemberAvailabilityOverlay:
    state, boundary, rule = context.state, context.as_of, context.rule
    runtime = state.aggregate.runtime
    provenance = {
        "risk": rule.key,
        "profile": state.aggregate.blueprint.risks.profile_name,
        "profile_version": state.aggregate.blueprint.risks.profile_version,
    }
    return MemberAvailabilityOverlay(
        semantic_uuid(
            f"risk-overlay/{runtime.team_id}/{runtime.run_id}/{member_id}/{boundary.date()}"
        ),
        runtime.team_id,
        runtime.run_id,
        member_id,
        "RISK",
        boundary,
        boundary + timedelta(days=duration_days),
        0.0,
        0,
        "Simulated teammate unavailability",
        canonical_json(provenance),
        canonical_sha256(provenance),
        boundary,
    )


def _transition_intent(
    context: _RiskContext, work_id: UUID, status_key: str
) -> ProjectionIntentDraft:
    state, occurred_at = context.state, context.as_of
    status = next(
        item for item in state.aggregate.blueprint.workflow.statuses if item.key == status_key
    )
    payload = {"depends_on": [], "issue_id": str(work_id), "status": status.jira_name}
    key = f"risk/{state.aggregate.runtime.run_id}/{work_id}/{status_key}/{occurred_at.isoformat()}"
    envelope = DraftEnvelope(key, "1.0", occurred_at, payload)
    details = ProjectionDetails(
        "JIRA", "TRANSITION_ISSUE", work_id, _aggregate_version(state), "PENDING"
    )
    return ProjectionIntentDraft.create(envelope, details)


def _intent_payload(intent: ProjectionIntentDraft | None) -> dict[str, object] | None:
    if intent is None:
        return None
    return {"operation": intent.operation_type, "payload": json.loads(intent.canonical_payload)}


def _risk_key(state: LiveTeamState, evidence: _DecisionEvidence) -> str:
    runtime = state.aggregate.runtime
    return (
        f"risk/{runtime.team_id}/{runtime.run_id}/{runtime.version}/"
        f"{evidence.rule.key}/{evidence.entity_id}/{evidence.occurred_at.isoformat()}"
    )


def _fallback_summary(evidence: _DecisionEvidence) -> str:
    result = "occurred" if evidence.outcome else "did not occur"
    return f"{evidence.rule.key.replace('_', ' ').title()} {result}: {evidence.cause}."


def _threshold_crossed(
    context: _RiskContext, visit: StatusVisitState, threshold: int
) -> bool:
    state, as_of = context.state, context.as_of
    cursor = state.aggregate.runtime.simulation_time
    before = max(0, _microseconds(cursor - visit.entered_at) - visit.pause_microseconds)
    after = max(0, _microseconds(as_of - visit.entered_at) - visit.pause_microseconds)
    return before < threshold <= after


def _review_due(state: LiveTeamState, visit: StatusVisitState, as_of: datetime) -> bool:
    cursor = state.aggregate.runtime.simulation_time
    return (
        visit.lifecycle is StatusVisitLifecycle.CLOSED
        and visit.status_key in SUPPORTED_REVIEW_STATUSES
        and visit.closed_at == cursor
        and as_of >= cursor
    )


def _workday_boundary(state: LiveTeamState, as_of: datetime) -> datetime | None:
    cursor = state.aggregate.runtime.simulation_time
    if as_of <= cursor:
        return None
    calendar = BusinessCalendar.from_blueprint(
        state.aggregate.blueprint.team.timezone, state.aggregate.blueprint.calendar
    )
    day = calendar.business_date(cursor)
    final = calendar.business_date(as_of - timedelta.resolution)
    while day <= final:
        interval = calendar.working_interval(day)
        if interval is not None and cursor <= interval.start < as_of:
            return interval.start
        day += timedelta(days=1)
    return None


def _factors(
    state: LiveTeamState, work: WorkItemState, visit: StatusVisitState
) -> dict[str, float]:
    factor_values = {
        item.kind: item.value
        for item in state.scrum.work_item_factors
        if item.work_item_id == work.id
    }
    quality = factor_values.get(FactorKind.DESCRIPTION_QUALITY, 1.0)
    complexity = factor_values.get(FactorKind.LATENT_COMPLEXITY, 0.0)
    prior_rework = max(0, _closed_visit_count(state, work.id) - 1)
    return {
        "size": min(1.0, work.story_points / 13),
        "story_points": min(1.0, work.story_points / 13),
        "poor_description": 1.0 - quality,
        "complexity": complexity,
        "dependency": 1.0 if visit.pause_microseconds else 0.0,
        "prior_rework": min(1.0, prior_rework / 3),
        "availability": 1.0 if visit.member_id is not None else 0.0,
    }


def _member_factors(state: LiveTeamState, member_id: UUID) -> dict[str, float]:
    identity = next(item for item in state.scrum.member_identities if item.id == member_id)
    member = state.aggregate.blueprint.members[identity.blueprint_index]
    owned = sum(
        visit.member_id == member_id and visit.lifecycle is StatusVisitLifecycle.OPEN
        for visit in state.scrum.status_visits
    )
    return {
        "availability": 1.0,
        "utilization": min(1.0, owned / member.max_concurrent_wip),
        "wip_ratio": min(1.0, owned / member.max_concurrent_wip),
    }


def _probability(rule: RiskRule, factors: dict[str, float]) -> float:
    base = rule.base_probability
    if base <= 0:
        probability = 0.0
    elif base >= 1:
        probability = 1.0
    else:
        logit = math.log(base / (1 - base))
        logit += sum(
            float(value) * factors.get(key, 0.0) for key, value in rule.coefficients.items()
        )
        probability = 1 / (1 + math.exp(-logit))
    return min(rule.clamp.max, max(rule.clamp.min, probability))


def _eligible_people(state: LiveTeamState, visit: StatusVisitState) -> tuple[UUID, ...]:
    step = WorkflowRouteStep(status_key=visit.status_key, required_activity=visit.activity_key)
    return _eligible_people_for_activity(state, step)


def _eligible_people_for_activity(
    state: LiveTeamState, step: WorkflowRouteStep
) -> tuple[UUID, ...]:
    if step.required_activity is None:
        return ()
    return tuple(
        identity.id
        for identity in state.scrum.member_identities
        if step.required_activity
        in {
            responsibility.activity
            for responsibility in state.aggregate.blueprint.members[
                identity.blueprint_index
            ].responsibilities
        }
    )


def _route_step(state: LiveTeamState, work: WorkItemState, status_key: str) -> WorkflowRouteStep:
    route = next(
        item
        for item in state.aggregate.blueprint.workflow.routes
        if item.issue_type == work.issue_type
    )
    return next(item for item in route.steps if item.status_key == status_key)


def _require_earlier_step(
    state: LiveTeamState, work: WorkItemState, transition: tuple[str, str]
) -> None:
    source, target = transition
    route = next(
        item
        for item in state.aggregate.blueprint.workflow.routes
        if item.issue_type == work.issue_type
    )
    positions = {step.status_key: index for index, step in enumerate(route.steps)}
    if target not in positions or positions[target] >= positions[source]:
        raise ValueError("review return status must be an earlier configured route step")


def _duration_days(context: _RiskContext, member_id: UUID, occurrence: int) -> int:
    rule, draws = context.rule, context.draws
    configured = rule.mechanical_parameters.root.get("duration_days")
    if isinstance(configured, int) and not isinstance(configured, bool) and configured > 0:
        return configured
    draw = draws.draw(
        DecisionOccurrence(member_id, DecisionType.RISK_MEMBER_UNAVAILABLE_DURATION, occurrence)
    )
    return 1 + min(2, int(draw.unit_value * 3))


def _number(rule: RiskRule, key: str, default: float | None = None) -> float:
    value = rule.mechanical_parameters.root.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{key} must be a non-negative number")
    return float(value)


def _text(rule: RiskRule, key: str) -> str:
    value = rule.mechanical_parameters.root.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be configured")
    return value


def _open_visits(state: LiveTeamState) -> tuple[StatusVisitState, ...]:
    return tuple(
        visit for visit in state.scrum.status_visits if visit.lifecycle is StatusVisitLifecycle.OPEN
    )


def _work(state: LiveTeamState, work_id: UUID) -> WorkItemState:
    return next(item for item in state.scrum.work_items if item.id == work_id)


def _work_visit(state: LiveTeamState, work_id: UUID) -> StatusVisitState:
    return next(
        visit
        for visit in state.scrum.status_visits
        if visit.work_item_id == work_id and visit.lifecycle is StatusVisitLifecycle.OPEN
    )


def _closed_visit_count(state: LiveTeamState, work_id: UUID) -> int:
    return sum(
        visit.work_item_id == work_id and visit.lifecycle is StatusVisitLifecycle.CLOSED
        for visit in state.scrum.status_visits
    )


def _aggregate_version(state: LiveTeamState) -> int:
    return state.aggregate.runtime.version + 1


def _microseconds(value: timedelta) -> int:
    return round(value.total_seconds() * 1_000_000)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be aware")
    return value.astimezone(UTC)
