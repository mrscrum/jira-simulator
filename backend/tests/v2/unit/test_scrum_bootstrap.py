"""Unit coverage for deterministic initial Scrum state construction."""

import json
from datetime import UTC, datetime

from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.scrum_bootstrap import build_initial_scrum_state
from app.v2.domain.scrum_state import StatusVisitLifecycle, WorkItemLifecycle
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import BLUEPRINT_JSON

STARTED_AT = datetime(2026, 8, 11, 16, tzinfo=UTC)


def test_bootstrap_builds_a_deterministic_complete_scrum_state(v2_session_factory):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, STARTED_AT)

    first = build_initial_scrum_state(aggregate, STARTED_AT, SeededDrawSource(aggregate))
    second = build_initial_scrum_state(aggregate, STARTED_AT, SeededDrawSource(aggregate))

    assert first == second
    assert len(first.member_identities) == len(aggregate.blueprint.members)
    assert len(first.work_items) == aggregate.blueprint.backlog.target_depth
    assert len(first.sprints) == 1
    assert first.sprints[0].observed_start_at == STARTED_AT
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
        json.dumps(document, separators=(",", ":"), sort_keys=True),
        STARTED_AT,
    )

    state = build_initial_scrum_state(aggregate, STARTED_AT, SeededDrawSource(aggregate))

    assert all(visit.status_key != "TO_DO" for visit in state.status_visits)
    assert {sample.visit_id for sample in state.status_visit_samples} == {
        visit.id for visit in state.status_visits
    }
