import ast
import json
import warnings
from dataclasses import fields, replace
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, event, func, inspect, select, text, update
from sqlalchemy.exc import IntegrityError, SAWarning
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.deterministic_rng import (
    DecisionType,
    item_rng_id,
    member_rng_id,
    sprint_rng_id,
    visit_rng_id,
)
from app.v2.domain.scrum_state import (
    MemberIdentity,
    NaturalDecisionEvaluation,
    ScrumStateQuery,
    ScrumStateSnapshot,
    ScrumStateWriteSet,
    SemanticCounter,
    SemanticCounterKind,
    SemanticCounterScope,
    SprintLifecycle,
    StatusVisitState,
)
from app.v2.persistence.live_models import V2ActivityEventModel
from app.v2.persistence.scrum_state_mapper import SqlAlchemyScrumStateMapper
from app.v2.persistence.scrum_state_models import (
    V2MemberAvailabilityOverlayModel,
    V2MemberBusinessDateConsumptionModel,
    V2MemberIdentityModel,
    V2NaturalDecisionEvaluationModel,
    V2SemanticCounterModel,
    V2SprintModel,
    V2SprintScopeModel,
    V2StatusVisitModel,
    V2StatusVisitSampleModel,
    V2WorkItemFactorModel,
    V2WorkItemModel,
)
from app.v2.persistence.team_models import V2RunModel, V2TeamBlueprintModel, V2TeamModel
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import (
    BLUEPRINT,
    BLUEPRINT_SHA256,
    BUSINESS_DATE,
    ITEM_ID,
    NOW,
    RUN_ID,
    TEAM_ID,
    make_factor,
    make_member,
    make_sample,
    make_work_item,
    make_write_set,
    make_zero_touch_write_set,
    seed_parent_team_and_run,
    zero_touch_blueprint_json,
)

TASK5_MODELS = (
    V2MemberIdentityModel,
    V2MemberAvailabilityOverlayModel,
    V2MemberBusinessDateConsumptionModel,
    V2WorkItemModel,
    V2WorkItemFactorModel,
    V2SprintModel,
    V2SprintScopeModel,
    V2StatusVisitModel,
    V2StatusVisitSampleModel,
    V2SemanticCounterModel,
    V2NaturalDecisionEvaluationModel,
)
MODEL_COLLECTIONS = (
    "member_identities",
    "member_availability_overlays",
    "member_business_date_consumption",
    "work_items",
    "work_item_factors",
    "sprints",
    "sprint_scope",
    "status_visits",
    "status_visit_samples",
    "semantic_counters",
    "natural_decision_evaluations",
)
CHECK_VIOLATIONS = (
    (V2MemberIdentityModel, {"blueprint_index": -1}),
    (V2MemberAvailabilityOverlayModel, {"ends_at": NOW}),
    (V2MemberAvailabilityOverlayModel, {"availability_fraction": 1.1}),
    (V2MemberAvailabilityOverlayModel, {"daily_capacity_ceiling_microseconds": -1}),
    (V2MemberBusinessDateConsumptionModel, {"consumed_labor_microseconds": -1}),
    (V2WorkItemModel, {"creation_sequence": -1}),
    (V2WorkItemModel, {"relative_rank": -1}),
    (V2WorkItemModel, {"creation_kind": "UNKNOWN"}),
    (V2WorkItemModel, {"issue_type": "UNKNOWN"}),
    (V2WorkItemModel, {"story_points": 4}),
    (V2WorkItemModel, {"priority": "UNKNOWN"}),
    (V2WorkItemModel, {"lifecycle": "UNKNOWN"}),
    (V2WorkItemModel, {"updated_at": NOW - timedelta(seconds=1)}),
    (V2WorkItemFactorModel, {"kind": "UNKNOWN"}),
    (V2WorkItemFactorModel, {"value": -0.1}),
    (V2SprintModel, {"ordinal": -1}),
    (V2SprintModel, {"lifecycle": "UNKNOWN"}),
    (V2SprintModel, {"planned_end_at": NOW}),
    (V2SprintModel, {"lifecycle": "PLANNED"}),
    (V2SprintModel, {"updated_at": NOW - timedelta(seconds=1)}),
    (V2SprintScopeModel, {"removed_at": NOW - timedelta(seconds=1)}),
    (V2StatusVisitModel, {"ordinal": -1}),
    (V2StatusVisitModel, {"lifecycle": "UNKNOWN"}),
    (
        V2StatusVisitModel,
        {"lifecycle": "CLOSED", "closed_at": NOW - timedelta(seconds=1)},
    ),
    (V2StatusVisitModel, {"queue_microseconds": -1}),
    (V2StatusVisitModel, {"remaining_work_microseconds": 1}),
    (V2StatusVisitModel, {"lifecycle": "CLOSED", "closed_at": NOW}),
    (V2StatusVisitSampleModel, {"dwell_unit_value": -0.1}),
    (V2StatusVisitSampleModel, {"dwell_sampled_hours": float("inf")}),
    (V2StatusVisitSampleModel, {"required_work_microseconds": -1}),
    (V2SemanticCounterModel, {"next_value": 2**53 + 1}),
    (V2SemanticCounterModel, {"scope_key": "UNKNOWN"}),
    (V2NaturalDecisionEvaluationModel, {"occurrence": -1}),
    (V2NaturalDecisionEvaluationModel, {"decision_type": "UNKNOWN"}),
)
TRUE_INTEGER_COLUMNS = (
    (V2MemberIdentityModel, "blueprint_index"),
    (V2MemberAvailabilityOverlayModel, "daily_capacity_ceiling_microseconds"),
    (V2MemberBusinessDateConsumptionModel, "consumed_labor_microseconds"),
    (V2WorkItemModel, "creation_sequence"),
    (V2WorkItemModel, "relative_rank"),
    (V2SprintModel, "ordinal"),
    (V2StatusVisitModel, "ordinal"),
    (V2StatusVisitModel, "required_work_microseconds"),
    (V2StatusVisitModel, "elapsed_work_microseconds"),
    (V2StatusVisitModel, "remaining_work_microseconds"),
    (V2StatusVisitModel, "queue_microseconds"),
    (V2StatusVisitModel, "pause_microseconds"),
    (V2StatusVisitModel, "credited_labor_microseconds"),
    (V2StatusVisitSampleModel, "required_work_microseconds"),
    (V2SemanticCounterModel, "next_value"),
    (V2NaturalDecisionEvaluationModel, "occurrence"),
)
CORRUPT_SHA256 = "f" * 64
AUTHORITY_CORRUPTIONS = (
    (
        V2TeamModel,
        str(TEAM_ID),
        {"blueprint_sha256": CORRUPT_SHA256},
    ),
    (
        V2RunModel,
        str(RUN_ID),
        {"ordinal": 1},
    ),
    (
        V2TeamBlueprintModel,
        str(semantic_uuid(f"blueprint/{TEAM_ID}/{BLUEPRINT_SHA256}")),
        {"sha256": CORRUPT_SHA256},
    ),
)


class StatefulEqualityFloat(float):
    def __new__(cls, value: float):
        instance = super().__new__(cls, value)
        instance.forged_state = "untrusted"
        return instance

    def __eq__(self, _other: object) -> bool:
        return True

    def __ne__(self, _other: object) -> bool:
        return False


def _counts(session: Session) -> tuple[int, ...]:
    return tuple(session.scalar(select(func.count()).select_from(model)) for model in TASK5_MODELS)


