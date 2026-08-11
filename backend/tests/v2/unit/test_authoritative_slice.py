import copy
import pickle
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.v2.domain.authoritative_slice import (
    AuthoritativeTickSliceCommit,
    CommittedAuthoritativeTickSlice,
    EligibleNaturalDecisionClaim,
    SemanticCounterClaim,
)
from app.v2.domain.deterministic_rng import (
    MAX_SAFE_INTEGER,
    DecisionOccurrence,
    DecisionType,
    item_rng_id,
    sprint_rng_id,
    visit_rng_id,
)
from app.v2.domain.live_slice import CommittedTickSlice
from app.v2.domain.scrum_state import (
    ScrumStateSnapshot,
    ScrumStateWriteSet,
    SemanticCounter,
    SprintLifecycle,
)
from app.v2.domain.team_runtime import TeamRuntime
from tests.v2.authoritative_slice_support import (
    aggregate_stub,
    allocation_claims,
    authoritative_write_set,
    eligible_claim,
    item_claim,
    member_eligible_claim,
    natural_counter_claim,
    new_work_item,
    sprint_claim,
    visit_claim,
)
from tests.v2.live_slice_support import make_tick_commit
from tests.v2.scrum_state_support import (
    BUSINESS_DATE,
    ITEM_ID,
    LATER,
    NOW,
    RUN_ID,
    TEAM_ID,
    make_consumption,
    make_evaluation,
    make_sprint,
    make_visit,
    make_work_item,
)


def _live_slice(label: str = "authoritative"):
    return make_tick_commit(aggregate_stub(), 0, label)


def _command() -> AuthoritativeTickSliceCommit:
    return AuthoritativeTickSliceCommit(
        _live_slice(),
        authoritative_write_set(),
        allocation_claims(),
        (eligible_claim(), member_eligible_claim()),
    )


def _committed_live_slice() -> CommittedTickSlice:
    runtime = TeamRuntime(
        UUID(int=7),
        TEAM_ID,
        RUN_ID,
        1,
        "RUNNING",
        NOW,
        LATER,
        NOW,
        NOW,
    )
    return CommittedTickSlice(runtime, (), (), ())


@pytest.mark.parametrize(
    "expected,count,error",
    [
        (True, 1, TypeError),
        (-1, 1, ValueError),
        (MAX_SAFE_INTEGER + 1, 1, ValueError),
        (0, False, TypeError),
        (0, 0, ValueError),
        (0, -1, ValueError),
        (0, MAX_SAFE_INTEGER + 1, ValueError),
        (MAX_SAFE_INTEGER, 2, ValueError),
    ],
)
def test_counter_claim_rejects_non_safe_or_overflowing_ranges(expected, count, error):
    with pytest.raises(error):
        sprint_claim(expected, count)


def test_counter_claim_accepts_the_exhausted_sentinel_after_last_safe_ordinal():
    claim = sprint_claim(MAX_SAFE_INTEGER, 1)

    assert claim.expected_next + claim.count == 2**53


@pytest.mark.parametrize(
    "decision",
    [
        DecisionOccurrence(ITEM_ID, DecisionType.RISK_REVIEW_REJECTION_OUTCOME, 0),
        DecisionOccurrence(ITEM_ID, DecisionType.RISK_MEMBER_UNAVAILABLE_DURATION, 1),
    ],
)
def test_eligible_claim_rejects_unsupported_natural_decision_types(decision):
    with pytest.raises(ValueError, match="supported natural"):
        EligibleNaturalDecisionClaim(decision, BUSINESS_DATE)


def test_eligible_claim_requires_an_exact_business_date_and_decision_value():
    decision = DecisionOccurrence(ITEM_ID, DecisionType.RISK_CANCELLATION_OUTCOME, 0)

    with pytest.raises(TypeError):
        EligibleNaturalDecisionClaim(decision, datetime(2026, 8, 10))
    with pytest.raises(TypeError):
        EligibleNaturalDecisionClaim(object(), BUSINESS_DATE)


@pytest.mark.parametrize(
    "change",
    [
        {"live_slice": object()},
        {"state": object()},
        {"counter_claims": [sprint_claim()]},
        {"natural_decision_claims": [eligible_claim()]},
        {"counter_claims": (sprint_claim(), sprint_claim())},
        {"natural_decision_claims": (eligible_claim(), eligible_claim())},
    ],
)
def test_authoritative_command_revalidates_exact_nested_types_and_uniqueness(change):
    values = {
        "live_slice": _live_slice(),
        "state": authoritative_write_set(),
        "counter_claims": allocation_claims(),
        "natural_decision_claims": (eligible_claim(), member_eligible_claim()),
    }

    with pytest.raises((TypeError, ValueError)):
        AuthoritativeTickSliceCommit(**(values | change))


