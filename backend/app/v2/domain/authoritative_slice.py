"""Immutable command values for one authoritative v2 tick slice."""

from datetime import date
from uuid import UUID

from app.v2.domain.deterministic_rng import (
    MAX_SAFE_INTEGER,
    DecisionOccurrence,
    DecisionType,
    item_rng_id,
    sprint_rng_id,
    visit_rng_id,
)
from app.v2.domain.immutable_value import ImmutableValue, immutable_dataclass
from app.v2.domain.live_slice import CommittedTickSlice, TickSliceCommit
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


def _validate_committed_live(live_slice: object) -> None:
    _require_exact(live_slice, CommittedTickSlice, "live_slice")
    _require_exact(live_slice.runtime, TeamRuntime, "live_slice runtime")
    for values, label in (
        (live_slice.activity, "activity"),
        (live_slice.ground_truth, "ground_truth"),
        (live_slice.projection_intents, "projection_intents"),
    ):
        if type(values) is not tuple:
            raise TypeError(f"{label} must be a tuple")


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