def test_mapper_flushes_in_caller_session_and_loads_exact_detached_state(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    expected = ScrumStateSnapshot.from_write_set(make_write_set())
    mapper = SqlAlchemyScrumStateMapper()

    with v2_session_factory.begin() as session:
        actual = mapper.add(session, make_write_set())
        assert session.in_transaction()
        assert _counts(session) == (1,) * len(TASK5_MODELS)

    with v2_session_factory() as session:
        reloaded = mapper.load(session, ScrumStateQuery(TEAM_ID, RUN_ID))

    assert actual == expected
    assert reloaded == expected
    assert all(not hasattr(item, "_sa_instance_state") for item in _flatten(reloaded))


def test_member_identity_is_derived_from_a_persisted_blueprint_position(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    blueprint_index = len(aggregate.blueprint.members) - 1
    identity = MemberIdentity(
        member_rng_id(aggregate.team.id, blueprint_index), aggregate.team.id, blueprint_index
    )
    state = ScrumStateWriteSet(member_identities=(identity,))
    with v2_session_factory.begin() as session:
        persisted = SqlAlchemyScrumStateMapper().add(session, state)

    assert persisted.member_identities == (identity,)
    assert aggregate.blueprint.members[identity.blueprint_index] == aggregate.blueprint.members[-1]


def test_add_result_uses_the_same_semantic_order_as_restart_load(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    first = make_write_set().work_items[0]
    second = replace(first, id=item_rng_id(TEAM_ID, first.creation_kind, 1), creation_sequence=1)
    state = replace(make_write_set(), work_items=(second, first), work_item_factors=(),
                    sprint_scope=(), status_visits=(), status_visit_samples=())
    mapper = SqlAlchemyScrumStateMapper()
    with v2_session_factory.begin() as session:
        added = mapper.add(session, state)
    with v2_session_factory() as session:
        loaded = mapper.load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
    assert added == loaded
    assert tuple(item.creation_sequence for item in added.work_items) == (0, 1)


def _flatten(snapshot: ScrumStateSnapshot) -> tuple[object, ...]:
    return tuple(item for name in snapshot.__dataclass_fields__ for item in getattr(snapshot, name))


def test_caller_rollback_leaves_every_task5_table_empty(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    mapper = SqlAlchemyScrumStateMapper()

    with v2_session_factory() as session:
        mapper.add(session, make_write_set())
        assert _counts(session) == (1,) * len(TASK5_MODELS)
        session.rollback()

    with v2_session_factory() as session:
        assert _counts(session) == (0,) * len(TASK5_MODELS)


def test_integrity_failure_still_leaves_rollback_ownership_with_caller(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    mapper = SqlAlchemyScrumStateMapper()
    with v2_session_factory() as session:
        mapper.add(session, make_write_set())
        with pytest.raises(IntegrityError):
            mapper.add(session, make_write_set())
        assert session.in_transaction()
        session.rollback()

    with v2_session_factory() as session:
        assert _counts(session) == (0,) * len(TASK5_MODELS)


@pytest.mark.parametrize("case", ["deleted_sample", "dirty_visit", "unrelated_new"])
def test_mapper_rejects_caller_pending_state_before_candidate_sql(
    v2_session_factory, case
):
    seed_parent_team_and_run(v2_session_factory)
    original = make_write_set()
    mapper = SqlAlchemyScrumStateMapper()
    with v2_session_factory.begin() as session:
        expected = mapper.add(session, original)
    updated_visit = replace(
        original.status_visits[0],
        queue_microseconds=original.status_visits[0].queue_microseconds + 2,
    )
    engine = v2_session_factory.kw["bind"]

    with v2_session_factory() as session:
        _prepare_pending_change(session, case, original)
        statements, listener = _all_sql(engine)
        try:
            with pytest.raises(ValueError, match="pending"):
                mapper.add(session, ScrumStateWriteSet(status_visits=(updated_visit,)))
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        assert statements == []
        assert _pending_collection(session, case)
        assert session.in_transaction()
        session.rollback()

    with v2_session_factory() as session:
        assert mapper.load(session, ScrumStateQuery(TEAM_ID, RUN_ID)) == expected
        assert _counts(session) == (1,) * len(TASK5_MODELS)


@pytest.mark.parametrize("case", ["deleted_sample", "dirty_visit", "unrelated_new"])
def test_mapper_load_rejects_caller_pending_state_before_authority_sql(
    v2_session_factory, case
):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    mapper = SqlAlchemyScrumStateMapper()
    with v2_session_factory.begin() as session:
        expected = mapper.add(session, state)
    engine = v2_session_factory.kw["bind"]

    with v2_session_factory() as session:
        _prepare_pending_change(session, case, state)
        statements, listener = _all_sql(engine)
        try:
            with pytest.raises(ValueError, match="pending"):
                mapper.load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        assert statements == []
        assert _pending_collection(session, case)
        assert session.in_transaction()
        session.rollback()

    with v2_session_factory() as session:
        assert mapper.load(session, ScrumStateQuery(TEAM_ID, RUN_ID)) == expected


def _prepare_pending_change(session: Session, case: str, state: ScrumStateWriteSet) -> None:
    if case == "unrelated_new":
        session.add(V2ActivityEventModel())
        return
    if case == "deleted_sample":
        sample = session.get(V2StatusVisitSampleModel, str(state.status_visit_samples[0].visit_id))
        assert sample is not None
        session.delete(sample)
        return
    visit = session.get(V2StatusVisitModel, str(state.status_visits[0].id))
    assert visit is not None
    visit.queue_microseconds += 1


def _pending_collection(session: Session, case: str):
    return {
        "deleted_sample": session.deleted,
        "dirty_visit": session.dirty,
        "unrelated_new": session.new,
    }[case]


def _persist_complete_state(v2_session_factory) -> ScrumStateWriteSet:
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, state)
    return state


def _load_cached_state(session: Session, _state: ScrumStateWriteSet) -> ScrumStateSnapshot:
    return SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))


def _add_sparse_cached_state(session: Session, state: ScrumStateWriteSet) -> ScrumStateSnapshot:
    visit = state.status_visits[0]
    updated = replace(visit, queue_microseconds=visit.queue_microseconds + 1)
    return SqlAlchemyScrumStateMapper().add(session, ScrumStateWriteSet(status_visits=(updated,)))


def _externally_update(v2_session_factory, case: tuple) -> None:
    model_type, identity, values = case
    identity_column = inspect(model_type).primary_key[0]
    with v2_session_factory.begin() as session:
        result = session.execute(
            update(model_type).where(identity_column == identity).values(**values)
        )
        assert result.rowcount == 1


@pytest.mark.parametrize(
    "operation", [_load_cached_state, _add_sparse_cached_state], ids=["load", "sparse-add"]
)
def test_cached_sample_external_corruption_is_refreshed_before_use(v2_session_factory, operation):
    state = _persist_complete_state(v2_session_factory)
    sample_identity = str(state.status_visit_samples[0].visit_id)
    corruption = (
        V2StatusVisitSampleModel,
        sample_identity,
        {"timing_profile": "CORRUPT"},
    )
    engine = v2_session_factory.kw["bind"]

    with v2_session_factory() as session:
        cached = session.get(V2StatusVisitSampleModel, sample_identity)
        assert cached is not None
        _externally_update(v2_session_factory, corruption)
        statements, listener = _task5_dml(engine)
        try:
            with pytest.raises(ValueError):
                operation(session, state)
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        assert statements == []


@pytest.mark.parametrize(
    "operation", [_load_cached_state, _add_sparse_cached_state], ids=["load", "sparse-add"]
)
@pytest.mark.parametrize(
    "case",
    AUTHORITY_CORRUPTIONS,
    ids=["team", "run", "blueprint"],
)
def test_cached_external_authority_corruption_is_refreshed_before_use(
    v2_session_factory, case, operation
):
    state = _persist_complete_state(v2_session_factory)
    model_type, identity, _values = case
    engine = v2_session_factory.kw["bind"]

    with v2_session_factory() as session:
        cached = session.get(model_type, identity)
        assert cached is not None
        _externally_update(v2_session_factory, case)
        statements, listener = _task5_dml(engine)
        try:
            with pytest.raises(ValueError):
                operation(session, state)
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        assert statements == []


def test_cached_external_run_deletion_cannot_return_an_empty_snapshot(
    v2_session_factory,
):
    state = _persist_complete_state(v2_session_factory)

    with v2_session_factory() as session:
        cached = session.get(V2RunModel, str(RUN_ID))
        assert cached is not None
        with v2_session_factory.begin() as external:
            result = external.execute(delete(V2RunModel).where(V2RunModel.id == str(RUN_ID)))
            assert result.rowcount == 1
        with pytest.raises(ValueError):
            _load_cached_state(session, state)


@pytest.mark.parametrize(
    "operation", [_load_cached_state, _add_sparse_cached_state], ids=["load", "sparse-add"]
)
def test_valid_external_update_is_reflected_without_expiring_unrelated_cache(
    v2_session_factory, operation
):
    state = _persist_complete_state(v2_session_factory)
    other_team_id, _other_run_id = _seed_second_team_and_run(v2_session_factory)
    factor_identity = str(state.work_item_factors[0].id)
    external_value = 0.75

    with v2_session_factory() as session:
        cached_factor = session.get(V2WorkItemFactorModel, factor_identity)
        assert cached_factor is not None
        unrelated = session.get(V2TeamModel, str(other_team_id))
        assert unrelated is not None
        _externally_update(
            v2_session_factory,
            (V2WorkItemFactorModel, factor_identity, {"value": external_value}),
        )

        snapshot = operation(session, state)

        assert snapshot.work_item_factors[0].value == external_value
        assert len(_flatten(snapshot)) == len(TASK5_MODELS)
        assert not inspect(unrelated).expired
        assert unrelated.name == "Other"


def test_member_only_add_refreshes_cached_external_member_corruption(
    v2_session_factory,
):
    state = _persist_complete_state(v2_session_factory)
    member_identity = str(state.member_identities[0].id)
    corruption = (V2MemberIdentityModel, member_identity, {"blueprint_index": 0})
    additional = MemberIdentity(member_rng_id(TEAM_ID, 0), TEAM_ID, 0)
    engine = v2_session_factory.kw["bind"]

    with v2_session_factory() as session:
        cached = session.get(V2MemberIdentityModel, member_identity)
        assert cached is not None
        _externally_update(v2_session_factory, corruption)
        statements, listener = _task5_dml(engine)
        try:
            with pytest.raises(ValueError):
                SqlAlchemyScrumStateMapper().add(
                    session, ScrumStateWriteSet(member_identities=(additional,))
                )
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        assert statements == []


def test_externally_deleted_cached_visit_can_be_reinserted_from_after_image(
    v2_session_factory,
):
    state = _persist_complete_state(v2_session_factory)
    other_team_id, _other_run_id = _seed_second_team_and_run(v2_session_factory)
    visit, after_image = _visit_after_image(state)

    with v2_session_factory() as session:
        cached_visit, cached_sample, unrelated = _cache_cascade_identities(
            session, visit.id, other_team_id
        )
        _delete_visit_and_verify_sample_cascade(v2_session_factory, visit.id)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            restored = SqlAlchemyScrumStateMapper().add(session, after_image)
        assert not [item for item in captured if issubclass(item.category, SAWarning)]
        assert inspect(cached_visit).detached
        assert inspect(cached_sample).detached
        assert inspect(unrelated).persistent and not inspect(unrelated).expired
        assert len(_flatten(restored)) == len(TASK5_MODELS)
        session.commit()

    with v2_session_factory() as session:
        assert _counts(session) == (1,) * len(TASK5_MODELS)
        assert (
            SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID)) == restored
        )


