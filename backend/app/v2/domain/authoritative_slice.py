"""Immutable command values for one authoritative v2 tick slice."""

from datetime import date, datetime
from uuid import UUID

from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.deterministic_rng import (
    MAX_SAFE_INTEGER,
    DecisionOccurrence,
    DecisionType,
    item_rng_id,
    sprint_rng_id,
    visit_rng_id,
)
from app.v2.domain.immutable_value import ImmutableValue, immutable_dataclass
from app.v2.domain.live_slice import (
    ActivityEvent,
    CommittedTickSlice,
    GroundTruthRecord,
    ProjectionIntent,
    TickSliceCommit,
)
from app.v2.domain.scrum_state import (
    NATURAL_OWNER_DECISIONS,
    NaturalDecisionEvaluation,
    ScrumStateSnapshot,
    ScrumStateWriteSet,
    SemanticCounter,
    SemanticCounterKind,
    SemanticCounterScope,
)
from app.v2.domain.team_runtime import TeamRuntime


def _require_exact(value: object, value_type: type, label: str) -> None:
    if type(value) is not value_type:
        raise TypeError(f"{label} must be an exact {value_type.__name__}")


def _require_safe_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if not 0 <= value <= MAX_SAFE_INTEGER:
        raise ValueError(f"{label} must be in the safe integer domain")
    return value


def _require_nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _require_uuid(value: object, label: str) -> UUID:
    if type(value) is not UUID:
        raise TypeError(f"{label} must be a UUID")
    return value


