import copy
import json
import pickle
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from functools import total_ordering
from uuid import uuid4

import pytest

from app.v2.domain.canonical_json import canonical_json, canonical_sha256
from app.v2.domain.deterministic_rng import MAX_SAFE_INTEGER, CreationKind, DecisionType
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
    StatusVisitState,
    WorkItemFactor,
    WorkItemLifecycle,
    WorkItemState,
    WorkPriority,
)
from tests.v2.immutable_value_testing import tampered_pickle
from tests.v2.scrum_state_support import (
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
    closed = replace(
        make_visit(),
        lifecycle=StatusVisitLifecycle.CLOSED,
        closed_at=LATER,
        remaining_work_microseconds=0,
        elapsed_work_microseconds=7_200_000_000,
    )
    assert closed.closed_at == LATER


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
    with pytest.raises(ValueError, match="canonical"):
        replace(sample, **{field_name: document + " "})
    digest_name = field_name.replace("_json", "_sha256")
    with pytest.raises(ValueError, match="digest"):
        replace(sample, **{digest_name: "f" * 64})


def test_sample_links_explicit_draws_formulas_and_required_work_hash():
    sample = make_sample()
    with pytest.raises(ValueError, match="unit"):
        replace(sample, dwell_unit_value=0.5)
    with pytest.raises(ValueError, match="sampled"):
        replace(sample, touch_sampled_hours=2.5)
    with pytest.raises(ValueError, match="required"):
        replace(sample, required_work_sha256="0" * 64)
    with pytest.raises(ValueError, match="required"):
        replace(sample, required_work_microseconds=1)


def test_sample_draw_provenance_is_bound_to_visit_and_canonical_message():
    sample = make_sample()
    document = json.loads(sample.dwell_draw_json)
    document["entity_id"] = str(uuid4())
    forged_json = canonical_json(document)
    with pytest.raises(ValueError, match="visit"):
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
    with pytest.raises(TypeError, match="integer"):
        replace(
            sample,
            dwell_draw_json=forged_json,
            dwell_draw_sha256=canonical_sha256(document),
        )


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


def test_write_set_validates_sample_required_work_against_its_visit():
    sample = replace(
        make_sample(),
        required_work_microseconds=1,
        required_work_sha256=canonical_sha256({"required_work_microseconds": 1}),
    )
    with pytest.raises(ValueError, match="visit required work"):
        replace(make_write_set(), status_visit_samples=(sample,))


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