def _visit_after_image(
    state: ScrumStateWriteSet,
) -> tuple[StatusVisitState, ScrumStateWriteSet]:
    visit = state.status_visits[0]
    updated = replace(visit, queue_microseconds=visit.queue_microseconds + 1)
    after_image = ScrumStateWriteSet(
        status_visits=(updated,), status_visit_samples=state.status_visit_samples
    )
    return visit, after_image


def _cache_cascade_identities(
    session: Session, visit_id: UUID, unrelated_team_id: UUID
) -> tuple[V2StatusVisitModel, V2StatusVisitSampleModel, V2TeamModel]:
    cached_visit = session.get(V2StatusVisitModel, str(visit_id))
    cached_sample = session.get(V2StatusVisitSampleModel, str(visit_id))
    unrelated = session.get(V2TeamModel, str(unrelated_team_id))
    assert cached_visit is not None and cached_sample is not None and unrelated is not None
    return cached_visit, cached_sample, unrelated


def _delete_visit_and_verify_sample_cascade(v2_session_factory, visit_id: UUID) -> None:
    with v2_session_factory.begin() as external:
        result = external.execute(
            delete(V2StatusVisitModel).where(V2StatusVisitModel.id == str(visit_id))
        )
        assert result.rowcount == 1
        assert external.get(V2StatusVisitSampleModel, str(visit_id)) is None


def _expire_cached(session: Session, model: object) -> None:
    session.expire(model)


def _detach_cached(session: Session, model: object) -> None:
    session.expunge(model)


def _rollback_cached(session: Session, _model: object) -> None:
    session.rollback()


@pytest.mark.parametrize(
    "transition",
    [_expire_cached, _detach_cached, _rollback_cached],
    ids=["expired", "detached", "post-rollback"],
)
def test_authoritative_refresh_supports_clean_cached_object_lifecycles(
    v2_session_factory, transition
):
    state = _persist_complete_state(v2_session_factory)
    expected = ScrumStateSnapshot.from_write_set(state)
    sample_identity = str(state.status_visit_samples[0].visit_id)

    with v2_session_factory() as session:
        cached = session.get(V2StatusVisitSampleModel, sample_identity)
        assert cached is not None
        transition(session, cached)
        assert _load_cached_state(session, state) == expected


@pytest.mark.parametrize("populated", [False, True])
def test_mapper_rejects_empty_sparse_input_without_sql(v2_session_factory, populated):
    mapper = SqlAlchemyScrumStateMapper()
    if populated:
        seed_parent_team_and_run(v2_session_factory)
        with v2_session_factory.begin() as session:
            mapper.add(session, make_write_set())
    with v2_session_factory() as session:
        before = _counts(session)
    engine = v2_session_factory.kw["bind"]

    statements, listener = _all_sql(engine)
    try:
        with v2_session_factory() as session, pytest.raises(ValueError, match="empty"):
            mapper.add(session, ScrumStateWriteSet())
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    assert statements == []
    with v2_session_factory() as session:
        assert _counts(session) == before


