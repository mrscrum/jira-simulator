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
    DecisionOccurrence,
    DecisionType,
    DeterministicRandomStream,
    UniformDraw,
    item_rng_id,
    member_rng_id,
    sprint_rng_id,
    team_rng_id,
    visit_rng_id,
)
from app.v2.domain.immutable_value import ImmutableValue, immutable_dataclass
from app.v2.domain.sampling import (
    DwellAnchors,
    TouchBounds,
    dwell_anchors,
    sample_dwell,
    sample_touch,
    touch_bounds,
)
from app.v2.domain.team_blueprint import (
    IssueType,
    ResolvedTeamBlueprint,
    StoryPoints,
    TimingEntry,
)

MAX_COUNTER_NEXT_VALUE = MAX_SAFE_INTEGER + 1
MAX_SQLITE_INTEGER = 2**63 - 1
ISSUE_TYPES = get_args(IssueType)
STORY_POINTS = get_args(StoryPoints)
WORK_PRIORITY_ORDER = ("HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST")
TOUCH_SAMPLER_VERSION = "LINEAR_UNIFORM_TOUCH_V1"
NATURAL_OWNER_DECISIONS = frozenset(
    {
        DecisionType.RISK_CANCELLATION_OUTCOME,
        DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME,
    }
)
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
    if type(value) is not UUID:
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
    if type(value) is not str:
        raise TypeError(f"{label} must be a string")
    if not value or value.strip() != value:
        raise ValueError(f"{label} must be non-empty canonical text")
    return value


def _require_optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, label)


def _require_lower_hex_digest(value: object, label: str) -> str:
    digest = _require_text(value, label)
    if LOWER_HEX_64_PATTERN.fullmatch(digest) is None:
        raise ValueError(f"{label} must be a lower-case SHA-256 digest")
    return digest


def _require_utc(value: object, label: str) -> datetime:
    if type(value) is not datetime:
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
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
    if type(value) is not enum_type:
        raise TypeError(f"{label} must be a {enum_type.__name__}")


def _canonical_document(text: object, digest: object, label: str) -> dict[str, object]:
    _require_text(text, f"{label}_json")
    _require_lower_hex_digest(digest, f"{label}_sha256")
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


def _require_exact_type(value: object, value_type: type, label: str) -> None:
    if type(value) is not value_type:
        raise TypeError(f"{label} must be an exact {value_type.__name__}")


def _hours_to_microseconds(hours: float) -> int:
    normalized = _require_finite_float(hours, "touch sampled hours")
    numerator, denominator = normalized.as_integer_ratio()
    whole, remainder = divmod(numerator * 3_600_000_000, denominator)
    twice_remainder = remainder * 2
    if twice_remainder > denominator or (
        twice_remainder == denominator and whole % 2 == 1
    ):
        whole += 1
    return _require_microseconds(whole, "required_work_microseconds")


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
    activity_key: str | None
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
        _require_optional_text(self.activity_key, "activity_key")
        if self.member_id is not None:
            _require_uuid(self.member_id, "member_id")
        self._validate_zero_touch()
        self._validate_times()
        self._validate_microseconds()

    def _validate_zero_touch(self) -> None:
        if self.activity_key is not None:
            return
        if self.member_id is not None:
            raise ValueError("zero-touch visit must not have a member owner")
        touch_values = (
            self.required_work_microseconds,
            self.elapsed_work_microseconds,
            self.remaining_work_microseconds,
            self.credited_labor_microseconds,
        )
        if any(touch_values):
            raise ValueError("zero-touch visit must have zero touch and labor clocks")

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
    if type(value) is not str:
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
class StatusVisitSampleInput(ImmutableValue):
    blueprint: ResolvedTeamBlueprint
    work_item: WorkItemState
    visit: StatusVisitState
    dwell_draw: UniformDraw
    touch_draw: UniformDraw

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_exact_type(self.blueprint, ResolvedTeamBlueprint, "blueprint")
        _require_exact_type(self.work_item, WorkItemState, "work_item")
        _require_exact_type(self.visit, StatusVisitState, "visit")
        _require_exact_type(self.dwell_draw, UniformDraw, "dwell_draw")
        _require_exact_type(self.touch_draw, UniformDraw, "touch_draw")
        self.work_item.validate()
        self.visit.validate()
        _validate_sample_input_links(self)
        _authenticate_draw(self, self.dwell_draw, DecisionType.STATUS_DWELL)
        _authenticate_draw(self, self.touch_draw, DecisionType.STATUS_TOUCH)


