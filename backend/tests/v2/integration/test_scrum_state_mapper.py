import ast
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, event, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.v2.domain.deterministic_rng import item_rng_id, member_rng_id, sprint_rng_id, visit_rng_id
from app.v2.domain.scrum_state import (
    MemberIdentity,
    ScrumStateQuery,
    ScrumStateSnapshot,
    ScrumStateWriteSet,
)
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
from app.v2.persistence.team_models import V2RunModel, V2TeamModel
from tests.v2.live_slice_support import create_aggregate
from tests.v2.scrum_state_support import (
    BUSINESS_DATE,
    ITEM_ID,
    NOW,
    RUN_ID,
    TEAM_ID,
    make_write_set,
    seed_parent_team_and_run,
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
        return {
            "team_id": str(record.team_id),
            "run_id": str(record.run_id),
            "kind": record.scope.kind.value,
            "scope_id": str(record.scope.scope_id),
            "scope_key": record.scope.scope_key,
            "next_value": record.next_value,
        }
    return {
        column.name: _persisted_value(getattr(record, column.name))
        for column in model.__table__.columns
    }


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