@pytest.mark.parametrize("status_key", ["TO_DO", "DONE"])
def test_nullable_zero_touch_visit_and_sample_survive_disposed_engine_restart(
    v2_session_factory, requested_at, status_key
):
    blueprint_json = zero_touch_blueprint_json(status_key)
    aggregate = create_aggregate(v2_session_factory, blueprint_json, requested_at)
    state = make_zero_touch_write_set(status_key)
    assert (state.work_items[0].team_id, state.work_items[0].run_id) == (
        aggregate.team.id,
        aggregate.run.id,
    )
    with v2_session_factory.begin() as session:
        expected = SqlAlchemyScrumStateMapper().add(session, state)
    database_url = str(v2_session_factory.kw["bind"].url)
    v2_session_factory.kw["bind"].dispose()

    restarted = _foreign_key_engine(database_url)
    with Session(restarted) as session:
        actual = SqlAlchemyScrumStateMapper().load(
            session, ScrumStateQuery(aggregate.team.id, aggregate.run.id)
        )
    restarted.dispose()

    assert actual == expected
    assert actual.status_visits[0].activity_key is None
    assert actual.status_visits[0].member_id is None
    assert actual.status_visit_samples[0].required_work_microseconds == 0


@pytest.mark.parametrize("case", ["consumption", "factor", "visit", "visit_counter"])
def test_sparse_after_images_resolve_unchanged_persisted_owners(v2_session_factory, case):
    seed_parent_team_and_run(v2_session_factory)
    owners = ScrumStateWriteSet(
        member_identities=(make_member(),),
        work_items=(make_work_item(),),
    )
    mapper = SqlAlchemyScrumStateMapper()
    with v2_session_factory.begin() as session:
        mapper.add(session, owners)
    sparse = _sparse_after_image(case)

    with v2_session_factory.begin() as session:
        persisted = mapper.add(session, sparse)

    assert persisted.member_identities == owners.member_identities
    assert persisted.work_items == owners.work_items
    assert getattr(persisted, _sparse_collection(case)) == getattr(sparse, _sparse_collection(case))


def _sparse_after_image(case: str) -> ScrumStateWriteSet:
    state = make_write_set()
    if case == "consumption":
        return ScrumStateWriteSet(
            member_business_date_consumption=state.member_business_date_consumption
        )
    if case == "factor":
        return ScrumStateWriteSet(work_item_factors=state.work_item_factors)
    if case == "visit":
        return ScrumStateWriteSet(
            status_visits=state.status_visits,
            status_visit_samples=state.status_visit_samples,
        )
    visit_scope = SemanticCounterScope(SemanticCounterKind.VISIT_ORDINAL, ITEM_ID, "VISIT")
    return ScrumStateWriteSet(
        semantic_counters=(SemanticCounter(TEAM_ID, RUN_ID, visit_scope, 1),)
    )


def _sparse_collection(case: str) -> str:
    return {
        "consumption": "member_business_date_consumption",
        "factor": "work_item_factors",
        "visit": "status_visits",
        "visit_counter": "semantic_counters",
    }[case]


@pytest.mark.parametrize("case", ["consumption", "factor", "visit_counter"])
def test_sparse_after_images_reject_nonexistent_owners_before_dml(v2_session_factory, case):
    seed_parent_team_and_run(v2_session_factory)
    _assert_rejected_without_new_task5_write(
        v2_session_factory, _sparse_missing_owner_state(case)
    )


def _sparse_missing_owner_state(case: str) -> ScrumStateWriteSet:
    missing = uuid4()
    if case == "consumption":
        consumption = replace(
            make_write_set().member_business_date_consumption[0], member_id=missing
        )
        return ScrumStateWriteSet(member_business_date_consumption=(consumption,))
    if case == "factor":
        factor = replace(
            make_factor(),
            id=semantic_uuid(f"factor/{missing}/DESCRIPTION_QUALITY"),
            work_item_id=missing,
        )
        return ScrumStateWriteSet(work_item_factors=(factor,))
    scope = SemanticCounterScope(SemanticCounterKind.VISIT_ORDINAL, missing, "VISIT")
    return ScrumStateWriteSet(semantic_counters=(SemanticCounter(TEAM_ID, RUN_ID, scope, 0),))


