import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.integrations.exceptions import JiraConnectionError, JiraRateLimitError
from app.integrations.v2_jira_intent_adapter import JiraClientV2IntentAdapter
from app.v2.application.jira_delivery import (
    JiraDeliveryProviderError,
    JiraDeliveryRateLimitError,
    JiraDeliveryWorker,
)
from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.jira_delivery import (
    JiraDeliverySuccess,
    PendingJiraIntent,
)
from app.v2.domain.live_slice import ProjectionIntent
from app.v2.runtime import register_v2_delivery_job

NOW = datetime(2026, 8, 11, 17, tzinfo=UTC)
TEAM_ONE = UUID("11111111-1111-4111-8111-111111111111")
TEAM_TWO = UUID("22222222-2222-4222-8222-222222222222")


@pytest.mark.asyncio
async def test_worker_records_success_and_continues_after_other_team_failure():
    first = _pending(TEAM_ONE, "first")
    second = _pending(TEAM_TWO, "second")
    store = _MemoryStore((first, second))
    adapter = _OutcomeAdapter({first.intent.id: JiraDeliveryProviderError("offline")})
    worker = JiraDeliveryWorker(store, adapter)

    result = await worker.drain_once(NOW)

    assert result.attempted == 2
    assert result.delivered == 1
    assert result.failed == 1
    assert [item.intent_id for item in store.successes] == [second.intent.id]
    assert [item.intent_id for item in store.failures] == [first.intent.id]
    assert store.failures[0].retry_at == NOW + timedelta(seconds=10)


@pytest.mark.asyncio
async def test_rate_limit_persists_retry_after_without_sleep(monkeypatch):
    pending = _pending(TEAM_ONE, "rate-limit")
    store = _MemoryStore((pending,))
    adapter = _OutcomeAdapter({pending.intent.id: JiraDeliveryRateLimitError(37.5)})

    async def forbidden_sleep(_seconds):
        raise AssertionError("delivery must not sleep")

    monkeypatch.setattr(asyncio, "sleep", forbidden_sleep)

    result = await JiraDeliveryWorker(store, adapter).drain_once(NOW)

    assert result.failed == 1
    assert store.failures[0].retry_at == NOW + timedelta(seconds=37.5)


@pytest.mark.asyncio
async def test_worker_requeries_after_success_to_drain_next_same_team_intent():
    first = _pending(TEAM_ONE, "fifo-first")
    second = _pending(TEAM_ONE, "fifo-second")
    store = _ChainedStore(first, second)

    result = await JiraDeliveryWorker(store, _OutcomeAdapter({})).drain_once(NOW)

    assert result.attempted == 2
    assert result.delivered == 2
    assert [item.intent_id for item in store.successes] == [first.intent.id, second.intent.id]


@pytest.mark.asyncio
async def test_adapter_translates_jira_transport_and_rate_limit_errors():
    pending = _pending(TEAM_ONE, "provider")
    client = _FakeJiraClient()
    client.search_error = JiraConnectionError("refused")
    adapter = JiraClientV2IntentAdapter(client, _EmptyMappings(), lambda: NOW)

    with pytest.raises(JiraDeliveryProviderError, match="refused"):
        await adapter.deliver(pending)

    client.search_error = JiraRateLimitError(19)
    with pytest.raises(JiraDeliveryRateLimitError) as error:
        await adapter.deliver(pending)
    assert error.value.retry_after_seconds == 19


@pytest.mark.asyncio
async def test_issue_preflight_prevents_duplicate_after_local_commit_crash():
    pending = _pending(TEAM_ONE, "crash-issue")
    client = _FakeJiraClient()
    adapter = JiraClientV2IntentAdapter(client, _EmptyMappings(), lambda: NOW)

    first = await adapter.deliver(pending)
    second = await adapter.deliver(pending)

    assert client.issue_creates == 1
    assert first.mappings == second.mappings
    assert first.mappings[0].jira_key == "SIM-1"
    marker = f"sim-v2-{pending.intent.aggregate_id}"
    assert marker in client.issues[0]["fields"]["labels"]


@pytest.mark.asyncio
async def test_sprint_preflight_prevents_duplicate_after_local_commit_crash():
    sprint_id = semantic_uuid("delivery/sprint/one")
    pending = _pending(
        TEAM_ONE,
        "crash-sprint",
        operation="CREATE_SPRINT",
        aggregate_id=sprint_id,
        payload={
            "board_id": 7,
            "depends_on": [],
            "end_at": "2026-08-25T17:00:00+00:00",
            "name": "Sprint 1",
            "sprint_id": str(sprint_id),
            "start_at": "2026-08-11T17:00:00+00:00",
        },
    )
    client = _FakeJiraClient()
    adapter = JiraClientV2IntentAdapter(client, _EmptyMappings(), lambda: NOW)

    first = await adapter.deliver(pending)
    second = await adapter.deliver(pending)

    assert client.sprint_creates == 1
    assert first.mappings == second.mappings
    marker = f"sim-v2-{sprint_id}"
    assert marker in client.sprints[0]["name"]


