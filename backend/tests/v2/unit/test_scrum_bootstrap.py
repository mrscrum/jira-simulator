"""Unit coverage for deterministic initial Scrum state construction."""

import json
from datetime import UTC, datetime

from app.v2.domain.canonical_json import canonical_json
from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.scrum_bootstrap import build_initial_scrum_state
from app.v2.domain.scrum_state import SprintLifecycle, StatusVisitLifecycle, WorkItemLifecycle
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import BLUEPRINT_JSON

STARTED_AT = datetime(2026, 8, 11, 16, tzinfo=UTC)
FIRST_BOUNDARY = datetime(2026, 8, 13, 16, tzinfo=UTC)


def test_bootstrap_builds_a_deterministic_complete_scrum_state(v2_session_factory):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)

    first = build_initial_scrum_state(aggregate, FIRST_BOUNDARY, SeededDrawSource(aggregate))
    second = build_initial_scrum_state(aggregate, FIRST_BOUNDARY, SeededDrawSource(aggregate))

    assert first == second
    assert len(first.member_identities) == len(aggregate.blueprint.members)
    assert len(first.work_items) == aggregate.blueprint.backlog.target_depth
    assert len(first.sprints) == 1
    assert first.sprints[0].observed_start_at == FIRST_BOUNDARY
    active_points = sum(
        item.story_points
        for item in first.work_items
        if item.lifecycle is WorkItemLifecycle.ACTIVE
    )
    assert active_points <= aggregate.blueprint.scrum.capacity_max_points
    assert all(visit.lifecycle is StatusVisitLifecycle.OPEN for visit in first.status_visits)
    assert {sample.visit_id for sample in first.status_visit_samples} == {
        visit.id for visit in first.status_visits
    }


def test_bootstrap_skips_zero_touch_route_steps_without_a_status_sample(
    v2_session_factory,
):
    document = json.loads(BLUEPRINT_JSON)
    document["workflow"]["statuses"][0]["consumes_capacity"] = False
    document["workflow"]["statuses"][0]["activities"] = []
    document["workflow"]["routes"][0]["steps"][0]["required_activity"] = None
    aggregate = create_aggregate(
        v2_session_factory,
        canonical_json(document),
        FIRST_BOUNDARY,
    )

    state = build_initial_scrum_state(aggregate, FIRST_BOUNDARY, SeededDrawSource(aggregate))

    assert all(visit.status_key != "TO_DO" for visit in state.status_visits)
    assert {sample.visit_id for sample in state.status_visit_samples} == {
        visit.id for visit in state.status_visits
    }


def test_bootstrap_before_first_boundary_only_plans_the_sprint(v2_session_factory):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, STARTED_AT)

    state = build_initial_scrum_state(aggregate, STARTED_AT, SeededDrawSource(aggregate))

    assert state.sprints[0].lifecycle is SprintLifecycle.PLANNED
    assert state.sprints[0].observed_start_at is None
    assert not state.sprint_scope
    assert not state.status_visits
    assert not state.status_visit_samples
    assert all(item.lifecycle is WorkItemLifecycle.BACKLOG for item in state.work_items)


def test_bootstrap_uses_local_cadence_for_a_sprint_crossing_dst(v2_session_factory):
    document = json.loads(BLUEPRINT_JSON)
    document["scrum"]["first_boundary"] = "2026-10-30T16:00:00Z"
    aggregate = create_aggregate(
        v2_session_factory,
        canonical_json(document),
        datetime(2026, 10, 30, 16, tzinfo=UTC),
    )

    state = build_initial_scrum_state(
        aggregate,
        datetime(2026, 10, 30, 16, tzinfo=UTC),
        SeededDrawSource(aggregate),
    )

    assert state.sprints[0].planned_end_at == datetime(2026, 11, 13, 17, tzinfo=UTC)


def test_bootstrap_continues_past_capacity_target_until_minimum_is_reached(
    v2_session_factory,
):
    document = json.loads(BLUEPRINT_JSON)
    document["scrum"]["capacity_min_points"] = 35
    document["scrum"]["capacity_max_points"] = 35
    aggregate = create_aggregate(v2_session_factory, canonical_json(document), FIRST_BOUNDARY)

    state = build_initial_scrum_state(aggregate, FIRST_BOUNDARY, SeededDrawSource(aggregate))

    scoped_ids = {scope.work_item_id for scope in state.sprint_scope}
    scoped_points = sum(item.story_points for item in state.work_items if item.id in scoped_ids)
    assert scoped_points >= 35
