"""Immutable contracts for retryable Jira projection delivery."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.v2.domain.live_slice import ProjectionIntent


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be an aware datetime")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class JiraResourceMapping:
    team_id: UUID
    internal_kind: str
    internal_id: UUID
    jira_id: str
    jira_key: str | None

    def __post_init__(self) -> None:
        for field_name in ("internal_kind", "jira_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.jira_key is not None and not self.jira_key.strip():
            raise ValueError("jira_key must be null or a non-empty string")


@dataclass(frozen=True)
class PendingJiraIntent:
    intent: ProjectionIntent
    dependency_keys: tuple[str, ...]
    attempts: int

    def __post_init__(self) -> None:
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")
        if any(not key.strip() for key in self.dependency_keys):
            raise ValueError("dependency keys must be non-empty strings")


@dataclass(frozen=True)
class JiraDeliverySuccess:
    intent_id: UUID
    mappings: tuple[JiraResourceMapping, ...]
    delivered_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "delivered_at", _utc(self.delivered_at, "delivered_at"))


@dataclass(frozen=True)
class JiraDeliveryFailure:
    intent_id: UUID
    retry_at: datetime
    error: str
    failed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "retry_at", _utc(self.retry_at, "retry_at"))
        object.__setattr__(self, "failed_at", _utc(self.failed_at, "failed_at"))
        if not self.error.strip():
            raise ValueError("error must be a non-empty string")


@dataclass(frozen=True)
class DeliveryBatchResult:
    attempted: int
    delivered: int
    deferred: int
    failed: int