def test_sparse_after_image_rejects_owner_from_another_team_run_before_dml(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    seed_parent_team_and_run(v2_session_factory)
    document = json.loads(resolved_blueprint_json)
    document["team"]["name"] = "Other sparse-owner team"
    other = create_aggregate(v2_session_factory, canonical_json(document), requested_at)
    template = make_work_item()
    other_work = replace(
        template,
        id=item_rng_id(other.team.id, template.creation_kind, 0),
        team_id=other.team.id,
        run_id=other.run.id,
    )
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(
            session, ScrumStateWriteSet(work_items=(other_work,))
        )
    factor = make_factor()
    alien = replace(
        factor,
        id=semantic_uuid(f"factor/{other_work.id}/{factor.kind.value}"),
        work_item_id=other_work.id,
    )
    _assert_rejected_without_new_task5_write(
        v2_session_factory, ScrumStateWriteSet(work_item_factors=(alien,))
    )


def test_existing_visit_after_image_can_reuse_unchanged_persisted_sample(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    original = make_write_set()
    mapper = SqlAlchemyScrumStateMapper()
    with v2_session_factory.begin() as session:
        mapper.add(session, original)
    updated_visit = replace(
        original.status_visits[0],
        queue_microseconds=original.status_visits[0].queue_microseconds + 1,
    )

    with v2_session_factory.begin() as session:
        updated = mapper.add(session, ScrumStateWriteSet(status_visits=(updated_visit,)))

    assert updated.status_visits == (updated_visit,)
    assert updated.status_visit_samples == original.status_visit_samples
    with v2_session_factory() as session:
        assert mapper.load(session, ScrumStateQuery(TEAM_ID, RUN_ID)) == updated


def test_new_visit_without_sample_is_rejected_before_dml(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    missing_sample = ScrumStateWriteSet(
        member_identities=state.member_identities,
        work_items=state.work_items,
        status_visits=state.status_visits,
    )
    _assert_rejected_before_task5_write(v2_session_factory, missing_sample)


def test_restart_load_rejects_visit_whose_sample_row_is_missing(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, make_write_set())
        session.execute(delete(V2StatusVisitSampleModel))
    database_url = str(v2_session_factory.kw["bind"].url)
    v2_session_factory.kw["bind"].dispose()

    restarted = _foreign_key_engine(database_url)
    with Session(restarted) as session, pytest.raises(ValueError, match="sample"):
        SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
    restarted.dispose()


def test_existing_visit_without_persisted_sample_rejects_sparse_update_before_dml(
    v2_session_factory,
):
    seed_parent_team_and_run(v2_session_factory)
    original = make_write_set()
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, original)
        session.execute(delete(V2StatusVisitSampleModel))
    updated = replace(
        original.status_visits[0],
        queue_microseconds=original.status_visits[0].queue_microseconds + 1,
    )
    _assert_rejected_without_new_task5_write(
        v2_session_factory, ScrumStateWriteSet(status_visits=(updated,))
    )


def test_forged_required_work_digest_subclass_rejects_before_sql(v2_session_factory):
    class ForgedDigest(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

    seed_parent_team_and_run(v2_session_factory)
    sample = make_sample()
    forged = object.__new__(type(sample))
    for field in fields(sample):
        value = getattr(sample, field.name)
        if field.name == "required_work_sha256":
            value = ForgedDigest("0" * 64)
        object.__setattr__(forged, field.name, value)
    state = make_write_set()
    invalid = _unsafe_write_set(
        member_identities=state.member_identities,
        work_items=state.work_items,
        status_visits=state.status_visits,
        status_visit_samples=(forged,),
    )
    _assert_rejected_before_task5_write(v2_session_factory, invalid)


@pytest.mark.parametrize("field_name", ["dwell_unit_value", "touch_unit_value"])
def test_stateful_sample_unit_subclass_rejects_before_mapper_sql(
    v2_session_factory, field_name
):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    sample = state.status_visit_samples[0]
    forged_value = StatefulEqualityFloat(getattr(sample, field_name))
    forged = _raw_sample_with_change(sample, field_name, forged_value)
    invalid = _unsafe_write_set(
        member_identities=state.member_identities,
        work_items=state.work_items,
        status_visits=state.status_visits,
        status_visit_samples=(forged,),
    )

    _assert_rejected_before_task5_write(v2_session_factory, invalid)


def _raw_sample_with_change(sample, field_name: str, value: object):
    forged = object.__new__(type(sample))
    for field in fields(sample):
        replacement = value if field.name == field_name else getattr(sample, field.name)
        object.__setattr__(forged, field.name, replacement)
    return forged


def test_invalid_write_set_is_rejected_before_first_sql(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    valid = make_write_set()
    invalid = object.__new__(type(valid))
    for field_name in valid.__dataclass_fields__:
        object.__setattr__(invalid, field_name, getattr(valid, field_name))
    object.__setattr__(invalid, "status_visits", (object(),))
    calls = 0
    engine = v2_session_factory.kw["bind"]

    def count_sql(*_args):
        nonlocal calls
        calls += 1

    event.listen(engine, "before_cursor_execute", count_sql)
    try:
        with v2_session_factory() as session, pytest.raises((TypeError, ValueError)):
            SqlAlchemyScrumStateMapper().add(session, invalid)
    finally:
        event.remove(engine, "before_cursor_execute", count_sql)

    assert calls == 0


def test_subclass_override_cannot_bypass_mapper_validation(v2_session_factory):
    try:
        forged_type = type(
            "ForgedScrumStateWriteSet",
            (ScrumStateWriteSet,),
            {"validate": lambda self: None},
        )
    except TypeError:
        return
    forged = object.__new__(forged_type)
    for field_name in ScrumStateWriteSet.__dataclass_fields__:
        object.__setattr__(forged, field_name, ())
    with v2_session_factory() as session, pytest.raises(TypeError):
        SqlAlchemyScrumStateMapper().add(session, forged)


def test_scalar_subclass_forgery_is_rejected_before_mapper_writes(v2_session_factory):
    class LyingUuid(UUID):
        def __ne__(self, _other):
            return False

    seed_parent_team_and_run(v2_session_factory)
    valid_work = make_write_set().work_items[0]
    forged_work = object.__new__(type(valid_work))
    for field_name in valid_work.__dataclass_fields__:
        object.__setattr__(forged_work, field_name, getattr(valid_work, field_name))
    object.__setattr__(forged_work, "id", LyingUuid(str(uuid4())))
    _assert_rejected_before_task5_write(
        v2_session_factory,
        _unsafe_write_set(work_items=(forged_work,)),
    )


def _all_sql(engine) -> tuple[list[str], object]:
    statements = []

    def capture(*event_arguments):
        statements.append(event_arguments[2])

    event.listen(engine, "before_cursor_execute", capture)
    return statements, capture


def _task5_dml(engine) -> tuple[list[str], object]:
    statements = []

    def capture(*event_arguments):
        statement = event_arguments[2]
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    return statements, capture


def _assert_rejected_before_task5_write(v2_session_factory, state) -> None:
    engine = v2_session_factory.kw["bind"]
    statements, listener = _task5_dml(engine)
    try:
        with v2_session_factory() as session, pytest.raises((TypeError, ValueError)):
            SqlAlchemyScrumStateMapper().add(session, state)
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert statements == []
    with v2_session_factory() as session:
        assert _counts(session) == (0,) * len(TASK5_MODELS)


def _assert_rejected_without_new_task5_write(v2_session_factory, state) -> None:
    engine = v2_session_factory.kw["bind"]
    with v2_session_factory() as session:
        before = _counts(session)
    statements, listener = _task5_dml(engine)
    try:
        with v2_session_factory() as session, pytest.raises((TypeError, ValueError)):
            SqlAlchemyScrumStateMapper().add(session, state)
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert statements == []
    with v2_session_factory() as session:
        assert _counts(session) == before


def test_mapper_requires_the_persisted_blueprint_before_any_write(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    with v2_session_factory.begin() as session:
        session.execute(delete(V2TeamBlueprintModel))
    _assert_rejected_before_task5_write(v2_session_factory, make_write_set())


def test_mapper_rejects_member_position_outside_persisted_blueprint(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    blueprint_index = len(BLUEPRINT.members)
    identity = MemberIdentity(member_rng_id(TEAM_ID, blueprint_index), TEAM_ID, blueprint_index)
    _assert_rejected_before_task5_write(
        v2_session_factory, ScrumStateWriteSet(member_identities=(identity,))
    )


@pytest.mark.parametrize(
    "case",
    [
        "issue_type",
        "status",
        "activity",
        "overlay_parent",
        "factor_parent",
        "scope_parents",
        "sample_parent",
    ],
)
def test_mapper_rejects_unknown_blueprint_and_missing_parent_references(
    v2_session_factory, case
):
    seed_parent_team_and_run(v2_session_factory)
    state = _invalid_reference_state(case)
    _assert_rejected_before_task5_write(v2_session_factory, state)


def _invalid_reference_state(case: str) -> ScrumStateWriteSet:
    state = make_write_set()
    if case == "issue_type":
        return ScrumStateWriteSet(work_items=(replace(state.work_items[0], issue_type="BUG"),))
    if case == "status":
        return ScrumStateWriteSet(
            work_items=(replace(state.work_items[0], current_status_key="UNKNOWN"),)
        )
    if case == "activity":
        return ScrumStateWriteSet(
            member_identities=state.member_identities,
            work_items=state.work_items,
            status_visits=(replace(state.status_visits[0], activity_key="analysis"),),
        )
    collection = {
        "overlay_parent": ("member_availability_overlays", state.member_availability_overlays),
        "factor_parent": ("work_item_factors", state.work_item_factors),
        "scope_parents": ("sprint_scope", state.sprint_scope),
        "sample_parent": ("status_visit_samples", state.status_visit_samples),
    }[case]
    return _unsafe_write_set(**{collection[0]: collection[1]})


def _unsafe_write_set(**changes: tuple[object, ...]) -> ScrumStateWriteSet:
    state = ScrumStateWriteSet()
    unsafe = object.__new__(ScrumStateWriteSet)
    for field_name in ScrumStateWriteSet.__dataclass_fields__:
        object.__setattr__(unsafe, field_name, changes.get(field_name, getattr(state, field_name)))
    return unsafe


def test_mapper_rejects_duplicate_and_mixed_run_collections_before_write(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    member = make_write_set().member_identities[0]
    _assert_rejected_before_task5_write(
        v2_session_factory, _unsafe_write_set(member_identities=(member, member))
    )
    first = make_write_set().member_business_date_consumption[0]
    second = replace(
        first,
        run_id=uuid4(),
        business_date=first.business_date.replace(day=first.business_date.day + 1),
    )
    _assert_rejected_before_task5_write(
        v2_session_factory,
        _unsafe_write_set(
            member_identities=(member,),
            member_business_date_consumption=(first, second),
        ),
    )


@pytest.mark.parametrize(
    "case",
    ["active_sprint", "open_visit", "current_scope", "evaluation_occurrence"],
)
def test_mapper_rejects_semantic_and_partial_uniqueness_conflicts_before_write(
    v2_session_factory, case
):
    seed_parent_team_and_run(v2_session_factory)
    _assert_rejected_before_task5_write(
        v2_session_factory,
        _semantic_conflict_state(case),
    )


def _semantic_conflict_state(case: str) -> ScrumStateWriteSet:
    factories = {
        "active_sprint": _two_active_sprints,
        "open_visit": _two_open_visits,
        "current_scope": _two_current_scopes,
        "evaluation_occurrence": _duplicate_evaluation_occurrence_state,
    }
    return factories[case]()


def _two_active_sprints() -> ScrumStateWriteSet:
    state = make_write_set()
    second = replace(
        state.sprints[0],
        id=sprint_rng_id(TEAM_ID, 1),
        ordinal=1,
    )
    return _unsafe_write_set(sprints=(state.sprints[0], second))


def _two_open_visits() -> ScrumStateWriteSet:
    state = make_write_set()
    second = replace(
        state.status_visits[0],
        id=visit_rng_id(ITEM_ID, 1),
        ordinal=1,
    )
    return _unsafe_write_set(
        member_identities=state.member_identities,
        work_items=state.work_items,
        status_visits=(state.status_visits[0], second),
    )


def _two_current_scopes() -> ScrumStateWriteSet:
    state = make_write_set()
    second_sprint = replace(
        state.sprints[0],
        id=sprint_rng_id(TEAM_ID, 1),
        ordinal=1,
        lifecycle=SprintLifecycle.PLANNED,
        observed_start_at=None,
    )
    identity = semantic_uuid(f"sprint-scope/{second_sprint.id}/{ITEM_ID}")
    second_scope = replace(state.sprint_scope[0], id=identity, sprint_id=second_sprint.id)
    return _unsafe_write_set(
        work_items=state.work_items,
        sprints=(state.sprints[0], second_sprint),
        sprint_scope=(state.sprint_scope[0], second_scope),
    )


def _duplicate_evaluation_occurrence_state() -> ScrumStateWriteSet:
    state = make_write_set()
    first = state.natural_decision_evaluations[0]
    next_date = first.business_date + timedelta(days=1)
    path = f"evaluation/{TEAM_ID}/{RUN_ID}/{first.decision_type.value}/{ITEM_ID}/{next_date}"
    second = replace(first, id=semantic_uuid(path), business_date=next_date)
    return _unsafe_write_set(
        work_items=state.work_items,
        natural_decision_evaluations=(first, second),
    )


def test_mapper_rejects_open_visit_that_disagrees_with_current_work_status(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    work_item = replace(state.work_items[0], current_status_key="TO_DO")
    mismatched = _unsafe_write_set(
        member_identities=state.member_identities,
        work_items=(work_item,),
        status_visits=state.status_visits,
    )
    _assert_rejected_before_task5_write(v2_session_factory, mismatched)


@pytest.mark.parametrize(
    "query",
    [ScrumStateQuery(uuid4(), uuid4()), ScrumStateQuery(TEAM_ID, uuid4())],
)
def test_load_rejects_missing_or_mixed_team_run_instead_of_partial_snapshot(
    v2_session_factory, query
):
    seed_parent_team_and_run(v2_session_factory)
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, make_write_set())
    with v2_session_factory() as session, pytest.raises(ValueError, match="team/run"):
        SqlAlchemyScrumStateMapper().load(session, query)


def test_disposed_engine_restart_reloads_every_state_type_exactly(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'task-5-restart.db'}"
    first_engine = _foreign_key_engine(database_url)
    Base.metadata.create_all(first_engine)
    first_factory = sessionmaker(bind=first_engine)
    seed_parent_team_and_run(first_factory)
    expected = ScrumStateSnapshot.from_write_set(make_write_set())
    with first_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, make_write_set())
    first_engine.dispose()

    restarted_engine = _foreign_key_engine(database_url)
    with Session(restarted_engine) as session:
        reloaded = SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))

    assert reloaded == expected
    restarted_engine.dispose()


@pytest.mark.parametrize(
    "case",
    [
        "low_digest_bit",
        "high_digest_bits",
        "message_coordinate",
        "draw_algorithm",
        "timing_profile",
        "sampler_version",
        "timing_parameters",
        "required_microseconds",
    ],
)
def test_load_authenticates_persisted_sample_against_blueprint(v2_session_factory, case):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, state)
    sample_updates, visit_updates = _sample_corruption(case, state)
    with v2_session_factory.begin() as session:
        session.execute(text("PRAGMA defer_foreign_keys=ON"))
        if visit_updates:
            session.execute(update(V2StatusVisitModel).values(**visit_updates))
        session.execute(update(V2StatusVisitSampleModel).values(**sample_updates))
    with v2_session_factory() as session, pytest.raises((TypeError, ValueError)):
        SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))


def _sample_corruption(case: str, state) -> tuple[dict[str, object], dict[str, object]]:
    sample = state.status_visit_samples[0]
    if case in {"timing_profile", "sampler_version"}:
        field = "timing_profile" if case == "timing_profile" else "touch_sampler_version"
        return {field: "FORGED_V999"}, {}
    if case == "timing_parameters":
        document = {"maximum": 0.0, "minimum": 0.0}
        return {
            "touch_parameters_json": canonical_json(document),
            "touch_parameters_sha256": canonical_sha256(document),
            "touch_sampled_hours": 0.0,
        }, {}
    if case == "required_microseconds":
        required = sample.required_work_microseconds + 1
        return {
            "required_work_microseconds": required,
            "required_work_sha256": canonical_sha256({"required_work_microseconds": required}),
        }, {
            "required_work_microseconds": required,
            "remaining_work_microseconds": required - 1_800_000_000,
        }
    return _draw_corruption(case, sample.dwell_draw_json)


def _draw_corruption(case: str, draw_json: str) -> tuple[dict[str, object], dict[str, object]]:
    document = json.loads(draw_json)
    if case == "low_digest_bit":
        tail = "0" if document["hmac_sha256"][-1] != "0" else "1"
        document["hmac_sha256"] = document["hmac_sha256"][:-1] + tail
    elif case == "high_digest_bits":
        document.update(hmac_sha256="0" * 64, u53_integer=0, unit_value=0.0)
    else:
        message = json.loads(document["canonical_message"])
        if case == "message_coordinate":
            message["entity_id"] = document["entity_id"] = str(uuid4())
        else:
            message["algorithm"] = document["algorithm"] = "FORGED_ALGORITHM"
        document["canonical_message"] = canonical_json(message)
    text = canonical_json(document)
    updates = {"dwell_draw_json": text, "dwell_draw_sha256": canonical_sha256(document)}
    if case == "high_digest_bits":
        updates.update(dwell_unit_value=0.0, dwell_sampled_hours=1.0)
    return updates, {}


def _foreign_key_engine(database_url: str):
    engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _seed_second_team_and_run(v2_session_factory) -> tuple:
    other_team = uuid4()
    other_run = uuid4()
    with v2_session_factory.begin() as session:
        session.add(
            V2TeamModel(
                id=str(other_team),
                idempotency_key="other",
                blueprint_sha256="2" * 64,
                name="Other",
                methodology="SCRUM",
                created_at=NOW,
            )
        )
        session.flush()
        session.add(
            V2RunModel(
                id=str(other_run), team_id=str(other_team), ordinal=0,
                state="ACTIVE", created_at=NOW,
            )
        )
    return other_team, other_run


@pytest.mark.parametrize("model", TASK5_MODELS[1:])
def test_foreign_keys_reject_mixed_team_run_for_every_run_table(
    v2_session_factory, model
):
    seed_parent_team_and_run(v2_session_factory)
    _, other_run = _seed_second_team_and_run(v2_session_factory)
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, make_write_set())
    values = _model_values(model, make_write_set())
    _make_semantically_distinct(model, values)
    values["run_id"] = str(other_run)
    with v2_session_factory() as session, pytest.raises(IntegrityError):
        session.add(model(**values))
        session.flush()


