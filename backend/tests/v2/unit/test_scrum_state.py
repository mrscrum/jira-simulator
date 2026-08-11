import copy
import json
import pickle
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from functools import total_ordering
from uuid import UUID, uuid4

import pytest

from app.v2.domain import scrum_state as scrum_state_module
from app.v2.domain.canonical_json import canonical_json, canonical_sha256
from app.v2.domain.deterministic_rng import (
    MAX_SAFE_INTEGER,
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    DeterministicRandomStream,
    UniformDraw,
    item_rng_id,
    member_rng_id,
    run_rng_id,
    team_rng_id,
    visit_rng_id,
)
from app.v2.domain.scrum_state import (
    FactorKind,
    MemberAvailabilityOverlay,
    MemberBusinessDateConsumption,
    MemberIdentity,
    NaturalDecisionEvaluation,
    ScrumStateQuery,
    ScrumStateSnapshot,
    ScrumStateWriteSet,
    SemanticCounter,
    SemanticCounterKind,
    SemanticCounterScope,
    SimulatorRank,
    SprintLifecycle,
    SprintScopeEntry,
    SprintState,
    StatusVisitLifecycle,
    StatusVisitSample,
    StatusVisitSampleInput,
    StatusVisitState,
    WorkItemFactor,
    WorkItemLifecycle,
    WorkItemState,
    WorkPriority,
)
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint
from tests.v2.immutable_value_testing import tampered_pickle
from tests.v2.scrum_state_support import (
    BLUEPRINT,
    BLUEPRINT_JSON,
    BUSINESS_DATE,
    ITEM_ID,
    LATER,
    MEMBER_ID,
    NOW,
    RUN_ID,
    TEAM_ID,
    make_counter,
    make_evaluation,
    make_factor,
    make_member,
    make_overlay,
    make_sample,
    make_scope,
    make_sprint,
    make_visit,
    make_work_item,
    make_write_set,
    make_zero_touch_write_set,
    zero_touch_blueprint_json,
)

TASK5_VALUE_TYPES = (
    SimulatorRank,
    MemberIdentity,
    MemberAvailabilityOverlay,
    MemberBusinessDateConsumption,
    WorkItemState,
    WorkItemFactor,
    SprintState,
    SprintScopeEntry,
    StatusVisitState,
    StatusVisitSample,
    SemanticCounterScope,
    SemanticCounter,
    NaturalDecisionEvaluation,
    ScrumStateQuery,
    ScrumStateWriteSet,
    ScrumStateSnapshot,
)


class EqualitySpoofText(str):
    def __eq__(self, _other: object) -> bool:
        return True

    def __ne__(self, _other: object) -> bool:
        return False


class StatefulEqualityFloat(float):
    def __new__(cls, value: float):
        instance = super().__new__(cls, value)
        instance.forged_state = "untrusted"
        return instance

    def __eq__(self, _other: object) -> bool:
        return True

    def __ne__(self, _other: object) -> bool:
        return False


class ScalarUuid(UUID):
    pass


class ScalarInt(int):
    pass


class ScalarBytes(bytes):
    pass


NESTED_DRAW_FORGERIES = (
    "algorithm",
    "decision_entity",
    "decision_type",
    "decision_occurrence",
    "draw_index",
    "canonical_message",
    "hmac_low_bit",
    "u53_integer",
    "unit_value",
)
FACTORY_DRAW_FORGERIES = (
    "algorithm",
    "decision_entity",
    "canonical_message",
    "hmac_low_bit",
    "u53_integer",
    "unit_value",
)


@pytest.mark.parametrize(
    "enum_type,values",
    [
        (WorkItemLifecycle, ("BACKLOG", "ACTIVE", "DONE", "CANCELLED")),
        (SprintLifecycle, ("PLANNED", "ACTIVE", "COMPLETED")),
        (StatusVisitLifecycle, ("OPEN", "CLOSED")),
        (WorkPriority, ("HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST")),
        (
            SemanticCounterKind,
            (
                "SPRINT_ORDINAL",
                "ITEM_SEQUENCE",
                "VISIT_ORDINAL",
                "NATURAL_DECISION_OCCURRENCE",
            ),
        ),
        (FactorKind, ("DESCRIPTION_QUALITY", "LATENT_COMPLEXITY")),
    ],
)
def test_closed_enums_are_exact(enum_type: type[StrEnum], values: tuple[str, ...]):
    assert tuple(item.value for item in enum_type) == values
    with pytest.raises(ValueError):
        enum_type("UNAPPROVED")


