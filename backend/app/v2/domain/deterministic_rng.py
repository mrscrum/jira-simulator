"""Stateless semantic identities and deterministic HMAC-U53 decision draws."""

import hashlib
import hmac
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.v2.domain.canonical_json import canonical_json, semantic_uuid

ALGORITHM_ID = "HMAC_SHA256_U53_V1"
BLUEPRINT_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
HMAC_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
U53_BIT_COUNT = 53
DISCARDED_LOW_BITS = 11
U53_DENOMINATOR = 1 << U53_BIT_COUNT
CANONICAL_DECISION_KEYS = frozenset(
    {
        "algorithm",
        "team_id",
        "run_id",
        "entity_id",
        "decision_type",
        "occurrence",
        "draw_index",
    }
)


class CreationKind(StrEnum):
    INITIAL_BACKLOG = "INITIAL_BACKLOG"
    SCRUM_REPLENISHMENT = "SCRUM_REPLENISHMENT"
    KANBAN_ARRIVAL = "KANBAN_ARRIVAL"
    AGENT_CREATED = "AGENT_CREATED"
    JIRA_IMPORTED = "JIRA_IMPORTED"


class DecisionType(StrEnum):
    BACKLOG_ISSUE_TYPE = "BACKLOG_ISSUE_TYPE"
    BACKLOG_STORY_POINTS = "BACKLOG_STORY_POINTS"
    BACKLOG_PRIORITY = "BACKLOG_PRIORITY"
    ITEM_DESCRIPTION_QUALITY = "ITEM_DESCRIPTION_QUALITY"
    ITEM_LATENT_COMPLEXITY = "ITEM_LATENT_COMPLEXITY"
    STATUS_DWELL = "STATUS_DWELL"
    STATUS_TOUCH = "STATUS_TOUCH"
    SCRUM_CAPACITY_TARGET = "SCRUM_CAPACITY_TARGET"
    RISK_EXTERNAL_DEPENDENCY_OUTCOME = "RISK_EXTERNAL_DEPENDENCY_OUTCOME"
    RISK_EXTERNAL_DEPENDENCY_DURATION = "RISK_EXTERNAL_DEPENDENCY_DURATION"
    RISK_CANCELLATION_OUTCOME = "RISK_CANCELLATION_OUTCOME"
    RISK_REVIEW_REJECTION_OUTCOME = "RISK_REVIEW_REJECTION_OUTCOME"
    RISK_REWORK_DURATION = "RISK_REWORK_DURATION"
    RISK_MEMBER_UNAVAILABLE_OUTCOME = "RISK_MEMBER_UNAVAILABLE_OUTCOME"
    RISK_MEMBER_UNAVAILABLE_DURATION = "RISK_MEMBER_UNAVAILABLE_DURATION"
    FORCED_REWORK_DURATION = "FORCED_REWORK_DURATION"
    KANBAN_ARRIVAL_GAP = "KANBAN_ARRIVAL_GAP"
    KANBAN_CLASS_OF_SERVICE = "KANBAN_CLASS_OF_SERVICE"


def _require_uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError(f"{label} must be a UUID")
    return value


def _require_non_negative_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _ordinal_uuid(prefix: str, parent_id: UUID, ordinal: int) -> UUID:
    parent = _require_uuid(parent_id, f"{prefix} parent")
    position = _require_non_negative_integer(ordinal, "ordinal")
    return semantic_uuid(f"{prefix}/{parent}/{position}")


def team_rng_id(blueprint_sha256: str) -> UUID:
    if not isinstance(blueprint_sha256, str):
        raise TypeError("blueprint_sha256 must be a string")
    if BLUEPRINT_DIGEST_PATTERN.fullmatch(blueprint_sha256) is None:
        raise ValueError("blueprint_sha256 must be 64 lower-case hexadecimal characters")
    return semantic_uuid(f"team/{blueprint_sha256}")


def run_rng_id(team_id: UUID, ordinal: int) -> UUID:
    return _ordinal_uuid("run", team_id, ordinal)


def member_rng_id(team_id: UUID, index: int) -> UUID:
    return _ordinal_uuid("member", team_id, index)


def sprint_rng_id(team_id: UUID, ordinal: int) -> UUID:
    return _ordinal_uuid("sprint", team_id, ordinal)


def item_rng_id(team_id: UUID, creation_kind: CreationKind, sequence: int) -> UUID:
    team = _require_uuid(team_id, "item team")
    if not isinstance(creation_kind, CreationKind):
        raise TypeError("creation_kind must be a CreationKind")
    position = _require_non_negative_integer(sequence, "sequence")
    return semantic_uuid(f"item/{team}/{creation_kind.value}/{position}")


def visit_rng_id(item_id: UUID, ordinal: int) -> UUID:
    return _ordinal_uuid("visit", item_id, ordinal)


def dependency_rng_id(visit_id: UUID, ordinal: int) -> UUID:
    return _ordinal_uuid("dependency", visit_id, ordinal)


def rework_rng_id(item_id: UUID, ordinal: int) -> UUID:
    return _ordinal_uuid("rework", item_id, ordinal)


def _entity_text(entity_id: UUID | str) -> str:
    if isinstance(entity_id, UUID):
        return str(entity_id)
    if not isinstance(entity_id, str):
        raise TypeError("entity_id must be a UUID or catalog key")
    if not entity_id or entity_id != entity_id.strip():
        raise ValueError("catalog entity_id must be non-empty and trimmed")
    return entity_id


