import json
from dataclasses import dataclass, replace
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, delete, event, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.v2.domain.authoritative_slice import (
    AuthoritativeTickSliceCommit,
)
from app.v2.domain.canonical_json import canonical_json, canonical_sha256
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    DeterministicRandomStream,
    item_rng_id,
    member_rng_id,
    run_rng_id,
    visit_rng_id,
)
from app.v2.domain.live_slice import (
    ActivityDetails,
    ActivityEventDraft,
    DraftEnvelope,
    LedgerPageQuery,
    ProjectionPageQuery,
)
from app.v2.domain.sampling import sample_touch, touch_bounds
from app.v2.domain.scrum_state import (
    MemberIdentity,
    ScrumStateQuery,
    ScrumStateSnapshot,
    ScrumStateWriteSet,
    SemanticCounterKind,
)
from app.v2.persistence.scrum_state_mapper import (
    ScrumStateConflictError,
    SqlAlchemyScrumStateMapper,
    _record_values,
    _require_immutable_fields,
)
from app.v2.persistence.scrum_state_models import (
    V2MemberBusinessDateConsumptionModel,
    V2MemberIdentityModel,
    V2SemanticCounterModel,
)
from app.v2.persistence.team_models import V2RunModel
from app.v2.persistence.unit_of_work import (
    NaturalEligibilityConflict,
    SemanticDeduplicationConflict,
    SqlAlchemyV2UnitOfWork,
    StaleRuntimeVersion,
    StaleSemanticCounter,
)
from tests.v2.authoritative_slice_support import (
    BASE_MEMBER_ID,
    AuthoritativeCommandSpec,
    allocation_claims,
    authoritative_write_set,
    baseline_write_set,
    counter_scope,
    eligible_claim,
    item_claim,
    make_authoritative_command,
    member_eligible_claim,
    member_natural_counter_claim,
    natural_counter_claim,
    new_sprint_scope,
    new_work_item,
    sprint_claim,
    visit_claim,
)
from tests.v2.live_slice_support import create_aggregate, make_tick_commit
from tests.v2.scrum_state_support import (
    BLUEPRINT,
    BUSINESS_DATE,
    LATER,
    NOW,
    RUN_ID,
    TEAM_ID,
    make_consumption,
    make_member,
    make_overlay,
    make_sample_for,
    make_sprint,
    make_visit,
    make_work_item,
)

STATE_INSERT_FRAGMENTS = (
    "INSERT INTO v2_member_availability_overlays",
    "INSERT INTO v2_member_business_date_consumption",
    "INSERT INTO v2_work_items",
    "INSERT INTO v2_work_item_factors",
    "INSERT INTO v2_sprints",
    "INSERT INTO v2_sprint_scope",
    "INSERT INTO v2_status_visits",
    "INSERT INTO v2_status_visit_samples",
)
OTHER_WRITE_FRAGMENTS = (
    "UPDATE v2_team_runtimes",
    "INSERT INTO v2_natural_decision_evaluations",
    "INSERT INTO v2_activity_events",
    "INSERT INTO v2_ground_truth_records",
    "INSERT INTO v2_projection_intents",
)
MUTABLE_COLLECTIONS = {
    "overlay": "member_availability_overlays",
    "consumption": "member_business_date_consumption",
    "work": "work_items",
    "sprint": "sprints",
    "scope": "sprint_scope",
    "visit": "status_visits",
}


@dataclass(frozen=True)
class AtomicContext:
    session_factory: object
    aggregate: object
    baseline: ScrumStateSnapshot
    baseline_runtime: object
    command: AuthoritativeTickSliceCommit


@dataclass(frozen=True)
class StoredView:
    runtime: object
    state: ScrumStateSnapshot
    activity: tuple[object, ...]
    ground_truth: tuple[object, ...]
    projection: tuple[object, ...]


@dataclass(frozen=True)
class DeletedTeamCounterCase:
    state: ScrumStateWriteSet
    claim: object
    seed: bool


class CountingSessionFactory:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.delegate()


class CommitFailureSession(Session):
    rollbacks = 0

    def commit(self) -> None:
        raise RuntimeError("injected commit failure")

    def rollback(self) -> None:
        CommitFailureSession.rollbacks += 1
        super().rollback()


class FinalFlushFailureSession(Session):
    def flush(self, objects=None) -> None:
        connection = self.connection()
        if connection.info.get("task6_projection_inserts") == 2:
            raise RuntimeError("injected final flush failure")
        super().flush(objects)


@pytest.fixture
def atomic_context(v2_session_factory, resolved_blueprint_json, requested_at):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    assert (aggregate.team.id, aggregate.run.id) == (TEAM_ID, RUN_ID)
    mapper = SqlAlchemyScrumStateMapper()
    with v2_session_factory.begin() as session:
        mapper.add(session, baseline_write_set())
    with v2_session_factory() as session:
        baseline = mapper.load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
    command = make_authoritative_command(AuthoritativeCommandSpec(aggregate))
    runtime = SqlAlchemyV2UnitOfWork(v2_session_factory).get_runtime(TEAM_ID)
    return AtomicContext(v2_session_factory, aggregate, baseline, runtime, command)


def _stored_view(context: AtomicContext) -> StoredView:
    unit_of_work = SqlAlchemyV2UnitOfWork(context.session_factory)
    with context.session_factory() as session:
        state = SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
    activity = unit_of_work.page_activity(LedgerPageQuery(TEAM_ID, RUN_ID, None, 100)).items
    ground = unit_of_work.page_ground_truth(LedgerPageQuery(TEAM_ID, RUN_ID, None, 100)).items
    projection = unit_of_work.page_projection(ProjectionPageQuery(TEAM_ID, RUN_ID, None, 100)).items
    return StoredView(unit_of_work.get_runtime(TEAM_ID), state, activity, ground, projection)


def _baseline_view(context: AtomicContext) -> StoredView:
    return StoredView(context.baseline_runtime, context.baseline, (), (), ())


def _single_after_image(case: str, item: object) -> ScrumStateWriteSet:
    return ScrumStateWriteSet(**{MUTABLE_COLLECTIONS[case]: (item,)})


def _forbidden_after_image(case: str) -> ScrumStateWriteSet:
    items = {
        "overlay": replace(make_overlay(), member_id=BASE_MEMBER_ID),
        "work": replace(new_work_item(), created_at=NOW - timedelta(minutes=1)),
        "sprint": replace(
            make_sprint(),
            planned_end_at=make_sprint().planned_end_at + timedelta(days=1),
            updated_at=LATER,
        ),
        "scope": replace(new_sprint_scope(), added_at=NOW - timedelta(minutes=1)),
        "visit": replace(make_visit(), entered_at=NOW - timedelta(minutes=1)),
    }
    return _single_after_image(case, items[case])