@pytest.mark.parametrize("value_type", TASK5_VALUE_TYPES)
def test_task5_values_reject_runtime_subclassing(value_type: type):
    with pytest.raises(TypeError, match="subclass"):
        type(f"Forged{value_type.__name__}", (value_type,), {})


def test_task5_scalar_subclasses_cannot_bypass_strict_validation():
    class ForgedUuid(UUID):
        def __ne__(self, _other):
            return False

    class ForgedText(str):
        pass

    class ForgedInstant(datetime):
        pass

    forged_uuid = ForgedUuid(str(uuid4()))
    forged_instant = ForgedInstant(2026, 8, 10, 18, 30, tzinfo=UTC)
    with pytest.raises(TypeError, match="UUID"):
        MemberIdentity(forged_uuid, TEAM_ID, 0)
    with pytest.raises(TypeError, match="string"):
        replace(make_work_item(), current_status_key=ForgedText("DEVELOPMENT"))
    with pytest.raises(TypeError, match="datetime"):
        replace(make_work_item(), created_at=forged_instant)


def test_trusted_sample_input_is_slotted_immutable_and_sealed():
    sample_input_type = getattr(scrum_state_module, "StatusVisitSampleInput")
    sample_input = _sample_input_with_seed(BLUEPRINT, 8_647_914_917, BLUEPRINT.seed)
    assert not hasattr(sample_input, "__dict__")
    assert copy.copy(sample_input) is sample_input
    assert copy.deepcopy(sample_input) is sample_input
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        sample_input.blueprint = None
    with pytest.raises(TypeError, match="cannot be pickled"):
        pickle.dumps(sample_input)
    with pytest.raises(TypeError, match="subclass"):
        type("ForgedStatusVisitSampleInput", (sample_input_type,), {})


def test_status_sample_direct_construction_and_replace_are_rejected():
    sample = make_sample()
    values = tuple(getattr(sample, field.name) for field in fields(sample))
    with pytest.raises(TypeError, match="trusted"):
        StatusVisitSample(*values)
    with pytest.raises(TypeError, match="trusted"):
        replace(sample, touch_sampled_hours=sample.touch_sampled_hours)


def test_semantic_identities_must_match_their_coordinates():
    with pytest.raises(ValueError, match="semantic member"):
        replace(make_member(), id=uuid4())
    with pytest.raises(ValueError, match="semantic work item"):
        replace(make_work_item(), id=uuid4())
    with pytest.raises(ValueError, match="semantic sprint"):
        replace(make_sprint(), id=uuid4())
    with pytest.raises(ValueError, match="semantic visit"):
        replace(make_visit(), id=uuid4())


@pytest.mark.parametrize("invalid", [True, -1, MAX_SAFE_INTEGER + 1])
def test_semantic_coordinates_reject_boolean_negative_and_unsafe_integers(invalid):
    with pytest.raises((TypeError, ValueError)):
        replace(make_member(), blueprint_index=invalid)
    with pytest.raises((TypeError, ValueError)):
        replace(make_work_item(), creation_sequence=invalid)
    with pytest.raises((TypeError, ValueError)):
        replace(make_sprint(), ordinal=invalid)
    with pytest.raises((TypeError, ValueError)):
        replace(make_visit(), ordinal=invalid)
    with pytest.raises((TypeError, ValueError)):
        replace(make_work_item(), relative_rank=invalid)
    with pytest.raises((TypeError, ValueError)):
        replace(make_evaluation(), occurrence=invalid)