def _validate_sample_input_links(sample_input: StatusVisitSampleInput) -> None:
    work = sample_input.work_item
    visit = sample_input.visit
    if (visit.team_id, visit.run_id, visit.work_item_id) != (work.team_id, work.run_id, work.id):
        raise ValueError("sample input work item and visit coordinates must match")
    if visit.lifecycle is StatusVisitLifecycle.OPEN and visit.status_key != work.current_status_key:
        raise ValueError("open visit status must match current work status")
    blueprint_document = json.loads(sample_input.blueprint.canonical_json())
    expected_team = team_rng_id(canonical_sha256(blueprint_document))
    if work.team_id != expected_team:
        raise ValueError("sample input team must match the canonical blueprint")
    _timing_entry(sample_input.blueprint, work, visit)


def _authenticate_draw(
    sample_input: StatusVisitSampleInput, draw: UniformDraw, decision_type: DecisionType
) -> None:
    _require_exact_type(draw.decision, DecisionOccurrence, "draw decision")
    decision = DecisionOccurrence(sample_input.visit.id, decision_type, 0)
    stream = DeterministicRandomStream(
        sample_input.blueprint.seed,
        sample_input.work_item.team_id,
        sample_input.work_item.run_id,
    )
    if draw != stream.draw(decision, 0):
        raise ValueError("draw is not authenticated by the persisted blueprint seed")


def _timing_entry(
    blueprint: ResolvedTeamBlueprint, work: WorkItemState, visit: StatusVisitState
) -> TimingEntry:
    matches = tuple(
        entry
        for entry in blueprint.timing.entries
        if (entry.status_key, entry.issue_type, entry.story_points)
        == (visit.status_key, work.issue_type, work.story_points)
    )
    if len(matches) != 1:
        raise ValueError("status sample must resolve one exact blueprint timing cell")
    return matches[0]


def _canonical_pair(document: dict[str, object]) -> tuple[str, str]:
    return canonical_json(document), canonical_sha256(document)


def _task3_draw_document(draw: UniformDraw) -> dict[str, object]:
    return {
        "algorithm": draw.algorithm,
        "canonical_message": draw.canonical_message.decode("utf-8"),
        "decision_type": draw.decision.decision_type.value,
        "draw_index": draw.draw_index,
        "entity_id": str(draw.decision.entity_id),
        "hmac_sha256": draw.hmac_sha256,
        "occurrence": draw.decision.occurrence,
        "u53_integer": draw.u53_integer,
        "unit_value": draw.unit_value,
    }


def _parameter_value_fields(entry: TimingEntry) -> dict[str, object]:
    dwell_document = {
        "maximum": entry.max,
        "minimum": entry.min,
        "p25": entry.p25,
        "p50": entry.p50,
        "p99": entry.p99,
    }
    touch_document = {"maximum": entry.touch_max, "minimum": entry.touch_min}
    dwell_json, dwell_sha256 = _canonical_pair(dwell_document)
    touch_json, touch_sha256 = _canonical_pair(touch_document)
    return {
        "dwell_parameters_json": dwell_json,
        "dwell_parameters_sha256": dwell_sha256,
        "touch_parameters_json": touch_json,
        "touch_parameters_sha256": touch_sha256,
    }


def _draw_value_fields(sample_input: StatusVisitSampleInput) -> dict[str, object]:
    dwell_document = _task3_draw_document(sample_input.dwell_draw)
    touch_document = _task3_draw_document(sample_input.touch_draw)
    dwell_json, dwell_sha256 = _canonical_pair(dwell_document)
    touch_json, touch_sha256 = _canonical_pair(touch_document)
    return {
        "dwell_draw_json": dwell_json,
        "dwell_draw_sha256": dwell_sha256,
        "touch_draw_json": touch_json,
        "touch_draw_sha256": touch_sha256,
    }


def _result_value_fields(
    sample_input: StatusVisitSampleInput, entry: TimingEntry
) -> dict[str, object]:
    dwell = sample_dwell(dwell_anchors(entry), sample_input.dwell_draw.unit_value)
    touch = sample_touch(touch_bounds(entry), sample_input.touch_draw.unit_value)
    required = _hours_to_microseconds(touch.sampled_hours)
    if sample_input.visit.required_work_microseconds != required:
        raise ValueError("visit required work must equal the retained touch sample")
    return {
        "dwell_unit_value": sample_input.dwell_draw.unit_value,
        "touch_unit_value": sample_input.touch_draw.unit_value,
        "dwell_sampled_hours": dwell.sampled_hours,
        "touch_sampled_hours": touch.sampled_hours,
        "required_work_microseconds": required,
        "required_work_sha256": canonical_sha256({"required_work_microseconds": required}),
    }


