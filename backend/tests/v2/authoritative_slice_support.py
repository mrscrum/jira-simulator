from dataclasses import dataclass, replace
from types import SimpleNamespace

from app.v2.domain.authoritative_slice import (
    AuthoritativeTickSliceCommit,
    EligibleNaturalDecisionClaim,
    SemanticCounterClaim,
)
from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    item_rng_id,
    member_rng_id,
)
from app.v2.domain.scrum_state import (
    MemberIdentity,
    ScrumStateWriteSet,
    SemanticCounter,
    SemanticCounterKind,
    SemanticCounterScope,
)
from tests.v2.live_slice_support import make_tick_commit
from tests.v2.scrum_state_support import (
    BUSINESS_DATE,
    ITEM_ID,
    RUN_ID,
    TEAM_ID,
    make_consumption,
    make_factor,
    make_member,
    make_overlay,
    make_sample,
    make_scope,
    make_sprint,
    make_visit,
    make_work_item,
)

BASE_MEMBER_ID = member_rng_id(TEAM_ID, 0)


def counter_scope(
    kind: SemanticCounterKind, scope_id, scope_key: str
) -> SemanticCounterScope:
    return SemanticCounterScope(kind, scope_id, scope_key)


def sprint_claim(expected_next: int = 0, count: int = 1) -> SemanticCounterClaim:
    scope = counter_scope(SemanticCounterKind.SPRINT_ORDINAL, TEAM_ID, "SCRUM")
    return SemanticCounterClaim(scope, expected_next, count)


def item_claim(expected_next: int = 1, count: int = 1) -> SemanticCounterClaim:
    scope = counter_scope(
        SemanticCounterKind.ITEM_SEQUENCE,
        TEAM_ID,
        CreationKind.INITIAL_BACKLOG.value,
    )
    return SemanticCounterClaim(scope, expected_next, count)


def visit_claim(expected_next: int = 0, count: int = 1) -> SemanticCounterClaim:
    scope = counter_scope(SemanticCounterKind.VISIT_ORDINAL, ITEM_ID, "VISIT")
    return SemanticCounterClaim(scope, expected_next, count)


def natural_counter_claim(
    expected_next: int = 0, count: int = 1
) -> SemanticCounterClaim:
    scope = counter_scope(
        SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
        ITEM_ID,
        DecisionType.RISK_CANCELLATION_OUTCOME.value,
    )
    return SemanticCounterClaim(scope, expected_next, count)


def member_natural_counter_claim(
    expected_next: int = 0, count: int = 1
) -> SemanticCounterClaim:
    scope = counter_scope(
        SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
        BASE_MEMBER_ID,
        DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME.value,
    )
    return SemanticCounterClaim(scope, expected_next, count)


def eligible_claim(occurrence: int = 0) -> EligibleNaturalDecisionClaim:
    decision = DecisionOccurrence(
        ITEM_ID,
        DecisionType.RISK_CANCELLATION_OUTCOME,
        occurrence,
    )
    return EligibleNaturalDecisionClaim(decision, BUSINESS_DATE)


def member_eligible_claim(occurrence: int = 0) -> EligibleNaturalDecisionClaim:
    decision = DecisionOccurrence(
        BASE_MEMBER_ID,
        DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME,
        occurrence,
    )
    return EligibleNaturalDecisionClaim(decision, BUSINESS_DATE)


def baseline_write_set() -> ScrumStateWriteSet:
    member = MemberIdentity(BASE_MEMBER_ID, TEAM_ID, 0)
    counters = (
        SemanticCounter(TEAM_ID, RUN_ID, sprint_claim().scope, 0),
        SemanticCounter(TEAM_ID, RUN_ID, item_claim().scope, 1),
        SemanticCounter(TEAM_ID, RUN_ID, visit_claim().scope, 0),
        SemanticCounter(TEAM_ID, RUN_ID, natural_counter_claim().scope, 0),
        SemanticCounter(TEAM_ID, RUN_ID, member_natural_counter_claim().scope, 0),
    )
    return ScrumStateWriteSet(
        member_identities=(member,),
        work_items=(make_work_item(),),
        semantic_counters=counters,
    )


def new_work_item():
    return replace(
        make_work_item(),
        id=item_rng_id(TEAM_ID, CreationKind.INITIAL_BACKLOG, 1),
        creation_sequence=1,
    )


def new_work_factor():
    item = new_work_item()
    factor = make_factor()
    identity = semantic_uuid(f"factor/{item.id}/{factor.kind.value}")
    return replace(factor, id=identity, work_item_id=item.id)


def new_sprint_scope():
    item = new_work_item()
    scope = make_scope()
    identity = semantic_uuid(f"sprint-scope/{scope.sprint_id}/{item.id}")
    return replace(scope, id=identity, work_item_id=item.id)


def authoritative_write_set() -> ScrumStateWriteSet:
    return ScrumStateWriteSet(
        member_identities=(make_member(),),
        member_availability_overlays=(make_overlay(),),
        member_business_date_consumption=(make_consumption(),),
        work_items=(new_work_item(),),
        work_item_factors=(new_work_factor(),),
        sprints=(make_sprint(),),
        sprint_scope=(new_sprint_scope(),),
        status_visits=(make_visit(),),
        status_visit_samples=(make_sample(),),
    )


def allocation_claims() -> tuple[SemanticCounterClaim, ...]:
    return (
        sprint_claim(),
        item_claim(),
        visit_claim(),
        natural_counter_claim(),
        member_natural_counter_claim(),
    )


@dataclass(frozen=True)
class AuthoritativeCommandSpec:
    aggregate: object
    expected_runtime_version: int = 0
    label: str = "authoritative"
    state: ScrumStateWriteSet | None = None
    counter_claims: tuple[SemanticCounterClaim, ...] | None = None
    natural_claims: tuple[EligibleNaturalDecisionClaim, ...] | None = None


def make_authoritative_command(spec: AuthoritativeCommandSpec) -> AuthoritativeTickSliceCommit:
    live_slice = make_tick_commit(
        spec.aggregate,
        spec.expected_runtime_version,
        spec.label,
    )
    return AuthoritativeTickSliceCommit(
        live_slice,
        spec.state if spec.state is not None else authoritative_write_set(),
        spec.counter_claims if spec.counter_claims is not None else allocation_claims(),
        spec.natural_claims
        if spec.natural_claims is not None
        else (eligible_claim(), member_eligible_claim()),
    )


def aggregate_stub():
    return SimpleNamespace(
        team=SimpleNamespace(id=TEAM_ID),
        run=SimpleNamespace(id=RUN_ID),
    )