def _allowed_after_image(case: str) -> ScrumStateWriteSet:
    items = {
        "overlay": replace(make_overlay(), availability_fraction=0.5),
        "consumption": replace(
            make_consumption(), consumed_labor_microseconds=3_600_000_001
        ),
        "work": replace(new_work_item(), relative_rank=4, updated_at=LATER),
        "sprint": replace(make_sprint(), updated_at=LATER),
        "scope": replace(new_sprint_scope(), removed_at=LATER),
        "visit": replace(make_visit(), queue_microseconds=300_000_001),
    }
    return _single_after_image(case, items[case])


def _claimed_replay(case: str) -> tuple[ScrumStateWriteSet, object]:
    if case == "sprint":
        changed = replace(make_sprint(), updated_at=LATER)
        return ScrumStateWriteSet(sprints=(changed,)), sprint_claim()
    if case == "item":
        changed = replace(new_work_item(), relative_rank=4, updated_at=LATER)
        return ScrumStateWriteSet(work_items=(changed,)), item_claim()
    changed = replace(make_visit(), queue_microseconds=300_000_001)
    return ScrumStateWriteSet(status_visits=(changed,)), visit_claim()


def _counter_values(snapshot: ScrumStateSnapshot) -> dict[tuple[str, str], int]:
    return {
        (counter.scope.kind.value, counter.scope.scope_key): counter.next_value
        for counter in snapshot.semantic_counters
    }


def _assert_touched_state_is_present(snapshot: ScrumStateSnapshot) -> None:
    touched = authoritative_write_set()._collection_values()
    stored = snapshot._collection_values()
    for touched_items, stored_items in zip(touched, stored, strict=True):
        assert all(item in stored_items for item in touched_items)


def _counter_key(counter) -> tuple[str, str, str]:
    scope = counter.scope
    return scope.kind.value, str(scope.scope_id), scope.scope_key


def _assert_committed_ledgers(committed, command) -> None:
    ledgers = (
        committed.live_slice.activity,
        committed.live_slice.ground_truth,
        committed.live_slice.projection_intents,
    )
    for rows in ledgers:
        assert tuple(item.append_sequence for item in rows) == (1, 2)
        assert tuple(item.transaction_sequence for item in rows) == (0, 1)
        assert all(item.commit_id == command.live_slice.commit_id for item in rows)


def _assert_success_state(committed, context: AtomicContext) -> None:
    assert committed.live_slice.runtime.version == 1
    assert committed.state == _stored_view(context).state
    assert len(committed.state.member_identities) == 2
    assert len(committed.state.work_items) == 2
    assert len(committed.state.status_visit_samples) == 1
    _assert_touched_state_is_present(committed.state)
    expected = {
        _counter_key_from_claim(claim): claim.expected_next + claim.count
        for claim in context.command.counter_claims
    }
    assert {_counter_key(item): item.next_value for item in committed.counters} == expected


def _counter_key_from_claim(claim) -> tuple[str, str, str]:
    scope = claim.scope
    return scope.kind.value, str(scope.scope_id), scope.scope_key


def _assert_success_evaluations(committed, context: AtomicContext) -> None:
    evaluations = committed.natural_decision_evaluations
    assert {item.decision_type for item in evaluations} == {
        DecisionType.RISK_CANCELLATION_OUTCOME,
        DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME,
    }
    assert all(item.occurrence == 0 for item in evaluations)
    assert all(item.commit_id == context.command.live_slice.commit_id for item in evaluations)
    assert all(item.recorded_at == context.command.live_slice.recorded_at for item in evaluations)
    actual = {
        (item.decision_type, item.semantic_entity_id, item.business_date, item.occurrence)
        for item in evaluations
    }
    expected = {
        (claim.decision.decision_type, claim.decision.entity_id, claim.business_date, 0)
        for claim in context.command.natural_decision_claims
    }
    assert actual == expected


def _assert_write_order(statements: list[str]) -> None:
    ordered = (
        "UPDATE v2_team_runtimes",
        "INSERT INTO v2_member_availability_overlays",
        "UPDATE v2_semantic_counters",
        "INSERT INTO v2_natural_decision_evaluations",
        "INSERT INTO v2_activity_events",
        "INSERT INTO v2_ground_truth_records",
        "INSERT INTO v2_projection_intents",
    )
    positions = [_position(statements, fragment) for fragment in ordered]
    assert positions == sorted(positions)
    first_counter = _position(statements, "UPDATE v2_semantic_counters")
    assert all(
        _position(statements, fragment) < first_counter for fragment in STATE_INSERT_FRAGMENTS
    )


def _write_listener(statements: list[str]):
    def capture(*arguments):
        statement = arguments[2]
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            statements.append(statement)

    return capture


def _position(statements: list[str], fragment: str) -> int:
    return next(index for index, statement in enumerate(statements) if fragment in statement)


def test_success_commits_runtime_state_claims_evaluations_and_ledgers_in_order(atomic_context):
    statements: list[str] = []
    engine = atomic_context.session_factory.kw["bind"]
    listener = _write_listener(statements)
    event.listen(engine, "before_cursor_execute", listener)
    try:
        committed = SqlAlchemyV2UnitOfWork(
            atomic_context.session_factory
        ).commit_authoritative_slice(atomic_context.command)
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    _assert_success_state(committed, atomic_context)
    _assert_success_evaluations(committed, atomic_context)
    _assert_committed_ledgers(committed, atomic_context.command)
    _assert_write_order(statements)
    assert all(item in committed.state.semantic_counters for item in committed.counters)
    assert all(
        item in committed.state.natural_decision_evaluations
        for item in committed.natural_decision_evaluations
    )


@pytest.mark.parametrize("case", ["overlay", "work", "sprint", "scope", "visit"])
def test_forbidden_after_image_coordinate_is_typed_and_fully_rolled_back(
    atomic_context, case
):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    before = _stored_view(atomic_context)
    live = make_tick_commit(atomic_context.aggregate, 1, f"forbidden-{case}")
    command = AuthoritativeTickSliceCommit(live, _forbidden_after_image(case), (), ())

    with pytest.raises(SemanticDeduplicationConflict):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


@pytest.mark.parametrize("case", tuple(MUTABLE_COLLECTIONS))
def test_each_mutable_after_image_accepts_one_permitted_field_update(atomic_context, case):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    live = make_tick_commit(atomic_context.aggregate, 1, f"allowed-{case}")
    changed = _allowed_after_image(case)

    committed = unit_of_work.commit_authoritative_slice(
        AuthoritativeTickSliceCommit(live, changed, (), ())
    )

    collection = getattr(committed.state, MUTABLE_COLLECTIONS[case])
    assert getattr(changed, MUTABLE_COLLECTIONS[case])[0] in collection


