import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.integrations.v2_jira_intent_adapter import JiraClientV2IntentAdapter
from app.v2.application.create_team import CreateTeamCommand, CreateTeamService
from app.v2.application.jira_delivery import JiraDeliveryProviderError, JiraDeliveryWorker
from app.v2.domain.canonical_json import canonical_json, semantic_uuid
from app.v2.domain.jira_delivery import (
    JiraDeliveryFailure,
    JiraDeliverySuccess,
    JiraResourceMapping,
)
from app.v2.domain.live_slice import (
    DraftEnvelope,
    ProjectionDetails,
    ProjectionIntentDraft,
    RuntimeAdvance,
    TickSliceCommit,
)
from app.v2.persistence.jira_delivery_models import V2JiraDeliveryReceiptModel
from app.v2.persistence.jira_delivery_store import SqlAlchemyJiraDeliveryStore
from app.v2.persistence.live_models import V2ProjectionIntentModel
from app.v2.persistence.team_repository import SqlAlchemyV2TeamRepository
from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork

NOW = datetime(2026, 8, 11, 16, tzinfo=UTC)


def test_same_team_fifo_waits_for_delivered_canonical_dependency(
    v2_session_factory, blueprint_document
):
    aggregate = _create_team(v2_session_factory, blueprint_document, "FIFO")
    first = _intent(aggregate.team.id, "create", "CREATE_ISSUE", [])
    second = _intent(
        aggregate.team.id,
        "transition",
        "TRANSITION_ISSUE",
        [first.semantic_key],
    )
    _commit(v2_session_factory, aggregate, (first, second))
    store = SqlAlchemyJiraDeliveryStore(v2_session_factory)

    pending = store.pending(NOW)

    assert [item.intent.semantic_key for item in pending] == [first.semantic_key]
    assert pending[0].dependency_keys == ()
    store.record_success(JiraDeliverySuccess(first.id, (), NOW))
    released = store.pending(NOW)
    assert [item.intent.semantic_key for item in released] == [second.semantic_key]
    assert released[0].dependency_keys == (first.semantic_key,)


def test_retry_on_one_team_does_not_block_another_team(
    v2_session_factory, blueprint_document
):
    first_team = _create_team(v2_session_factory, blueprint_document, "ONE")
    second_team = _create_team(v2_session_factory, blueprint_document, "TWO")
    first_intent = _intent(first_team.team.id, "first", "CREATE_ISSUE", [])
    blocked_later = _intent(first_team.team.id, "later", "TRANSITION_ISSUE", [])
    other_intent = _intent(second_team.team.id, "other", "CREATE_ISSUE", [])
    _commit(v2_session_factory, first_team, (first_intent, blocked_later))
    _commit(v2_session_factory, second_team, (other_intent,))
    store = SqlAlchemyJiraDeliveryStore(v2_session_factory)
    store.record_failure(
        JiraDeliveryFailure(first_intent.id, NOW + timedelta(minutes=5), "offline", NOW)
    )

    pending = store.pending(NOW)

    assert [item.intent.id for item in pending] == [other_intent.id]


def test_restart_discovers_due_retry_with_persisted_attempt_count(
    v2_session_factory, blueprint_document
):
    aggregate = _create_team(v2_session_factory, blueprint_document, "RETRY")
    intent = _intent(aggregate.team.id, "retry", "CREATE_ISSUE", [])
    _commit(v2_session_factory, aggregate, (intent,))
    first_store = SqlAlchemyJiraDeliveryStore(v2_session_factory)
    retry_at = NOW + timedelta(seconds=30)
    first_store.record_failure(JiraDeliveryFailure(intent.id, retry_at, "timeout", NOW))

    restarted_store = SqlAlchemyJiraDeliveryStore(v2_session_factory)

    assert restarted_store.pending(retry_at - timedelta(microseconds=1)) == ()
    pending = restarted_store.pending(retry_at)
    assert len(pending) == 1
    assert pending[0].intent.id == intent.id
    assert pending[0].attempts == 1


def test_mapping_and_success_receipt_commit_atomically(
    v2_session_factory, blueprint_document
):
    aggregate = _create_team(v2_session_factory, blueprint_document, "ATOMIC")
    intent = _intent(aggregate.team.id, "atomic", "CREATE_ISSUE", [])
    _commit(v2_session_factory, aggregate, (intent,))
    store = SqlAlchemyJiraDeliveryStore(v2_session_factory)
    internal_id = UUID(json.loads(intent.canonical_payload)["issue_id"])
    first = JiraResourceMapping(aggregate.team.id, "ISSUE", internal_id, "10001", "ATM-1")
    conflicting = replace(first, jira_id="10002", jira_key="ATM-2")
    store.record_success(JiraDeliverySuccess(intent.id, (first,), NOW))

    with pytest.raises(ValueError, match="mapping"):
        store.record_success(
            JiraDeliverySuccess(
                intent.id,
                (conflicting,),
                NOW + timedelta(seconds=1),
            )
        )

    assert store.find_mapping(aggregate.team.id, "ISSUE", internal_id) == first
    with v2_session_factory() as session:
        receipt = session.get(V2JiraDeliveryReceiptModel, str(intent.id))
        assert receipt is not None
        assert receipt.attempts == 1
        assert receipt.delivered_at == NOW
        projection = session.scalar(
            select(V2ProjectionIntentModel).where(V2ProjectionIntentModel.id == str(intent.id))
        )
        assert projection is not None
        assert projection.status == "PENDING"


