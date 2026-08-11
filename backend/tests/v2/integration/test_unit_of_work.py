from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.live_slice import (
    ActivityDetails,
    ActivityEventDraft,
    DraftEnvelope,
    GroundTruthDetails,
    GroundTruthRecordDraft,
    LedgerPageQuery,
    ProjectionDetails,
    ProjectionIntentDraft,
    ProjectionPageQuery,
    RuntimeAdvance,
)
from app.v2.persistence.live_models import (
    V2ActivityEventModel,
    V2GroundTruthRecordModel,
    V2ProjectionIntentModel,
)
from app.v2.persistence.unit_of_work import (
    SemanticDeduplicationConflict,
    SqlAlchemyV2UnitOfWork,
    StaleRuntimeVersion,
)
from tests.v2.live_slice_support import (
    SLICE_TIME,
    create_aggregate,
    make_tick_commit,
)

LEDGER_MODELS = (V2ActivityEventModel, V2GroundTruthRecordModel, V2ProjectionIntentModel)
RACE_TARGETS = (
    ("activity", V2ActivityEventModel),
    ("ground_truth", V2GroundTruthRecordModel),
    ("projection_intents", V2ProjectionIntentModel),
)


class _CountingSessionFactory:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.delegate()


@pytest.fixture
def live_context(v2_session_factory, resolved_blueprint_json, requested_at):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    return v2_session_factory, aggregate, SqlAlchemyV2UnitOfWork(v2_session_factory)


def _ledger_counts(session_factory) -> list[int]:
    with session_factory() as session:
        return [
            session.scalar(select(func.count(model.append_sequence)))
            for model in LEDGER_MODELS
        ]


def _assert_committed_shape(committed, aggregate) -> None:
    assert committed.runtime.team_id == aggregate.team.id
    assert committed.runtime.version == 1
    assert [item.append_sequence for item in committed.activity] == [1, 2]
    assert [item.transaction_sequence for item in committed.activity] == [0, 1]
    assert [item.event_type for item in committed.activity] == ["ISSUE_UPDATED", "ISSUE_UPDATED"]
    assert [item.aggregate_version for item in committed.activity] == [7, 7]
    assert [item.append_sequence for item in committed.ground_truth] == [1, 2]
    assert [item.append_sequence for item in committed.projection_intents] == [1, 2]
    assert [item.status for item in committed.projection_intents] == ["PENDING", "PENDING"]


def _hiding_session_factory(session_factory, hidden_model):
    engine = session_factory.kw["bind"]

    class _HidingSession(session_factory.class_):
        def scalar(self, statement, *args, **kwargs):
            descriptions = getattr(statement, "column_descriptions", ())
            selected = descriptions[0].get("entity") if descriptions else None
            already_hidden = self.info.get("semantic_lookup_hidden", False)
            if selected is hidden_model and not already_hidden:
                self.info["semantic_lookup_hidden"] = True
                return None
            return super().scalar(statement, *args, **kwargs)

    return sessionmaker(bind=engine, class_=_HidingSession)


def _conflicting_draft(aggregate, original):
    envelope = DraftEnvelope(
        original.semantic_key,
        original.schema_version,
        original.occurred_at,
        {"changed": True},
    )
    if isinstance(original, ActivityEventDraft):
        details = ActivityDetails("ISSUE_UPDATED", "ISSUE", aggregate.team.id, 7)
        return ActivityEventDraft.create(envelope, details)
    if isinstance(original, GroundTruthRecordDraft):
        return GroundTruthRecordDraft.create(
            envelope, GroundTruthDetails("ISSUE_STATE", "SIMULATOR_V1")
        )
    details = ProjectionDetails("JIRA", "UPSERT_ISSUE", aggregate.team.id, 7, "PENDING")
    return ProjectionIntentDraft.create(envelope, details)


def _with_conflicting_target(aggregate, winner, loser, collection_name: str):
    original = getattr(winner, collection_name)[0]
    conflicting = _conflicting_draft(aggregate, original)
    return replace(loser, **{collection_name: (conflicting,)})


