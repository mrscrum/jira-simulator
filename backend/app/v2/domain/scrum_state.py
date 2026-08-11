"""Immutable authoritative Scrum-state contracts for the v2 simulator."""

import json
import math
from datetime import UTC, date, datetime
from enum import StrEnum
from functools import total_ordering
from typing import Self, get_args
from uuid import UUID

from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.deterministic_rng import (
    ALGORITHM_ID,
    CANONICAL_DECISION_KEYS,
    DISCARDED_LOW_BITS,
    LOWER_HEX_64_PATTERN,
    MAX_SAFE_INTEGER,
    U53_DENOMINATOR,
    CreationKind,
    DecisionType,
    item_rng_id,
    member_rng_id,
    sprint_rng_id,
    visit_rng_id,
)
from app.v2.domain.immutable_value import ImmutableValue, immutable_dataclass
from app.v2.domain.sampling import DwellAnchors, TouchBounds, sample_dwell, sample_touch
from app.v2.domain.team_blueprint import IssueType, StoryPoints

MAX_COUNTER_NEXT_VALUE = MAX_SAFE_INTEGER + 1
MAX_SQLITE_INTEGER = 2**63 - 1
ISSUE_TYPES = get_args(IssueType)
STORY_POINTS = get_args(StoryPoints)
WORK_PRIORITY_ORDER = ("HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST")
DRAW_KEYS = frozenset(
    {
        "algorithm",
        "canonical_message",
        "decision_type",
        "draw_index",
        "entity_id",
        "hmac_sha256",
        "occurrence",
        "u53_integer",
        "unit_value",
    }
)