@pytest.mark.parametrize(
    "model", [V2MemberAvailabilityOverlayModel, V2MemberBusinessDateConsumptionModel]
)
def test_member_children_reject_cross_team_member_identity(v2_session_factory, model):
    seed_parent_team_and_run(v2_session_factory)
    other_team, _ = _seed_second_team_and_run(v2_session_factory)
    other_member = member_rng_id(other_team, 0)
    with v2_session_factory.begin() as session:
        session.add(V2MemberIdentityModel(
            id=str(other_member), team_id=str(other_team), blueprint_index=0
        ))
    values = _model_values(model, make_write_set())
    _make_semantically_distinct(model, values)
    values["member_id"] = str(other_member)
    with v2_session_factory() as session, pytest.raises(IntegrityError):
        session.add(model(**values))
        session.flush()


@pytest.mark.parametrize(
    "case",
    [
        "visit_counter",
        "cancellation_counter",
        "member_counter",
        "cancellation_evaluation",
        "member_evaluation",
        "team_counter_with_item_owner",
    ],
)
def test_create_all_schema_rejects_missing_or_wrong_typed_semantic_owner(
    v2_session_factory, case
):
    seed_parent_team_and_run(v2_session_factory)
    model, values = _invalid_owner_row(case)
    with v2_session_factory() as session:
        assert session.scalar(text("PRAGMA foreign_keys")) == 1
        with pytest.raises(IntegrityError):
            session.add(model(**values))
            session.flush()


