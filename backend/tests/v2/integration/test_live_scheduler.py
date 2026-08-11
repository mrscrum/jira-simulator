"""Integration coverage for persisted scheduling and restart semantics."""

import json
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.v2.application.live_scheduler import LiveScheduler, SchedulerDependencies
from app.v2.application.team_tick import TeamTickService
from app.v2.domain.canonical_json import canonical_json
from app.v2.domain.live_slice import ProjectionPageQuery
from app.v2.domain.scrum_tick import TickRequest
from app.v2.persistence.due_team_store import SqlAlchemyDueTeamStore
from app.v2.persistence.live_models import V2ActivityEventModel
from app.v2.persistence.live_team_store import SqlAlchemyLiveTeamStore
from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork
from app.v2.runtime import register_v2_job
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import BLUEPRINT_JSON

FIRST_BOUNDARY = datetime(2026, 8, 13, 16, tzinfo=UTC)


def test_one_due_team_runs_through_the_authoritative_tick_service(v2_session_factory):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)
    store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    scheduler = _scheduler(v2_session_factory, store=store)
    as_of = FIRST_BOUNDARY + timedelta(hours=1)

    result = scheduler.run_due(as_of)

    assert result.attempted == (aggregate.team.id,)
    assert result.succeeded == (aggregate.team.id,)
    assert result.failed == ()
    assert store.load(aggregate.team.id).aggregate.runtime.simulation_time == as_of


def test_due_team_activates_a_planned_sprint_before_post_boundary_work(
    v2_session_factory,
):
    started_at = FIRST_BOUNDARY - timedelta(days=1)
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, started_at)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)
    store.ensure_bootstrapped(aggregate.team.id, started_at)
    scheduler = _scheduler(v2_session_factory, store=store)
    as_of = FIRST_BOUNDARY + timedelta(hours=1)

    result = scheduler.run_due(as_of)

    after = store.load(aggregate.team.id)
    assert result.succeeded == (aggregate.team.id,)
    assert after.aggregate.runtime.simulation_time == as_of
    assert after.scrum.sprint_scope
    assert any(visit.elapsed_work_microseconds > 0 for visit in after.scrum.status_visits)


def test_two_due_teams_use_one_path_and_isolate_one_team_failure(v2_session_factory):
    first = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    second = create_aggregate(
        v2_session_factory, _blueprint_variant("Isolation Team"), FIRST_BOUNDARY
    )
    store = SqlAlchemyLiveTeamStore(v2_session_factory)
    store.ensure_bootstrapped(first.team.id, FIRST_BOUNDARY)
    store.ensure_bootstrapped(second.team.id, FIRST_BOUNDARY)
    service = _FailingTeamService(
        TeamTickService(store, SqlAlchemyV2UnitOfWork(v2_session_factory)), first.team.id
    )
    scheduler = _scheduler(v2_session_factory, store=store, tick_service=service)
    as_of = FIRST_BOUNDARY + timedelta(hours=1)

    result = scheduler.run_due(as_of)

    expected = tuple(sorted((first.team.id, second.team.id), key=str))
    assert result.attempted == expected
    assert service.attempted == list(expected)
    assert result.failed == (first.team.id,)
    assert result.succeeded == (second.team.id,)
    assert store.load(first.team.id).aggregate.runtime.simulation_time == FIRST_BOUNDARY
    assert store.load(second.team.id).aggregate.runtime.simulation_time == as_of