@pytest.mark.parametrize("field_name", ["team_id", "run_id"])
def test_authoritative_command_rejects_wrong_team_or_run_before_persistence(field_name):
    consumption = replace(make_consumption(), **{field_name: uuid4()})
    state = ScrumStateWriteSet(member_business_date_consumption=(consumption,))

    with pytest.raises(ValueError, match="team/run"):
        AuthoritativeTickSliceCommit(_live_slice(), state, (), ())


@pytest.mark.parametrize(
    "state",
    [
        ScrumStateWriteSet(
            semantic_counters=(
                SemanticCounter(TEAM_ID, RUN_ID, sprint_claim().scope, 1),
            )
        ),
        ScrumStateWriteSet(
            natural_decision_evaluations=(make_evaluation(),)
        ),
    ],
)
def test_authoritative_command_rejects_counter_and_evaluation_rows_owned_by_claims(state):

    with pytest.raises(ValueError, match="claims"):
        AuthoritativeTickSliceCommit(_live_slice(), state, (sprint_claim(),), ())


def test_overlapping_claims_for_the_same_scope_are_rejected():
    with pytest.raises(ValueError, match="unique semantic scopes"):
        AuthoritativeTickSliceCommit(
            _live_slice(),
            ScrumStateWriteSet(sprints=(make_sprint(),)),
            (sprint_claim(0, 1), sprint_claim(1, 1)),
            (),
        )


def test_claim_ranges_cross_bind_contiguous_coordinates_and_semantic_ids():
    second = replace(
        make_sprint(),
        id=sprint_rng_id(TEAM_ID, 2),
        ordinal=2,
        lifecycle=SprintLifecycle.PLANNED,
        observed_start_at=None,
    )
    state = ScrumStateWriteSet(sprints=(make_sprint(), second))

    with pytest.raises(ValueError, match="contiguous"):
        AuthoritativeTickSliceCommit(_live_slice(), state, (sprint_claim(0, 2),), ())

    forged = make_sprint()
    object.__setattr__(forged, "id", UUID(int=1))
    unsafe_state = object.__new__(ScrumStateWriteSet)
    for field_name in ScrumStateWriteSet.__dataclass_fields__:
        object.__setattr__(
            unsafe_state,
            field_name,
            (forged,) if field_name == "sprints" else (),
        )
    with pytest.raises(ValueError, match="semantic"):
        AuthoritativeTickSliceCommit(_live_slice(), unsafe_state, (sprint_claim(),), ())


@pytest.mark.parametrize(
    "state,claim",
    [
        (ScrumStateWriteSet(sprints=(make_sprint(),)), sprint_claim(1)),
        (ScrumStateWriteSet(work_items=(new_work_item(),)), item_claim(2)),
        (ScrumStateWriteSet(status_visits=(make_visit(),)), visit_claim(1)),
    ],
)
def test_each_allocated_coordinate_must_equal_its_claimed_range(state, claim):
    with pytest.raises(ValueError, match="claim"):
        AuthoritativeTickSliceCommit(_live_slice(), state, (claim,), ())


def test_item_and_visit_claim_ids_are_derived_from_their_exact_coordinates():
    work = replace(
        new_work_item(),
        id=item_rng_id(TEAM_ID, new_work_item().creation_kind, 7),
        creation_sequence=7,
    )
    visit = replace(
        make_visit(),
        id=visit_rng_id(ITEM_ID, 7),
        ordinal=7,
    )

    with pytest.raises(ValueError, match="claim"):
        AuthoritativeTickSliceCommit(
            _live_slice(), ScrumStateWriteSet(work_items=(work,)), (item_claim(),), ()
        )
    with pytest.raises(ValueError, match="claim"):
        AuthoritativeTickSliceCommit(
            _live_slice(), ScrumStateWriteSet(status_visits=(visit,)), (visit_claim(),), ()
        )


def test_extra_or_unrelated_ordinal_claim_rejects_before_persistence():
    state = ScrumStateWriteSet(member_business_date_consumption=(make_consumption(),))

    with pytest.raises(ValueError, match="claim"):
        AuthoritativeTickSliceCommit(_live_slice(), state, (sprint_claim(),), ())


def test_unclaimed_sparse_ordinal_rows_are_valid_existing_after_images():
    state = ScrumStateWriteSet(
        work_items=(make_work_item(),),
        sprints=(make_sprint(),),
        status_visits=(make_visit(),),
    )

    command = AuthoritativeTickSliceCommit(_live_slice(), state, (), ())

    assert command.state == state


def test_claimed_range_ignores_older_after_images_in_the_same_scope():
    state = ScrumStateWriteSet(work_items=(make_work_item(), new_work_item()))

    command = AuthoritativeTickSliceCommit(_live_slice(), state, (item_claim(),), ())

    assert command.counter_claims == (item_claim(),)