def _invalid_owner_row(case: str) -> tuple[type, dict[str, object]]:
    entity_id = uuid4()
    if case.endswith("evaluation"):
        decision = (
            DecisionType.RISK_CANCELLATION_OUTCOME
            if case.startswith("cancellation")
            else DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME
        )
        values = _evaluation_row(decision, entity_id)
        return V2NaturalDecisionEvaluationModel, values
    kind, key = {
        "visit_counter": (SemanticCounterKind.VISIT_ORDINAL, "VISIT"),
        "cancellation_counter": (
            SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
            DecisionType.RISK_CANCELLATION_OUTCOME.value,
        ),
        "member_counter": (
            SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
            DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME.value,
        ),
        "team_counter_with_item_owner": (SemanticCounterKind.SPRINT_ORDINAL, "SCRUM"),
    }[case]
    values = _counter_row(kind, key, entity_id)
    return V2SemanticCounterModel, values


def _counter_row(kind, key: str, entity_id) -> dict[str, object]:
    is_member = key == DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME.value
    is_team = kind is SemanticCounterKind.SPRINT_ORDINAL
    scope_id = TEAM_ID if is_team else entity_id
    return {
        "team_id": str(TEAM_ID),
        "run_id": str(RUN_ID),
        "kind": kind.value,
        "scope_id": str(scope_id),
        "scope_key": key,
        "work_item_id": str(entity_id) if not is_member else None,
        "member_id": str(entity_id) if is_member else None,
        "next_value": 0,
    }


def _evaluation_row(decision: DecisionType, entity_id) -> dict[str, object]:
    is_member = decision is DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME
    return {
        "id": str(uuid4()),
        "team_id": str(TEAM_ID),
        "run_id": str(RUN_ID),
        "decision_type": decision.value,
        "semantic_entity_id": str(entity_id),
        "work_item_id": None if is_member else str(entity_id),
        "member_id": str(entity_id) if is_member else None,
        "business_date": BUSINESS_DATE,
        "occurrence": 0,
        "commit_id": str(uuid4()),
        "recorded_at": NOW,
    }


@pytest.mark.parametrize("model, updates", CHECK_VIOLATIONS)
def test_database_checks_reject_invalid_raw_rows(v2_session_factory, model, updates):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, state)
        session.execute(delete(model))
    values = _model_values(model, state)
    values.update(updates)
    with v2_session_factory() as session, pytest.raises(IntegrityError):
        session.add(model(**values))
        session.flush()


def _model_values(model, state) -> dict[str, object]:
    record = _record_for_model(model, state)
    if model is V2SemanticCounterModel:
        values = {
            "team_id": str(record.team_id),
            "run_id": str(record.run_id),
            "kind": record.scope.kind.value,
            "scope_id": str(record.scope.scope_id),
            "scope_key": record.scope.scope_key,
            "next_value": record.next_value,
        }
        if hasattr(model, "work_item_id"):
            values.update(_counter_owner_values(record))
        return values
    if model is V2NaturalDecisionEvaluationModel:
        values = {
            column.name: _persisted_value(getattr(record, column.name))
            for column in model.__table__.columns
            if column.name not in {"work_item_id", "member_id"}
        }
        if hasattr(model, "work_item_id"):
            values.update(_evaluation_owner_values(record))
        return values
    return {
        column.name: _persisted_value(getattr(record, column.name))
        for column in model.__table__.columns
    }


def _counter_owner_values(record: SemanticCounter) -> dict[str, str | None]:
    if record.scope.kind is SemanticCounterKind.VISIT_ORDINAL:
        return {"work_item_id": str(record.scope.scope_id), "member_id": None}
    if record.scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE:
        if record.scope.scope_key == DecisionType.RISK_CANCELLATION_OUTCOME.value:
            return {"work_item_id": str(record.scope.scope_id), "member_id": None}
        return {"work_item_id": None, "member_id": str(record.scope.scope_id)}
    return {"work_item_id": None, "member_id": None}


def _evaluation_owner_values(record: NaturalDecisionEvaluation) -> dict[str, str | None]:
    if record.decision_type is DecisionType.RISK_CANCELLATION_OUTCOME:
        return {"work_item_id": str(record.semantic_entity_id), "member_id": None}
    return {"work_item_id": None, "member_id": str(record.semantic_entity_id)}


def _persisted_value(value):
    return (
        value.value if hasattr(value, "value") else str(value) if hasattr(value, "hex") else value
    )


def _record_for_model(model, state):
    mapping = dict(
        zip(
            TASK5_MODELS,
            (getattr(state, name)[0] for name in MODEL_COLLECTIONS),
            strict=True,
        )
    )
    return mapping[model]