def test_failure_receipt_does_not_mutate_projection_row(
    v2_session_factory, blueprint_document
):
    aggregate = _create_team(v2_session_factory, blueprint_document, "FAILURE")
    intent = _intent(aggregate.team.id, "failure", "CREATE_ISSUE", [])
    _commit(v2_session_factory, aggregate, (intent,))
    store = SqlAlchemyJiraDeliveryStore(v2_session_factory)

    store.record_failure(
        JiraDeliveryFailure(intent.id, NOW + timedelta(seconds=5), "provider unavailable", NOW)
    )

    with v2_session_factory() as session:
        receipt = session.get(V2JiraDeliveryReceiptModel, str(intent.id))
        projection = session.scalar(
            select(V2ProjectionIntentModel).where(V2ProjectionIntentModel.id == str(intent.id))
        )
        assert receipt is not None
        assert receipt.state == "RETRYABLE"
        assert receipt.attempts == 1
        assert projection is not None
        assert projection.status == "PENDING"
        assert session.scalar(select(func.count()).select_from(V2ProjectionIntentModel)) == 1


@pytest.mark.asyncio
async def test_incomplete_scope_stays_retryable_and_does_not_release_start(
    v2_session_factory, blueprint_document
):
    aggregate = _create_team(v2_session_factory, blueprint_document, "SCOPE")
    sprint_id = semantic_uuid(f"delivery/{aggregate.team.id}/sprint")
    created = _sprint_intent(aggregate.team.id, sprint_id, "create", "CREATE_SPRINT", [])
    scoped = _sprint_intent(
        aggregate.team.id,
        sprint_id,
        "scope",
        "SCOPE_SPRINT",
        [created.semantic_key],
    )
    started = _sprint_intent(
        aggregate.team.id,
        sprint_id,
        "start",
        "START_SPRINT",
        [scoped.semantic_key],
    )
    _commit(v2_session_factory, aggregate, (created, scoped, started))
    store = SqlAlchemyJiraDeliveryStore(v2_session_factory)
    sprint_mapping = JiraResourceMapping(
        aggregate.team.id, "SPRINT", sprint_id, "501", None
    )
    store.record_success(JiraDeliverySuccess(created.id, (sprint_mapping,), NOW))
    pending = store.pending(NOW)[0]
    adapter = JiraClientV2IntentAdapter(_ScopeClient(), store, lambda: NOW)

    with pytest.raises(JiraDeliveryProviderError, match="issue_ids"):
        await adapter.deliver(pending)
    result = await JiraDeliveryWorker(store, adapter).drain_once(NOW)

    assert result == result.__class__(attempted=1, delivered=0, deferred=0, failed=1)
    with v2_session_factory() as session:
        scope_receipt = session.get(V2JiraDeliveryReceiptModel, str(scoped.id))
        start_receipt = session.get(V2JiraDeliveryReceiptModel, str(started.id))
        assert scope_receipt is not None
        assert scope_receipt.state == "RETRYABLE"
        assert scope_receipt.delivered_at is None
        assert start_receipt is None
    assert store.pending(NOW + timedelta(seconds=10))[0].intent.id == scoped.id


def _create_team(session_factory, blueprint_document, suffix: str):
    document = json.loads(json.dumps(blueprint_document))
    document["team"]["name"] = f"Team {suffix}"
    document["jira"]["project_key"] = f"SIM{suffix}"
    blueprint = canonical_json(document)
    service = CreateTeamService(SqlAlchemyV2TeamRepository(session_factory))
    return service.create(CreateTeamCommand(f"delivery-{suffix}", blueprint, NOW))


def _intent(
    team_id: UUID,
    label: str,
    operation: str,
    dependencies: list[str],
) -> ProjectionIntentDraft:
    issue_id = semantic_uuid(f"delivery/{team_id}/{label}/issue")
    payload = {
        "depends_on": dependencies,
        "fields": {},
        "issue_id": str(issue_id),
        "issue_type": "Story",
        "project_key": "SIM",
        "status": "Done",
        "summary": label,
    }
    envelope = DraftEnvelope(f"delivery/{team_id}/{label}", "1.0", NOW, payload)
    details = ProjectionDetails("JIRA", operation, issue_id, 1, "PENDING")
    return ProjectionIntentDraft.create(envelope, details)


def _sprint_intent(
    team_id: UUID,
    sprint_id: UUID,
    label: str,
    operation: str,
    dependencies: list[str],
) -> ProjectionIntentDraft:
    payload = {"depends_on": dependencies, "sprint_id": str(sprint_id)}
    envelope = DraftEnvelope(f"delivery/{team_id}/sprint/{label}", "1.0", NOW, payload)
    details = ProjectionDetails("JIRA", operation, sprint_id, 1, "PENDING")
    return ProjectionIntentDraft.create(envelope, details)


class _ScopeClient:
    async def get_sprint_issues(self, sprint_id: int, max_results: int = 50):
        del sprint_id, max_results
        return []

    async def add_issues_to_sprint(self, sprint_id: int, issue_keys: list[str]):
        raise AssertionError((sprint_id, issue_keys))


def _commit(session_factory, aggregate, intents: tuple[ProjectionIntentDraft, ...]) -> None:
    runtime = aggregate.runtime
    command = TickSliceCommit(
        uuid4(),
        aggregate.team.id,
        aggregate.run.id,
        runtime.version,
        RuntimeAdvance("RUNNING", NOW, NOW + timedelta(minutes=1)),
        (),
        (),
        intents,
        NOW,
    )
    SqlAlchemyV2UnitOfWork(session_factory).commit_tick_slice(command)