def test_counter_accepts_exhausted_sentinel_but_no_larger_value():
    assert replace(make_counter(), next_value=MAX_SAFE_INTEGER + 1).next_value == 2**53
    with pytest.raises(ValueError, match="exhausted sentinel"):
        replace(make_counter(), next_value=2**53 + 1)
    with pytest.raises(TypeError):
        replace(make_counter(), next_value=True)


@pytest.mark.parametrize(
    "kind,scope_id,scope_key",
    [
        (SemanticCounterKind.SPRINT_ORDINAL, TEAM_ID, "SCRUM"),
        (SemanticCounterKind.ITEM_SEQUENCE, TEAM_ID, CreationKind.KANBAN_ARRIVAL.value),
        (SemanticCounterKind.VISIT_ORDINAL, ITEM_ID, "VISIT"),
        (
            SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
            ITEM_ID,
            DecisionType.RISK_CANCELLATION_OUTCOME.value,
        ),
    ],
)
def test_counter_scope_accepts_only_the_exact_kind_specific_key(kind, scope_id, scope_key):
    assert SemanticCounterScope(kind, scope_id, scope_key).scope_key == scope_key
    with pytest.raises(ValueError, match="scope_key"):
        SemanticCounterScope(kind, scope_id, "wrong")


def test_rank_order_uses_priority_rank_and_work_item_uuid_only():
    ids = sorted((uuid4(), uuid4()))
    ranked = [
        SimulatorRank(WorkPriority.LOW, 0, ids[0]),
        SimulatorRank(WorkPriority.HIGH, 2, ids[1]),
        SimulatorRank(WorkPriority.HIGH, 1, ids[1]),
        SimulatorRank(WorkPriority.HIGH, 1, ids[0]),
        SimulatorRank(WorkPriority.HIGHEST, MAX_SAFE_INTEGER, ids[1]),
    ]
    assert sorted(ranked) == [ranked[4], ranked[3], ranked[2], ranked[1], ranked[0]]
    assert total_ordering is not None


@pytest.mark.parametrize("points", [1, 2, 3, 5, 8, 13])
def test_work_items_accept_only_supported_fibonacci_points(points: int):
    assert replace(make_work_item(), story_points=points).story_points == points


@pytest.mark.parametrize("points", [True, 0, 4, 21, "5"])
def test_work_items_reject_non_fibonacci_or_coerced_points(points):
    with pytest.raises((TypeError, ValueError)):
        replace(make_work_item(), story_points=points)


def test_all_scalar_boundaries_are_strict_and_canonical():
    with pytest.raises(TypeError):
        replace(make_work_item(), team_id=str(TEAM_ID))
    with pytest.raises(TypeError):
        replace(make_factor(), value=True)
    with pytest.raises(ValueError):
        replace(make_factor(), value=1.01)
    with pytest.raises(ValueError, match="canonical"):
        replace(make_factor(), provenance_json='{ "unit":0.625,"decision":"quality"}')
    with pytest.raises(ValueError, match="digest"):
        replace(make_factor(), provenance_sha256="0" * 64)
    with pytest.raises((TypeError, ValueError)):
        replace(make_consumption(), consumed_labor_microseconds=-1)


def make_consumption() -> MemberBusinessDateConsumption:
    return MemberBusinessDateConsumption(TEAM_ID, RUN_ID, MEMBER_ID, BUSINESS_DATE, 1)


def test_aware_instants_normalize_to_utc_and_naive_values_are_rejected():
    with pytest.raises(ValueError, match="aware"):
        replace(make_overlay(), starts_at=datetime(2026, 8, 10, 18, 30))
    offset_end = LATER.astimezone(timezone(timedelta(hours=-7)))
    normalized = replace(make_overlay(), ends_at=offset_end)
    assert normalized.ends_at == LATER
    assert normalized.ends_at.tzinfo is UTC
    with pytest.raises(TypeError):
        replace(make_consumption(), business_date=datetime(2026, 8, 10))
    with pytest.raises(ValueError, match="half-open"):
        replace(make_overlay(), ends_at=NOW)