@pytest.mark.asyncio
async def test_runtime_registers_exactly_one_async_delivery_job():
    scheduler = AsyncIOScheduler()
    worker = _RecordingWorker()

    register_v2_delivery_job(scheduler, worker, lambda: NOW)
    await scheduler.get_job("v2_jira_delivery").func()

    assert worker.calls == [NOW]
    assert [job.id for job in scheduler.get_jobs()].count("v2_jira_delivery") == 1


class _MemoryStore:
    def __init__(self, pending: tuple[PendingJiraIntent, ...]):
        self._pending = pending
        self._queried = False
        self.successes = []
        self.failures = []

    def pending(self, as_of: datetime, limit: int = 50) -> tuple[PendingJiraIntent, ...]:
        del as_of
        if self._queried:
            return ()
        self._queried = True
        return self._pending[:limit]

    def record_success(self, result) -> None:
        self.successes.append(result)

    def record_failure(self, result) -> None:
        self.failures.append(result)


class _OutcomeAdapter:
    def __init__(self, errors: dict[UUID, Exception]):
        self._errors = errors

    async def deliver(self, pending: PendingJiraIntent) -> JiraDeliverySuccess:
        error = self._errors.get(pending.intent.id)
        if error is not None:
            raise error
        return JiraDeliverySuccess(pending.intent.id, (), NOW)


class _ChainedStore:
    def __init__(self, first: PendingJiraIntent, second: PendingJiraIntent):
        self._remaining = [first, second]
        self.successes = []

    def pending(self, as_of: datetime, limit: int = 50):
        del as_of
        return tuple(self._remaining[:1])[:limit]

    def record_success(self, result) -> None:
        self.successes.append(result)
        self._remaining.pop(0)

    def record_failure(self, result) -> None:
        raise AssertionError(f"unexpected failure: {result}")


class _RecordingWorker:
    def __init__(self):
        self.calls = []

    async def drain_once(self, as_of: datetime):
        self.calls.append(as_of)


class _EmptyMappings:
    def find_mapping(self, team_id: UUID, internal_kind: str, internal_id: UUID):
        del team_id, internal_kind, internal_id
        return None


class _FakeJiraClient:
    def __init__(self):
        self.issues: list[dict] = []
        self.sprints: list[dict] = []
        self.issue_creates = 0
        self.sprint_creates = 0
        self.search_error: Exception | None = None

    async def search_issues(self, jql: str, fields=None, max_results: int = 50):
        del fields, max_results
        if self.search_error is not None:
            raise self.search_error
        marker = jql.split('"')[1]
        return [item for item in self.issues if marker in item["fields"]["labels"]]

    async def create_issue(self, project_key: str, issue_type: str, summary: str, fields: dict):
        self.issue_creates += 1
        issue = {
            "id": str(10_000 + self.issue_creates),
            "key": f"{project_key}-{self.issue_creates}",
            "fields": {"issuetype": issue_type, "summary": summary, **fields},
        }
        self.issues.append(issue)
        return issue

    async def get_board_sprints(self, board_id: int, state: str | None = None):
        del board_id, state
        return list(self.sprints)

    async def create_sprint(
        self,
        board_id: int,
        name: str,
        start_date: datetime,
        end_date: datetime,
    ):
        del board_id, start_date, end_date
        self.sprint_creates += 1
        sprint = {"id": 200 + self.sprint_creates, "name": name}
        self.sprints.append(sprint)
        return sprint


def _pending(
    team_id: UUID,
    label: str,
    operation: str = "CREATE_ISSUE",
    aggregate_id: UUID | None = None,
    payload: dict[str, object] | None = None,
) -> PendingJiraIntent:
    resource_id = aggregate_id or semantic_uuid(f"delivery/{team_id}/{label}/issue")
    document = payload or {
        "depends_on": [],
        "fields": {},
        "issue_id": str(resource_id),
        "issue_type": "Story",
        "project_key": "SIM",
        "summary": label,
    }
    canonical_payload = canonical_json(document)
    intent = ProjectionIntent(
        id=semantic_uuid(f"projection/delivery/{team_id}/{label}"),
        semantic_key=f"delivery/{team_id}/{label}",
        schema_version="1.0",
        occurred_at=NOW,
        canonical_payload=canonical_payload,
        payload_sha256=canonical_sha256(document),
        target_kind="JIRA",
        operation_type=operation,
        aggregate_id=resource_id,
        aggregate_version=1,
        status="PENDING",
        append_sequence=1,
        team_id=team_id,
        run_id=uuid4(),
        commit_id=uuid4(),
        transaction_sequence=0,
        recorded_at=NOW,
    )
    return PendingJiraIntent(intent, (), 0)