def _invalid_key_draft(aggregate, collection_name: str):
    envelope = DraftEnvelope("slice/strict-key/1", "1.0", SLICE_TIME, {"valid": True})
    object.__setattr__(envelope, "payload", {"nested": [{None: "invalid"}]})
    if collection_name == "activity":
        details = ActivityDetails("ISSUE_UPDATED", "ISSUE", aggregate.team.id, 7)
        return ActivityEventDraft.create(envelope, details)
    if collection_name == "ground_truth":
        details = GroundTruthDetails("ISSUE_STATE", "SIMULATOR_V1")
        return GroundTruthRecordDraft.create(envelope, details)
    details = ProjectionDetails("JIRA", "UPSERT_ISSUE", aggregate.team.id, 7, "PENDING")
    return ProjectionIntentDraft.create(envelope, details)


def _commit_with_invalid_key(aggregate, collection_name: str):
    draft = _invalid_key_draft(aggregate, collection_name)
    commit = make_tick_commit(aggregate, 0, "invalid-key")
    return replace(commit, **{collection_name: (draft,)})


def test_commit_advances_runtime_and_appends_each_ordered_ledger_atomically(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)

    committed = unit_of_work.commit_tick_slice(make_tick_commit(aggregate, 0, "first"))

    _assert_committed_shape(committed, aggregate)
    assert unit_of_work.get_runtime(aggregate.team.id) == committed.runtime
    assert _ledger_counts(v2_session_factory) == [2, 2, 2]


@pytest.mark.parametrize(
    "statement_fragment",
    [
        "UPDATE v2_team_runtimes",
        "INSERT INTO v2_activity_events",
        "INSERT INTO v2_ground_truth_records",
        "INSERT INTO v2_projection_intents",
    ],
)
def test_failure_at_each_write_class_rolls_back_runtime_and_ledgers(
    live_context, statement_fragment
):
    v2_session_factory, aggregate, unit_of_work = live_context
    engine = v2_session_factory.kw["bind"]

    def fail_target_write(*callback_arguments):
        statement = callback_arguments[2]
        if statement_fragment.upper() in statement.upper():
            raise RuntimeError(f"injected {statement_fragment} failure")

    event.listen(engine, "before_cursor_execute", fail_target_write)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            unit_of_work.commit_tick_slice(make_tick_commit(aggregate, 0, "failure"))
    finally:
        event.remove(engine, "before_cursor_execute", fail_target_write)

    assert unit_of_work.get_runtime(aggregate.team.id).version == 0
    assert _ledger_counts(v2_session_factory) == [0, 0, 0]