def test_overlay_and_sprint_interval_and_lifecycle_coherence():
    with pytest.raises(ValueError, match="fraction"):
        replace(make_overlay(), availability_fraction=1.1)
    with pytest.raises(ValueError, match="planned"):
        replace(make_sprint(), planned_end_at=NOW)
    with pytest.raises(ValueError, match="observed_end"):
        replace(make_sprint(), observed_end_at=LATER)
    completed = replace(make_sprint(), lifecycle=SprintLifecycle.COMPLETED, observed_end_at=LATER)
    assert completed.observed_end_at == LATER


def test_status_visit_requires_balanced_microseconds_and_coherent_close_time():
    with pytest.raises(ValueError, match="elapsed plus remaining"):
        replace(make_visit(), remaining_work_microseconds=1)
    with pytest.raises(ValueError, match="closed_at"):
        replace(make_visit(), closed_at=LATER)
    visit = make_visit()
    closed = replace(
        visit,
        lifecycle=StatusVisitLifecycle.CLOSED,
        closed_at=LATER,
        remaining_work_microseconds=0,
        elapsed_work_microseconds=visit.required_work_microseconds,
    )
    assert closed.closed_at == LATER


@pytest.mark.parametrize("status_key", ["TO_DO", "DONE"])
def test_zero_touch_route_visits_use_exact_none_activity_and_no_member(status_key: str):
    state = make_zero_touch_write_set(status_key)
    visit = state.status_visits[0]
    blueprint = ResolvedTeamBlueprint.from_canonical_json(zero_touch_blueprint_json(status_key))

    state.validate_against(blueprint)

    assert visit.activity_key is None
    assert visit.member_id is None
    assert visit.required_work_microseconds == 0
    assert state.status_visit_samples[0].touch_sampled_hours == 0.0


def test_activity_key_accepts_only_exact_text_or_none():
    class ForgedActivity(str):
        pass

    with pytest.raises(TypeError, match="activity_key"):
        replace(make_visit(), activity_key=ForgedActivity("development"))
    with pytest.raises(TypeError, match="activity_key"):
        replace(make_visit(), activity_key=1)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"member_id": MEMBER_ID}, "member"),
        ({"required_work_microseconds": 1, "remaining_work_microseconds": 1}, "zero-touch"),
        ({"elapsed_work_microseconds": 1, "required_work_microseconds": 1}, "zero-touch"),
        ({"credited_labor_microseconds": 1}, "zero-touch"),
    ],
)
def test_none_activity_is_intrinsically_zero_touch_without_a_member(changes, message):
    with pytest.raises(ValueError, match=message):
        replace(make_visit(), activity_key=None, **changes)


def test_blueprint_rejects_activity_or_member_on_the_wrong_route_step():
    activity_visit = replace(
        make_visit(),
        activity_key=None,
        member_id=None,
        required_work_microseconds=0,
        elapsed_work_microseconds=0,
        remaining_work_microseconds=0,
        credited_labor_microseconds=0,
    )
    activity_state = ScrumStateWriteSet(
        member_identities=(make_member(),),
        work_items=(make_work_item(),),
        status_visits=(activity_visit,),
    )
    with pytest.raises(ValueError, match="route step"):
        activity_state.validate_against(BLUEPRINT)

    zero_state = make_zero_touch_write_set("TO_DO")
    zero_blueprint = ResolvedTeamBlueprint.from_canonical_json(
        zero_touch_blueprint_json("TO_DO")
    )
    wrong_activity = replace(zero_state.status_visits[0], activity_key="development")
    with pytest.raises(ValueError, match="route step"):
        replace(zero_state, status_visits=(wrong_activity,)).validate_against(zero_blueprint)

    member_id = member_rng_id(zero_state.status_visits[0].team_id, 1)
    with pytest.raises(ValueError, match="zero-touch"):
        replace(zero_state.status_visits[0], member_id=member_id)


def test_sprint_scope_removed_time_follows_added_time():
    with pytest.raises(ValueError, match="removed_at"):
        replace(make_scope(), removed_at=NOW.replace(year=2025))
    assert replace(make_scope(), removed_at=LATER).removed_at == LATER