@dataclass(frozen=True)
class DecisionOccurrence:
    entity_id: UUID | str
    decision_type: DecisionType
    occurrence: int

    def __post_init__(self) -> None:
        _entity_text(self.entity_id)
        if not isinstance(self.decision_type, DecisionType):
            raise TypeError("decision_type must be a DecisionType")
        _require_non_negative_integer(self.occurrence, "occurrence")


def _canonical_message(
    stream: "DeterministicRandomStream", decision: DecisionOccurrence, draw_index: int
) -> bytes:
    document = {
        "algorithm": ALGORITHM_ID,
        "team_id": str(stream.team_id),
        "run_id": str(stream.run_id),
        "entity_id": _entity_text(decision.entity_id),
        "decision_type": decision.decision_type.value,
        "occurrence": decision.occurrence,
        "draw_index": draw_index,
    }
    return canonical_json(document).encode("utf-8")


def _root_key(root_seed: str) -> bytes:
    normalized_seed = unicodedata.normalize("NFC", root_seed)
    return hashlib.sha256(normalized_seed.encode("utf-8")).digest()


def _hmac_digest(root_seed: str, message: bytes) -> bytes:
    return hmac.new(_root_key(root_seed), message, hashlib.sha256).digest()


def _high_u53(digest: bytes) -> int:
    first_word = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return first_word >> DISCARDED_LOW_BITS


def _canonical_uuid_text(value: object, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError(f"{label} must be canonical UUID text") from error
    if str(parsed) != value:
        raise ValueError(f"{label} must be lower-case hyphenated UUID text")


def _validate_canonical_message(
    message: bytes, decision: DecisionOccurrence, draw_index: int
) -> None:
    try:
        document = json.loads(message.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("canonical_message must be valid UTF-8 JSON") from error
    if not isinstance(document, dict) or frozenset(document) != CANONICAL_DECISION_KEYS:
        raise ValueError("canonical_message has the wrong decision schema")
    if canonical_json(document).encode("utf-8") != message:
        raise ValueError("canonical_message must use canonical JSON")
    _canonical_uuid_text(document["team_id"], "team_id")
    _canonical_uuid_text(document["run_id"], "run_id")
    expected = (ALGORITHM_ID, _entity_text(decision.entity_id), decision.decision_type.value)
    if (document["algorithm"], document["entity_id"], document["decision_type"]) != expected:
        raise ValueError("canonical_message does not match the decision")
    if (document["occurrence"], document["draw_index"]) != (decision.occurrence, draw_index):
        raise ValueError("canonical_message does not match the decision coordinate")


@dataclass(frozen=True)
class UniformDraw:
    algorithm: str
    decision: DecisionOccurrence
    draw_index: int
    canonical_message: bytes
    hmac_sha256: str
    u53_integer: int
    unit_value: float

    def __post_init__(self) -> None:
        if self.algorithm != ALGORITHM_ID:
            raise ValueError("algorithm must be HMAC_SHA256_U53_V1")
        if not isinstance(self.decision, DecisionOccurrence):
            raise TypeError("decision must be a DecisionOccurrence")
        _require_non_negative_integer(self.draw_index, "draw_index")
        if not isinstance(self.canonical_message, bytes):
            raise TypeError("canonical_message must be bytes")
        _validate_canonical_message(self.canonical_message, self.decision, self.draw_index)
        self._validate_digest_and_value()

    def _validate_digest_and_value(self) -> None:
        if not isinstance(self.hmac_sha256, str):
            raise TypeError("hmac_sha256 must be a string")
        if HMAC_DIGEST_PATTERN.fullmatch(self.hmac_sha256) is None:
            raise ValueError("hmac_sha256 must be 64 lower-case hexadecimal characters")
        expected_integer = _high_u53(bytes.fromhex(self.hmac_sha256))
        if type(self.u53_integer) is not int or self.u53_integer != expected_integer:
            raise ValueError("u53_integer does not match the HMAC digest")
        expected_value = self.u53_integer / U53_DENOMINATOR
        if type(self.unit_value) is not float or not math.isfinite(self.unit_value):
            raise TypeError("unit_value must be a finite float")
        if self.unit_value != expected_value:
            raise ValueError("unit_value does not match u53_integer")


@dataclass(frozen=True)
class DeterministicRandomStream:
    root_seed: str
    team_id: UUID
    run_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.root_seed, str):
            raise TypeError("root_seed must be a string")
        if not self.root_seed:
            raise ValueError("root_seed must not be empty")
        _require_uuid(self.team_id, "team_id")
        _require_uuid(self.run_id, "run_id")

    def draw(self, decision: DecisionOccurrence, draw_index: int = 0) -> UniformDraw:
        if not isinstance(decision, DecisionOccurrence):
            raise TypeError("decision must be a DecisionOccurrence")
        index = _require_non_negative_integer(draw_index, "draw_index")
        message = _canonical_message(self, decision, index)
        digest = _hmac_digest(self.root_seed, message)
        integer = _high_u53(digest)
        return UniformDraw(
            ALGORITHM_ID,
            decision,
            index,
            message,
            digest.hex(),
            integer,
            integer / U53_DENOMINATOR,
        )
