"""Focused behavioral coverage for the first pragmatic causal risks."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.canonical_json import canonical_json
from app.v2.domain.deterministic_rng import DecisionOccurrence, DecisionType, visit_rng_id
from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.risks import evaluate_due_risks
from app.v2.domain.sampling import sample_touch, touch_bounds
from app.v2.domain.scrum_state import (
    ScrumStateSnapshot,
    SemanticCounterKind,
    StatusVisitLifecycle,
    StatusVisitSample,
    StatusVisitSampleInput,
    StatusVisitState,
    WorkItemLifecycle,
)
from app.v2.persistence.live_team_store import SqlAlchemyLiveTeamStore
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import BLUEPRINT_JSON

BOUNDARY = datetime(2026, 8, 13, 16, tzinfo=UTC)
ONE_HOUR_MICROSECONDS = 3_600_000_000


def test_long_stay_emits_sampled_threshold_evidence_once_when_crossed(v2_session_factory):
    state = _state(v2_session_factory, [_rule("LONG_STAY", "STATUS_AGED")])
    visit = _active_visit(state)
    sample = _sample(state, visit.id)
    threshold = visit.entered_at + timedelta(hours=sample.dwell_sampled_hours)
    state = _at_cursor(state, threshold - timedelta(microseconds=1))

    evaluation = evaluate_due_risks(
        state, threshold + timedelta(microseconds=1), SeededDrawSource(state.aggregate)
    )

    assert [event.event_type for event in evaluation.activity] == ["LONG_STAY_DETECTED"]
    truth = json.loads(evaluation.ground_truth[0].canonical_payload)
    assert truth["configuration"]["profile"] == "TEST_RISKS"
    assert truth["cause"] == "sampled dwell threshold crossed"
    assert truth["progress_delta_microseconds"] == 0
    assert truth["wait_delta_microseconds"] == 0
    assert truth["jira_intent"] is None


def test_review_rejection_returns_to_configured_earlier_step_and_retains_history(
    v2_session_factory,
):
    rule = _rule(
        "REVIEW_REJECTION",
        "STATUS_EXITED",
        mechanical_parameters={"return_status": "DEVELOPMENT"},
    )
    state = _review_completed_state(v2_session_factory, rule)
    review = next(visit for visit in state.scrum.status_visits if visit.status_key == "CODE_REVIEW")

    evaluation = evaluate_due_risks(state, review.closed_at, SeededDrawSource(state.aggregate))

    assert evaluation.state.work_items[0].current_status_key == "DEVELOPMENT"
    assert evaluation.state.work_items[0].lifecycle is WorkItemLifecycle.ACTIVE
    returned = evaluation.state.status_visits[0]
    assert returned.status_key == "DEVELOPMENT"
    assert returned.ordinal > review.ordinal
    assert review.lifecycle is StatusVisitLifecycle.CLOSED
    assert evaluation.projection_intents[0].operation_type == "TRANSITION_ISSUE"
    assert json.loads(evaluation.projection_intents[0].canonical_payload) == {
        "depends_on": [],
        "issue_id": str(review.work_item_id),
        "status": "Development",
    }


def test_review_rejection_is_timestamped_at_its_due_status_boundary(v2_session_factory):
    rule = _rule(
        "REVIEW_REJECTION",
        "STATUS_EXITED",
        mechanical_parameters={"return_status": "DEVELOPMENT"},
    )
    state = _review_completed_state(v2_session_factory, rule)
    review = next(visit for visit in state.scrum.status_visits if visit.status_key == "CODE_REVIEW")

    evaluation = evaluate_due_risks(
        state,
        review.closed_at + timedelta(hours=1),
        SeededDrawSource(state.aggregate),
    )

    returned_work = evaluation.state.work_items[0]
    returned_visit = evaluation.state.status_visits[0]
    assert returned_work.updated_at == review.closed_at
    assert returned_visit.entered_at == review.closed_at
    assert evaluation.ground_truth[0].occurred_at == review.closed_at


def test_cancellation_closes_work_and_releases_owner_at_workday_start(v2_session_factory):
    rule = _rule(
        "CANCELLATION",
        "WORKDAY_STARTED",
        mechanical_parameters={"target_status": "CANCELLED"},
    )
    state = _state(v2_session_factory, [rule], cancelled=True)
    visit = _active_visit(state)

    evaluation = evaluate_due_risks(
        state, BOUNDARY + timedelta(hours=1), SeededDrawSource(state.aggregate)
    )

    cancelled = next(item for item in evaluation.state.work_items if item.id == visit.work_item_id)
    closed = next(item for item in evaluation.state.status_visits if item.id == visit.id)
    assert cancelled.lifecycle is WorkItemLifecycle.CANCELLED
    assert cancelled.current_status_key == "CANCELLED"
    assert closed.id == visit.id
    assert closed.lifecycle is StatusVisitLifecycle.CLOSED
    assert closed.member_id is None
    assert evaluation.natural_decision_claims[0].business_date == BOUNDARY.date()


def test_external_dependency_pauses_only_the_selected_visit_with_causal_delta(
    v2_session_factory,
):
    rule = _rule(
        "EXTERNAL_DEPENDENCY",
        "STATUS_ENTERED",
        mechanical_parameters={"wait_hours": 1},
    )
    state = _state(v2_session_factory, [rule])
    visit = _active_visit(state)

    evaluation = evaluate_due_risks(
        state, BOUNDARY + timedelta(hours=1), SeededDrawSource(state.aggregate)
    )

    blocked = evaluation.state.status_visits[0]
    assert blocked.id == visit.id
    assert blocked.member_id is None
    assert blocked.remaining_work_microseconds == visit.remaining_work_microseconds
    assert blocked.pause_microseconds == visit.pause_microseconds + ONE_HOUR_MICROSECONDS
    assert blocked.queue_microseconds == visit.queue_microseconds + ONE_HOUR_MICROSECONDS
    truth = json.loads(evaluation.ground_truth[0].canonical_payload)
    assert truth["eligible_people"] == [str(visit.member_id)]
    assert truth["wait_delta_microseconds"] == ONE_HOUR_MICROSECONDS
    assert truth["progress_delta_microseconds"] == 0


def test_member_unavailability_persists_zero_capacity_overlay(v2_session_factory):
    rule = _rule(
        "MEMBER_UNAVAILABLE",
        "WORKDAY_STARTED",
        mechanical_parameters={"duration_days": 2},
    )
    state = _state(v2_session_factory, [rule])
    visit = _active_visit(state)

    evaluation = evaluate_due_risks(
        state, BOUNDARY + timedelta(hours=1), SeededDrawSource(state.aggregate)
    )

    overlay = evaluation.state.member_availability_overlays[0]
    assert overlay.member_id == visit.member_id
    assert overlay.availability_fraction == 0.0
    assert overlay.daily_capacity_ceiling_microseconds == 0
    assert overlay.ends_at == BOUNDARY + timedelta(days=2)
    assert evaluation.natural_decision_claims[0].decision.decision_type is (
        DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME
    )


def test_due_false_review_rejection_persists_evaluation_without_activity(v2_session_factory):
    rule = _rule(
        "REVIEW_REJECTION",
        "STATUS_EXITED",
        probability=0.0,
        mechanical_parameters={"return_status": "DEVELOPMENT"},
    )
    state = _review_completed_state(v2_session_factory, rule)
    review = next(visit for visit in state.scrum.status_visits if visit.status_key == "CODE_REVIEW")

    evaluation = evaluate_due_risks(state, review.closed_at, SeededDrawSource(state.aggregate))

    assert evaluation.activity == ()
    assert evaluation.state == _empty_write_set()
    assert json.loads(evaluation.ground_truth[0].canonical_payload)["outcome"] is False


def test_due_false_cancellation_persists_evaluation_without_activity(v2_session_factory):
    rule = _rule(
        "CANCELLATION",
        "WORKDAY_STARTED",
        probability=0.0,
        mechanical_parameters={"target_status": "CANCELLED"},
    )
    state = _state(v2_session_factory, [rule], cancelled=True)

    evaluation = evaluate_due_risks(
        state, BOUNDARY + timedelta(hours=1), SeededDrawSource(state.aggregate)
    )

    assert evaluation.activity == ()
    assert evaluation.state == _empty_write_set()
    assert json.loads(evaluation.ground_truth[0].canonical_payload)["outcome"] is False
    active_count = sum(
        item.lifecycle is WorkItemLifecycle.ACTIVE for item in state.scrum.work_items
    )
    assert len(evaluation.natural_decision_claims) == active_count
    assert len(evaluation.ground_truth) == active_count


def test_due_false_dependency_is_recorded_once_for_the_entry(v2_session_factory):
    rule = _rule(
        "EXTERNAL_DEPENDENCY",
        "STATUS_ENTERED",
        probability=0.0,
        mechanical_parameters={"wait_hours": 1},
    )
    state = _state(v2_session_factory, [rule])
    first = evaluate_due_risks(
        state, BOUNDARY + timedelta(minutes=30), SeededDrawSource(state.aggregate)
    )
    resumed = _at_cursor(state, BOUNDARY + timedelta(minutes=30))
    second = evaluate_due_risks(
        resumed,
        BOUNDARY + timedelta(hours=1),
        _RejectDependencyDraws(state.aggregate),
    )

    assert first.activity == ()
    assert json.loads(first.ground_truth[0].canonical_payload)["outcome"] is False
    assert second.ground_truth == ()


def test_due_false_unavailability_persists_evaluation_without_activity(v2_session_factory):
    rule = _rule(
        "MEMBER_UNAVAILABLE",
        "WORKDAY_STARTED",
        probability=0.0,
        mechanical_parameters={"duration_days": 2},
    )
    state = _state(v2_session_factory, [rule])

    evaluation = evaluate_due_risks(
        state, BOUNDARY + timedelta(hours=1), SeededDrawSource(state.aggregate)
    )

    assert evaluation.activity == ()
    assert evaluation.state == _empty_write_set()
    assert json.loads(evaluation.ground_truth[0].canonical_payload)["outcome"] is False
    assert len(evaluation.natural_decision_claims) == 1


def test_dependency_continuation_records_wait_without_redraw_or_another_start(
    v2_session_factory,
):
    rule = _rule(
        "EXTERNAL_DEPENDENCY",
        "STATUS_ENTERED",
        mechanical_parameters={"wait_hours": 1},
    )
    state = _state(v2_session_factory, [rule])
    visit = _active_visit(state)
    first = evaluate_due_risks(
        state, BOUNDARY + timedelta(minutes=30), SeededDrawSource(state.aggregate)
    )
    blocked = first.state.status_visits[0]
    resumed = _with_visit(state, blocked, BOUNDARY + timedelta(minutes=30))

    second = evaluate_due_risks(
        resumed,
        BOUNDARY + timedelta(hours=1),
        _RejectDependencyDraws(state.aggregate),
    )

    continued = second.state.status_visits[0]
    assert continued.id == visit.id
    assert continued.pause_microseconds == ONE_HOUR_MICROSECONDS
    assert second.activity == ()
    assert second.projection_intents == ()
    assert len(second.ground_truth) == 1
    continuation = second.ground_truth[0]
    truth = json.loads(continuation.canonical_payload)
    assert str(visit.id) in continuation.semantic_key
    assert truth["draw"] is None
    assert truth["outcome"] is True
    assert truth["wait_delta_microseconds"] == ONE_HOUR_MICROSECONDS // 2
    assert truth["progress_delta_microseconds"] == 0
    assert truth["cause"] == "external dependency pause continuation"


def test_long_stay_does_not_cross_during_non_business_weekend_time(v2_session_factory):
    rule = _rule(
        "LONG_STAY",
        "STATUS_AGED",
        mechanical_parameters={"threshold_multiplier": 10.0},
    )
    state = _state(v2_session_factory, [rule])
    visit = max(
        (item for item in state.scrum.status_visits if item.lifecycle is StatusVisitLifecycle.OPEN),
        key=lambda item: _sample(state, item.id).dwell_sampled_hours,
    )
    friday_start = BOUNDARY + timedelta(days=1)
    monday_start = BOUNDARY + timedelta(days=4)
    state = _at_cursor(state, friday_start)

    evaluation = evaluate_due_risks(state, monday_start, SeededDrawSource(state.aggregate))

    assert all(event.aggregate_id != visit.work_item_id for event in evaluation.activity)


def test_cancellation_has_terminal_precedence_over_same_tick_dependency(v2_session_factory):
    rules = [
        _rule(
            "CANCELLATION",
            "WORKDAY_STARTED",
            mechanical_parameters={"target_status": "CANCELLED"},
        ),
        _rule(
            "EXTERNAL_DEPENDENCY",
            "STATUS_ENTERED",
            mechanical_parameters={"wait_hours": 1},
        ),
    ]
    state = _state(v2_session_factory, rules, cancelled=True)
    visit = _active_visit(state)

    evaluation = evaluate_due_risks(
        state, BOUNDARY + timedelta(hours=1), SeededDrawSource(state.aggregate)
    )

    final_visit = next(item for item in evaluation.state.status_visits if item.id == visit.id)
    assert final_visit.lifecycle is StatusVisitLifecycle.CLOSED
    assert final_visit.member_id is None
    assert final_visit.pause_microseconds == visit.pause_microseconds


def _state(v2_session_factory, rules: list[dict], *, cancelled: bool = False) -> LiveTeamState:
    document = json.loads(BLUEPRINT_JSON)
    document["risks"] = {
        "algorithm_version": "TEST_V1",
        "profile_name": "TEST_RISKS",
        "profile_version": 1,
        "rules": rules,
    }
    if cancelled:
        document["workflow"]["statuses"].append(
            {
                "activities": [],
                "category": "DONE",
                "consumes_capacity": False,
                "jira_name": "Cancelled",
                "key": "CANCELLED",
                "pauses_service_clock": False,
            }
        )
        document["workflow"]["routes"][0]["steps"].insert(
            -1, {"required_activity": None, "status_key": "CANCELLED"}
        )
    aggregate = create_aggregate(v2_session_factory, canonical_json(document), BOUNDARY)
    return SqlAlchemyLiveTeamStore(v2_session_factory).ensure_bootstrapped(
        aggregate.team.id, BOUNDARY
    )


def _review_completed_state(v2_session_factory, rule: dict) -> LiveTeamState:
    document = json.loads(BLUEPRINT_JSON)
    document["risks"] = {
        "algorithm_version": "TEST_V1",
        "profile_name": "TEST_RISKS",
        "profile_version": 1,
        "rules": [rule],
    }
    document["workflow"]["statuses"].insert(
        -1,
        {
            "activities": ["code_review"],
            "category": "IN_PROGRESS",
            "consumes_capacity": True,
            "jira_name": "Code Review",
            "key": "CODE_REVIEW",
            "pauses_service_clock": False,
        },
    )
    document["workflow"]["routes"][0]["steps"].insert(
        -1, {"required_activity": "code_review", "status_key": "CODE_REVIEW"}
    )
    document["members"][1]["responsibilities"].append(
        {"activity": "code_review", "proficiency": 1.0}
    )
    timing = dict(document["timing"]["entries"][0])
    timing["status_key"] = "CODE_REVIEW"
    document["timing"]["entries"].append(timing)
    state = _state_from_document(v2_session_factory, document)
    work = next(
        item for item in state.scrum.work_items if item.lifecycle is WorkItemLifecycle.ACTIVE
    )
    development = next(
        visit for visit in state.scrum.status_visits if visit.work_item_id == work.id
    )
    development_closed = replace(
        development,
        lifecycle=StatusVisitLifecycle.CLOSED,
        member_id=None,
        closed_at=BOUNDARY + timedelta(hours=1),
        elapsed_work_microseconds=development.required_work_microseconds,
        remaining_work_microseconds=0,
        credited_labor_microseconds=development.required_work_microseconds,
    )
    review_work = replace(
        work,
        current_status_key="CODE_REVIEW",
        updated_at=development_closed.closed_at,
    )
    review_id = visit_rng_id(work.id, 1)
    draws = SeededDrawSource(state.aggregate)
    touch_draw = draws.draw(DecisionOccurrence(review_id, DecisionType.STATUS_TOUCH, 0))
    timing_entry = next(
        item
        for item in state.aggregate.blueprint.timing.entries
        if item.status_key == "CODE_REVIEW"
        and item.issue_type == review_work.issue_type
        and item.story_points == review_work.story_points
    )
    required = round(
        sample_touch(touch_bounds(timing_entry), touch_draw.unit_value).sampled_hours
        * ONE_HOUR_MICROSECONDS
    )
    review_open = StatusVisitState(
        review_id,
        work.team_id,
        work.run_id,
        work.id,
        1,
        StatusVisitLifecycle.OPEN,
        "CODE_REVIEW",
        "code_review",
        development.member_id,
        development_closed.closed_at,
        None,
        required,
        0,
        required,
        0,
        0,
        0,
    )
    review_sample = StatusVisitSample.create(
        StatusVisitSampleInput(
            state.aggregate.blueprint,
            review_work,
            review_open,
            draws.draw(DecisionOccurrence(review_id, DecisionType.STATUS_DWELL, 0)),
            touch_draw,
        )
    )
    review_open = replace(
        review_open,
        required_work_microseconds=review_sample.required_work_microseconds,
        remaining_work_microseconds=review_sample.required_work_microseconds,
    )
    review_closed = replace(
        review_open,
        lifecycle=StatusVisitLifecycle.CLOSED,
        member_id=None,
        closed_at=BOUNDARY + timedelta(hours=2),
        elapsed_work_microseconds=review_open.required_work_microseconds,
        remaining_work_microseconds=0,
        credited_labor_microseconds=review_open.required_work_microseconds,
    )
    done_work = replace(
        review_work,
        lifecycle=WorkItemLifecycle.DONE,
        current_status_key="DONE",
        updated_at=review_closed.closed_at,
    )
    counters = tuple(
        replace(counter, next_value=2)
        if counter.scope.kind is SemanticCounterKind.VISIT_ORDINAL
        and counter.scope.scope_id == work.id
        else counter
        for counter in state.scrum.semantic_counters
    )
    snapshot = replace(
        state.scrum,
        work_items=tuple(
            done_work if item.id == work.id else item for item in state.scrum.work_items
        ),
        status_visits=(
            *tuple(
                development_closed if item.id == development.id else item
                for item in state.scrum.status_visits
            ),
            review_closed,
        ),
        status_visit_samples=(*state.scrum.status_visit_samples, review_sample),
        semantic_counters=counters,
    )
    return LiveTeamState(
        replace(
            state.aggregate,
            runtime=replace(
                state.aggregate.runtime,
                simulation_time=review_closed.closed_at,
                next_wake_at=review_closed.closed_at,
            ),
        ),
        ScrumStateSnapshot.from_write_set(_snapshot_write_set(snapshot)),
    )


def _state_from_document(v2_session_factory, document: dict) -> LiveTeamState:
    aggregate = create_aggregate(v2_session_factory, canonical_json(document), BOUNDARY)
    return SqlAlchemyLiveTeamStore(v2_session_factory).ensure_bootstrapped(
        aggregate.team.id, BOUNDARY
    )


def _snapshot_write_set(snapshot: ScrumStateSnapshot):
    from app.v2.domain.scrum_state import ScrumStateWriteSet

    return ScrumStateWriteSet(
        **{name: getattr(snapshot, name) for name in snapshot.__dataclass_fields__}
    )


def _at_cursor(state: LiveTeamState, cursor: datetime) -> LiveTeamState:
    runtime = replace(state.aggregate.runtime, simulation_time=cursor, next_wake_at=cursor)
    return replace(state, aggregate=replace(state.aggregate, runtime=runtime))


def _with_visit(state: LiveTeamState, changed: StatusVisitState, cursor: datetime) -> LiveTeamState:
    visits = tuple(changed if item.id == changed.id else item for item in state.scrum.status_visits)
    return _at_cursor(replace(state, scrum=replace(state.scrum, status_visits=visits)), cursor)


def _empty_write_set():
    from app.v2.domain.scrum_state import ScrumStateWriteSet

    return ScrumStateWriteSet()


class _RejectDependencyDraws:
    def __init__(self, aggregate) -> None:
        self._delegate = SeededDrawSource(aggregate)

    def draw(self, decision, draw_index=0):
        if decision.decision_type is DecisionType.RISK_EXTERNAL_DEPENDENCY_OUTCOME:
            raise AssertionError("dependency outcome was redrawn")
        return self._delegate.draw(decision, draw_index)


def _active_visit(state: LiveTeamState) -> StatusVisitState:
    return next(
        visit for visit in state.scrum.status_visits if visit.lifecycle is StatusVisitLifecycle.OPEN
    )


def _sample(state: LiveTeamState, visit_id):
    return next(
        sample for sample in state.scrum.status_visit_samples if sample.visit_id == visit_id
    )


def _rule(
    key: str,
    trigger: str,
    *,
    probability: float = 1.0,
    mechanical_parameters: dict | None = None,
) -> dict:
    return {
        "base_probability": probability,
        "clamp": {"max": probability, "min": probability},
        "coefficients": {
            "complexity": 0.2,
            "poor_description": 0.2,
            "prior_rework": 0.2,
            "size": 0.2,
        },
        "key": key,
        "mechanical_parameters": mechanical_parameters or {"threshold_multiplier": 1.0},
        "trigger": trigger,
    }