def _make_semantically_distinct(model, values: dict[str, object]) -> None:
    if "id" in values:
        values["id"] = str(uuid4())
    if model is V2MemberIdentityModel:
        values["blueprint_index"] = 1
    if model is V2MemberBusinessDateConsumptionModel:
        values["business_date"] = BUSINESS_DATE.replace(day=11)
    if model is V2WorkItemModel:
        values["creation_kind"] = "AGENT_CREATED"
    if model is V2WorkItemFactorModel:
        values["kind"] = "LATENT_COMPLEXITY"
    if model is V2SprintModel:
        values["ordinal"] = 1
        values["id"] = str(sprint_rng_id(TEAM_ID, 1))
        values["lifecycle"] = "PLANNED"
    if model is V2NaturalDecisionEvaluationModel:
        values["business_date"] = BUSINESS_DATE.replace(day=11)
    if model is V2StatusVisitSampleModel:
        values["visit_id"] = str(uuid4())
    if model is V2StatusVisitModel:
        values["ordinal"] = 1
    if model is V2SemanticCounterModel:
        values["kind"] = "SPRINT_ORDINAL"
        values["scope_id"] = str(TEAM_ID)
        values["scope_key"] = "SCRUM"


def test_partial_and_semantic_unique_constraints(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, make_write_set())
        session.add(_planned_sprint(1))

    violations = (
        _duplicate_member_index(),
        _duplicate_work_creation(),
        _duplicate_sprint_ordinal(),
        _duplicate_visit_ordinal(),
        _duplicate_scope_pair(),
        _duplicate_sample(),
        _second_active_sprint(),
        _second_open_visit(),
        _second_current_scope(),
        _duplicate_factor(),
        _duplicate_evaluation_eligibility(),
        _duplicate_evaluation_occurrence(),
    )
    for model in violations:
        with v2_session_factory() as session, pytest.raises(IntegrityError):
            session.add(model)
            session.flush()


def test_sample_required_microseconds_are_foreign_key_bound_to_visit(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, state)
        session.execute(delete(V2StatusVisitSampleModel))
    values = _model_values(V2StatusVisitSampleModel, state)
    values["required_work_microseconds"] = 1
    with v2_session_factory() as session, pytest.raises(IntegrityError):
        session.add(V2StatusVisitSampleModel(**values))
        session.flush()


@pytest.mark.parametrize("model", [V2SemanticCounterModel, V2NaturalDecisionEvaluationModel])
def test_database_rejects_unknown_natural_decision_types(v2_session_factory, model):
    seed_parent_team_and_run(v2_session_factory)
    values = _model_values(model, make_write_set())
    if model is V2SemanticCounterModel:
        values.update(kind="NATURAL_DECISION_OCCURRENCE", scope_key="UNKNOWN_DECISION")
    else:
        values.update(id=str(uuid4()), decision_type="UNKNOWN_DECISION")
    with v2_session_factory() as session, pytest.raises(IntegrityError):
        session.add(model(**values))
        session.flush()


@pytest.mark.parametrize("case", TRUE_INTEGER_COLUMNS)
def test_database_rejects_noninteger_coordinates_and_microseconds(v2_session_factory, case):
    model, field = case
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, state)
        session.execute(delete(model))
    values = _model_values(model, state)
    values[field] = 0.5
    with v2_session_factory() as session, pytest.raises(IntegrityError):
        session.add(model(**values))
        session.flush()


def test_database_rejects_infinite_sample_hours(v2_session_factory):
    seed_parent_team_and_run(v2_session_factory)
    state = make_write_set()
    with v2_session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, state)
        session.execute(delete(V2StatusVisitSampleModel))
    values = _model_values(V2StatusVisitSampleModel, state)
    values["dwell_sampled_hours"] = float("inf")
    with v2_session_factory() as session, pytest.raises(IntegrityError):
        session.add(V2StatusVisitSampleModel(**values))
        session.flush()


def _second_active_sprint():
    values = _model_values(V2SprintModel, make_write_set())
    values.update(id=str(sprint_rng_id(TEAM_ID, 2)), ordinal=2)
    return V2SprintModel(**values)


def _second_open_visit():
    values = _model_values(V2StatusVisitModel, make_write_set())
    values.update(id=str(visit_rng_id(ITEM_ID, 1)), ordinal=1)
    return V2StatusVisitModel(**values)


def _second_current_scope():
    values = _model_values(V2SprintScopeModel, make_write_set())
    values.update(id=str(uuid4()), sprint_id=str(sprint_rng_id(TEAM_ID, 1)))
    return V2SprintScopeModel(**values)


def _duplicate_factor():
    values = _model_values(V2WorkItemFactorModel, make_write_set())
    values["id"] = str(uuid4())
    return V2WorkItemFactorModel(**values)


def _duplicate_evaluation_eligibility():
    values = _model_values(V2NaturalDecisionEvaluationModel, make_write_set())
    values["id"] = str(uuid4())
    values["commit_id"] = str(uuid4())
    values["occurrence"] = 1
    return V2NaturalDecisionEvaluationModel(**values)


def _duplicate_evaluation_occurrence():
    values = _model_values(V2NaturalDecisionEvaluationModel, make_write_set())
    values.update(id=str(uuid4()), commit_id=str(uuid4()))
    values["business_date"] = BUSINESS_DATE.replace(day=11)
    return V2NaturalDecisionEvaluationModel(**values)


def _planned_sprint(ordinal: int):
    values = _model_values(V2SprintModel, make_write_set())
    values.update(
        id=str(sprint_rng_id(TEAM_ID, ordinal)), ordinal=ordinal,
        lifecycle="PLANNED", observed_start_at=None,
    )
    return V2SprintModel(**values)


def _duplicate_member_index():
    values = _model_values(V2MemberIdentityModel, make_write_set())
    values["id"] = str(uuid4())
    return V2MemberIdentityModel(**values)


def _duplicate_work_creation():
    values = _model_values(V2WorkItemModel, make_write_set())
    values["id"] = str(uuid4())
    return V2WorkItemModel(**values)


def _duplicate_sprint_ordinal():
    values = _model_values(V2SprintModel, make_write_set())
    values.update(id=str(uuid4()), ordinal=1, lifecycle="PLANNED", observed_start_at=None)
    return V2SprintModel(**values)


def _duplicate_visit_ordinal():
    values = _model_values(V2StatusVisitModel, make_write_set())
    values.update(
        id=str(uuid4()), lifecycle="CLOSED", closed_at=NOW,
        elapsed_work_microseconds=values["required_work_microseconds"],
        remaining_work_microseconds=0,
    )
    return V2StatusVisitModel(**values)


def _duplicate_scope_pair():
    values = _model_values(V2SprintScopeModel, make_write_set())
    values.update(id=str(uuid4()), removed_at=NOW)
    return V2SprintScopeModel(**values)


def _duplicate_sample():
    values = _model_values(V2StatusVisitSampleModel, make_write_set())
    return V2StatusVisitSampleModel(**values)


def test_mapper_owns_no_session_or_transaction_boundary():
    module_path = Path(__file__).parents[3] / "app" / "v2" / "persistence" / "scrum_state_mapper.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden_calls = {"begin", "commit", "rollback", "close"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not forbidden_calls & called
    assert "sessionmaker" not in module_path.read_text(encoding="utf-8")


def test_v1_tables_do_not_reference_task5_tables(v2_session_factory):
    task5_names = {model.__tablename__ for model in TASK5_MODELS}
    inspector = inspect(v2_session_factory.kw["bind"])
    legacy_tables = set(inspector.get_table_names()) - {
        name for name in inspector.get_table_names() if name.startswith("v2_")
    }
    references = {
        foreign_key["referred_table"]
        for table_name in legacy_tables
        for foreign_key in inspector.get_foreign_keys(table_name)
    }
    assert task5_names.isdisjoint(references)
