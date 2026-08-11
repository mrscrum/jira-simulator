"""Integration coverage for service retries and atomic Scrum-tick persistence."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.v2.application.team_tick import TeamTickService
from app.v2.domain.canonical_json import canonical_json
from app.v2.domain.scrum_state import SemanticCounterKind, StatusVisitLifecycle
from app.v2.domain.scrum_tick import TickRequest
from app.v2.persistence.live_models import V2ActivityEventModel
from app.v2.persistence.live_team_store import SqlAlchemyLiveTeamStore
from app.v2.persistence.scrum_state_models import V2MemberBusinessDateConsumptionModel
from app.v2.persistence.team_models import V2TeamRuntimeModel
from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork, StaleRuntimeVersion
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import BLUEPRINT_JSON

FIRST_BOUNDARY = datetime(2026, 8, 13, 16, tzinfo=UTC)
TICK_END = FIRST_BOUNDARY + timedelta(hours=1)


def test_service_commits_runtime_scrum_state_and_ledgers_atomically(v2_session_factory):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)
    before = store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    service = TeamTickService(store, SqlAlchemyV2UnitOfWork(v2_session_factory))

    committed = service.advance(TickRequest(aggregate.team.id, TICK_END, TICK_END))

    after = store.load(aggregate.team.id)
    assert committed.live_slice.runtime.version == before.aggregate.runtime.version + 1
    assert after.aggregate.runtime.simulation_time == TICK_END
    assert any(
        visit.elapsed_work_microseconds > 0 for visit in after.scrum.status_visits
    )
    with v2_session_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(V2MemberBusinessDateConsumptionModel)
        ) > 0
        assert session.scalar(select(func.count()).select_from(V2ActivityEventModel)) > 0


def test_bootstrapped_item_atomically_opens_a_later_timed_route_step(v2_session_factory):
    blueprint_json = _two_timed_step_blueprint()
    aggregate = create_aggregate(v2_session_factory, blueprint_json, FIRST_BOUNDARY)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)
    bootstrapped = store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    item = next(item for item in bootstrapped.scrum.work_items if item.lifecycle == "ACTIVE")
    initial_counter = next(
        counter
        for counter in bootstrapped.scrum.semantic_counters
        if counter.scope.kind is SemanticCounterKind.VISIT_ORDINAL
        and counter.scope.scope_id == item.id
    )
    service = TeamTickService(store, SqlAlchemyV2UnitOfWork(v2_session_factory))

    service.advance(
        TickRequest(
            aggregate.team.id,
            FIRST_BOUNDARY + timedelta(days=2, hours=8),
            FIRST_BOUNDARY + timedelta(days=2, hours=8),
        )
    )

    after = store.load(aggregate.team.id)
    open_visit = next(
        visit
        for visit in after.scrum.status_visits
        if visit.work_item_id == item.id and visit.lifecycle is StatusVisitLifecycle.OPEN
    )
    counter = next(
        value for value in after.scrum.semantic_counters if value.scope == initial_counter.scope
    )
    assert initial_counter.next_value == 1
    assert open_visit.ordinal == 1
    assert open_visit.status_key == "REVIEW"
    assert any(sample.visit_id == open_visit.id for sample in after.scrum.status_visit_samples)
    assert counter.next_value == 2


def test_service_rolls_back_the_whole_transaction_after_scrum_rows_change(
    v2_session_factory, monkeypatch
):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)
    before = store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)

    def fail_before_ledgers(_session, _commit, _runtime):
        raise RuntimeError("injected tick transaction failure")

    monkeypatch.setattr(unit_of_work, "_persist_ledgers", fail_before_ledgers)

    with pytest.raises(RuntimeError, match="injected tick transaction failure"):
        TeamTickService(store, unit_of_work).advance(
            TickRequest(aggregate.team.id, TICK_END, TICK_END)
        )

    assert store.load(aggregate.team.id) == before
    with v2_session_factory() as session:
        runtime = session.get(V2TeamRuntimeModel, str(aggregate.runtime.id))
        assert runtime.version == before.aggregate.runtime.version
        assert session.scalar(
            select(func.count()).select_from(V2MemberBusinessDateConsumptionModel)
        ) == 0
        assert session.scalar(select(func.count()).select_from(V2ActivityEventModel)) == 0


def test_service_reloads_recalculates_and_retries_exactly_once_on_stale_runtime(
    v2_session_factory,
):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    real_store = SqlAlchemyLiveTeamStore(v2_session_factory)
    real_store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    store = _CountingStore(real_store)
    unit_of_work = _StaleOnceUnitOfWork(SqlAlchemyV2UnitOfWork(v2_session_factory))

    committed = TeamTickService(store, unit_of_work).advance(
        TickRequest(aggregate.team.id, TICK_END, TICK_END)
    )

    assert committed.live_slice.runtime.simulation_time == TICK_END
    assert store.loads == 2
    assert unit_of_work.attempts == 2


def test_service_propagates_a_second_stale_runtime_without_a_third_attempt(
    v2_session_factory,
):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    real_store = SqlAlchemyLiveTeamStore(v2_session_factory)
    real_store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    store = _CountingStore(real_store)
    unit_of_work = _AlwaysStaleUnitOfWork()

    with pytest.raises(StaleRuntimeVersion):
        TeamTickService(store, unit_of_work).advance(
            TickRequest(aggregate.team.id, TICK_END, TICK_END)
        )

    assert store.loads == 2
    assert unit_of_work.attempts == 2


class _CountingStore:
    def __init__(self, store):
        self.store = store
        self.loads = 0

    def load(self, team_id):
        self.loads += 1
        return self.store.load(team_id)


class _StaleOnceUnitOfWork:
    def __init__(self, unit_of_work):
        self.unit_of_work = unit_of_work
        self.attempts = 0

    def commit_authoritative_slice(self, command):
        self.attempts += 1
        if self.attempts == 1:
            raise StaleRuntimeVersion("injected first-attempt race")
        return self.unit_of_work.commit_authoritative_slice(command)


class _AlwaysStaleUnitOfWork:
    def __init__(self):
        self.attempts = 0

    def commit_authoritative_slice(self, _command):
        self.attempts += 1
        raise StaleRuntimeVersion("injected persistent race")


def _two_timed_step_blueprint() -> str:
    document = json.loads(BLUEPRINT_JSON)
    document["backlog"]["target_depth"] = 1
    review = {
        "activities": ["development"],
        "category": "IN_PROGRESS",
        "consumes_capacity": True,
        "jira_name": "Review",
        "key": "REVIEW",
        "pauses_service_clock": False,
    }
    document["workflow"]["statuses"].insert(-1, review)
    document["workflow"]["routes"][0]["steps"].insert(
        -1, {"required_activity": "development", "status_key": "REVIEW"}
    )
    review_entries = [
        {**entry, "status_key": "REVIEW"}
        for entry in document["timing"]["entries"]
        if entry["status_key"] == "DEVELOPMENT"
    ]
    document["timing"]["entries"].extend(review_entries)
    return canonical_json(document)