def test_consumption_identity_coordinates_are_explicitly_immutable(atomic_context):
    SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
        atomic_context.command
    )
    original = make_consumption()
    changed = replace(original, business_date=original.business_date + timedelta(days=1))
    identity = (str(TEAM_ID), str(RUN_ID), str(original.member_id), original.business_date)
    with atomic_context.session_factory() as session:
        model = session.get(V2MemberBusinessDateConsumptionModel, identity)
        assert model is not None
        with pytest.raises(ScrumStateConflictError):
            _require_immutable_fields(
                model,
                _record_values(changed),
                V2MemberBusinessDateConsumptionModel,
            )


def _other_team_overlay_state(other: object) -> ScrumStateWriteSet:
    member_id = member_rng_id(other.team.id, 1)
    member = MemberIdentity(member_id, other.team.id, 1)
    overlay = replace(
        make_overlay(),
        team_id=other.team.id,
        run_id=other.run.id,
        member_id=member_id,
    )
    return ScrumStateWriteSet(
        member_identities=(member,),
        member_availability_overlays=(overlay,),
    )


def test_global_overlay_id_cannot_steal_a_row_from_another_team(
    atomic_context, resolved_blueprint_json, requested_at
):
    document = json.loads(resolved_blueprint_json)
    document["team"]["name"] = "Authoritative collision team"
    other = create_aggregate(
        atomic_context.session_factory,
        canonical_json(document),
        requested_at,
    )
    other_state = _other_team_overlay_state(other)
    mapper = SqlAlchemyScrumStateMapper()
    with atomic_context.session_factory.begin() as session:
        assert session.scalar(text("PRAGMA foreign_keys")) == 1
        mapper.add(session, other_state)
    with atomic_context.session_factory() as session:
        other_before = mapper.load(session, ScrumStateQuery(other.team.id, other.run.id))
    before = _stored_view(atomic_context)
    live = make_tick_commit(atomic_context.aggregate, 0, "cross-team-overlay")
    state = ScrumStateWriteSet(member_availability_overlays=(make_overlay(),))

    with pytest.raises(SemanticDeduplicationConflict):
        SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
            AuthoritativeTickSliceCommit(live, state, (), ())
        )

    assert _stored_view(atomic_context) == before
    with atomic_context.session_factory() as session:
        assert mapper.load(session, ScrumStateQuery(other.team.id, other.run.id)) == other_before


def _seed_cross_run_item(context: AtomicContext) -> tuple[object, object]:
    second_run_id = run_rng_id(TEAM_ID, 1)
    item = replace(_sequence_two_item(), run_id=second_run_id)
    with context.session_factory.begin() as session:
        session.add(
            V2RunModel(
                id=str(second_run_id),
                team_id=str(TEAM_ID),
                ordinal=1,
                state="CREATED",
                created_at=NOW,
            )
        )
    with context.session_factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(
            session,
            ScrumStateWriteSet(work_items=(item,)),
        )
    return second_run_id, item


def test_global_work_id_cannot_move_a_row_between_runs(atomic_context):
    second_run_id, item = _seed_cross_run_item(atomic_context)
    mapper = SqlAlchemyScrumStateMapper()
    with atomic_context.session_factory() as session:
        other_before = mapper.load(session, ScrumStateQuery(TEAM_ID, second_run_id))
    before = _stored_view(atomic_context)
    live = make_tick_commit(atomic_context.aggregate, 0, "cross-run-work")
    state = ScrumStateWriteSet(work_items=(replace(item, run_id=RUN_ID),))

    with pytest.raises(SemanticDeduplicationConflict):
        SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
            AuthoritativeTickSliceCommit(live, state, (), ())
        )

    assert _stored_view(atomic_context) == before
    with atomic_context.session_factory() as session:
        assert mapper.load(session, ScrumStateQuery(TEAM_ID, second_run_id)) == other_before


@pytest.mark.parametrize("fragment", (*STATE_INSERT_FRAGMENTS, *OTHER_WRITE_FRAGMENTS))
def test_failure_at_each_write_class_rolls_back_every_authoritative_row(atomic_context, fragment):
    engine = atomic_context.session_factory.kw["bind"]

    def fail_write(*arguments):
        if fragment.upper() in arguments[2].upper():
            raise RuntimeError(f"injected {fragment} failure")

    event.listen(engine, "before_cursor_execute", fail_write)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
                atomic_context.command
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_write)

    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


@pytest.mark.parametrize("target_update", range(1, 6))
def test_failure_at_each_counter_update_rolls_back_without_a_gap(atomic_context, target_update):
    engine = atomic_context.session_factory.kw["bind"]
    seen = 0

    def fail_counter(*arguments):
        nonlocal seen
        if "UPDATE v2_semantic_counters" not in arguments[2]:
            return
        seen += 1
        if seen == target_update:
            raise RuntimeError(f"injected counter {target_update} failure")

    event.listen(engine, "before_cursor_execute", fail_counter)
    try:
        with pytest.raises(RuntimeError, match="injected counter"):
            SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
                atomic_context.command
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_counter)

    assert seen == target_update
    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


def _mark_projection_inserts(*arguments) -> None:
    connection, statement = arguments[0], arguments[2]
    if "INSERT INTO v2_projection_intents" in statement:
        count = connection.info.get("task6_projection_inserts", 0)
        connection.info["task6_projection_inserts"] = count + 1


def test_final_flush_failure_rolls_back_every_authoritative_row(atomic_context):
    engine = atomic_context.session_factory.kw["bind"]
    failing_factory = sessionmaker(bind=engine, class_=FinalFlushFailureSession)
    event.listen(engine, "before_cursor_execute", _mark_projection_inserts)
    try:
        with pytest.raises(RuntimeError, match="final flush"):
            SqlAlchemyV2UnitOfWork(failing_factory).commit_authoritative_slice(
                atomic_context.command
            )
    finally:
        event.remove(engine, "before_cursor_execute", _mark_projection_inserts)

    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


def test_commit_failure_rolls_back_every_authoritative_row(atomic_context):
    engine = atomic_context.session_factory.kw["bind"]
    CommitFailureSession.rollbacks = 0
    failing_factory = sessionmaker(bind=engine, class_=CommitFailureSession)

    with pytest.raises(RuntimeError, match="commit failure"):
        SqlAlchemyV2UnitOfWork(failing_factory).commit_authoritative_slice(atomic_context.command)

    assert _stored_view(atomic_context) == _baseline_view(atomic_context)
    assert CommitFailureSession.rollbacks == 1