def test_restart_reconciles_then_skips_downtime_without_progress_or_intent_mutation(
    v2_session_factory,
):
    aggregate = create_aggregate(v2_session_factory, BLUEPRINT_JSON, FIRST_BOUNDARY)
    store = SqlAlchemyLiveTeamStore(v2_session_factory)
    store.ensure_bootstrapped(aggregate.team.id, FIRST_BOUNDARY)
    real_uow = SqlAlchemyV2UnitOfWork(v2_session_factory)
    TeamTickService(store, real_uow).advance(
        TickRequest(
            aggregate.team.id,
            FIRST_BOUNDARY + timedelta(hours=1),
            FIRST_BOUNDARY + timedelta(hours=1),
        )
    )
    before = store.load(aggregate.team.id)
    carry_visit = before.scrum.status_visits[0]
    consumption = before.scrum.member_business_date_consumption
    pending = real_uow.page_projection(
        ProjectionPageQuery(aggregate.team.id, aggregate.run.id, None, 100)
    ).items
    calls = []
    reconciler = _RecordingReconciler(calls)
    uow = _RecordingUnitOfWork(real_uow, calls)
    scheduler = _scheduler(v2_session_factory, store=store, unit_of_work=uow, reconciler=reconciler)
    as_of = FIRST_BOUNDARY + timedelta(days=17)

    result = scheduler.resume_after_restart(as_of)

    after = store.load(aggregate.team.id)
    same_visit = next(item for item in after.scrum.status_visits if item.id == carry_visit.id)
    runtime = after.aggregate.runtime
    assert result.succeeded == (aggregate.team.id,)
    assert calls[0] == ("reconcile", aggregate.team.id)
    assert calls[1][0] == "commit"
    assert same_visit == carry_visit
    assert after.scrum.member_business_date_consumption == consumption
    assert runtime.simulation_time == as_of
    assert runtime.next_wake_at == as_of
    existing_pending = real_uow.page_projection(
        ProjectionPageQuery(aggregate.team.id, aggregate.run.id, None, 100)
    ).items[: len(pending)]
    assert existing_pending == pending
    with v2_session_factory() as session:
        downtime = session.scalars(
            select(V2ActivityEventModel).where(
                V2ActivityEventModel.event_type == "DOWNTIME_SKIPPED"
            )
        ).all()
        assert downtime


def test_runtime_registers_one_injectable_v2_poller_job():
    scheduler = AsyncIOScheduler()
    service = _RecordingPoller()
    as_of = FIRST_BOUNDARY

    register_v2_job(scheduler, service, lambda: as_of)
    scheduler.get_job("v2_live_scheduler").func()

    assert service.calls == [as_of]
    assert [job.id for job in scheduler.get_jobs()].count("v2_live_scheduler") == 1


def _scheduler(
    session_factory,
    *,
    store=None,
    unit_of_work=None,
    tick_service=None,
    reconciler=None,
):
    live_store = store or SqlAlchemyLiveTeamStore(session_factory)
    uow = unit_of_work or SqlAlchemyV2UnitOfWork(session_factory)
    service = tick_service or TeamTickService(live_store, uow)
    dependencies = SchedulerDependencies(
        SqlAlchemyDueTeamStore(session_factory), service, live_store, uow, reconciler or _Noop()
    )
    return LiveScheduler(dependencies)


def _blueprint_variant(name: str) -> str:
    document = json.loads(BLUEPRINT_JSON)
    document["team"]["name"] = name
    document["seed"] = f"seed-{name}"
    return canonical_json(document)


class _FailingTeamService:
    def __init__(self, service, failed_team_id):
        self.service = service
        self.failed_team_id = failed_team_id
        self.attempted = []

    def advance(self, request):
        self.attempted.append(request.team_id)
        if request.team_id == self.failed_team_id:
            raise RuntimeError("injected isolated team failure")
        return self.service.advance(request)


class _Noop:
    def reconcile(self, _team_id, _as_of):
        return None


class _RecordingReconciler:
    def __init__(self, calls):
        self.calls = calls

    def reconcile(self, team_id, _as_of):
        self.calls.append(("reconcile", team_id))


class _RecordingUnitOfWork:
    def __init__(self, unit_of_work, calls):
        self.unit_of_work = unit_of_work
        self.calls = calls

    def commit_authoritative_slice(self, command):
        self.calls.append(("commit", command.live_slice.team_id))
        return self.unit_of_work.commit_authoritative_slice(command)


class _RecordingPoller:
    def __init__(self):
        self.calls = []

    def run_due(self, as_of):
        self.calls.append(as_of)