def _require_text(value: object, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be a string")
    if not value or value.strip() != value:
        raise ValueError(f"{label} must be non-empty canonical text")
    return value


def _require_aware(value: object, label: str) -> datetime:
    if type(value) is not datetime:
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be aware")
    return value


def _require_tuple(values: object, value_type: type, label: str) -> tuple:
    if type(values) is not tuple:
        raise TypeError(f"{label} must be a tuple")
    for value in values:
        _require_exact(value, value_type, label)
        value.validate()
    return values


@immutable_dataclass
class SemanticCounterClaim(ImmutableValue):
    scope: SemanticCounterScope
    expected_next: int
    count: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_exact(self.scope, SemanticCounterScope, "scope")
        self.scope.validate()
        start = _require_safe_integer(self.expected_next, "expected_next")
        count = _require_safe_integer(self.count, "count")
        if count == 0:
            raise ValueError("count must be positive")
        if start + count - 1 > MAX_SAFE_INTEGER:
            raise ValueError("claimed ordinal range exceeds the safe integer domain")


@immutable_dataclass
class EligibleNaturalDecisionClaim(ImmutableValue):
    decision: DecisionOccurrence
    business_date: date

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_decision(self.decision)
        if self.decision.decision_type not in NATURAL_OWNER_DECISIONS:
            raise ValueError("decision type is not a supported natural decision")
        if type(self.business_date) is not date:
            raise TypeError("business_date must be an exact date")


def _validate_decision(decision: object) -> None:
    _require_exact(decision, DecisionOccurrence, "decision")
    if type(decision.entity_id) is not UUID:
        raise TypeError("decision entity_id must be a UUID")
    _require_exact(decision.decision_type, DecisionType, "decision type")
    _require_safe_integer(decision.occurrence, "decision occurrence")
    DecisionOccurrence(
        decision.entity_id,
        decision.decision_type,
        decision.occurrence,
    )


@immutable_dataclass
class AuthoritativeTickSliceCommit(ImmutableValue):
    live_slice: TickSliceCommit
    state: ScrumStateWriteSet
    counter_claims: tuple[SemanticCounterClaim, ...]
    natural_decision_claims: tuple[EligibleNaturalDecisionClaim, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_exact(self.live_slice, TickSliceCommit, "live_slice")
        self.live_slice.validate()
        _require_exact(self.state, ScrumStateWriteSet, "state")
        self.state.validate()
        claims = _require_tuple(self.counter_claims, SemanticCounterClaim, "counter_claims")
        natural = _require_tuple(
            self.natural_decision_claims,
            EligibleNaturalDecisionClaim,
            "natural_decision_claims",
        )
        _validate_coordinates(self.state, self.live_slice.team_id, self.live_slice.run_id)
        _validate_claim_bindings(self.state, claims, natural)


@immutable_dataclass
class CommittedAuthoritativeTickSlice(ImmutableValue):
    live_slice: CommittedTickSlice
    state: ScrumStateSnapshot
    counters: tuple[SemanticCounter, ...]
    natural_decision_evaluations: tuple[NaturalDecisionEvaluation, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_committed_live(self.live_slice)
        _require_exact(self.state, ScrumStateSnapshot, "state")
        self.state.validate()
        counters = _require_tuple(self.counters, SemanticCounter, "counters")
        evaluations = _require_tuple(
            self.natural_decision_evaluations,
            NaturalDecisionEvaluation,
            "natural_decision_evaluations",
        )
        runtime = self.live_slice.runtime
        _validate_coordinates(self.state, runtime.team_id, runtime.run_id)
        _validate_result_coordinates(counters, evaluations, runtime)
        _validate_snapshot_members(counters, self.state.semantic_counters, "counter")
        _validate_snapshot_members(
            evaluations,
            self.state.natural_decision_evaluations,
            "natural evaluation",
        )


def _validate_committed_live(live_slice: object) -> None:
    _require_exact(live_slice, CommittedTickSlice, "live_slice")
    runtime = live_slice.runtime
    _validate_runtime(runtime)
    for values, specification in (
        (live_slice.activity, (ActivityEvent, "activity")),
        (live_slice.ground_truth, (GroundTruthRecord, "ground_truth")),
        (live_slice.projection_intents, (ProjectionIntent, "projection_intents")),
    ):
        _validate_committed_collection(values, specification, runtime)


def _validate_runtime(runtime: object) -> None:
    _require_exact(runtime, TeamRuntime, "live_slice runtime")
    for name in ("id", "team_id", "run_id"):
        _require_uuid(getattr(runtime, name), f"runtime {name}")
    _require_nonnegative_integer(runtime.version, "runtime version")
    _require_text(runtime.state, "runtime state")
    for name in ("simulation_time", "created_at", "updated_at"):
        _require_aware(getattr(runtime, name), f"runtime {name}")
    if runtime.next_wake_at is not None:
        _require_aware(runtime.next_wake_at, "runtime next_wake_at")
    if runtime.id != semantic_uuid(f"runtime/{runtime.team_id}"):
        raise ValueError("runtime id must match its semantic team coordinate")
    if runtime.updated_at < runtime.created_at:
        raise ValueError("runtime updated_at must not precede created_at")


def _validate_committed_collection(
    values: object, specification: tuple[type, str], runtime: TeamRuntime
) -> None:
    value_type, label = specification
    if type(values) is not tuple:
        raise TypeError(f"{label} must be a tuple")
    for value in values:
        _require_exact(value, value_type, label)
        value.validate()
        _validate_ledger_metadata(value, runtime)


def _validate_ledger_metadata(value: object, runtime: TeamRuntime) -> None:
    append_sequence = _require_nonnegative_integer(
        value.append_sequence, "append_sequence"
    )
    if append_sequence == 0:
        raise ValueError("append_sequence must be positive")
    _require_nonnegative_integer(value.transaction_sequence, "transaction_sequence")
    for name in ("team_id", "run_id", "commit_id"):
        _require_uuid(getattr(value, name), name)
    _require_aware(value.recorded_at, "recorded_at")
    if (value.team_id, value.run_id) != (runtime.team_id, runtime.run_id):
        raise ValueError("committed ledger row must match the runtime team/run")


def _validate_coordinates(
    state: ScrumStateWriteSet | ScrumStateSnapshot, team_id: UUID, run_id: UUID
) -> None:
    records = tuple(item for values in state._collection_values() for item in values)
    if any(item.team_id != team_id for item in records):
        raise ValueError("Scrum state rows must match the live-slice team/run")
    run_rows = tuple(item for item in records if hasattr(item, "run_id"))
    if any(item.run_id != run_id for item in run_rows):
        raise ValueError("Scrum state rows must match the live-slice team/run")


def _validate_result_coordinates(
    counters: tuple[SemanticCounter, ...],
    evaluations: tuple[NaturalDecisionEvaluation, ...],
    runtime: TeamRuntime,
) -> None:
    records = (*counters, *evaluations)
    if any((item.team_id, item.run_id) != (runtime.team_id, runtime.run_id) for item in records):
        raise ValueError("committed claims must match the committed runtime")


def _validate_snapshot_members(
    returned: tuple[object, ...], stored: tuple[object, ...], label: str
) -> None:
    identities = tuple(_result_identity(item) for item in returned)
    if len(set(identities)) != len(identities):
        raise ValueError(f"returned {label} values must be unique snapshot members")
    stored_by_identity = {_result_identity(item): item for item in stored}
    returned_pairs = zip(identities, returned)
    if any(stored_by_identity.get(identity) != item for identity, item in returned_pairs):
        raise ValueError(f"returned {label} must be an exact snapshot member")


def _result_identity(value: object) -> object:
    if type(value) is SemanticCounter:
        return value.team_id, value.run_id, value.scope
    return value.id


def _validate_claim_bindings(
    state: ScrumStateWriteSet,
    claims: tuple[SemanticCounterClaim, ...],
    natural: tuple[EligibleNaturalDecisionClaim, ...],
) -> None:
    if state.semantic_counters or state.natural_decision_evaluations:
        raise ValueError("counter and evaluation rows are owned by claims")
    claim_map = _unique_claims(claims)
    natural_map = _unique_natural_claims(natural)
    natural_scopes = tuple(_natural_scope(item) for item in natural)
    if len(set(natural_scopes)) != len(natural_scopes):
        raise ValueError("natural counter scopes must be unique per command")
    _validate_natural_bindings(claim_map, natural_map)
    _validate_visible_natural_owners(state, natural)
    claimed_natural = {
        scope
        for scope in claim_map
        if scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE
    }
    if claimed_natural != set(natural_scopes):
        raise ValueError("missing, extra, or unrelated natural counter claim")
    _validate_allocation_ranges(state, claim_map)


def _unique_claims(
    claims: tuple[SemanticCounterClaim, ...],
) -> dict[SemanticCounterScope, SemanticCounterClaim]:
    result = {claim.scope: claim for claim in claims}
    if len(result) != len(claims):
        raise ValueError("counter claims must use unique semantic scopes")
    return result


def _unique_natural_claims(
    claims: tuple[EligibleNaturalDecisionClaim, ...],
) -> dict[tuple[DecisionType, UUID, date], EligibleNaturalDecisionClaim]:
    result = {
        (claim.decision.decision_type, claim.decision.entity_id, claim.business_date): claim
        for claim in claims
    }
    if len(result) != len(claims):
        raise ValueError("natural decision claims must use unique eligibility keys")
    return result


def _natural_scope(claim: EligibleNaturalDecisionClaim) -> SemanticCounterScope:
    decision = claim.decision
    return SemanticCounterScope(
        SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
        decision.entity_id,
        decision.decision_type.value,
    )


def _validate_allocation_ranges(
    state: ScrumStateWriteSet,
    claims: dict[SemanticCounterScope, SemanticCounterClaim],
) -> None:
    for scope, claim in claims.items():
        if scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE:
            continue
        coordinates = _coordinates_for_scope(state, scope)
        end = claim.expected_next + claim.count
        covered = tuple(
            value for value in sorted(coordinates) if claim.expected_next <= value < end
        )
        is_contiguous = all(
            value == claim.expected_next + offset for offset, value in enumerate(covered)
        )
        if len(covered) != claim.count or not is_contiguous:
            raise ValueError("allocated coordinates must equal one contiguous claimed range")
        _validate_allocated_ids(state, scope, claim)


def _coordinates_for_scope(
    state: ScrumStateWriteSet, scope: SemanticCounterScope
) -> tuple[int, ...]:
    if scope.kind is SemanticCounterKind.SPRINT_ORDINAL:
        return tuple(item.ordinal for item in state.sprints if item.team_id == scope.scope_id)
    if scope.kind is SemanticCounterKind.ITEM_SEQUENCE:
        return tuple(
            item.creation_sequence
            for item in state.work_items
            if item.team_id == scope.scope_id and item.creation_kind.value == scope.scope_key
        )
    return tuple(
        item.ordinal for item in state.status_visits if item.work_item_id == scope.scope_id
    )


def _validate_allocated_ids(
    state: ScrumStateWriteSet,
    scope: SemanticCounterScope,
    claim: SemanticCounterClaim,
) -> None:
    end = claim.expected_next + claim.count
    if scope.kind is SemanticCounterKind.SPRINT_ORDINAL:
        pairs = (
            (item.id, sprint_rng_id(item.team_id, item.ordinal))
            for item in state.sprints
            if item.team_id == scope.scope_id and claim.expected_next <= item.ordinal < end
        )
    elif scope.kind is SemanticCounterKind.ITEM_SEQUENCE:
        pairs = (
            (item.id, item_rng_id(item.team_id, item.creation_kind, item.creation_sequence))
            for item in state.work_items
            if item.team_id == scope.scope_id
            and item.creation_kind.value == scope.scope_key
            and claim.expected_next <= item.creation_sequence < end
        )
    else:
        pairs = (
            (item.id, visit_rng_id(item.work_item_id, item.ordinal))
            for item in state.status_visits
            if item.work_item_id == scope.scope_id and claim.expected_next <= item.ordinal < end
        )
    if any(actual != expected for actual, expected in pairs):
        raise ValueError("allocated row has the wrong semantic identity")


def _validate_natural_bindings(
    claims: dict[SemanticCounterScope, SemanticCounterClaim],
    natural: dict[tuple[DecisionType, UUID, date], EligibleNaturalDecisionClaim],
) -> None:
    for eligible in natural.values():
        claim = claims.get(_natural_scope(eligible))
        if claim is None:
            raise ValueError("eligible decision requires one matching natural counter claim")
        if claim.count != 1:
            raise ValueError("natural counter claim count must be exactly one")
        if eligible.decision.occurrence != claim.expected_next:
            raise ValueError("natural decision occurrence must equal counter expected_next")


def _validate_visible_natural_owners(
    state: ScrumStateWriteSet,
    natural: tuple[EligibleNaturalDecisionClaim, ...],
) -> None:
    member_ids = {item.id for item in state.member_identities}
    work_ids = {item.id for item in state.work_items}
    for eligible in natural:
        decision = eligible.decision
        wrong_ids = (
            member_ids
            if decision.decision_type is DecisionType.RISK_CANCELLATION_OUTCOME
            else work_ids
        )
        if decision.entity_id in wrong_ids:
            raise ValueError("natural decision is visibly bound to the wrong owner kind")
