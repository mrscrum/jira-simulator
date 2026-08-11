"""Immutable contracts for one atomically persisted v2 live slice."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID

from app.v2.domain.canonical_json import (
    JsonValue,
    canonical_json,
    canonical_sha256,
    semantic_uuid,
)
from app.v2.domain.team_runtime import TeamRuntime

MAX_PAGE_SIZE = 100


class _FrozenJsonDict(dict):
    """A JSON-object snapshot that rejects mutation after construction."""

    def _reject(self, *args, **kwargs) -> None:
        raise TypeError("JSON payload is immutable")

    __setitem__ = _reject
    __delitem__ = _reject
    clear = _reject
    pop = _reject
    popitem = _reject
    setdefault = _reject
    update = _reject
    __ior__ = _reject


def _freeze_json(value: Any) -> JsonValue:
    if isinstance(value, dict):
        return _FrozenJsonDict({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)  # type: ignore[return-value]
    return value


def _require_string_json_object_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            _require_string_json_object_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _require_string_json_object_keys(item)


def _validated_json(value: Any) -> tuple[JsonValue, str, str]:
    _require_string_json_object_keys(value)
    try:
        encoded = canonical_json(value)
        copied = json.loads(encoded)
    except (TypeError, ValueError) as error:
        raise ValueError("payload must be valid JSON") from error
    digest = canonical_sha256(copied)
    return _freeze_json(copied), encoded, digest


def _canonical_document(encoded: object) -> JsonValue:
    if not isinstance(encoded, str):
        raise TypeError("canonical_payload must be a string")
    try:
        document = json.loads(encoded)
    except (TypeError, ValueError) as error:
        raise ValueError("canonical_payload must contain valid JSON") from error
    if canonical_json(document) != encoded:
        raise ValueError("canonical_payload must use canonical JSON encoding")
    return document


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _uuid(value: object, field_name: str) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError(f"{field_name} must be a UUID")
    return value


def _non_negative(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _aware_utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be an aware datetime")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class DraftEnvelope:
    semantic_key: str
    schema_version: str
    occurred_at: datetime
    payload: JsonValue
    supplied_id: UUID | None = None
    supplied_payload_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "semantic_key", _non_empty(self.semantic_key, "semantic key"))
        object.__setattr__(
            self, "schema_version", _non_empty(self.schema_version, "schema version")
        )
        object.__setattr__(self, "occurred_at", _aware_utc(self.occurred_at, "occurred_at"))
        payload, _, _ = _validated_json(self.payload)
        object.__setattr__(self, "payload", payload)
        if self.supplied_id is not None:
            _uuid(self.supplied_id, "supplied identifier")

    def canonical(self) -> tuple[str, str]:
        _, encoded, digest = _validated_json(self.payload)
        return encoded, digest


@dataclass(frozen=True)
class ActivityDetails:
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    aggregate_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", _non_empty(self.event_type, "event type"))
        object.__setattr__(
            self, "aggregate_type", _non_empty(self.aggregate_type, "aggregate type")
        )
        _uuid(self.aggregate_id, "aggregate_id")
        _non_negative(self.aggregate_version, "aggregate_version")


@dataclass(frozen=True)
class GroundTruthDetails:
    record_type: str
    provenance_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_type", _non_empty(self.record_type, "record type"))
        object.__setattr__(
            self, "provenance_type", _non_empty(self.provenance_type, "provenance type")
        )


@dataclass(frozen=True)
class ProjectionDetails:
    target_kind: str
    operation_type: str
    aggregate_id: UUID
    aggregate_version: int
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_kind", _non_empty(self.target_kind, "target kind"))
        object.__setattr__(
            self, "operation_type", _non_empty(self.operation_type, "operation type")
        )
        _uuid(self.aggregate_id, "aggregate_id")
        _non_negative(self.aggregate_version, "aggregate_version")
        if self.status != "PENDING":
            raise ValueError("projection status must be PENDING")


def _draft_identity(path: str, envelope: DraftEnvelope) -> tuple[UUID, str, str]:
    identifier = semantic_uuid(f"{path}/{envelope.semantic_key}")
    payload, digest = envelope.canonical()
    if envelope.supplied_id is not None and envelope.supplied_id != identifier:
        raise ValueError("supplied identifier does not match semantic key")
    if envelope.supplied_payload_sha256 is not None:
        if envelope.supplied_payload_sha256 != digest:
            raise ValueError("supplied payload hash does not match canonical payload")
    return identifier, payload, digest


def _validate_draft_envelope(draft: object, path: str) -> None:
    identifier = _uuid(getattr(draft, "id"), "identifier")
    semantic_key = _non_empty(getattr(draft, "semantic_key"), "semantic key")
    _non_empty(getattr(draft, "schema_version"), "schema version")
    occurred_at = _aware_utc(getattr(draft, "occurred_at"), "occurred_at")
    object.__setattr__(draft, "occurred_at", occurred_at)
    document = _canonical_document(getattr(draft, "canonical_payload"))
    expected_digest = canonical_sha256(document)
    if getattr(draft, "payload_sha256") != expected_digest:
        raise ValueError("payload hash does not match canonical payload")
    if identifier != semantic_uuid(f"{path}/{semantic_key}"):
        raise ValueError("identifier does not match semantic key")


@dataclass(frozen=True)
class ActivityEventDraft:
    id: UUID
    semantic_key: str
    schema_version: str
    occurred_at: datetime
    canonical_payload: str
    payload_sha256: str
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    aggregate_version: int

    def __post_init__(self) -> None:
        _validate_draft_envelope(self, "activity")
        ActivityDetails(
            self.event_type,
            self.aggregate_type,
            self.aggregate_id,
            self.aggregate_version,
        )

    def validate(self) -> None:
        self.__post_init__()

    @classmethod
    def create(cls, envelope: DraftEnvelope, details: ActivityDetails) -> Self:
        identifier, payload, digest = _draft_identity("activity", envelope)
        return cls(
            identifier,
            envelope.semantic_key,
            envelope.schema_version,
            envelope.occurred_at,
            payload,
            digest,
            details.event_type,
            details.aggregate_type,
            details.aggregate_id,
            details.aggregate_version,
        )

    def deduplication_content(self) -> tuple[object, ...]:
        return (
            self.schema_version,
            self.occurred_at,
            self.canonical_payload,
            self.payload_sha256,
            self.event_type,
            self.aggregate_type,
            self.aggregate_id,
            self.aggregate_version,
        )


@dataclass(frozen=True)
class GroundTruthRecordDraft:
    id: UUID
    semantic_key: str
    schema_version: str
    occurred_at: datetime
    canonical_payload: str
    payload_sha256: str
    record_type: str
    provenance_type: str

    def __post_init__(self) -> None:
        _validate_draft_envelope(self, "ground-truth")
        GroundTruthDetails(self.record_type, self.provenance_type)

    def validate(self) -> None:
        self.__post_init__()

    @classmethod
    def create(cls, envelope: DraftEnvelope, details: GroundTruthDetails) -> Self:
        identifier, payload, digest = _draft_identity("ground-truth", envelope)
        return cls(
            identifier,
            envelope.semantic_key,
            envelope.schema_version,
            envelope.occurred_at,
            payload,
            digest,
            details.record_type,
            details.provenance_type,
        )

    def deduplication_content(self) -> tuple[object, ...]:
        return (
            self.schema_version,
            self.occurred_at,
            self.canonical_payload,
            self.payload_sha256,
            self.record_type,
            self.provenance_type,
        )


@dataclass(frozen=True)
class ProjectionIntentDraft:
    id: UUID
    semantic_key: str
    schema_version: str
    occurred_at: datetime
    canonical_payload: str
    payload_sha256: str
    target_kind: str
    operation_type: str
    aggregate_id: UUID
    aggregate_version: int
    status: str

    def __post_init__(self) -> None:
        _validate_draft_envelope(self, "projection")
        ProjectionDetails(
            self.target_kind,
            self.operation_type,
            self.aggregate_id,
            self.aggregate_version,
            self.status,
        )

    def validate(self) -> None:
        self.__post_init__()

    @classmethod
    def create(cls, envelope: DraftEnvelope, details: ProjectionDetails) -> Self:
        identifier, payload, digest = _draft_identity("projection", envelope)
        return cls(
            identifier,
            envelope.semantic_key,
            envelope.schema_version,
            envelope.occurred_at,
            payload,
            digest,
            details.target_kind,
            details.operation_type,
            details.aggregate_id,
            details.aggregate_version,
            details.status,
        )

    def deduplication_content(self) -> tuple[object, ...]:
        return (
            self.schema_version,
            self.occurred_at,
            self.canonical_payload,
            self.payload_sha256,
            self.target_kind,
            self.operation_type,
            self.aggregate_id,
            self.aggregate_version,
            self.status,
        )


@dataclass(frozen=True)
class RuntimeAdvance:
    state: str
    simulation_time: datetime
    next_wake_at: datetime | None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        object.__setattr__(self, "state", _non_empty(self.state, "runtime state"))
        object.__setattr__(
            self, "simulation_time", _aware_utc(self.simulation_time, "simulation_time")
        )
        if self.next_wake_at is not None:
            object.__setattr__(
                self, "next_wake_at", _aware_utc(self.next_wake_at, "next_wake_at")
            )


def _validate_draft_tuple(items: object, item_type: type, field_name: str) -> tuple:
    if not isinstance(items, tuple) or any(not isinstance(item, item_type) for item in items):
        raise TypeError(f"{field_name} must be a tuple of {item_type.__name__}")
    seen: dict[str, tuple[object, ...]] = {}
    for item in items:
        item.validate()
        content = item.deduplication_content()
        if item.semantic_key in seen and seen[item.semantic_key] != content:
            raise ValueError(f"duplicate semantic key has conflicting {field_name} content")
        seen[item.semantic_key] = content
    return items


@dataclass(frozen=True)
class TickSliceCommit:
    commit_id: UUID
    team_id: UUID
    run_id: UUID
    expected_runtime_version: int
    runtime_after: RuntimeAdvance
    activity: tuple[ActivityEventDraft, ...]
    ground_truth: tuple[GroundTruthRecordDraft, ...]
    projection_intents: tuple[ProjectionIntentDraft, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _uuid(self.commit_id, "commit_id")
        _uuid(self.team_id, "team_id")
        _uuid(self.run_id, "run_id")
        _non_negative(self.expected_runtime_version, "expected_runtime_version")
        if not isinstance(self.runtime_after, RuntimeAdvance):
            raise TypeError("runtime_after must be a RuntimeAdvance")
        self.runtime_after.validate()
        _validate_draft_tuple(self.activity, ActivityEventDraft, "activity")
        _validate_draft_tuple(self.ground_truth, GroundTruthRecordDraft, "ground truth")
        _validate_draft_tuple(
            self.projection_intents, ProjectionIntentDraft, "projection intents"
        )
        object.__setattr__(self, "recorded_at", _aware_utc(self.recorded_at, "recorded_at"))


@dataclass(frozen=True)
class ActivityEvent(ActivityEventDraft):
    append_sequence: int
    team_id: UUID
    run_id: UUID
    commit_id: UUID
    transaction_sequence: int
    recorded_at: datetime


@dataclass(frozen=True)
class GroundTruthRecord(GroundTruthRecordDraft):
    append_sequence: int
    team_id: UUID
    run_id: UUID
    commit_id: UUID
    transaction_sequence: int
    recorded_at: datetime


@dataclass(frozen=True)
class ProjectionIntent(ProjectionIntentDraft):
    append_sequence: int
    team_id: UUID
    run_id: UUID
    commit_id: UUID
    transaction_sequence: int
    recorded_at: datetime


@dataclass(frozen=True)
class LedgerPageQuery:
    team_id: UUID
    run_id: UUID | None
    after_sequence: int | None
    limit: int

    def __post_init__(self) -> None:
        _validate_page_query(self)


@dataclass(frozen=True)
class ProjectionPageQuery:
    team_id: UUID
    run_id: UUID | None
    after_sequence: int | None
    limit: int

    def __post_init__(self) -> None:
        _validate_page_query(self)


def _validate_page_query(query: LedgerPageQuery | ProjectionPageQuery) -> None:
    _uuid(query.team_id, "team_id")
    if query.run_id is not None:
        _uuid(query.run_id, "run_id")
    if query.after_sequence is not None:
        _non_negative(query.after_sequence, "after_sequence")
    invalid_type = isinstance(query.limit, bool) or not isinstance(query.limit, int)
    if invalid_type or not 1 <= query.limit <= MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")


@dataclass(frozen=True)
class ActivityPage:
    items: tuple[ActivityEvent, ...]
    next_cursor: int | None


@dataclass(frozen=True)
class GroundTruthPage:
    items: tuple[GroundTruthRecord, ...]
    next_cursor: int | None


@dataclass(frozen=True)
class ProjectionPage:
    items: tuple[ProjectionIntent, ...]
    next_cursor: int | None


@dataclass(frozen=True)
class CommittedTickSlice:
    runtime: TeamRuntime
    activity: tuple[ActivityEvent, ...]
    ground_truth: tuple[GroundTruthRecord, ...]
    projection_intents: tuple[ProjectionIntent, ...]