def _status_sample_values(sample_input: StatusVisitSampleInput) -> dict[str, object]:
    sample_input.validate()
    entry = _timing_entry(sample_input.blueprint, sample_input.work_item, sample_input.visit)
    identity = {
        "visit_id": sample_input.visit.id,
        "team_id": sample_input.work_item.team_id,
        "run_id": sample_input.work_item.run_id,
        "timing_profile": sample_input.blueprint.timing.profile_name,
        "timing_profile_version": str(sample_input.blueprint.timing.profile_version),
        "dwell_sampler_version": sample_input.blueprint.timing.algorithm_version,
        "touch_sampler_version": TOUCH_SAMPLER_VERSION,
    }
    return {
        **identity,
        **_parameter_value_fields(entry),
        **_draw_value_fields(sample_input),
        **_result_value_fields(sample_input, entry),
    }


def _create_status_sample(sample_input: StatusVisitSampleInput) -> "StatusVisitSample":
    sample = object.__new__(StatusVisitSample)
    for field_name, value in _status_sample_values(sample_input).items():
        object.__setattr__(sample, field_name, value)
    sample.validate()
    return sample


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

    def __init__(self, *_values: object, **_named_values: object) -> None:
        raise TypeError("StatusVisitSample instances require trusted sampling inputs")

    @classmethod
    def create(cls, sample_input: StatusVisitSampleInput) -> Self:
        _require_exact_type(sample_input, StatusVisitSampleInput, "sample_input")
        return _create_status_sample(sample_input)

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

    def authenticate(self, sample_input: StatusVisitSampleInput) -> None:
        expected = _status_sample_values(sample_input)
        actual = {name: getattr(self, name) for name in self.__dataclass_fields__}
        if actual != expected:
            raise ValueError("persisted status sample does not match authenticated provenance")
        self.validate()

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
        if required != _hours_to_microseconds(self.touch_sampled_hours):
            raise ValueError("required work must equal retained touch sampled hours")
        expected = canonical_sha256({"required_work_microseconds": required})
        digest = _require_lower_hex_digest(
            self.required_work_sha256, "required_work_sha256"
        )
        if digest != expected:
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
        if type(self.scope) is not SemanticCounterScope:
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
        if (
            self.scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE
            and DecisionType(self.scope.scope_key) not in NATURAL_OWNER_DECISIONS
        ):
            raise ValueError("counter decision type has no supported natural owner")


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
        if self.decision_type not in NATURAL_OWNER_DECISIONS:
            raise ValueError("decision type has no supported natural owner")
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
    if type(items) is not tuple:
        raise TypeError("Scrum state collections must be tuples")
    for item in items:
        if type(item) is not value_type:
            raise TypeError(f"collection values must be {value_type.__name__}")
        item.validate()


def _record_identity(record: object) -> object:
    if type(record) is SemanticCounter:
        return record.team_id, record.run_id, record.scope
    if type(record) is MemberBusinessDateConsumption:
        return record.team_id, record.run_id, record.member_id, record.business_date
    return getattr(record, "id", getattr(record, "visit_id", None))


def _validate_collection_uniqueness(collections: tuple[tuple[object, ...], ...]) -> None:
    for items in collections:
        identities = tuple(_record_identity(item) for item in items)
        if len(set(identities)) != len(identities):
            raise ValueError("Scrum state collections must not contain duplicate identities")


def _validate_partial_uniqueness(state: "_ScrumCollections") -> None:
    active = tuple(item for item in state.sprints if item.lifecycle is SprintLifecycle.ACTIVE)
    current = tuple(item for item in state.sprint_scope if item.removed_at is None)
    open_visits = tuple(
        item for item in state.status_visits if item.lifecycle is StatusVisitLifecycle.OPEN
    )
    _require_unique_coordinates(active, ("team_id", "run_id"), "active sprint")
    _require_unique_coordinates(
        current, ("team_id", "run_id", "work_item_id"), "current sprint scope"
    )
    _require_unique_coordinates(
        open_visits, ("team_id", "run_id", "work_item_id"), "open status visit"
    )
    _require_unique_coordinates(
        state.natural_decision_evaluations,
        ("team_id", "run_id", "decision_type", "semantic_entity_id", "occurrence"),
        "natural evaluation occurrence",
    )


