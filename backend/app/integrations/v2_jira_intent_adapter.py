"""Concrete JiraClient adapter for committed v2 projection intents."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import httpx

from app.integrations.exceptions import JiraApiError, JiraRateLimitError
from app.integrations.jira_client import JiraClient
from app.v2.application.jira_delivery import (
    JiraDeliveryProviderError,
    JiraDeliveryRateLimitError,
)
from app.v2.domain.jira_delivery import (
    JiraDeliverySuccess,
    JiraResourceMapping,
    PendingJiraIntent,
)


class ResourceMappingReader(Protocol):
    def find_mapping(
        self, team_id: UUID, internal_kind: str, internal_id: UUID
    ) -> JiraResourceMapping | None: ...


class JiraClientV2IntentAdapter:
    """Translate transport-neutral v2 intent payloads through public JiraClient methods."""

    def __init__(
        self,
        client: JiraClient,
        mappings: ResourceMappingReader,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client
        self._mappings = mappings
        self._now = now

    async def deliver(self, pending: PendingJiraIntent) -> JiraDeliverySuccess:
        try:
            mappings = await self._deliver(pending)
        except JiraRateLimitError as error:
            raise JiraDeliveryRateLimitError(error.retry_after) from error
        except (JiraApiError, httpx.TransportError) as error:
            raise JiraDeliveryProviderError(str(error)) from error
        return JiraDeliverySuccess(pending.intent.id, mappings, self._now())

    async def _deliver(self, pending: PendingJiraIntent) -> tuple[JiraResourceMapping, ...]:
        operation = pending.intent.operation_type
        payload = _payload(pending)
        handlers = {
            "CREATE_PROJECT": self._create_project,
            "CREATE_BOARD": self._create_board,
            "CREATE_ISSUE": self._create_issue,
            "UPSERT_ISSUE": self._create_issue,
            "CREATE_SPRINT": self._create_sprint,
            "SCOPE_SPRINT": self._scope_sprint,
            "START_SPRINT": self._start_sprint,
            "COMPLETE_SPRINT": self._complete_sprint,
            "TRANSITION_ISSUE": self._transition_issue,
        }
        handler = handlers.get(operation)
        if handler is None:
            raise JiraDeliveryProviderError(f"unsupported Jira intent operation: {operation}")
        return await handler(pending, payload)

    async def _create_project(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        project_key = _string(payload, "project_key")
        project = await self._client.get_project(project_key)
        if project is None:
            project = await self._client.create_project(
                project_key,
                _string(payload, "name"),
                _string(payload, "board_type").lower(),
            )
        mapping = _resource_mapping(pending, "PROJECT", pending.intent.aggregate_id, project)
        return (mapping,)

    async def _create_board(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        project_key = _string(payload, "project_key")
        board = await self._client.get_board(project_key)
        if board is None:
            project = await self._client.get_project(project_key)
            if project is None:
                await self._client.create_project(
                    project_key,
                    _string(payload, "project_name"),
                    _string(payload, "board_type").lower(),
                )
                board = await self._client.get_board(project_key)
        if board is None:
            raise JiraDeliveryProviderError("Jira project exists without its expected board")
        return (_resource_mapping(pending, "BOARD", pending.intent.aggregate_id, board),)

    async def _create_issue(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        issue_id = _uuid(payload, "issue_id", pending.intent.aggregate_id)
        marker = _marker(issue_id)
        matches = await self._client.search_issues(
            f'labels = "{marker}"', fields=["key", "labels"], max_results=2
        )
        if len(matches) > 1:
            raise JiraDeliveryProviderError(f"multiple Jira issues carry marker {marker}")
        issue = matches[0] if matches else await self._create_marked_issue(payload, marker)
        return (_resource_mapping(pending, "ISSUE", issue_id, issue),)

    async def _create_marked_issue(self, payload: dict[str, object], marker: str) -> dict:
        fields = dict(_object(payload, "fields", default={}))
        labels = list(fields.get("labels", []))
        if marker not in labels:
            labels.append(marker)
        fields["labels"] = labels
        return await self._client.create_issue(
            _string(payload, "project_key"),
            _string(payload, "issue_type"),
            _string(payload, "summary"),
            fields,
        )

    async def _create_sprint(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        sprint_id = _uuid(payload, "sprint_id", pending.intent.aggregate_id)
        board = self._required_mapping(pending, "BOARD", _uuid(payload, "board_id"))
        board_id = int(board.jira_id)
        marker = _marker(sprint_id)
        matches = [
            sprint
            for sprint in await self._client.get_board_sprints(board_id)
            if marker in str(sprint.get("name", "")) or marker in str(sprint.get("goal", ""))
        ]
        if len(matches) > 1:
            raise JiraDeliveryProviderError(f"multiple Jira sprints carry marker {marker}")
        if matches:
            sprint = matches[0]
        else:
            name = f"{_string(payload, 'name')} [{marker}]"
            sprint = await self._client.create_sprint(
                board_id,
                name,
                _datetime(payload, "start_at"),
                _datetime(payload, "end_at"),
            )
        return (_resource_mapping(pending, "SPRINT", sprint_id, sprint),)

    async def _scope_sprint(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        sprint = self._required_mapping(pending, "SPRINT", _uuid(payload, "sprint_id"))
        if "issue_ids" not in payload:
            raise JiraDeliveryProviderError("issue_ids is required for SCOPE_SPRINT")
        issue_ids = _uuid_list(payload["issue_ids"], "issue_ids")
        issues = [self._required_mapping(pending, "ISSUE", issue_id) for issue_id in issue_ids]
        existing = await self._client.get_sprint_issues(int(sprint.jira_id), max_results=100)
        existing_keys = {str(issue["key"]) for issue in existing}
        missing = [item.jira_key for item in issues if item.jira_key not in existing_keys]
        if missing:
            await self._client.add_issues_to_sprint(int(sprint.jira_id), missing)
        return ()

    async def _start_sprint(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        mapping = self._required_mapping(pending, "SPRINT", _uuid(payload, "sprint_id"))
        sprint = await self._client.get_sprint(int(mapping.jira_id))
        if sprint.get("state") != "active":
            await self._client.start_sprint(int(mapping.jira_id))
        return ()

    async def _complete_sprint(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        mapping = self._required_mapping(pending, "SPRINT", _uuid(payload, "sprint_id"))
        sprint = await self._client.get_sprint(int(mapping.jira_id))
        if sprint.get("state") != "closed":
            await self._client.complete_sprint(int(mapping.jira_id))
        return ()

    async def _transition_issue(
        self, pending: PendingJiraIntent, payload: dict[str, object]
    ) -> tuple[JiraResourceMapping, ...]:
        mapping = self._required_mapping(pending, "ISSUE", _uuid(payload, "issue_id"))
        if mapping.jira_key is None:
            raise JiraDeliveryProviderError("issue mapping has no Jira key")
        target = _string(payload, "status")
        issue = await self._client.get_issue(mapping.jira_key)
        current = issue.get("fields", {}).get("status", {}).get("name")
        if current == target:
            return ()
        transitions = await self._client.get_issue_transitions(mapping.jira_key)
        match = next(
            (
                item
                for item in transitions
                if item.get("to", {}).get("name") == target or item.get("name") == target
            ),
            None,
        )
        if match is None:
            raise JiraDeliveryProviderError(f"no Jira transition reaches {target}")
        await self._client.transition_issue(mapping.jira_key, str(match["id"]))
        return ()

    def _required_mapping(
        self,
        pending: PendingJiraIntent,
        internal_kind: str,
        internal_id: UUID,
    ) -> JiraResourceMapping:
        mapping = self._mappings.find_mapping(pending.intent.team_id, internal_kind, internal_id)
        if mapping is None:
            raise JiraDeliveryProviderError(f"missing {internal_kind} mapping for {internal_id}")
        return mapping


def _payload(pending: PendingJiraIntent) -> dict[str, object]:
    document = json.loads(pending.intent.canonical_payload)
    if not isinstance(document, dict):
        raise JiraDeliveryProviderError("Jira intent payload must be an object")
    return document


def _resource_mapping(
    pending: PendingJiraIntent,
    internal_kind: str,
    internal_id: UUID,
    provider: dict,
) -> JiraResourceMapping:
    jira_id = str(provider["id"])
    jira_key = provider.get("key")
    return JiraResourceMapping(
        pending.intent.team_id,
        internal_kind,
        internal_id,
        jira_id,
        None if jira_key is None else str(jira_key),
    )


def _marker(internal_id: UUID) -> str:
    return f"sim-v2-{internal_id}"


def _string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise JiraDeliveryProviderError(f"{key} must be a non-empty string")
    return value


def _object(payload: dict[str, object], key: str, default: dict[str, object]) -> dict[str, object]:
    value = payload.get(key, default)
    if not isinstance(value, dict):
        raise JiraDeliveryProviderError(f"{key} must be an object")
    return value


def _uuid(payload: dict[str, object], key: str, default: UUID | None = None) -> UUID:
    value = payload.get(key)
    if value is None and default is not None:
        return default
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as error:
        raise JiraDeliveryProviderError(f"{key} must be a UUID") from error


def _uuid_list(value: object, key: str) -> tuple[UUID, ...]:
    if not isinstance(value, list):
        raise JiraDeliveryProviderError(f"{key} must be a list")
    try:
        return tuple(UUID(str(item)) for item in value)
    except (TypeError, ValueError) as error:
        raise JiraDeliveryProviderError(f"{key} must contain UUIDs") from error


def _datetime(payload: dict[str, object], key: str) -> datetime:
    try:
        value = datetime.fromisoformat(_string(payload, key))
    except ValueError as error:
        raise JiraDeliveryProviderError(f"{key} must be an ISO datetime") from error
    if value.tzinfo is None or value.utcoffset() is None:
        raise JiraDeliveryProviderError(f"{key} must be an aware datetime")
    return value.astimezone(UTC)
