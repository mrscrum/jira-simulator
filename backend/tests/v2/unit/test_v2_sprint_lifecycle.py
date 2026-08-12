"""Behavioral coverage for fixed Scrum sprint boundaries."""

import json
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.scrum_bootstrap import build_initial_scrum_state
from app.v2.domain.scrum_state import (
    ScrumStateSnapshot,
    SprintLifecycle,
    StatusVisitLifecycle,
    WorkItemLifecycle,
)
from app.v2.domain.scrum_tick import TickRequest, calculate_scrum_tick
from app.v2.domain.sprint_lifecycle import cross_sprint_boundary
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import BLUEPRINT_JSON

STARTED_AT = datetime(2026, 8, 11, 16, tzinfo=UTC)
FIRST_BOUNDARY = datetime(2026, 8, 13, 16, tzinfo=UTC)


def test_first_boundary_activates_planned_sprint_and_selects_scope_before_work(
    v2_session_factory,
):
    state = _live_state(v2_session_factory, STARTED_AT)

    transition = cross_sprint_boundary(state, FIRST_BOUNDARY)

    sprint = transition.state.sprints[0]
    scoped_ids = {entry.work_item_id for entry in transition.state.sprint_scope}
    assert sprint.lifecycle is SprintLifecycle.ACTIVE
    assert sprint.observed_start_at == FIRST_BOUNDARY
    assert scoped_ids
    assert all(
        item.lifecycle is WorkItemLifecycle.ACTIVE
        for item in transition.state.work_items
        if item.id in scoped_ids
    )
    assert all(
        visit.entered_at == FIRST_BOUNDARY
        for visit in transition.state.status_visits
        if visit.lifecycle is StatusVisitLifecycle.OPEN
    )
    assert [intent.operation_type for intent in transition.projection_intents] == [
        "CREATE_SPRINT",
        "SCOPE_SPRINT",
        "START_SPRINT",
    ]


def test_authoritative_tick_runs_lifecycle_before_work_at_the_first_boundary(
    v2_session_factory,
):
    state = _live_state(v2_session_factory, STARTED_AT)
    runtime = replace(
        state.aggregate.runtime,
        state="RUNNING",
        simulation_time=FIRST_BOUNDARY,
        next_wake_at=FIRST_BOUNDARY,
    )
    state = replace(state, aggregate=replace(state.aggregate, runtime=runtime))

    command = calculate_scrum_tick(
        state,
        TickRequest(state.aggregate.team.id, FIRST_BOUNDARY, FIRST_BOUNDARY),
        SeededDrawSource(state.aggregate),
    )

    assert command.state.sprints[0].lifecycle is SprintLifecycle.ACTIVE
    assert command.live_slice.runtime_after.simulation_time == FIRST_BOUNDARY
    assert [intent.operation_type for intent in command.live_slice.projection_intents] == [
        "CREATE_SPRINT",
        "SCOPE_SPRINT",
        "START_SPRINT",
    ]


def test_tick_stops_at_a_future_planned_boundary_without_crediting_work(
    v2_session_factory,
):
    state = _live_state(v2_session_factory, STARTED_AT)
    runtime = replace(
        state.aggregate.runtime,
        state="RUNNING",
        simulation_time=STARTED_AT,
        next_wake_at=FIRST_BOUNDARY,
    )
    state = replace(state, aggregate=replace(state.aggregate, runtime=runtime))

    command = calculate_scrum_tick(
        state,
        TickRequest(
            state.aggregate.team.id,
            FIRST_BOUNDARY + timedelta(hours=1),
            FIRST_BOUNDARY + timedelta(hours=1),
        ),
        SeededDrawSource(state.aggregate),
    )

    assert command.live_slice.runtime_after.simulation_time == FIRST_BOUNDARY
    assert command.state.work_items == ()
    assert command.state.status_visits == ()


def test_rollover_preserves_carryover_and_orders_it_before_ranked_backlog(
    v2_session_factory,
):
    state = _live_state(v2_session_factory, FIRST_BOUNDARY)
    active = next(
        item for item in state.scrum.work_items if item.lifecycle is WorkItemLifecycle.ACTIVE
    )
    visit = next(item for item in state.scrum.status_visits if item.work_item_id == active.id)
    sample = next(item for item in state.scrum.status_visit_samples if item.visit_id == visit.id)
    boundary = state.scrum.sprints[0].planned_end_at

    transition = cross_sprint_boundary(state, boundary)

    successor = next(sprint for sprint in transition.state.sprints if sprint.ordinal == 1)
    successor_scope = [
        entry for entry in transition.state.sprint_scope if entry.sprint_id == successor.id
    ]
    work_by_id = {item.id: item for item in state.scrum.work_items}
    carry_ids = [
        entry.work_item_id
        for entry in state.scrum.sprint_scope
        if work_by_id[entry.work_item_id].lifecycle is WorkItemLifecycle.ACTIVE
    ]
    assert [entry.work_item_id for entry in successor_scope[: len(carry_ids)]] == carry_ids
    assert active not in transition.state.work_items
    assert visit not in transition.state.status_visits
    assert sample not in transition.state.status_visit_samples
    backlog_by_id = {
        item.id: item
        for item in state.scrum.work_items
        if item.lifecycle is WorkItemLifecycle.BACKLOG
    }
    newly_selected = [entry.work_item_id for entry in successor_scope[len(carry_ids) :]]
    assert newly_selected == sorted(
        newly_selected, key=lambda item_id: backlog_by_id[item_id].simulator_rank
    )


def test_rollover_is_exactly_once_and_intents_have_dependency_order(
    v2_session_factory,
):
    state = _live_state(v2_session_factory, FIRST_BOUNDARY)
    boundary = state.scrum.sprints[0].planned_end_at

    transition = cross_sprint_boundary(state, boundary)
    after = LiveTeamState(state.aggregate, _apply_transition(state.scrum, transition.state))
    repeated = cross_sprint_boundary(after, boundary)

    assert repeated.state == type(repeated.state)()
    assert repeated.projection_intents == ()
    operations = [intent.operation_type for intent in transition.projection_intents]
    assert operations == [
        "COMPLETE_SPRINT",
        "CREATE_SPRINT",
        "SCOPE_SPRINT",
        "START_SPRINT",
    ]
    payloads = [json.loads(intent.canonical_payload) for intent in transition.projection_intents]
    assert payloads[0]["depends_on"] == []
    assert payloads[1]["depends_on"] == [transition.projection_intents[0].semantic_key]
    assert payloads[2]["depends_on"] == [transition.projection_intents[1].semantic_key]
    assert payloads[3]["depends_on"] == [transition.projection_intents[2].semantic_key]


def _live_state(v2_session_factory, started_at: datetime) -> LiveTeamState:
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, started_at)
    write_set = build_initial_scrum_state(aggregate, started_at, SeededDrawSource(aggregate))
    return LiveTeamState(aggregate, ScrumStateSnapshot.from_write_set(write_set))


def _apply_transition(snapshot: ScrumStateSnapshot, write_set) -> ScrumStateSnapshot:
    values = {}
    for field in fields(ScrumStateSnapshot):
        existing = getattr(snapshot, field.name)
        changes = getattr(write_set, field.name)
        if not changes:
            values[field.name] = existing
            continue
        changed_by_identity = {_identity(item): item for item in changes}
        retained = tuple(changed_by_identity.pop(_identity(item), item) for item in existing)
        values[field.name] = (*retained, *changed_by_identity.values())
    return replace(snapshot, **values)


def _identity(item):
    if hasattr(item, "id"):
        return item.id
    if hasattr(item, "visit_id"):
        return item.visit_id
    return item.scope