def _require_unique_coordinates(
    records: tuple[object, ...], field_names: tuple[str, ...], label: str
) -> None:
    coordinates = tuple(
        tuple(getattr(record, field_name) for field_name in field_names) for record in records
    )
    if len(set(coordinates)) != len(coordinates):
        raise ValueError(f"Scrum state must contain at most one {label}")


def _validate_one_team_run(collections: tuple[tuple[object, ...], ...]) -> None:
    records = tuple(item for items in collections for item in items)
    teams = {record.team_id for record in records}
    runs = {record.run_id for record in records if hasattr(record, "run_id")}
    if len(teams) > 1 or len(runs) > 1:
        raise ValueError("Scrum state collections must use one team/run")


def _require_reference(identifier: UUID, owners: dict[UUID, object], label: str) -> None:
    if identifier not in owners:
        raise ValueError(f"{label} must reference a state owner")


def _validate_member_references(state: "_ScrumCollections") -> None:
    members = {item.id: item for item in state.member_identities}
    for item in (*state.member_availability_overlays, *state.member_business_date_consumption):
        _require_reference(item.member_id, members, "member child")
    for visit in state.status_visits:
        if visit.member_id is not None:
            _require_reference(visit.member_id, members, "visit member")


def _validate_work_references(state: "_ScrumCollections") -> None:
    work_items = {item.id: item for item in state.work_items}
    sprints = {item.id: item for item in state.sprints}
    visits = {item.id: item for item in state.status_visits}
    for factor in state.work_item_factors:
        _require_reference(factor.work_item_id, work_items, "factor work item")
    for scope in state.sprint_scope:
        _require_reference(scope.work_item_id, work_items, "scope work item")
        _require_reference(scope.sprint_id, sprints, "scope sprint")
    for visit in state.status_visits:
        _require_reference(visit.work_item_id, work_items, "visit work item")
    for sample in state.status_visit_samples:
        _require_reference(sample.visit_id, visits, "sample visit")


def _validate_counter_references(state: "_ScrumCollections") -> None:
    work_ids = {item.id for item in state.work_items}
    member_ids = {item.id for item in state.member_identities}
    owner_sets = work_ids, member_ids
    for counter in state.semantic_counters:
        scope = counter.scope
        if scope.kind is SemanticCounterKind.VISIT_ORDINAL and scope.scope_id not in work_ids:
            raise ValueError("visit ordinal counter must reference a work item")
        if scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE:
            _validate_natural_owner(scope.scope_key, scope.scope_id, owner_sets)
    for evaluation in state.natural_decision_evaluations:
        _validate_natural_owner(
            evaluation.decision_type.value,
            evaluation.semantic_entity_id,
            owner_sets,
        )


def _validate_natural_owner(
    decision_key: str, owner_id: UUID, owner_sets: tuple[set[UUID], set[UUID]]
) -> None:
    decision = DecisionType(decision_key)
    work_ids, member_ids = owner_sets
    owners = member_ids if decision is DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME else work_ids
    if decision not in NATURAL_OWNER_DECISIONS or owner_id not in owners:
        raise ValueError("natural decision must reference its supported state owner")


def _validate_open_visit_status(state: "_ScrumCollections") -> None:
    work_items = {item.id: item for item in state.work_items}
    for visit in state.status_visits:
        work = work_items.get(visit.work_item_id)
        if work is None:
            continue
        is_open_status_mismatch = (
            visit.lifecycle is StatusVisitLifecycle.OPEN
            and visit.status_key != work.current_status_key
        )
        if is_open_status_mismatch:
            raise ValueError("open visit status must match current work status")


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
        _validate_collection_uniqueness(collections)
        _validate_partial_uniqueness(self)
        _validate_one_team_run(collections)
        _validate_open_visit_status(self)
        _validate_sample_links(self.status_visits, self.status_visit_samples)

    def validate_against(self, blueprint: ResolvedTeamBlueprint) -> None:
        _require_exact_type(blueprint, ResolvedTeamBlueprint, "blueprint")
        _validate_blueprint_team(self, blueprint)
        _validate_blueprint_members(self, blueprint)
        _validate_blueprint_work(self, blueprint)
        _validate_blueprint_visits(self, blueprint)
        _authenticate_samples(self, blueprint)


def _validate_blueprint_team(
    state: _ScrumCollections, blueprint: ResolvedTeamBlueprint
) -> None:
    expected = team_rng_id(canonical_sha256(json.loads(blueprint.canonical_json())))
    teams = {item.team_id for items in state._collection_values() for item in items}
    if teams and teams != {expected}:
        raise ValueError("Scrum state team must match the persisted blueprint")


