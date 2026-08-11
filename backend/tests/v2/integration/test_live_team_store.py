"""Integration coverage for the coherent live-team store."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.v2.persistence.live_team_store import SqlAlchemyLiveTeamStore
from app.v2.persistence.scrum_state_models import V2SprintModel, V2WorkItemModel
from app.v2.persistence.team_models import V2TeamRuntimeModel
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import BLUEPRINT_JSON

STARTED_AT = datetime(2026, 8, 11, 16, tzinfo=UTC)
FIRST_BOUNDARY = datetime(2026, 8, 13, 16, tzinfo=UTC)


def test_store_bootstrap_is_idempotent_and_reloads_detached_state(v2_session_factory):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)

    first = store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    second = store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    reloaded = SqlAlchemyLiveTeamStore(v2_session_factory).load(aggregate.team.id)

    assert first == second == reloaded
    assert reloaded.aggregate.runtime.state == "RUNNING"
    assert reloaded.aggregate.runtime.simulation_time == FIRST_BOUNDARY
    assert reloaded.aggregate.runtime.next_wake_at == FIRST_BOUNDARY
    assert all(not hasattr(record, "_sa_instance_state") for record in reloaded.scrum.work_items)


def test_store_rolls_back_bootstrap_rows_and_runtime_when_persistence_fails(
    v2_session_factory, monkeypatch
):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, STARTED_AT)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)

    def fail_after_scrum_rows(*_args):
        raise RuntimeError("injected bootstrap failure")

    monkeypatch.setattr(store, "_after_scrum_persisted", fail_after_scrum_rows)

    with pytest.raises(RuntimeError, match="injected bootstrap failure"):
        store.ensure_bootstrapped(aggregate.team.id, STARTED_AT)

    with v2_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(V2WorkItemModel)) == 0
        assert session.scalar(select(func.count()).select_from(V2SprintModel)) == 0
        runtime = session.get(V2TeamRuntimeModel, str(aggregate.runtime.id))
        assert runtime.state == "CREATED"


def test_store_bootstrap_before_boundary_wakes_for_the_planned_sprint(v2_session_factory):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, STARTED_AT)

    state = SqlAlchemyLiveTeamStore(v2_session_factory).ensure_bootstrapped(
        aggregate.team.id, STARTED_AT
    )

    assert state.aggregate.runtime.state == "RUNNING"
    assert state.aggregate.runtime.simulation_time == STARTED_AT
    assert state.aggregate.runtime.next_wake_at == FIRST_BOUNDARY
    assert not state.scrum.sprint_scope
    assert not state.scrum.status_visits
    assert not state.scrum.status_visit_samples