def test_natural_claim_requires_one_matching_counter_claim_at_expected_occurrence():
    with pytest.raises(ValueError, match="natural counter"):
        AuthoritativeTickSliceCommit(
            _live_slice(), ScrumStateWriteSet(), (), (eligible_claim(),)
        )
    with pytest.raises(ValueError, match="occurrence"):
        AuthoritativeTickSliceCommit(
            _live_slice(),
            ScrumStateWriteSet(),
            (natural_counter_claim(1),),
            (eligible_claim(0),),
        )
    with pytest.raises(ValueError, match="count"):
        AuthoritativeTickSliceCommit(
            _live_slice(),
            ScrumStateWriteSet(),
            (natural_counter_claim(0, 2),),
            (eligible_claim(0),),
        )


def test_empty_state_and_empty_claims_remain_a_valid_live_only_authoritative_slice():
    command = AuthoritativeTickSliceCommit(_live_slice(), ScrumStateWriteSet(), (), ())

    assert command.state == ScrumStateWriteSet()


def test_low_level_forged_nested_claim_is_revalidated_by_command():
    forged = object.__new__(SemanticCounterClaim)
    object.__setattr__(forged, "scope", sprint_claim().scope)
    object.__setattr__(forged, "expected_next", False)
    object.__setattr__(forged, "count", 1)

    with pytest.raises(TypeError):
        AuthoritativeTickSliceCommit(_live_slice(), ScrumStateWriteSet(), (forged,), ())


def test_low_level_forged_eligible_claim_is_revalidated_by_command():
    forged_decision = object.__new__(DecisionOccurrence)
    object.__setattr__(forged_decision, "entity_id", ITEM_ID)
    object.__setattr__(
        forged_decision,
        "decision_type",
        DecisionType.RISK_CANCELLATION_OUTCOME,
    )
    object.__setattr__(forged_decision, "occurrence", False)
    forged = object.__new__(EligibleNaturalDecisionClaim)
    object.__setattr__(forged, "decision", forged_decision)
    object.__setattr__(forged, "business_date", BUSINESS_DATE)

    with pytest.raises(TypeError):
        AuthoritativeTickSliceCommit(
            _live_slice(),
            ScrumStateWriteSet(),
            (natural_counter_claim(),),
            (forged,),
        )


def test_natural_claim_must_bind_the_same_decision_type_and_entity_scope():
    with pytest.raises(ValueError, match="claim"):
        AuthoritativeTickSliceCommit(
            _live_slice(),
            ScrumStateWriteSet(),
            (natural_counter_claim(),),
            (member_eligible_claim(),),
        )


def test_one_natural_counter_scope_cannot_claim_multiple_business_dates():
    second_date = replace(
        eligible_claim(),
        business_date=BUSINESS_DATE.replace(day=BUSINESS_DATE.day + 1),
    )

    with pytest.raises(ValueError, match="natural counter scope"):
        AuthoritativeTickSliceCommit(
            _live_slice(),
            ScrumStateWriteSet(),
            (natural_counter_claim(),),
            (eligible_claim(), second_date),
        )


def test_authoritative_values_are_slotted_frozen_copy_stable_and_reconstruction_safe():
    command = _command()
    result = CommittedAuthoritativeTickSlice(
        _committed_live_slice(),
        ScrumStateSnapshot(),
        (),
        (),
    )
    values = (sprint_claim(), eligible_claim(), command, result)
    for value in values:
        assert not hasattr(value, "__dict__")
        assert copy.copy(value) is value
        assert copy.deepcopy(value) is value
        with pytest.raises(FrozenInstanceError):
            value.__setattr__(next(iter(value.__dataclass_fields__)), None)
        with pytest.raises(TypeError):
            pickle.dumps(value)
    with pytest.raises(TypeError):
        CommittedAuthoritativeTickSlice(
            CommittedTickSlice(command.live_slice.runtime_after, (), (), ()),
            ScrumStateSnapshot(),
            (),
            (),
        )


@pytest.mark.parametrize(
    "change",
    [
        {"state": object()},
        {"counters": [object()]},
        {"counters": (object(),)},
        {"natural_decision_evaluations": (object(),)},
    ],
)
def test_committed_result_revalidates_exact_nested_types(change):
    values = {
        "live_slice": _committed_live_slice(),
        "state": ScrumStateSnapshot(),
        "counters": (),
        "natural_decision_evaluations": (),
    }

    with pytest.raises(TypeError):
        CommittedAuthoritativeTickSlice(**(values | change))


@pytest.mark.parametrize(
    "value_type",
    [
        SemanticCounterClaim,
        EligibleNaturalDecisionClaim,
        AuthoritativeTickSliceCommit,
        CommittedAuthoritativeTickSlice,
    ],
)
def test_authoritative_value_types_reject_runtime_subclassing(value_type):
    with pytest.raises(TypeError):

        class _Subclass(value_type):
            pass


def test_replacement_cannot_bypass_claim_or_command_validation():
    with pytest.raises(TypeError):
        replace(sprint_claim(), expected_next=False)
    with pytest.raises(ValueError, match="natural counter"):
        replace(
            _command(),
            counter_claims=(sprint_claim(), item_claim(), visit_claim()),
        )
