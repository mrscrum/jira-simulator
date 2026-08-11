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
    LedgerPageQuery,
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


def _conflicting_activity(aggregate, original) -> ActivityEventDraft:
    envelope = DraftEnvelope(
        original.semantic_key,
        original.schema_version,
        original.occurred_at,
        {"changed": True},
    )
    details = ActivityDetails("ISSUE_UPDATED", "ISSUE", aggregate.team.id, 7)
    return ActivityEventDraft.create(envelope, details)


def test_conflicting_semantic_replay_rolls_back_runtime_and_new_rows(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)
    first = make_tick_commit(aggregate, 0, "conflict")
    unit_of_work.commit_tick_slice(first)
    conflict = replace(
        make_tick_commit(aggregate, 1, "second"),
        activity=(_conflicting_activity(aggregate, first.activity[0]),),
    )

    with pytest.raises(SemanticDeduplicationConflict):
        unit_of_work.commit_tick_slice(conflict)

    assert unit_of_work.get_runtime(aggregate.team.id).version == 1
    assert _ledger_counts(v2_session_factory) == [2, 2, 2]


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