@pytest.mark.parametrize("forgery", ["claim", "state", "instant", "run"])
def test_uow_revalidates_forged_commands_before_requesting_a_session(atomic_context, forgery):
    command = atomic_context.command
    if forgery == "claim":
        object.__setattr__(command.counter_claims[0], "expected_next", False)
    elif forgery == "state":
        object.__setattr__(command.state.work_items[0], "creation_sequence", True)
    elif forgery == "instant":
        naive = command.live_slice.recorded_at.replace(tzinfo=None)
        object.__setattr__(command.live_slice, "recorded_at", naive)
    else:
        object.__setattr__(command.live_slice, "run_id", RUN_ID.__class__(int=1))
    counting = CountingSessionFactory(atomic_context.session_factory)

    with pytest.raises((TypeError, ValueError)):
        SqlAlchemyV2UnitOfWork(counting).commit_authoritative_slice(command)

    assert counting.calls == 0
    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


def test_uow_rejects_duck_typed_command_before_requesting_a_session(atomic_context):
    class Impostor:
        @staticmethod
        def validate() -> None:
            return None

    counting = CountingSessionFactory(atomic_context.session_factory)

    with pytest.raises(TypeError, match="AuthoritativeTickSliceCommit"):
        SqlAlchemyV2UnitOfWork(counting).commit_authoritative_slice(Impostor())

    assert counting.calls == 0


def _crossbound_natural_command(
    context: AtomicContext, case: str
) -> AuthoritativeTickSliceCommit:
    is_cancellation = case == "cancellation-member"
    decision_type = (
        DecisionType.RISK_CANCELLATION_OUTCOME
        if is_cancellation
        else DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME
    )
    entity_id = make_member().id if is_cancellation else make_work_item().id
    template = eligible_claim() if is_cancellation else member_eligible_claim()
    eligible = replace(
        template,
        decision=DecisionOccurrence(entity_id, decision_type, 0),
    )
    scope = counter_scope(
        SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
        entity_id,
        decision_type.value,
    )
    counter = replace(natural_counter_claim(), scope=scope)
    live = make_tick_commit(context.aggregate, 0, f"crossbound-{case}")
    return AuthoritativeTickSliceCommit(live, ScrumStateWriteSet(), (counter,), (eligible,))


@pytest.mark.parametrize("case", ["cancellation-member", "unavailable-work"])
def test_visible_wrong_natural_owner_rejects_before_requesting_session(
    atomic_context, case
):
    command = _crossbound_natural_command(atomic_context, case)
    wrong_state = (
        ScrumStateWriteSet(member_identities=(make_member(),))
        if case == "cancellation-member"
        else ScrumStateWriteSet(work_items=(make_work_item(),))
    )
    object.__setattr__(command, "state", wrong_state)
    counting = CountingSessionFactory(atomic_context.session_factory)

    with pytest.raises(ValueError, match="owner"):
        SqlAlchemyV2UnitOfWork(counting).commit_authoritative_slice(command)

    assert counting.calls == 0
    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


def _stale_runtime_command(context: AtomicContext) -> AuthoritativeTickSliceCommit:
    unique_consumption = replace(
        authoritative_write_set().member_business_date_consumption[0],
        business_date=BUSINESS_DATE + timedelta(days=1),
    )
    loser_state = replace(
        authoritative_write_set(),
        member_business_date_consumption=(unique_consumption,),
    )
    return make_authoritative_command(
        AuthoritativeCommandSpec(
            context.aggregate,
            label="stale-runtime",
            state=loser_state,
        )
    )


def test_runtime_stale_writer_leaves_no_loser_state_or_ledgers(atomic_context):
    first = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    second = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    winner = first.commit_authoritative_slice(atomic_context.command)

    with pytest.raises(StaleRuntimeVersion):
        second.commit_authoritative_slice(_stale_runtime_command(atomic_context))

    view = _stored_view(atomic_context)
    assert view == StoredView(
        winner.live_slice.runtime,
        winner.state,
        winner.live_slice.activity,
        winner.live_slice.ground_truth,
        winner.live_slice.projection_intents,
    )


def test_stale_counter_rolls_back_runtime_state_and_ledgers(atomic_context):
    scope = sprint_claim().scope
    with atomic_context.session_factory.begin() as session:
        session.execute(
            update(V2SemanticCounterModel)
            .where(V2SemanticCounterModel.team_id == str(TEAM_ID))
            .where(V2SemanticCounterModel.run_id == str(RUN_ID))
            .where(V2SemanticCounterModel.kind == scope.kind.value)
            .where(V2SemanticCounterModel.scope_id == str(scope.scope_id))
            .where(V2SemanticCounterModel.scope_key == scope.scope_key)
            .values(next_value=1)
        )
    before = _stored_view(atomic_context)

    with pytest.raises(StaleSemanticCounter):
        SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
            atomic_context.command
        )

    assert _stored_view(atomic_context) == before


def test_identical_authoritative_replay_is_idempotent_and_consumes_no_claim_twice(
    atomic_context,
):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    initial = unit_of_work.commit_authoritative_slice(atomic_context.command)
    replay = make_authoritative_command(
        AuthoritativeCommandSpec(
            atomic_context.aggregate,
            expected_runtime_version=1,
            label="authoritative",
        )
    )

    repeated = unit_of_work.commit_authoritative_slice(replay)

    assert repeated.state == initial.state
    assert repeated.counters == initial.counters
    assert repeated.natural_decision_evaluations == initial.natural_decision_evaluations
    assert repeated.live_slice.activity == initial.live_slice.activity
    assert repeated.live_slice.ground_truth == initial.live_slice.ground_truth
    assert repeated.live_slice.projection_intents == initial.live_slice.projection_intents
    assert repeated.live_slice.runtime.version == 2


@pytest.mark.parametrize("case", ["sprint", "item", "visit"])
def test_advanced_allocation_replay_requires_exact_persisted_after_image(
    atomic_context, case
):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    before = _stored_view(atomic_context)
    state, claim = _claimed_replay(case)
    live = make_tick_commit(atomic_context.aggregate, 1, f"changed-{case}-replay")
    command = AuthoritativeTickSliceCommit(live, state, (claim,), ())

    with pytest.raises((SemanticDeduplicationConflict, StaleSemanticCounter)):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