@pytest.mark.parametrize(
    "collection_name", ["activity", "ground_truth", "projection_intents"]
)
def test_uow_revalidates_forged_drafts_before_opening_a_session(
    v2_session_factory, resolved_blueprint_json, requested_at, collection_name
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    commit = make_tick_commit(aggregate, 0, "forged")
    object.__setattr__(getattr(commit, collection_name)[0], "payload_sha256", "0" * 64)
    counting_factory = _CountingSessionFactory(v2_session_factory)
    unit_of_work = SqlAlchemyV2UnitOfWork(counting_factory)

    with pytest.raises(ValueError, match="hash|digest"):
        unit_of_work.commit_tick_slice(commit)

    assert counting_factory.calls == 0
    assert SqlAlchemyV2UnitOfWork(v2_session_factory).get_runtime(aggregate.team.id).version == 0
    assert _ledger_counts(v2_session_factory) == [0, 0, 0]


@pytest.mark.parametrize(
    "collection_name", ["activity", "ground_truth", "projection_intents"]
)
def test_non_string_json_keys_fail_before_session_and_leave_all_state_unchanged(
    live_context, collection_name
):
    session_factory, aggregate, _ = live_context
    counting_factory = _CountingSessionFactory(session_factory)
    unit_of_work = SqlAlchemyV2UnitOfWork(counting_factory)

    with pytest.raises(ValueError, match="JSON object keys must be strings"):
        unit_of_work.commit_tick_slice(_commit_with_invalid_key(aggregate, collection_name))

    assert counting_factory.calls == 0
    assert SqlAlchemyV2UnitOfWork(session_factory).get_runtime(aggregate.team.id).version == 0
    assert _ledger_counts(session_factory) == [0, 0, 0]


def test_two_loaded_writers_leave_stale_writer_with_zero_partial_rows(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    first = SqlAlchemyV2UnitOfWork(v2_session_factory)
    second = SqlAlchemyV2UnitOfWork(v2_session_factory)
    first_version = first.get_runtime(aggregate.team.id).version
    second_version = second.get_runtime(aggregate.team.id).version

    first.commit_tick_slice(make_tick_commit(aggregate, first_version, "winner"))
    with pytest.raises(StaleRuntimeVersion):
        second.commit_tick_slice(make_tick_commit(aggregate, second_version, "stale"))

    assert first.get_runtime(aggregate.team.id).version == 1
    assert _ledger_counts(v2_session_factory) == [2, 2, 2]


def test_identical_semantic_replay_returns_existing_records_without_new_rows(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)
    first = make_tick_commit(aggregate, 0, "replay")
    initial = unit_of_work.commit_tick_slice(first)
    replay = replace(
        first,
        commit_id=semantic_uuid("commit/replay/second"),
        expected_runtime_version=1,
        runtime_after=RuntimeAdvance("RUNNING", SLICE_TIME + timedelta(hours=2), None),
    )

    repeated = unit_of_work.commit_tick_slice(replay)

    assert repeated.activity == initial.activity
    assert repeated.ground_truth == initial.ground_truth
    assert repeated.projection_intents == initial.projection_intents
    assert repeated.runtime.version == 2
    assert _ledger_counts(v2_session_factory) == [2, 2, 2]


@pytest.mark.parametrize("collection_name,hidden_model", RACE_TARGETS)
def test_identical_semantic_insert_race_resolves_to_existing_records(
    v2_session_factory,
    resolved_blueprint_json,
    requested_at,
    collection_name,
    hidden_model,
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    normal = SqlAlchemyV2UnitOfWork(v2_session_factory)
    winner = make_tick_commit(aggregate, 0, "race-identical")
    initial = normal.commit_tick_slice(winner)
    replay = replace(
        winner,
        commit_id=semantic_uuid(f"commit/race-identical/{collection_name}"),
        expected_runtime_version=1,
        runtime_after=RuntimeAdvance("RUNNING", SLICE_TIME + timedelta(hours=2), None),
    )
    raced = SqlAlchemyV2UnitOfWork(
        _hiding_session_factory(v2_session_factory, hidden_model)
    ).commit_tick_slice(replay)

    assert raced.activity == initial.activity
    assert raced.ground_truth == initial.ground_truth
    assert raced.projection_intents == initial.projection_intents
    assert raced.runtime.version == 2
    assert _ledger_counts(v2_session_factory) == [2, 2, 2]


def test_conflicting_semantic_replay_rolls_back_runtime_and_new_rows(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)
    first = make_tick_commit(aggregate, 0, "conflict")
    unit_of_work.commit_tick_slice(first)
    conflict = replace(
        make_tick_commit(aggregate, 1, "second"),
        activity=(_conflicting_draft(aggregate, first.activity[0]),),
    )

    with pytest.raises(SemanticDeduplicationConflict):
        unit_of_work.commit_tick_slice(conflict)

    assert unit_of_work.get_runtime(aggregate.team.id).version == 1
    assert _ledger_counts(v2_session_factory) == [2, 2, 2]


@pytest.mark.parametrize("collection_name,hidden_model", RACE_TARGETS)
def test_conflicting_semantic_insert_race_is_typed_and_rolls_back_whole_slice(
    v2_session_factory,
    resolved_blueprint_json,
    requested_at,
    collection_name,
    hidden_model,
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    normal = SqlAlchemyV2UnitOfWork(v2_session_factory)
    winner = make_tick_commit(aggregate, 0, "race-conflict")
    committed = normal.commit_tick_slice(winner)
    loser = make_tick_commit(aggregate, 1, f"loser-{collection_name}")
    conflict = _with_conflicting_target(aggregate, winner, loser, collection_name)
    raced = SqlAlchemyV2UnitOfWork(_hiding_session_factory(v2_session_factory, hidden_model))

    with pytest.raises(SemanticDeduplicationConflict):
        raced.commit_tick_slice(conflict)

    assert normal.get_runtime(aggregate.team.id).version == 1
    assert _ledger_counts(v2_session_factory) == [2, 2, 2]
    assert normal.page_activity(LedgerPageQuery(aggregate.team.id, None, None, 10)).items == (
        committed.activity
    )


def _activity_sequences(unit_of_work, aggregate) -> list[int]:
    sequences: list[int] = []
    cursor = None
    while True:
        page = unit_of_work.page_activity(LedgerPageQuery(aggregate.team.id, None, cursor, 1))
        sequences.extend(item.append_sequence for item in page.items)
        if page.next_cursor is None:
            return sequences
        cursor = page.next_cursor


def test_cursor_pagination_uses_append_order_for_equal_and_late_times(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)
    unit_of_work.commit_tick_slice(make_tick_commit(aggregate, 0, "ordered"))
    issued = unit_of_work.page_activity(LedgerPageQuery(aggregate.team.id, None, None, 2))
    cursor = issued.items[-1].append_sequence
    late = make_tick_commit(aggregate, 1, "late")
    late_events = tuple(
        replace(item, occurred_at=SLICE_TIME - timedelta(days=1)) for item in late.activity
    )

    unit_of_work.commit_tick_slice(replace(late, activity=late_events))
    after_cursor = unit_of_work.page_activity(
        LedgerPageQuery(aggregate.team.id, aggregate.run.id, cursor, 10)
    )

    assert [item.append_sequence for item in after_cursor.items] == [3, 4]
    assert all(item.occurred_at < issued.items[0].occurred_at for item in after_cursor.items)
    assert _activity_sequences(unit_of_work, aggregate) == [1, 2, 3, 4]


def test_cross_team_run_pair_fails_before_any_runtime_or_ledger_write(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    first = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    second_json = resolved_blueprint_json.replace("Payments Platform", "Revenue Platform")
    second = create_aggregate(v2_session_factory, second_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)
    invalid = replace(make_tick_commit(first, 0, "cross-run"), run_id=second.run.id)

    with pytest.raises(StaleRuntimeVersion):
        unit_of_work.commit_tick_slice(invalid)

    assert unit_of_work.get_runtime(first.team.id).version == 0
    assert unit_of_work.get_runtime(second.team.id).version == 0
    assert _ledger_counts(v2_session_factory) == [0, 0, 0]


def test_page_projection_filters_team_run_and_keeps_pending_state(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)
    unit_of_work.commit_tick_slice(make_tick_commit(aggregate, 0, "projection-page"))

    page = unit_of_work.page_projection(
        ProjectionPageQuery(aggregate.team.id, aggregate.run.id, None, 1)
    )

    assert len(page.items) == 1
    assert page.items[0].status == "PENDING"
    assert page.next_cursor == 1


def test_disposed_engine_restart_reloads_runtime_ledgers_payloads_and_cursors(
    tmp_path, resolved_blueprint_json, requested_at
):
    database_url = f"sqlite:///{tmp_path / 'live-restart.db'}"
    first_engine = create_engine(database_url)
    Base.metadata.create_all(first_engine)
    first_factory = sessionmaker(bind=first_engine)
    aggregate = create_aggregate(first_factory, resolved_blueprint_json, requested_at)
    first = SqlAlchemyV2UnitOfWork(first_factory)
    committed = first.commit_tick_slice(make_tick_commit(aggregate, 0, "restart"))
    query = LedgerPageQuery(aggregate.team.id, aggregate.run.id, None, 1)
    expected_pages = (first.page_activity(query), first.page_ground_truth(query))
    expected_projection = first.page_projection(
        ProjectionPageQuery(aggregate.team.id, aggregate.run.id, None, 1)
    )
    first_engine.dispose()

    restarted_engine = create_engine(database_url)
    restarted = SqlAlchemyV2UnitOfWork(sessionmaker(bind=restarted_engine))

    assert restarted.get_runtime(aggregate.team.id) == committed.runtime
    assert (restarted.page_activity(query), restarted.page_ground_truth(query)) == expected_pages
    assert restarted.page_projection(
        ProjectionPageQuery(aggregate.team.id, aggregate.run.id, None, 1)
    ) == expected_projection
    assert expected_projection.items[0].status == "PENDING"
    restarted_engine.dispose()