@pytest.mark.parametrize(
    "field_name",
    [
        "dwell_parameters_json",
        "touch_parameters_json",
        "dwell_draw_json",
        "touch_draw_json",
    ],
)
def test_sample_rejects_noncanonical_provenance_and_wrong_digest(field_name: str):
    sample = make_sample()
    document = getattr(sample, field_name)
    with pytest.raises((TypeError, ValueError)):
        replace(sample, **{field_name: document + " "})
    digest_name = field_name.replace("_json", "_sha256")
    with pytest.raises((TypeError, ValueError)):
        replace(sample, **{digest_name: "f" * 64})


def test_sample_links_explicit_draws_formulas_and_required_work_hash():
    sample = make_sample()
    with pytest.raises((TypeError, ValueError)):
        replace(sample, dwell_unit_value=0.5)
    with pytest.raises((TypeError, ValueError)):
        replace(sample, touch_sampled_hours=2.5)
    with pytest.raises((TypeError, ValueError)):
        replace(sample, required_work_sha256="0" * 64)
    with pytest.raises((TypeError, ValueError)):
        replace(sample, required_work_microseconds=1)


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "g" * 64])
def test_required_work_digest_is_exact_lower_case_sha256_text(digest: str):
    with pytest.raises((TypeError, ValueError), match="digest|sha256"):
        _raw_status_sample(required_work_sha256=digest).validate()


def test_required_work_digest_rejects_equal_string_subclass_in_value_and_aggregate():
    class ForgedDigest(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

    forged = _raw_status_sample(required_work_sha256=ForgedDigest("0" * 64))
    with pytest.raises(TypeError, match="string"):
        forged.validate()
    with pytest.raises(TypeError, match="string"):
        replace(make_write_set(), status_visit_samples=(forged,))


def _raw_status_sample(**changes: object) -> StatusVisitSample:
    original = make_sample()
    sample = object.__new__(StatusVisitSample)
    for field in fields(original):
        value = changes.get(field.name, getattr(original, field.name))
        object.__setattr__(sample, field.name, value)
    return sample


def _raw_value(value: object, **changes: object) -> object:
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged, field.name, changes.get(field.name, getattr(value, field.name))
        )
    return forged


def _changed_low_nibble(digest: str) -> str:
    replacement = "0" if digest[-1] != "0" else "1"
    return digest[:-1] + replacement


def _forged_decision(decision: DecisionOccurrence, case: str) -> DecisionOccurrence:
    changes = {
        "decision_entity": {"entity_id": ScalarUuid(str(decision.entity_id))},
        "decision_type": {"decision_type": decision.decision_type.value},
        "decision_occurrence": {"occurrence": False},
    }[case]
    return _raw_value(decision, **changes)


def _forged_draw(sample_input: StatusVisitSampleInput, case: str) -> UniformDraw:
    draw = sample_input.dwell_draw
    if case.startswith("decision_"):
        return _raw_value(draw, decision=_forged_decision(draw.decision, case))
    changes = {
        "algorithm": {"algorithm": EqualitySpoofText(draw.algorithm)},
        "draw_index": {"draw_index": False},
        "canonical_message": {"canonical_message": ScalarBytes(draw.canonical_message)},
        "hmac_low_bit": {
            "hmac_sha256": EqualitySpoofText(_changed_low_nibble(draw.hmac_sha256))
        },
        "u53_integer": {"u53_integer": ScalarInt(draw.u53_integer)},
        "unit_value": {"unit_value": StatefulEqualityFloat(draw.unit_value)},
    }[case]
    return _raw_value(draw, **changes)


@pytest.mark.parametrize("case", NESTED_DRAW_FORGERIES)
def test_sample_input_rejects_every_nonexact_nested_draw_scalar(case: str):
    trusted = _sample_input_with_seed(BLUEPRINT, 8_647_914_917, BLUEPRINT.seed)
    forged_draw = _forged_draw(trusted, case)

    with pytest.raises((TypeError, ValueError)):
        StatusVisitSampleInput(
            trusted.blueprint,
            trusted.work_item,
            trusted.visit,
            forged_draw,
            trusted.touch_draw,
        )