class WorkItemLifecycle(StrEnum):
    BACKLOG = "BACKLOG"
    ACTIVE = "ACTIVE"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class SprintLifecycle(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class StatusVisitLifecycle(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class WorkPriority(StrEnum):
    HIGHEST = "HIGHEST"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    LOWEST = "LOWEST"


class SemanticCounterKind(StrEnum):
    SPRINT_ORDINAL = "SPRINT_ORDINAL"
    ITEM_SEQUENCE = "ITEM_SEQUENCE"
    VISIT_ORDINAL = "VISIT_ORDINAL"
    NATURAL_DECISION_OCCURRENCE = "NATURAL_DECISION_OCCURRENCE"


class FactorKind(StrEnum):
    DESCRIPTION_QUALITY = "DESCRIPTION_QUALITY"
    LATENT_COMPLEXITY = "LATENT_COMPLEXITY"


def _require_uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError(f"{label} must be a UUID")
    return value


def _require_safe_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    if value > MAX_SAFE_INTEGER:
        raise ValueError(f"{label} must not exceed 2^53 - 1")
    return value


def _require_counter_value(value: object) -> int:
    if type(value) is not int:
        raise TypeError("next_value must be an integer")
    if not 0 <= value <= MAX_COUNTER_NEXT_VALUE:
        raise ValueError("next_value must be safe or the exact exhausted sentinel")
    return value


def _require_microseconds(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if not 0 <= value <= MAX_SQLITE_INTEGER:
        raise ValueError(f"{label} must fit the non-negative signed SQLite integer range")
    return value


def _require_fraction(value: object, label: str) -> float:
    if type(value) is not float:
        raise TypeError(f"{label} must be a float")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{label} must be a finite fraction in [0, 1]")
    return value


def _require_finite_float(value: object, label: str) -> float:
    if type(value) is not float:
        raise TypeError(f"{label} must be a float")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return value


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value or value.strip() != value:
        raise ValueError(f"{label} must be non-empty canonical text")
    return value


def _require_utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be an aware datetime")
    return value.astimezone(UTC)


def _normalize_utc_fields(value: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        instant = getattr(value, field_name)
        if instant is not None:
            object.__setattr__(value, field_name, _require_utc(instant, field_name))


def _require_date(value: object, label: str) -> date:
    if type(value) is not date:
        raise TypeError(f"{label} must be a date")
    return value


def _require_enum(value: object, enum_type: type[StrEnum], label: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{label} must be a {enum_type.__name__}")


def _canonical_document(text: object, digest: object, label: str) -> dict[str, object]:
    _require_text(text, f"{label}_json")
    _require_text(digest, f"{label}_sha256")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be valid canonical JSON") from error
    if not isinstance(document, dict) or canonical_json(document) != text:
        raise ValueError(f"{label} must be a canonical JSON object")
    if canonical_sha256(document) != digest:
        raise ValueError(f"{label} digest does not match canonical JSON")
    return document


def _require_semantic_id(actual: UUID, expected: UUID, label: str) -> None:
    _require_uuid(actual, label)
    if actual != expected:
        raise ValueError(f"{label} does not match its semantic coordinates")


@total_ordering
@immutable_dataclass
class SimulatorRank(ImmutableValue):
    priority: WorkPriority
    relative_rank: int
    work_item_id: UUID

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_enum(self.priority, WorkPriority, "priority")
        _require_safe_integer(self.relative_rank, "relative_rank")
        _require_uuid(self.work_item_id, "work_item_id")

    def _sort_key(self) -> tuple[int, int, UUID]:
        return WORK_PRIORITY_ORDER.index(self.priority.value), self.relative_rank, self.work_item_id

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SimulatorRank):
            return NotImplemented
        return self._sort_key() < other._sort_key()


@immutable_dataclass
class MemberIdentity(ImmutableValue):
    id: UUID
    team_id: UUID
    blueprint_index: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_uuid(self.team_id, "team_id")
        index = _require_safe_integer(self.blueprint_index, "blueprint_index")
        _require_semantic_id(self.id, member_rng_id(self.team_id, index), "semantic member id")


@immutable_dataclass
class MemberAvailabilityOverlay(ImmutableValue):
    id: UUID
    team_id: UUID
    run_id: UUID
    member_id: UUID
    source: str
    starts_at: datetime
    ends_at: datetime
    availability_fraction: float
    daily_capacity_ceiling_microseconds: int | None
    reason: str
    provenance_json: str
    provenance_sha256: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _normalize_utc_fields(self, ("starts_at", "ends_at", "created_at"))
        for value, label in (
            (self.id, "id"),
            (self.team_id, "team_id"),
            (self.run_id, "run_id"),
            (self.member_id, "member_id"),
        ):
            _require_uuid(value, label)
        _require_text(self.source, "source")
        if _require_utc(self.starts_at, "starts_at") >= _require_utc(self.ends_at, "ends_at"):
            raise ValueError("overlay interval must be half-open with starts_at before ends_at")
        _require_fraction(self.availability_fraction, "availability_fraction")
        if self.daily_capacity_ceiling_microseconds is not None:
            _require_microseconds(self.daily_capacity_ceiling_microseconds, "capacity ceiling")
        _require_text(self.reason, "reason")
        _canonical_document(self.provenance_json, self.provenance_sha256, "provenance")
        _require_utc(self.created_at, "created_at")


@immutable_dataclass
class MemberBusinessDateConsumption(ImmutableValue):
    team_id: UUID
    run_id: UUID
    member_id: UUID
    business_date: date
    consumed_labor_microseconds: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")
        _require_uuid(self.member_id, "member_id")
        _require_date(self.business_date, "business_date")
        _require_microseconds(self.consumed_labor_microseconds, "consumed_labor_microseconds")


@immutable_dataclass
class WorkItemState(ImmutableValue):
    id: UUID
    team_id: UUID
    run_id: UUID
    creation_kind: CreationKind
    creation_sequence: int
    issue_type: IssueType
    story_points: StoryPoints
    priority: WorkPriority
    relative_rank: int
    lifecycle: WorkItemLifecycle
    current_status_key: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    @property
    def simulator_rank(self) -> SimulatorRank:
        return SimulatorRank(self.priority, self.relative_rank, self.id)

    def validate(self) -> None:
        _normalize_utc_fields(self, ("created_at", "updated_at"))
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")
        _require_enum(self.creation_kind, CreationKind, "creation_kind")
        sequence = _require_safe_integer(self.creation_sequence, "creation_sequence")
        _require_semantic_id(
            self.id,
            item_rng_id(self.team_id, self.creation_kind, sequence),
            "semantic work item id",
        )
        self._validate_classification()
        if _require_utc(self.updated_at, "updated_at") < _require_utc(
            self.created_at, "created_at"
        ):
            raise ValueError("updated_at must not precede created_at")

    def _validate_classification(self) -> None:
        if type(self.issue_type) is not str or self.issue_type not in ISSUE_TYPES:
            raise ValueError("issue_type must be a supported exact value")
        if type(self.story_points) is not int:
            raise TypeError("story_points must be an integer")
        if self.story_points not in STORY_POINTS:
            raise ValueError("story_points must use the supported Fibonacci scale")
        _require_enum(self.priority, WorkPriority, "priority")
        _require_safe_integer(self.relative_rank, "relative_rank")
        _require_enum(self.lifecycle, WorkItemLifecycle, "lifecycle")
        _require_text(self.current_status_key, "current_status_key")


@immutable_dataclass
class WorkItemFactor(ImmutableValue):
    id: UUID
    team_id: UUID
    run_id: UUID
    work_item_id: UUID
    kind: FactorKind
    value: float
    provenance_json: str
    provenance_sha256: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _normalize_utc_fields(self, ("recorded_at",))
        for value, label in (
            (self.team_id, "team_id"),
            (self.run_id, "run_id"),
            (self.work_item_id, "work_item_id"),
        ):
            _require_uuid(value, label)
        _require_enum(self.kind, FactorKind, "kind")
        expected = semantic_uuid(f"factor/{self.work_item_id}/{self.kind.value}")
        _require_semantic_id(self.id, expected, "semantic factor id")
        _require_fraction(self.value, "factor value")
        _canonical_document(self.provenance_json, self.provenance_sha256, "provenance")
        _require_utc(self.recorded_at, "recorded_at")


@immutable_dataclass
class SprintState(ImmutableValue):
    id: UUID
    team_id: UUID
    run_id: UUID
    ordinal: int
    lifecycle: SprintLifecycle
    planned_start_at: datetime
    planned_end_at: datetime
    observed_start_at: datetime | None
    observed_end_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _normalize_utc_fields(
            self,
            (
                "planned_start_at",
                "planned_end_at",
                "observed_start_at",
                "observed_end_at",
                "created_at",
                "updated_at",
            ),
        )
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")
        ordinal = _require_safe_integer(self.ordinal, "ordinal")
        _require_semantic_id(self.id, sprint_rng_id(self.team_id, ordinal), "semantic sprint id")
        _require_enum(self.lifecycle, SprintLifecycle, "lifecycle")
        if _require_utc(self.planned_start_at, "planned_start_at") >= _require_utc(
            self.planned_end_at, "planned_end_at"
        ):
            raise ValueError("planned sprint interval must be positive")
        self._validate_observed_times()
        if _require_utc(self.updated_at, "updated_at") < _require_utc(
            self.created_at, "created_at"
        ):
            raise ValueError("updated_at must not precede created_at")

    def _validate_observed_times(self) -> None:
        start = (
            None
            if self.observed_start_at is None
            else _require_utc(self.observed_start_at, "observed_start_at")
        )
        end = (
            None
            if self.observed_end_at is None
            else _require_utc(self.observed_end_at, "observed_end_at")
        )
        expected_presence = {
            SprintLifecycle.PLANNED: (False, False),
            SprintLifecycle.ACTIVE: (True, False),
            SprintLifecycle.COMPLETED: (True, True),
        }[self.lifecycle]
        if (start is not None, end is not None) != expected_presence:
            raise ValueError("observed_start_at/observed_end_at do not match sprint lifecycle")
        if start is not None and end is not None and end < start:
            raise ValueError("observed_end_at must not precede observed_start_at")


@immutable_dataclass
class SprintScopeEntry(ImmutableValue):
    id: UUID
    team_id: UUID
    run_id: UUID
    sprint_id: UUID
    work_item_id: UUID
    added_at: datetime
    removed_at: datetime | None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _normalize_utc_fields(self, ("added_at", "removed_at"))
        for value, label in (
            (self.team_id, "team_id"),
            (self.run_id, "run_id"),
            (self.sprint_id, "sprint_id"),
            (self.work_item_id, "work_item_id"),
        ):
            _require_uuid(value, label)
        expected = semantic_uuid(f"sprint-scope/{self.sprint_id}/{self.work_item_id}")
        _require_semantic_id(self.id, expected, "semantic sprint scope id")
        added = _require_utc(self.added_at, "added_at")
        if self.removed_at is not None and _require_utc(self.removed_at, "removed_at") < added:
            raise ValueError("removed_at must not precede added_at")


@immutable_dataclass
class StatusVisitState(ImmutableValue):
    id: UUID
    team_id: UUID
    run_id: UUID
    work_item_id: UUID
    ordinal: int
    lifecycle: StatusVisitLifecycle
    status_key: str
    activity_key: str
    member_id: UUID | None
    entered_at: datetime
    closed_at: datetime | None
    required_work_microseconds: int
    elapsed_work_microseconds: int
    remaining_work_microseconds: int
    queue_microseconds: int
    pause_microseconds: int
    credited_labor_microseconds: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _normalize_utc_fields(self, ("entered_at", "closed_at"))
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")
        _require_uuid(self.work_item_id, "work_item_id")
        ordinal = _require_safe_integer(self.ordinal, "ordinal")
        _require_semantic_id(self.id, visit_rng_id(self.work_item_id, ordinal), "semantic visit id")
        _require_enum(self.lifecycle, StatusVisitLifecycle, "lifecycle")
        _require_text(self.status_key, "status_key")
        _require_text(self.activity_key, "activity_key")
        if self.member_id is not None:
            _require_uuid(self.member_id, "member_id")
        self._validate_times()
        self._validate_microseconds()

    def _validate_times(self) -> None:
        entered = _require_utc(self.entered_at, "entered_at")
        if self.lifecycle is StatusVisitLifecycle.OPEN and self.closed_at is not None:
            raise ValueError("open visit must not have closed_at")
        if self.lifecycle is StatusVisitLifecycle.CLOSED and self.closed_at is None:
            raise ValueError("closed visit must have closed_at")
        if self.closed_at is not None and _require_utc(self.closed_at, "closed_at") < entered:
            raise ValueError("closed_at must not precede entered_at")

    def _validate_microseconds(self) -> None:
        values = (
            (self.required_work_microseconds, "required_work_microseconds"),
            (self.elapsed_work_microseconds, "elapsed_work_microseconds"),
            (self.remaining_work_microseconds, "remaining_work_microseconds"),
            (self.queue_microseconds, "queue_microseconds"),
            (self.pause_microseconds, "pause_microseconds"),
            (self.credited_labor_microseconds, "credited_labor_microseconds"),
        )
        for value, label in values:
            _require_microseconds(value, label)
        if self.required_work_microseconds != (
            self.elapsed_work_microseconds + self.remaining_work_microseconds
        ):
            raise ValueError("required work must equal elapsed plus remaining")
        if self.lifecycle is StatusVisitLifecycle.CLOSED and self.remaining_work_microseconds:
            raise ValueError("closed visit must have no remaining work")


def _parameter_documents(sample: "StatusVisitSample") -> tuple[dict[str, object], ...]:
    dwell = _canonical_document(
        sample.dwell_parameters_json, sample.dwell_parameters_sha256, "dwell parameters"
    )
    touch = _canonical_document(
        sample.touch_parameters_json, sample.touch_parameters_sha256, "touch parameters"
    )
    if frozenset(dwell) != {"minimum", "p25", "p50", "p99", "maximum"}:
        raise ValueError("dwell parameters have the wrong canonical schema")
    if frozenset(touch) != {"minimum", "maximum"}:
        raise ValueError("touch parameters have the wrong canonical schema")
    return dwell, touch


def _draw_document(text: str, digest: str, label: str) -> dict[str, object]:
    document = _canonical_document(text, digest, label)
    if frozenset(document) != DRAW_KEYS or document["algorithm"] != ALGORITHM_ID:
        raise ValueError(f"{label} has the wrong Task 3 draw schema")
    _canonical_message(document, label)
    digest_text = _require_text(document["hmac_sha256"], f"{label} hmac_sha256")
    if LOWER_HEX_64_PATTERN.fullmatch(digest_text) is None:
        raise ValueError(f"{label} hmac_sha256 must be lower-case hexadecimal")
    u53_integer = _require_safe_integer(document["u53_integer"], f"{label} u53_integer")
    expected_integer = (
        int.from_bytes(bytes.fromhex(digest_text)[:8], "big") >> DISCARDED_LOW_BITS
    )
    if u53_integer != expected_integer:
        raise ValueError(f"{label} u53_integer does not match HMAC provenance")
    unit_value = _require_fraction(document["unit_value"], f"{label} unit_value")
    if unit_value != u53_integer / U53_DENOMINATOR:
        raise ValueError(f"{label} unit value does not match U53 provenance")
    return document


def _canonical_message(document: dict[str, object], label: str) -> dict[str, object]:
    message = document["canonical_message"]
    if not isinstance(message, str):
        raise TypeError(f"{label} canonical_message must be a string")
    try:
        message_document = json.loads(message)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} canonical_message must be JSON") from error
    if not isinstance(message_document, dict) or canonical_json(message_document) != message:
        raise ValueError(f"{label} canonical_message must be canonical JSON")
    if frozenset(message_document) != CANONICAL_DECISION_KEYS:
        raise ValueError(f"{label} canonical_message has the wrong decision schema")
    return message_document


def _canonical_uuid_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError(f"{label} must be canonical UUID text") from error
    if str(parsed) != value:
        raise ValueError(f"{label} must be lower-case hyphenated UUID text")
    return value


def _validate_draw_coordinate(
    sample: "StatusVisitSample", document: dict[str, object], expected_type: DecisionType
) -> None:
    message = _canonical_message(document, expected_type.value)
    outer = _outer_draw_coordinate(document)
    if outer[2] != str(sample.visit_id):
        raise ValueError("draw entity_id must match visit_id")
    if outer[4] != 0 or outer[3] != expected_type.value:
        raise ValueError("draw decision coordinate does not match the status sample")
    expected = (ALGORITHM_ID, str(sample.team_id), str(sample.run_id), *outer[2:])
    if _message_draw_coordinate(message) != expected:
        raise ValueError("canonical message does not match the status sample coordinate")


def _outer_draw_coordinate(document: dict[str, object]) -> tuple[object, ...]:
    return (
        document["algorithm"],
        document["canonical_message"],
        _canonical_uuid_text(document["entity_id"], "draw entity_id"),
        _require_text(document["decision_type"], "draw decision_type"),
        _require_safe_integer(document["occurrence"], "draw occurrence"),
        _require_safe_integer(document["draw_index"], "draw_index"),
    )


def _message_draw_coordinate(message: dict[str, object]) -> tuple[object, ...]:
    return (
        _require_text(message["algorithm"], "message algorithm"),
        _canonical_uuid_text(message["team_id"], "message team_id"),
        _canonical_uuid_text(message["run_id"], "message run_id"),
        _canonical_uuid_text(message["entity_id"], "message entity_id"),
        _require_text(message["decision_type"], "message decision_type"),
        _require_safe_integer(message["occurrence"], "message occurrence"),
        _require_safe_integer(message["draw_index"], "message draw_index"),
    )


def _anchors(document: dict[str, object]) -> DwellAnchors:
    return DwellAnchors(
        document["minimum"], document["p25"], document["p50"], document["p99"], document["maximum"]
    )


def _bounds(document: dict[str, object]) -> TouchBounds:
    return TouchBounds(document["minimum"], document["maximum"])


@immutable_dataclass
class StatusVisitSample(ImmutableValue):
    visit_id: UUID
    team_id: UUID
    run_id: UUID
    timing_profile: str
    timing_profile_version: str
    dwell_sampler_version: str
    touch_sampler_version: str
    dwell_parameters_json: str
    dwell_parameters_sha256: str
    touch_parameters_json: str
    touch_parameters_sha256: str
    dwell_draw_json: str
    dwell_draw_sha256: str
    touch_draw_json: str
    touch_draw_sha256: str
    dwell_unit_value: float
    touch_unit_value: float
    dwell_sampled_hours: float
    touch_sampled_hours: float
    required_work_microseconds: int
    required_work_sha256: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_uuid(self.visit_id, "visit_id")
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")
        for value, label in (
            (self.timing_profile, "timing_profile"),
            (self.timing_profile_version, "timing_profile_version"),
            (self.dwell_sampler_version, "dwell_sampler_version"),
            (self.touch_sampler_version, "touch_sampler_version"),
        ):
            _require_text(value, label)
        self._validate_samples()
        self._validate_required_work()

    def _validate_samples(self) -> None:
        dwell_parameters, touch_parameters = _parameter_documents(self)
        dwell_draw = _draw_document(self.dwell_draw_json, self.dwell_draw_sha256, "dwell draw")
        touch_draw = _draw_document(self.touch_draw_json, self.touch_draw_sha256, "touch draw")
        _validate_draw_coordinate(self, dwell_draw, DecisionType.STATUS_DWELL)
        _validate_draw_coordinate(self, touch_draw, DecisionType.STATUS_TOUCH)
        if dwell_draw["unit_value"] != self.dwell_unit_value:
            raise ValueError("dwell unit value does not match draw provenance")
        if touch_draw["unit_value"] != self.touch_unit_value:
            raise ValueError("touch unit value does not match draw provenance")
        expected_dwell = sample_dwell(_anchors(dwell_parameters), self.dwell_unit_value)
        expected_touch = sample_touch(_bounds(touch_parameters), self.touch_unit_value)
        _require_finite_float(self.dwell_sampled_hours, "dwell_sampled_hours")
        _require_finite_float(self.touch_sampled_hours, "touch_sampled_hours")
        if self.dwell_sampled_hours != expected_dwell.sampled_hours:
            raise ValueError("dwell sampled hours do not match parameters and unit draw")
        if self.touch_sampled_hours != expected_touch.sampled_hours:
            raise ValueError("touch sampled hours do not match parameters and unit draw")

    def _validate_required_work(self) -> None:
        required = _require_microseconds(
            self.required_work_microseconds, "required_work_microseconds"
        )
        expected = canonical_sha256({"required_work_microseconds": required})
        if self.required_work_sha256 != expected:
            raise ValueError("required work digest does not match exact microseconds")


def _scope_key(kind: SemanticCounterKind) -> tuple[str, ...]:
    if kind is SemanticCounterKind.SPRINT_ORDINAL:
        return ("SCRUM",)
    if kind is SemanticCounterKind.ITEM_SEQUENCE:
        return tuple(item.value for item in CreationKind)
    if kind is SemanticCounterKind.VISIT_ORDINAL:
        return ("VISIT",)
    return tuple(item.value for item in DecisionType)


@immutable_dataclass
class SemanticCounterScope(ImmutableValue):
    kind: SemanticCounterKind
    scope_id: UUID
    scope_key: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_enum(self.kind, SemanticCounterKind, "kind")
        _require_uuid(self.scope_id, "scope_id")
        _require_text(self.scope_key, "scope_key")
        if self.scope_key not in _scope_key(self.kind):
            raise ValueError("scope_key does not match the semantic counter kind")


@immutable_dataclass
class SemanticCounter(ImmutableValue):
    team_id: UUID
    run_id: UUID
    scope: SemanticCounterScope
    next_value: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")
        if not isinstance(self.scope, SemanticCounterScope):
            raise TypeError("scope must be a SemanticCounterScope")
        self.scope.validate()
        _require_counter_value(self.next_value)
        if (
            self.scope.kind
            in {
                SemanticCounterKind.SPRINT_ORDINAL,
                SemanticCounterKind.ITEM_SEQUENCE,
            }
            and self.scope.scope_id != self.team_id
        ):
            raise ValueError("team-scoped counter must use team_id as scope_id")


@immutable_dataclass
class NaturalDecisionEvaluation(ImmutableValue):
    id: UUID
    team_id: UUID
    run_id: UUID
    decision_type: DecisionType
    semantic_entity_id: UUID
    business_date: date
    occurrence: int
    commit_id: UUID
    recorded_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _normalize_utc_fields(self, ("recorded_at",))
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")
        _require_enum(self.decision_type, DecisionType, "decision_type")
        _require_uuid(self.semantic_entity_id, "semantic_entity_id")
        _require_date(self.business_date, "business_date")
        _require_safe_integer(self.occurrence, "occurrence")
        _require_uuid(self.commit_id, "commit_id")
        _require_utc(self.recorded_at, "recorded_at")
        _require_semantic_id(self.id, self._expected_id(), "semantic evaluation id")

    def _expected_id(self) -> UUID:
        path = (
            f"evaluation/{self.team_id}/{self.run_id}/{self.decision_type.value}/"
            f"{self.semantic_entity_id}/{self.business_date}"
        )
        return semantic_uuid(path)


@immutable_dataclass
class ScrumStateQuery(ImmutableValue):
    team_id: UUID
    run_id: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")


COLLECTION_TYPES = (
    MemberIdentity,
    MemberAvailabilityOverlay,
    MemberBusinessDateConsumption,
    WorkItemState,
    WorkItemFactor,
    SprintState,
    SprintScopeEntry,
    StatusVisitState,
    StatusVisitSample,
    SemanticCounter,
    NaturalDecisionEvaluation,
)


def _validate_collection(items: object, value_type: type) -> None:
    if not isinstance(items, tuple):
        raise TypeError("Scrum state collections must be tuples")
    for item in items:
        if not isinstance(item, value_type):
            raise TypeError(f"collection values must be {value_type.__name__}")
        item.validate()


class _ScrumCollections:
    __slots__ = ()

    def _collection_values(self) -> tuple[tuple[object, ...], ...]:
        return (
            self.member_identities,
            self.member_availability_overlays,
            self.member_business_date_consumption,
            self.work_items,
            self.work_item_factors,
            self.sprints,
            self.sprint_scope,
            self.status_visits,
            self.status_visit_samples,
            self.semantic_counters,
            self.natural_decision_evaluations,
        )

    def validate(self) -> None:
        collections = self._collection_values()
        for items, value_type in zip(collections, COLLECTION_TYPES, strict=True):
            _validate_collection(items, value_type)
        _validate_sample_links(self.status_visits, self.status_visit_samples)


def _validate_sample_links(
    visits: tuple[StatusVisitState, ...], samples: tuple[StatusVisitSample, ...]
) -> None:
    by_id = {visit.id: visit for visit in visits}
    for sample in samples:
        visit = by_id.get(sample.visit_id)
        if visit is None:
            continue
        if (sample.team_id, sample.run_id) != (visit.team_id, visit.run_id):
            raise ValueError("status sample team/run must match its visit")
        if sample.required_work_microseconds != visit.required_work_microseconds:
            raise ValueError("status sample must match visit required work")


@immutable_dataclass
class ScrumStateWriteSet(_ScrumCollections, ImmutableValue):
    member_identities: tuple[MemberIdentity, ...] = ()
    member_availability_overlays: tuple[MemberAvailabilityOverlay, ...] = ()
    member_business_date_consumption: tuple[MemberBusinessDateConsumption, ...] = ()
    work_items: tuple[WorkItemState, ...] = ()
    work_item_factors: tuple[WorkItemFactor, ...] = ()
    sprints: tuple[SprintState, ...] = ()
    sprint_scope: tuple[SprintScopeEntry, ...] = ()
    status_visits: tuple[StatusVisitState, ...] = ()
    status_visit_samples: tuple[StatusVisitSample, ...] = ()
    semantic_counters: tuple[SemanticCounter, ...] = ()
    natural_decision_evaluations: tuple[NaturalDecisionEvaluation, ...] = ()

    def __post_init__(self) -> None:
        self.validate()


@immutable_dataclass
class ScrumStateSnapshot(_ScrumCollections, ImmutableValue):
    member_identities: tuple[MemberIdentity, ...] = ()
    member_availability_overlays: tuple[MemberAvailabilityOverlay, ...] = ()
    member_business_date_consumption: tuple[MemberBusinessDateConsumption, ...] = ()
    work_items: tuple[WorkItemState, ...] = ()
    work_item_factors: tuple[WorkItemFactor, ...] = ()
    sprints: tuple[SprintState, ...] = ()
    sprint_scope: tuple[SprintScopeEntry, ...] = ()
    status_visits: tuple[StatusVisitState, ...] = ()
    status_visit_samples: tuple[StatusVisitSample, ...] = ()
    semantic_counters: tuple[SemanticCounter, ...] = ()
    natural_decision_evaluations: tuple[NaturalDecisionEvaluation, ...] = ()

    def __post_init__(self) -> None:
        self.validate()

    @classmethod
    def from_write_set(cls, state: ScrumStateWriteSet) -> Self:
        if not isinstance(state, ScrumStateWriteSet):
            raise TypeError("state must be a ScrumStateWriteSet")
        state.validate()
        return cls(*state._collection_values())