def test_advanced_allocation_replay_rejects_an_unrelated_state_mutation(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    before = _stored_view(atomic_context)
    state = ScrumStateWriteSet(
        sprints=(make_sprint(),),
        member_availability_overlays=(
            replace(make_overlay(), availability_fraction=0.5),
        ),
    )
    live = make_tick_commit(atomic_context.aggregate, 1, "unrelated-replay-mutation")
    command = AuthoritativeTickSliceCommit(live, state, (sprint_claim(),), ())

    with pytest.raises((SemanticDeduplicationConflict, StaleSemanticCounter)):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


def test_advanced_allocation_replay_rejects_fresh_ledger_semantic_keys(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    before = _stored_view(atomic_context)
    live = make_tick_commit(atomic_context.aggregate, 1, "fresh-ledger-replay")
    state = ScrumStateWriteSet(sprints=(make_sprint(),))
    command = AuthoritativeTickSliceCommit(live, state, (sprint_claim(),), ())

    with pytest.raises((SemanticDeduplicationConflict, StaleSemanticCounter)):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


def test_advanced_replay_cannot_mix_a_current_allocation_claim(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    before = _stored_view(atomic_context)
    state = ScrumStateWriteSet(
        sprints=(make_sprint(),),
        work_items=(_sequence_two_item(),),
    )
    live = make_tick_commit(atomic_context.aggregate, 1, "mixed-replay-allocation")
    command = AuthoritativeTickSliceCommit(
        live,
        state,
        (sprint_claim(), item_claim(2)),
        (),
    )

    with pytest.raises(StaleSemanticCounter):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


def test_advanced_replay_cannot_consume_a_fresh_natural_occurrence(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    before = _stored_view(atomic_context)
    next_date = BUSINESS_DATE + timedelta(days=1)
    natural = replace(eligible_claim(1), business_date=next_date)
    live = make_tick_commit(atomic_context.aggregate, 1, "mixed-replay-natural")
    command = AuthoritativeTickSliceCommit(
        live,
        ScrumStateWriteSet(sprints=(make_sprint(),)),
        (sprint_claim(), natural_counter_claim(1)),
        (natural,),
    )

    with pytest.raises(StaleSemanticCounter):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


def _existing_update_state() -> ScrumStateWriteSet:
    work = replace(make_work_item(), relative_rank=3, updated_at=LATER)
    sprint = replace(make_sprint(), updated_at=LATER)
    visit = replace(make_visit(), queue_microseconds=300_000_001)
    return ScrumStateWriteSet(work_items=(work,), sprints=(sprint,), status_visits=(visit,))


def test_existing_sparse_after_images_update_without_reconsuming_claims(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    live = make_tick_commit(atomic_context.aggregate, 1, "existing-update")
    command = AuthoritativeTickSliceCommit(live, _existing_update_state(), (), ())

    committed = unit_of_work.commit_authoritative_slice(command)

    assert committed.live_slice.runtime.version == 2
    assert committed.counters == ()
    assert committed.state.work_items[0].relative_rank == 3
    assert committed.state.status_visits[0].queue_microseconds == 300_000_001


def _sequence_two_item():
    item = new_work_item()
    return replace(
        item,
        id=item_rng_id(TEAM_ID, item.creation_kind, 2),
        creation_sequence=2,
    )


def test_existing_update_and_new_allocation_share_one_scope(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    state = ScrumStateWriteSet(work_items=(make_work_item(), _sequence_two_item()))
    live = make_tick_commit(atomic_context.aggregate, 1, "mixed-allocation")
    command = AuthoritativeTickSliceCommit(live, state, (item_claim(2),), ())

    committed = unit_of_work.commit_authoritative_slice(command)

    assert _counter_values(committed.state)[("ITEM_SEQUENCE", "INITIAL_BACKLOG")] == 3
    assert _sequence_two_item() in committed.state.work_items


def test_unclaimed_new_ordinal_row_is_typed_and_fully_rolled_back(atomic_context):
    live = make_tick_commit(atomic_context.aggregate, 0, "missing-allocation-claim")
    state = ScrumStateWriteSet(work_items=(new_work_item(),))
    command = AuthoritativeTickSliceCommit(live, state, (), ())

    with pytest.raises(StaleSemanticCounter):
        SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


def _new_owner_command(context: AtomicContext) -> AuthoritativeTickSliceCommit:
    item = new_work_item()
    claims, natural = _new_owner_claims(item)
    live = make_tick_commit(context.aggregate, 0, "new-owner-counters")
    return AuthoritativeTickSliceCommit(
        live,
        _new_owner_state(item),
        (item_claim(), *claims),
        (natural,),
    )


def _new_owner_state(item) -> ScrumStateWriteSet:
    visits = _new_owner_visit_state(item)
    return replace(
        visits,
        member_identities=(make_member(),),
        work_items=(item,),
    )


def _new_owner_visit_state(item) -> ScrumStateWriteSet:
    visit_id = visit_rng_id(item.id, 0)
    required = _required_work_for_visit(item, visit_id)
    visit = replace(
        make_visit(),
        id=visit_id,
        work_item_id=item.id,
        required_work_microseconds=required,
        elapsed_work_microseconds=0,
        remaining_work_microseconds=required,
        credited_labor_microseconds=0,
    )
    return ScrumStateWriteSet(
        status_visits=(visit,),
        status_visit_samples=(make_sample_for(BLUEPRINT, item, visit),),
    )


def _new_owner_claims(item):
    visit_counter = replace(
        item_claim(),
        scope=counter_scope(SemanticCounterKind.VISIT_ORDINAL, item.id, "VISIT"),
        expected_next=0,
    )
    natural_counter = replace(
        natural_counter_claim(),
        scope=counter_scope(
            SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
            item.id,
            DecisionType.RISK_CANCELLATION_OUTCOME.value,
        ),
    )
    natural = replace(
        eligible_claim(),
        decision=DecisionOccurrence(
            item.id,
            DecisionType.RISK_CANCELLATION_OUTCOME,
            0,
        ),
    )
    return (visit_counter, natural_counter), natural


def _owner_only_command(context: AtomicContext) -> AuthoritativeTickSliceCommit:
    state = ScrumStateWriteSet(
        member_identities=(make_member(),),
        work_items=(new_work_item(),),
    )
    live = make_tick_commit(context.aggregate, 0, "new-owners-only")
    return AuthoritativeTickSliceCommit(live, state, (item_claim(),), ())


def _later_owner_claim_command(context: AtomicContext) -> AuthoritativeTickSliceCommit:
    item = new_work_item()
    claims, cancellation = _new_owner_claims(item)
    member_counter = replace(
        member_natural_counter_claim(),
        scope=counter_scope(
            SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
            make_member().id,
            DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME.value,
        ),
    )
    member_decision = DecisionOccurrence(
        make_member().id,
        DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME,
        0,
    )
    member_claim = replace(member_eligible_claim(), decision=member_decision)
    live = make_tick_commit(context.aggregate, 1, "later-owner-claims")
    return AuthoritativeTickSliceCommit(
        live,
        _new_owner_visit_state(item),
        (*claims, member_counter),
        (cancellation, member_claim),
    )


def _owner_child_keys() -> set[tuple[str, str, str]]:
    item = new_work_item()
    return {
        ("VISIT_ORDINAL", str(item.id), "VISIT"),
        (
            "NATURAL_DECISION_OCCURRENCE",
            str(item.id),
            DecisionType.RISK_CANCELLATION_OUTCOME.value,
        ),
        (
            "NATURAL_DECISION_OCCURRENCE",
            str(make_member().id),
            DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME.value,
        ),
    }


def _required_work_for_visit(item, visit_id) -> int:
    stream = DeterministicRandomStream(BLUEPRINT.seed, item.team_id, item.run_id)
    decision = DecisionOccurrence(visit_id, DecisionType.STATUS_TOUCH, 0)
    unit_value = stream.draw(decision, 0).unit_value
    entry = next(
        value
        for value in BLUEPRINT.timing.entries
        if (value.status_key, value.issue_type, value.story_points)
        == (item.current_status_key, item.issue_type, item.story_points)
    )
    hours = sample_touch(touch_bounds(entry), unit_value).sampled_hours
    numerator, denominator = hours.as_integer_ratio()
    quotient, remainder = divmod(numerator * 3_600_000_000, denominator)
    return quotient + (
        2 * remainder > denominator or (2 * remainder == denominator and quotient % 2 == 1)
    )


def test_new_item_initializes_first_visit_and_natural_counters_atomically(atomic_context):
    committed = SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
        _new_owner_command(atomic_context)
    )

    values = {_counter_key(item): item.next_value for item in committed.counters}
    item = new_work_item()
    assert values[("VISIT_ORDINAL", str(item.id), "VISIT")] == 1
    natural_key = ("NATURAL_DECISION_OCCURRENCE", str(item.id), "RISK_CANCELLATION_OUTCOME")
    assert values[natural_key] == 1
    assert committed.natural_decision_evaluations[0].semantic_entity_id == item.id


def test_new_owner_counter_initialization_rolls_back_with_later_failure(atomic_context):
    engine = atomic_context.session_factory.kw["bind"]

    def fail_activity(*arguments):
        if "INSERT INTO v2_activity_events" in arguments[2]:
            raise RuntimeError("injected after counter initialization")

    event.listen(engine, "before_cursor_execute", fail_activity)
    try:
        with pytest.raises(RuntimeError, match="counter initialization"):
            SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
                _new_owner_command(atomic_context)
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_activity)

    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


def _fresh_session_factory(context: AtomicContext):
    current_engine = context.session_factory.kw["bind"]
    database_url = str(current_engine.url)
    current_engine.dispose()
    engine = create_engine(database_url)
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine, sessionmaker(bind=engine)


def test_new_owners_seed_child_counters_for_restart_and_later_claims(atomic_context):
    first = SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
        _owner_only_command(atomic_context)
    )
    values = {_counter_key(item): item.next_value for item in first.state.semantic_counters}
    assert all(values[key] == 0 for key in _owner_child_keys())
    restarted_engine, restarted_factory = _fresh_session_factory(atomic_context)
    try:
        committed = SqlAlchemyV2UnitOfWork(restarted_factory).commit_authoritative_slice(
            _later_owner_claim_command(atomic_context)
        )
        current = {_counter_key(item): item.next_value for item in committed.counters}
        assert all(current[key] == 1 for key in _owner_child_keys())
        with restarted_factory() as session:
            exact = SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
        assert exact == committed.state
    finally:
        restarted_engine.dispose()


def test_seeded_child_counters_roll_back_with_their_new_owners(atomic_context):
    engine = atomic_context.session_factory.kw["bind"]

    def fail_after_seeds(*arguments):
        if "INSERT INTO v2_activity_events" in arguments[2]:
            raise RuntimeError("injected after owner counter seeds")

    event.listen(engine, "before_cursor_execute", fail_after_seeds)
    try:
        with pytest.raises(RuntimeError, match="owner counter seeds"):
            SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
                _owner_only_command(atomic_context)
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_after_seeds)
    assert _stored_view(atomic_context) == _baseline_view(atomic_context)


def test_deleted_established_member_and_counter_are_not_recreated(atomic_context):
    with atomic_context.session_factory.begin() as session:
        result = session.execute(
            delete(V2MemberIdentityModel).where(
                V2MemberIdentityModel.id == str(make_member().id)
            )
        )
        assert result.rowcount == 1
    before = _stored_view(atomic_context)

    with pytest.raises(SemanticDeduplicationConflict):
        SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
            atomic_context.command
        )

    assert _stored_view(atomic_context) == before


def test_deleted_established_child_counter_is_not_recreated(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(_owner_only_command(atomic_context))
    counter = _new_owner_claims(new_work_item())[0][1]
    scope = counter.scope
    with atomic_context.session_factory.begin() as session:
        result = session.execute(
            delete(V2SemanticCounterModel).where(
                V2SemanticCounterModel.team_id == str(TEAM_ID),
                V2SemanticCounterModel.run_id == str(RUN_ID),
                V2SemanticCounterModel.kind == scope.kind.value,
                V2SemanticCounterModel.scope_id == str(scope.scope_id),
                V2SemanticCounterModel.scope_key == scope.scope_key,
            )
        )
        assert result.rowcount == 1
    before = _stored_view(atomic_context)
    cancellation = _new_owner_claims(new_work_item())[1]
    live = make_tick_commit(atomic_context.aggregate, 1, "deleted-child-counter")
    command = AuthoritativeTickSliceCommit(
        live,
        ScrumStateWriteSet(),
        (counter,),
        (cancellation,),
    )

    with pytest.raises(StaleSemanticCounter):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


def _alternate_item_and_claim():
    kind = CreationKind.SCRUM_REPLENISHMENT
    item = replace(
        make_work_item(),
        id=item_rng_id(TEAM_ID, kind, 0),
        creation_kind=kind,
        creation_sequence=0,
    )
    scope = counter_scope(SemanticCounterKind.ITEM_SEQUENCE, TEAM_ID, kind.value)
    return item, replace(item_claim(), scope=scope, expected_next=0)


def _seed_then_delete_counter(session_factory, claim, seed: bool) -> None:
    scope = claim.scope
    with session_factory.begin() as session:
        if seed:
            session.add(
                V2SemanticCounterModel(
                    team_id=str(TEAM_ID),
                    run_id=str(RUN_ID),
                    kind=scope.kind.value,
                    scope_id=str(scope.scope_id),
                    scope_key=scope.scope_key,
                    next_value=0,
                    work_item_id=None,
                    member_id=None,
                )
            )
            session.flush()
        result = session.execute(
            delete(V2SemanticCounterModel).where(
                V2SemanticCounterModel.team_id == str(TEAM_ID),
                V2SemanticCounterModel.run_id == str(RUN_ID),
                V2SemanticCounterModel.kind == scope.kind.value,
                V2SemanticCounterModel.scope_id == str(scope.scope_id),
                V2SemanticCounterModel.scope_key == scope.scope_key,
            )
        )
        assert result.rowcount == 1


@pytest.mark.parametrize(
    "case",
    (
        DeletedTeamCounterCase(ScrumStateWriteSet(sprints=(make_sprint(),)), sprint_claim(), False),
        DeletedTeamCounterCase(
            ScrumStateWriteSet(work_items=(_alternate_item_and_claim()[0],)),
            _alternate_item_and_claim()[1],
            True,
        ),
    ),
)
def test_deleted_team_scoped_counter_is_not_recreated(atomic_context, case):
    _seed_then_delete_counter(atomic_context.session_factory, case.claim, case.seed)
    before = _stored_view(atomic_context)
    label = f"deleted-{case.claim.scope.kind.value}"
    live = make_tick_commit(atomic_context.aggregate, 0, label)
    command = AuthoritativeTickSliceCommit(live, case.state, (case.claim,), ())

    with pytest.raises(StaleSemanticCounter):
        SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(command)

    assert _stored_view(atomic_context) == before


def _conflicting_factor():
    document = {"decision": "quality", "unit": 0.5}
    return replace(
        authoritative_write_set().work_item_factors[0],
        value=0.5,
        provenance_json=canonical_json(document),
        provenance_sha256=canonical_sha256(document),
    )


def test_conflicting_immutable_state_rolls_back_the_full_replay(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    initial = unit_of_work.commit_authoritative_slice(atomic_context.command)
    state = replace(
        authoritative_write_set(),
        work_item_factors=(_conflicting_factor(),),
    )
    conflict = make_authoritative_command(
        AuthoritativeCommandSpec(
            atomic_context.aggregate,
            expected_runtime_version=1,
            label="state-conflict",
            state=state,
        )
    )

    with pytest.raises(SemanticDeduplicationConflict):
        unit_of_work.commit_authoritative_slice(conflict)

    assert _stored_view(atomic_context) == StoredView(
        initial.live_slice.runtime,
        initial.state,
        initial.live_slice.activity,
        initial.live_slice.ground_truth,
        initial.live_slice.projection_intents,
    )


def test_changed_immutable_sprint_plan_is_typed_and_rolled_back(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    initial = unit_of_work.commit_authoritative_slice(atomic_context.command)
    sprint = replace(
        make_sprint(),
        planned_end_at=make_sprint().planned_end_at + timedelta(days=1),
        updated_at=LATER,
    )
    live = make_tick_commit(atomic_context.aggregate, 1, "sprint-plan-conflict")
    command = AuthoritativeTickSliceCommit(live, ScrumStateWriteSet(sprints=(sprint,)), (), ())

    with pytest.raises(SemanticDeduplicationConflict):
        unit_of_work.commit_authoritative_slice(command)

    assert _stored_view(atomic_context).state == initial.state


def _natural_only_command(atomic_context, natural_claim, counter_claim):
    live = make_tick_commit(atomic_context.aggregate, 1, "natural-conflict")
    return AuthoritativeTickSliceCommit(
        live,
        ScrumStateWriteSet(),
        (counter_claim,),
        (natural_claim,),
    )


def test_conflicting_eligibility_occurrence_is_typed_and_rolls_back(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    initial = unit_of_work.commit_authoritative_slice(atomic_context.command)
    claim = eligible_claim(1)
    conflict = _natural_only_command(atomic_context, claim, natural_counter_claim(1))

    with pytest.raises(NaturalEligibilityConflict):
        unit_of_work.commit_authoritative_slice(conflict)

    assert _stored_view(atomic_context) == StoredView(
        initial.live_slice.runtime,
        initial.state,
        initial.live_slice.activity,
        initial.live_slice.ground_truth,
        initial.live_slice.projection_intents,
    )


def test_conflicting_occurrence_on_another_business_date_is_typed(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    initial = unit_of_work.commit_authoritative_slice(atomic_context.command)
    claim = replace(eligible_claim(0), business_date=BUSINESS_DATE + timedelta(days=1))
    conflict = _natural_only_command(atomic_context, claim, natural_counter_claim(0))

    with pytest.raises(NaturalEligibilityConflict):
        unit_of_work.commit_authoritative_slice(conflict)

    assert _stored_view(atomic_context) == StoredView(
        initial.live_slice.runtime,
        initial.state,
        initial.live_slice.activity,
        initial.live_slice.ground_truth,
        initial.live_slice.projection_intents,
    )


def test_older_identical_natural_eligibility_replays_after_later_occurrence(
    atomic_context,
):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    unit_of_work.commit_authoritative_slice(atomic_context.command)
    next_claim = replace(eligible_claim(1), business_date=BUSINESS_DATE + timedelta(days=1))
    second = _natural_only_command(atomic_context, next_claim, natural_counter_claim(1))
    unit_of_work.commit_authoritative_slice(second)
    old_live = make_tick_commit(atomic_context.aggregate, 2, "old-natural-replay")
    old = AuthoritativeTickSliceCommit(
        old_live,
        ScrumStateWriteSet(),
        (natural_counter_claim(0),),
        (eligible_claim(0),),
    )

    replay = unit_of_work.commit_authoritative_slice(old)

    assert replay.counters[0].next_value == 2
    assert replay.natural_decision_evaluations[0].occurrence == 0
    assert len(replay.state.natural_decision_evaluations) == 3


def _conflicting_live_slice(atomic_context):
    original = atomic_context.command.live_slice.activity[0]
    envelope = DraftEnvelope(
        original.semantic_key,
        original.schema_version,
        original.occurred_at,
        {"changed": True},
    )
    details = ActivityDetails("ISSUE_UPDATED", "ISSUE", TEAM_ID, 7)
    conflicting = ActivityEventDraft.create(envelope, details)
    live = make_tick_commit(atomic_context.aggregate, 1, "evidence-conflict")
    return replace(live, activity=(conflicting,))


def test_conflicting_canonical_evidence_rolls_back_runtime_and_state(atomic_context):
    unit_of_work = SqlAlchemyV2UnitOfWork(atomic_context.session_factory)
    initial = unit_of_work.commit_authoritative_slice(atomic_context.command)
    conflict = AuthoritativeTickSliceCommit(
        _conflicting_live_slice(atomic_context), ScrumStateWriteSet(), (), ()
    )

    with pytest.raises(SemanticDeduplicationConflict):
        unit_of_work.commit_authoritative_slice(conflict)

    assert _stored_view(atomic_context) == StoredView(
        initial.live_slice.runtime,
        initial.state,
        initial.live_slice.activity,
        initial.live_slice.ground_truth,
        initial.live_slice.projection_intents,
    )


def test_absent_natural_claims_consume_no_natural_counter(atomic_context):
    claims = tuple(
        claim
        for claim in allocation_claims()
        if claim.scope.kind is not SemanticCounterKind.NATURAL_DECISION_OCCURRENCE
    )
    command = make_authoritative_command(
        AuthoritativeCommandSpec(
            atomic_context.aggregate,
            counter_claims=claims,
            natural_claims=(),
        )
    )

    committed = SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
        command
    )

    values = _counter_values(committed.state)
    assert values[("NATURAL_DECISION_OCCURRENCE", "RISK_CANCELLATION_OUTCOME")] == 0
    assert values[("NATURAL_DECISION_OCCURRENCE", "RISK_MEMBER_UNAVAILABLE_OUTCOME")] == 0
    assert committed.natural_decision_evaluations == ()


def test_rollback_after_counter_claim_does_not_create_an_occurrence_gap(atomic_context):
    engine = atomic_context.session_factory.kw["bind"]

    def fail_activity(*arguments):
        if "INSERT INTO v2_activity_events" in arguments[2]:
            raise RuntimeError("injected post-claim failure")

    event.listen(engine, "before_cursor_execute", fail_activity)
    try:
        with pytest.raises(RuntimeError, match="post-claim"):
            SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
                atomic_context.command
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_activity)

    committed = SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
        atomic_context.command
    )
    assert {item.occurrence for item in committed.natural_decision_evaluations} == {0}
    assert all(
        counter.next_value == 1
        for counter in committed.counters
        if counter.scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE
    )


def test_empty_state_skips_mapper_application_and_returns_complete_snapshot(atomic_context):
    live = make_tick_commit(atomic_context.aggregate, 0, "live-only")
    command = AuthoritativeTickSliceCommit(live, ScrumStateWriteSet(), (), ())

    committed = SqlAlchemyV2UnitOfWork(atomic_context.session_factory).commit_authoritative_slice(
        command
    )

    assert committed.state == atomic_context.baseline
    assert committed.counters == ()
    assert committed.natural_decision_evaluations == ()


def _enable_foreign_keys(connection, _record) -> None:
    connection.execute("PRAGMA foreign_keys=ON")


def _restart_context(database_url, resolved_blueprint_json, requested_at):
    engine = create_engine(database_url)
    event.listen(engine, "connect", _enable_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    aggregate = create_aggregate(factory, resolved_blueprint_json, requested_at)
    with factory.begin() as session:
        SqlAlchemyScrumStateMapper().add(session, baseline_write_set())
    with factory() as session:
        baseline = SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
    command = make_authoritative_command(AuthoritativeCommandSpec(aggregate))
    runtime = SqlAlchemyV2UnitOfWork(factory).get_runtime(TEAM_ID)
    return engine, AtomicContext(factory, aggregate, baseline, runtime, command)


def _assert_restarted_live_slice(unit_of_work, committed) -> None:
    query = LedgerPageQuery(TEAM_ID, RUN_ID, None, 100)
    projection_query = ProjectionPageQuery(TEAM_ID, RUN_ID, None, 100)
    assert unit_of_work.get_runtime(TEAM_ID) == committed.live_slice.runtime
    assert unit_of_work.page_activity(query).items == committed.live_slice.activity
    assert unit_of_work.page_ground_truth(query).items == committed.live_slice.ground_truth
    assert unit_of_work.page_projection(projection_query).items == (
        committed.live_slice.projection_intents
    )
    first = unit_of_work.page_activity(LedgerPageQuery(TEAM_ID, RUN_ID, None, 1))
    second = unit_of_work.page_activity(LedgerPageQuery(TEAM_ID, RUN_ID, 1, 100))
    assert tuple(item.append_sequence for item in first.items) == (1,)
    assert first.next_cursor == 1
    assert tuple(item.append_sequence for item in second.items) == (2,)
    assert second.next_cursor is None


def _assert_continued_cursors(unit_of_work) -> None:
    activity = unit_of_work.page_activity(LedgerPageQuery(TEAM_ID, RUN_ID, None, 100))
    projection = unit_of_work.page_projection(ProjectionPageQuery(TEAM_ID, RUN_ID, None, 100))
    assert tuple(item.append_sequence for item in activity.items) == (1, 2, 3, 4)
    assert tuple(item.transaction_sequence for item in activity.items) == (0, 1, 0, 1)
    assert tuple(item.append_sequence for item in projection.items) == (1, 2, 3, 4)
    assert all(item.status == "PENDING" for item in projection.items)


def _continuation_command(context: AtomicContext) -> AuthoritativeTickSliceCommit:
    next_date = BUSINESS_DATE + timedelta(days=1)
    natural_claims = (
        replace(eligible_claim(1), business_date=next_date),
        replace(member_eligible_claim(1), business_date=next_date),
    )
    return make_authoritative_command(
        AuthoritativeCommandSpec(
            context.aggregate,
            expected_runtime_version=1,
            label="continuation",
            state=ScrumStateWriteSet(),
            counter_claims=(natural_counter_claim(1), member_natural_counter_claim(1)),
            natural_claims=natural_claims,
        )
    )


def test_disposed_engine_restart_reloads_and_continues_exact_occurrences(
    tmp_path, resolved_blueprint_json, requested_at
):
    database_url = f"sqlite:///{tmp_path / 'authoritative-restart.db'}"
    engine, context = _restart_context(database_url, resolved_blueprint_json, requested_at)
    first = SqlAlchemyV2UnitOfWork(context.session_factory).commit_authoritative_slice(
        context.command
    )
    engine.dispose()

    restarted_engine = create_engine(database_url)
    event.listen(restarted_engine, "connect", _enable_foreign_keys)
    restarted_factory = sessionmaker(bind=restarted_engine)
    restarted = SqlAlchemyV2UnitOfWork(restarted_factory)
    with restarted_factory() as session:
        state = SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
    _assert_restarted_live_slice(restarted, first)

    continued = restarted.commit_authoritative_slice(_continuation_command(context))

    assert state == first.state
    assert continued.live_slice.runtime.version == 2
    assert {item.occurrence for item in continued.natural_decision_evaluations} == {1}
    with restarted_factory() as session:
        exact = SqlAlchemyScrumStateMapper().load(session, ScrumStateQuery(TEAM_ID, RUN_ID))
    assert {item.occurrence for item in exact.natural_decision_evaluations} == {0, 1}
    assert all(counter.next_value == 2 for counter in continued.counters)
    _assert_continued_cursors(restarted)
    restarted_engine.dispose()


def test_success_uses_one_session_and_one_commit_without_rollback(atomic_context):
    engine = atomic_context.session_factory.kw["bind"]

    class CountingTransactionSession(Session):
        commits = 0
        rollbacks = 0

        def commit(self) -> None:
            CountingTransactionSession.commits += 1
            super().commit()

        def rollback(self) -> None:
            CountingTransactionSession.rollbacks += 1
            super().rollback()

    factory = CountingSessionFactory(sessionmaker(bind=engine, class_=CountingTransactionSession))

    SqlAlchemyV2UnitOfWork(factory).commit_authoritative_slice(atomic_context.command)

    assert factory.calls == 1
    assert CountingTransactionSession.commits == 1
    assert CountingTransactionSession.rollbacks == 0