@pytest.mark.parametrize("case", FACTORY_DRAW_FORGERIES)
def test_sample_factory_revalidates_raw_trusted_input(case: str):
    trusted = _sample_input_with_seed(BLUEPRINT, 8_647_914_917, BLUEPRINT.seed)
    forged_draw = _forged_draw(trusted, case)
    forged_input = _raw_value(trusted, dwell_draw=forged_draw)

    with pytest.raises((TypeError, ValueError)):
        StatusVisitSample.create(forged_input)


def test_sample_input_binds_every_plain_hmac_digest_bit():
    trusted = _sample_input_with_seed(BLUEPRINT, 8_647_914_917, BLUEPRINT.seed)
    changed_digest = _changed_low_nibble(trusted.dwell_draw.hmac_sha256)
    forged_draw = _raw_value(trusted.dwell_draw, hmac_sha256=changed_digest)

    with pytest.raises(ValueError, match="authenticated"):
        StatusVisitSampleInput(
            trusted.blueprint,
            trusted.work_item,
            trusted.visit,
            forged_draw,
            trusted.touch_draw,
        )


@pytest.mark.parametrize("field_name", ["dwell_unit_value", "touch_unit_value"])
def test_retained_unit_values_require_exact_stateless_floats(field_name: str):
    original = make_sample()
    forged_value = StatefulEqualityFloat(getattr(original, field_name))
    forged = _raw_status_sample(**{field_name: forged_value})

    assert forged_value.forged_state == "untrusted"
    with pytest.raises(TypeError, match="float"):
        forged.validate()
    with pytest.raises(TypeError, match="float"):
        replace(make_write_set(), status_visit_samples=(forged,))


@pytest.mark.parametrize("invalid", [float("-inf"), float("inf"), float("nan"), -0.1, 1.1])
@pytest.mark.parametrize("field_name", ["dwell_unit_value", "touch_unit_value"])
def test_retained_unit_values_reject_nonfinite_and_out_of_range_values(
    field_name: str, invalid: float
):
    with pytest.raises(ValueError, match="fraction"):
        _raw_status_sample(**{field_name: invalid}).validate()


def test_sample_draw_provenance_is_bound_to_visit_and_canonical_message():
    sample = make_sample()
    document = json.loads(sample.dwell_draw_json)
    document["entity_id"] = str(uuid4())
    forged_json = canonical_json(document)
    with pytest.raises((TypeError, ValueError)):
        replace(
            sample,
            dwell_draw_json=forged_json,
            dwell_draw_sha256=canonical_sha256(document),
        )


@pytest.mark.parametrize("field_name", ["occurrence", "draw_index"])
def test_sample_draw_message_rejects_boolean_coordinates(field_name: str):
    sample = make_sample()
    document = json.loads(sample.dwell_draw_json)
    message = json.loads(document["canonical_message"])
    message[field_name] = False
    document["canonical_message"] = canonical_json(message)
    forged_json = canonical_json(document)
    with pytest.raises((TypeError, ValueError)):
        replace(
            sample,
            dwell_draw_json=forged_json,
            dwell_draw_sha256=canonical_sha256(document),
        )


def _blueprint_with_touch_hours(hours: float) -> ResolvedTeamBlueprint:
    document = json.loads(BLUEPRINT_JSON)
    timing_entry = document["timing"]["entries"][0]
    timing_entry["touch_min"] = hours
    timing_entry["touch_max"] = hours
    return ResolvedTeamBlueprint.from_canonical_json(canonical_json(document))