def _validate_blueprint_members(
    state: _ScrumCollections, blueprint: ResolvedTeamBlueprint
) -> None:
    for identity in state.member_identities:
        if identity.blueprint_index >= len(blueprint.members):
            raise ValueError("member blueprint_index is outside the persisted blueprint")


def _route_for(blueprint: ResolvedTeamBlueprint, issue_type: str):
    routes = tuple(route for route in blueprint.workflow.routes if route.issue_type == issue_type)
    if len(routes) != 1:
        raise ValueError("work item issue type must have one blueprint route")
    return routes[0]


def _validate_blueprint_work(
    state: _ScrumCollections, blueprint: ResolvedTeamBlueprint
) -> None:
    for work in state.work_items:
        route = _route_for(blueprint, work.issue_type)
        if work.current_status_key not in {step.status_key for step in route.steps}:
            raise ValueError("work current status must belong to its blueprint route")


def _status_for(blueprint: ResolvedTeamBlueprint, status_key: str):
    statuses = tuple(item for item in blueprint.workflow.statuses if item.key == status_key)
    if len(statuses) != 1:
        raise ValueError("visit status must exist in the persisted blueprint")
    return statuses[0]


def _validate_blueprint_visits(
    state: _ScrumCollections, blueprint: ResolvedTeamBlueprint
) -> None:
    work_items = {item.id: item for item in state.work_items}
    identities = {item.id: item for item in state.member_identities}
    for visit in state.status_visits:
        work = work_items[visit.work_item_id]
        route = _route_for(blueprint, work.issue_type)
        matches_step = any(
            (item.status_key, item.required_activity)
            == (visit.status_key, visit.activity_key)
            for item in route.steps
        )
        status = _status_for(blueprint, visit.status_key)
        if not matches_step:
            raise ValueError("visit activity must match the blueprint route step")
        if visit.activity_key is None:
            if visit.member_id is not None:
                raise ValueError("zero-touch visit must not have a member owner")
            continue
        if visit.activity_key not in status.activities:
            raise ValueError("visit activity must belong to the blueprint status")
        _validate_member_activity(visit, identities, blueprint)


def _validate_member_activity(
    visit: StatusVisitState,
    identities: dict[UUID, MemberIdentity],
    blueprint: ResolvedTeamBlueprint,
) -> None:
    if visit.member_id is None:
        return
    identity = identities[visit.member_id]
    member = blueprint.members[identity.blueprint_index]
    if visit.activity_key not in {item.activity for item in member.responsibilities}:
        raise ValueError("visit member must own the blueprint activity")


def _authenticated_sample_input(
    blueprint: ResolvedTeamBlueprint, work: WorkItemState, visit: StatusVisitState
) -> StatusVisitSampleInput:
    stream = DeterministicRandomStream(blueprint.seed, work.team_id, work.run_id)
    dwell = stream.draw(DecisionOccurrence(visit.id, DecisionType.STATUS_DWELL, 0), 0)
    touch = stream.draw(DecisionOccurrence(visit.id, DecisionType.STATUS_TOUCH, 0), 0)
    return StatusVisitSampleInput(blueprint, work, visit, dwell, touch)


def _authenticate_samples(
    state: _ScrumCollections, blueprint: ResolvedTeamBlueprint
) -> None:
    work_items = {item.id: item for item in state.work_items}
    visits = {item.id: item for item in state.status_visits}
    for sample in state.status_visit_samples:
        visit = visits[sample.visit_id]
        work = work_items[visit.work_item_id]
        sample.authenticate(_authenticated_sample_input(blueprint, work, visit))


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


def _validate_sample_cardinality(state: "_ScrumCollections") -> None:
    visit_ids = {visit.id for visit in state.status_visits}
    sample_visit_ids = {sample.visit_id for sample in state.status_visit_samples}
    if visit_ids != sample_visit_ids:
        raise ValueError("complete Scrum state requires exactly one sample per visit")


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

    def validate(self) -> None:
        _ScrumCollections.validate(self)
        _validate_member_references(self)
        _validate_work_references(self)
        _validate_counter_references(self)
        _validate_open_visit_status(self)
        _validate_sample_cardinality(self)

    @classmethod
    def from_write_set(cls, state: ScrumStateWriteSet) -> Self:
        if type(state) is not ScrumStateWriteSet:
            raise TypeError("state must be a ScrumStateWriteSet")
        state.validate()
        return cls(*state._collection_values())
