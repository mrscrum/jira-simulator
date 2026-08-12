"""Meaningful fake-Jira acceptance for the persisted v2 Scrum loop."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.integrations.v2_jira_intent_adapter import JiraClientV2IntentAdapter
from app.v2.application.create_team import CreateTeamCommand, CreateTeamService
from app.v2.application.jira_delivery import JiraDeliveryWorker
from app.v2.application.live_scheduler import LiveScheduler, SchedulerDependencies
from app.v2.application.team_tick import TeamTickService
from app.v2.domain.canonical_json import canonical_json
from app.v2.persistence.due_team_store import SqlAlchemyDueTeamStore
from app.v2.persistence.jira_delivery_store import SqlAlchemyJiraDeliveryStore
from app.v2.persistence.live_team_store import SqlAlchemyLiveTeamStore
from app.v2.persistence.team_repository import SqlAlchemyV2TeamRepository
from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork
from tests.v2.fakes.fake_jira_client import FakeJiraClient

STARTED_AT = datetime(2026, 8, 11, 16, tzinfo=UTC)
FIRST_BOUNDARY = datetime(2026, 8, 13, 16, tzinfo=UTC)


@pytest.mark.asyncio
async def test_live_scrum_converges_after_restart_outage_and_receipt_retry(
    v2_session_factory, blueprint_document
):
    aggregate = _create_team(v2_session_factory, blueprint_document)
    live_store = SqlAlchemyLiveTeamStore(v2_session_factory)
    state = live_store.ensure_bootstrapped(aggregate.team.id, STARTED_AT)
    delivery_store = SqlAlchemyJiraDeliveryStore(v2_session_factory)
    jira = FakeJiraClient()
    adapter = JiraClientV2IntentAdapter(jira, delivery_store, lambda: STARTED_AT)

    jira.online = False
    outage = await JiraDeliveryWorker(delivery_store, adapter).drain_once(STARTED_AT)
    assert outage.failed == 1
    assert delivery_store.pending(STARTED_AT + timedelta(seconds=10))

    jira.online = True
    failing_receipt_store = _FailFirstSuccessStore(delivery_store)
    with pytest.raises(RuntimeError, match="receipt commit failed"):
        await JiraDeliveryWorker(failing_receipt_store, adapter).drain_once(
            STARTED_AT + timedelta(seconds=10)
        )
    assert jira.project_creates == 1

    recovered = await JiraDeliveryWorker(delivery_store, adapter).drain_once(
        STARTED_AT + timedelta(seconds=10), limit=50
    )
    assert recovered.failed == 0
    assert jira.project_creates == 1
    assert jira.issue_creates == len(state.scrum.work_items)

    scheduler = _scheduler(v2_session_factory, live_store)
    first = scheduler.run_due(FIRST_BOUNDARY + timedelta(hours=2))
    assert first.succeeded == (aggregate.team.id,)
    await _drain(delivery_store, adapter, FIRST_BOUNDARY + timedelta(hours=2))

    before_restart = live_store.load(aggregate.team.id)
    tracked = before_restart.scrum.status_visits[0]
    restarted = _scheduler(v2_session_factory, SqlAlchemyLiveTeamStore(v2_session_factory))
    restart_at = FIRST_BOUNDARY + timedelta(days=1)
    assert restarted.resume_after_restart(restart_at).succeeded == (aggregate.team.id,)
    after_restart = live_store.load(aggregate.team.id)
    same_visit = next(item for item in after_restart.scrum.status_visits if item.id == tracked.id)
    assert same_visit == tracked

    first_end = after_restart.scrum.sprints[0].planned_end_at
    assert scheduler.run_due(first_end + timedelta(hours=2)).succeeded == (aggregate.team.id,)
    await _drain(delivery_store, adapter, first_end + timedelta(hours=2))
    second_end = max(
        sprint.planned_end_at for sprint in live_store.load(aggregate.team.id).scrum.sprints
    )
    assert scheduler.run_due(second_end + timedelta(hours=2)).succeeded == (aggregate.team.id,)
    await _drain(delivery_store, adapter, second_end + timedelta(hours=2))

    assert delivery_store.pending(second_end + timedelta(days=1)) == ()
    assert jira.project_creates == 1
    assert jira.issue_creates == len(state.scrum.work_items)
    assert jira.sprint_creates == len(jira.sprints)
    assert len(jira.sprints) >= 3
    assert any(issue["fields"]["status"]["name"] == "Done" for issue in jira.issues.values())


def _create_team(session_factory, blueprint_document):
    document = json.loads(json.dumps(blueprint_document))
    rule = document["risks"]["rules"][0]
    rule["base_probability"] = 0.0
    rule["clamp"] = {"max": 0.0, "min": 0.0}
    blueprint = canonical_json(document)
    service = CreateTeamService(SqlAlchemyV2TeamRepository(session_factory))
    return service.create(CreateTeamCommand("acceptance-live-loop", blueprint, STARTED_AT))


def _scheduler(session_factory, live_store) -> LiveScheduler:
    unit_of_work = SqlAlchemyV2UnitOfWork(session_factory)
    dependencies = SchedulerDependencies(
        SqlAlchemyDueTeamStore(session_factory),
        TeamTickService(live_store, unit_of_work),
        live_store,
        unit_of_work,
        _NoopReconciler(),
    )
    return LiveScheduler(dependencies)


async def _drain(store, adapter, as_of: datetime) -> None:
    result = await JiraDeliveryWorker(store, adapter).drain_once(as_of, limit=50)
    assert result.failed == 0


class _NoopReconciler:
    def reconcile(self, team_id, as_of) -> None:
        del team_id, as_of


class _FailFirstSuccessStore:
    def __init__(self, store) -> None:
        self._store = store
        self._failed = False

    def pending(self, as_of, limit=50):
        return self._store.pending(as_of, limit)

    def record_success(self, result) -> None:
        if not self._failed:
            self._failed = True
            raise RuntimeError("receipt commit failed")
        self._store.record_success(result)

    def record_failure(self, result) -> None:
        self._store.record_failure(result)