def _sample_input_with_seed(
    blueprint: ResolvedTeamBlueprint, required_microseconds: int, seed: str
):
    team_id = team_rng_id(canonical_sha256(json.loads(blueprint.canonical_json())))
    run_id = run_rng_id(team_id, 0)
    work_item_id = item_rng_id(team_id, CreationKind.INITIAL_BACKLOG, 0)
    visit_id = visit_rng_id(work_item_id, 0)
    work_item = replace(
        make_work_item(), id=work_item_id, team_id=team_id, run_id=run_id
    )
    visit = replace(
        make_visit(), id=visit_id, team_id=team_id, run_id=run_id,
        work_item_id=work_item_id, member_id=None,
        required_work_microseconds=required_microseconds, elapsed_work_microseconds=0,
        remaining_work_microseconds=required_microseconds,
    )
    stream = DeterministicRandomStream(seed, team_id, run_id)
    dwell = stream.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_DWELL, 0), 0)
    touch = stream.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_TOUCH, 0), 0)
    input_type = getattr(scrum_state_module, "StatusVisitSampleInput")
    return input_type(blueprint, work_item, visit, dwell, touch)


@pytest.mark.parametrize(
    "hours,expected_microseconds",
    [(0.0, 0), (2**-11, 1_757_812), (3 * 2**-11, 5_273_438)],
)
def test_touch_hours_convert_to_exact_half_even_microseconds(hours, expected_microseconds):
    blueprint = _blueprint_with_touch_hours(hours)
    sample_input = _sample_input_with_seed(
        blueprint, expected_microseconds, blueprint.seed
    )
    sample = StatusVisitSample.create(sample_input)
    assert sample.required_work_microseconds == expected_microseconds


def test_touch_hours_reject_signed_64_microsecond_overflow():
    overflowing_hours = (2**63 / 3_600_000_000) + 1
    blueprint = _blueprint_with_touch_hours(overflowing_hours)
    sample_input = _sample_input_with_seed(blueprint, 0, blueprint.seed)
    with pytest.raises(ValueError, match="signed SQLite"):
        StatusVisitSample.create(sample_input)


def test_status_sample_rejects_otherwise_consistent_draws_from_the_wrong_seed():
    with pytest.raises(ValueError, match="authenticated"):
        _sample_input_with_seed(BLUEPRINT, 8_647_914_917, "wrong-seed")


def test_repeated_route_status_matches_the_exact_activity_step():
    document = json.loads(BLUEPRINT_JSON)
    route = document["workflow"]["routes"][0]
    route["steps"].insert(
        1,
        {"required_activity": "analysis", "status_key": "DEVELOPMENT"},
    )
    document["workflow"]["statuses"][1]["activities"].append("analysis")
    blueprint = ResolvedTeamBlueprint.from_canonical_json(canonical_json(document))
    team_id = team_rng_id(canonical_sha256(document))
    run_id = run_rng_id(team_id, 0)
    item_id = item_rng_id(team_id, CreationKind.INITIAL_BACKLOG, 0)
    member_id = member_rng_id(team_id, 1)
    work = replace(make_work_item(), id=item_id, team_id=team_id, run_id=run_id)
    member = replace(make_member(), id=member_id, team_id=team_id)
    visit = replace(
        make_visit(),
        id=visit_rng_id(item_id, 0),
        team_id=team_id,
        run_id=run_id,
        work_item_id=item_id,
        member_id=member_id,
    )
    state = ScrumStateWriteSet(
        member_identities=(member,),
        work_items=(work,),
        status_visits=(visit,),
    )

    state.validate_against(blueprint)


@pytest.mark.parametrize("value", [2**63, True, 0.5])
def test_duration_microseconds_use_true_signed_sqlite_integers(value):
    with pytest.raises((TypeError, ValueError)):
        replace(make_consumption(), consumed_labor_microseconds=value)
    with pytest.raises((TypeError, ValueError)):
        replace(make_overlay(), daily_capacity_ceiling_microseconds=value)
    with pytest.raises((TypeError, ValueError)):
        replace(
            make_visit(),
            required_work_microseconds=value,
            elapsed_work_microseconds=value,
            remaining_work_microseconds=0,
        )
    with pytest.raises((TypeError, ValueError)):
        replace(
            make_sample(),
            required_work_microseconds=value,
            required_work_sha256=canonical_sha256({"required_work_microseconds": value}),
        )


def test_natural_evaluation_rejects_wrong_types_and_naive_recording_time():
    with pytest.raises(TypeError):
        replace(make_evaluation(), business_date="2026-08-10")
    with pytest.raises(TypeError):
        replace(make_evaluation(), decision_type="RISK_CANCELLATION_OUTCOME")
    with pytest.raises(ValueError, match="aware"):
        replace(make_evaluation(), recorded_at=NOW.replace(tzinfo=None))


@pytest.mark.parametrize(
    "decision_type",
    [DecisionType.RISK_REVIEW_REJECTION_OUTCOME, DecisionType.STATUS_DWELL],
)
def test_natural_state_rejects_decision_types_without_supported_owner(decision_type):
    with pytest.raises(ValueError, match="supported natural"):
        replace(make_evaluation(), decision_type=decision_type)
    scope = SemanticCounterScope(
        SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
        ITEM_ID,
        decision_type.value,
    )
    with pytest.raises(ValueError, match="supported natural"):
        SemanticCounter(TEAM_ID, RUN_ID, scope, 0)


def test_all_values_are_slotted_frozen_copy_stable_and_reconstruction_safe():
    write_set = make_write_set()
    values = [write_set, *[items[0] for items in _collections(write_set)]]
    values.extend((make_counter().scope, make_work_item().simulator_rank))
    values.append(ScrumStateQuery(TEAM_ID, RUN_ID))
    for value in values:
        assert not hasattr(value, "__dict__")
        assert copy.copy(value) is value
        assert copy.deepcopy(value) is value
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            setattr(value, fields(value)[0].name, None)
        with pytest.raises(TypeError, match="cannot be pickled"):
            pickle.dumps(value)
        state = {field.name: getattr(value, field.name) for field in fields(value)}
        with pytest.raises(TypeError, match="cannot be pickled"):
            pickle.loads(tampered_pickle(type(value), state))


def _collections(state: ScrumStateWriteSet) -> tuple[tuple[object, ...], ...]:
    return tuple(getattr(state, field.name) for field in fields(state))


def test_write_set_is_tuple_only_deeply_immutable_and_snapshot_is_detached():
    write_set = make_write_set()
    assert all(isinstance(items, tuple) for items in _collections(write_set))
    with pytest.raises(TypeError):
        replace(write_set, work_items=[make_work_item()])
    snapshot = ScrumStateSnapshot.from_write_set(write_set)
    assert _collections(snapshot) == _collections(write_set)
    assert snapshot is not write_set


def test_sparse_write_set_allows_persisted_owners_but_snapshot_requires_complete_closure():
    sparse = ScrumStateWriteSet(status_visits=(make_visit(),))
    assert sparse.status_visits == (make_visit(),)

    state = make_write_set()
    values = {field.name: getattr(state, field.name) for field in fields(state)}
    with pytest.raises(ValueError, match="sample"):
        ScrumStateSnapshot(**{**values, "status_visit_samples": ()})
    with pytest.raises(ValueError, match="visit"):
        ScrumStateSnapshot(**{**values, "status_visits": ()})


def test_write_set_validates_sample_required_work_against_its_visit():
    visit = make_visit()
    mismatched_visit = replace(
        visit,
        required_work_microseconds=visit.required_work_microseconds + 1,
        remaining_work_microseconds=visit.remaining_work_microseconds + 1,
    )
    with pytest.raises(ValueError, match="visit required work"):
        replace(make_write_set(), status_visits=(mismatched_visit,))


def test_blueprint_configuration_is_absent_from_authoritative_state_contracts():
    prohibited = {
        "name",
        "role",
        "responsibility",
        "proficiency",
        "wip",
        "route",
        "timing_grid",
        "calendar",
        "policy",
        "nominal_capacity",
    }
    state_types = (
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
    for value_type in state_types:
        field_names = {field.name for field in fields(value_type)}
        assert not any(token in name for name in field_names for token in prohibited)


def test_payload_examples_are_byte_canonical():
    factor = make_factor()
    assert factor.provenance_json == canonical_json({"decision": "quality", "unit": 0.625})
    assert factor.provenance_sha256 == canonical_sha256({"decision": "quality", "unit": 0.625})
