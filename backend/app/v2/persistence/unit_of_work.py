"""Atomic SQLAlchemy unit of work for one v2 live-slice commit."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, NoReturn
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.v2.domain.authoritative_slice import (
    AuthoritativeTickSliceCommit,
    CommittedAuthoritativeTickSlice,
)
from app.v2.domain.live_slice import (
    ActivityEvent,
    ActivityEventDraft,
    ActivityPage,
    CommittedTickSlice,
    GroundTruthPage,
    GroundTruthRecord,
    GroundTruthRecordDraft,
    LedgerPageQuery,
    ProjectionIntent,
    ProjectionIntentDraft,
    ProjectionPage,
    ProjectionPageQuery,
    TickSliceCommit,
)
from app.v2.domain.scrum_state import ScrumStateQuery
from app.v2.domain.team_runtime import TeamRuntime
from app.v2.persistence.live_models import (
    V2ActivityEventModel,
    V2GroundTruthRecordModel,
    V2ProjectionIntentModel,
)
from app.v2.persistence.scrum_state_mapper import (
    CounterClaimStaleError,
    NaturalClaimConflictError,
    ScrumStateConflictError,
    SqlAlchemyScrumStateMapper,
)
from app.v2.persistence.team_models import V2TeamRuntimeModel


class StaleRuntimeVersion(RuntimeError):  # noqa: N818
    """The requested team/run/version no longer identifies one runtime row."""


class SemanticDeduplicationConflict(RuntimeError):  # noqa: N818
    """A semantic key already identifies different immutable content."""


class StaleSemanticCounter(RuntimeError):  # noqa: N818
    """A semantic counter no longer matches its explicit expected-next claim."""


class NaturalEligibilityConflict(RuntimeError):  # noqa: N818
    """A natural eligibility or occurrence identifies different immutable content."""


class V2UnitOfWork(ABC):
    """Application-facing atomic live-slice persistence port."""

    @abstractmethod
    def commit_tick_slice(self, commit: TickSliceCommit) -> CommittedTickSlice:
        """Atomically advance runtime and persist all local records."""

    @abstractmethod
    def commit_authoritative_slice(
        self, commit: AuthoritativeTickSliceCommit
    ) -> CommittedAuthoritativeTickSlice:
        """Atomically commit runtime, Scrum after-images, claims, and ledgers."""

    @abstractmethod
    def get_runtime(self, team_id: UUID) -> TeamRuntime:
        """Load one detached team runtime."""

    @abstractmethod
    def page_activity(self, query: LedgerPageQuery) -> ActivityPage:
        """Read activity in exclusive append-cursor order."""

    @abstractmethod
    def page_ground_truth(self, query: LedgerPageQuery) -> GroundTruthPage:
        """Read ground truth in exclusive append-cursor order."""

    @abstractmethod
    def page_projection(self, query: ProjectionPageQuery) -> ProjectionPage:
        """Read pending generic projection intents in append order."""


class SqlAlchemyV2UnitOfWork(V2UnitOfWork):
    """One-short-transaction SQLAlchemy implementation of the v2 port."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def commit_tick_slice(self, commit: TickSliceCommit) -> CommittedTickSlice:
        commit.validate()
        with self._session_factory() as session:
            try:
                committed = self._commit_in_session(session, commit)
                session.commit()
            except Exception:
                session.rollback()
                raise
            return committed

    def commit_authoritative_slice(
        self, commit: AuthoritativeTickSliceCommit
    ) -> CommittedAuthoritativeTickSlice:
        if type(commit) is not AuthoritativeTickSliceCommit:
            raise TypeError("commit must be an AuthoritativeTickSliceCommit")
        commit.validate()
        with self._session_factory() as session:
            try:
                committed = self._commit_authoritative_in_session(session, commit)
                session.commit()
            except Exception as error:
                session.rollback()
                _raise_authoritative_error(error)
            return committed

    def _commit_authoritative_in_session(
        self, session: Session, commit: AuthoritativeTickSliceCommit
    ) -> CommittedAuthoritativeTickSlice:
        mapper = SqlAlchemyScrumStateMapper()
        runtime = self._advance_runtime(session, commit.live_slice)
        if any(commit.state._collection_values()):
            mapper.apply_after_images(session, commit)
        counters = mapper.apply_counter_claims(session, commit)
        evaluations = mapper.resolve_natural_claims(session, commit)
        query = ScrumStateQuery(commit.live_slice.team_id, commit.live_slice.run_id)
        state = mapper.load(session, query)
        live_slice = self._persist_ledgers(session, commit.live_slice, runtime)
        session.flush()
        return CommittedAuthoritativeTickSlice(live_slice, state, counters, evaluations)

    def _commit_in_session(
        self, session: Session, commit: TickSliceCommit
    ) -> CommittedTickSlice:
        runtime = self._advance_runtime(session, commit)
        return self._persist_ledgers(session, commit, runtime)

    @staticmethod
    def _persist_ledgers(
        session: Session, commit: TickSliceCommit, runtime: TeamRuntime
    ) -> CommittedTickSlice:
        activity = SqlAlchemyV2UnitOfWork._persist_activity(session, commit)
        ground_truth = SqlAlchemyV2UnitOfWork._persist_ground_truth(session, commit)
        projection = SqlAlchemyV2UnitOfWork._persist_projection(session, commit)
        return CommittedTickSlice(runtime, activity, ground_truth, projection)

    def get_runtime(self, team_id: UUID) -> TeamRuntime:
        with self._session_factory() as session:
            model = session.scalar(
                select(V2TeamRuntimeModel).where(V2TeamRuntimeModel.team_id == str(team_id))
            )
            if model is None:
                raise LookupError(f"runtime not found for team {team_id}")
            return _map_runtime(model)

    def page_activity(self, query: LedgerPageQuery) -> ActivityPage:
        with self._session_factory() as session:
            rows, cursor = _page_rows(session, V2ActivityEventModel, query)
            return ActivityPage(tuple(_map_activity(item) for item in rows), cursor)

    def page_ground_truth(self, query: LedgerPageQuery) -> GroundTruthPage:
        with self._session_factory() as session:
            rows, cursor = _page_rows(session, V2GroundTruthRecordModel, query)
            return GroundTruthPage(tuple(_map_ground_truth(item) for item in rows), cursor)

    def page_projection(self, query: ProjectionPageQuery) -> ProjectionPage:
        with self._session_factory() as session:
            rows, cursor = _page_rows(session, V2ProjectionIntentModel, query)
            return ProjectionPage(tuple(_map_projection(item) for item in rows), cursor)

    @staticmethod
    def _advance_runtime(session: Session, commit: TickSliceCommit) -> TeamRuntime:
        statement = (
            update(V2TeamRuntimeModel)
            .where(V2TeamRuntimeModel.team_id == str(commit.team_id))
            .where(V2TeamRuntimeModel.run_id == str(commit.run_id))
            .where(V2TeamRuntimeModel.version == commit.expected_runtime_version)
            .values(
                version=commit.expected_runtime_version + 1,
                state=commit.runtime_after.state,
                simulation_time=commit.runtime_after.simulation_time,
                next_wake_at=commit.runtime_after.next_wake_at,
                updated_at=commit.recorded_at,
            )
        )
        if session.execute(statement).rowcount != 1:
            raise StaleRuntimeVersion("runtime compare-and-swap updated zero rows")
        model = session.scalar(
            select(V2TeamRuntimeModel).where(V2TeamRuntimeModel.team_id == str(commit.team_id))
        )
        if model is None:
            raise StaleRuntimeVersion("runtime disappeared after compare-and-swap")
        return _map_runtime(model)

    @staticmethod
    def _persist_activity(
        session: Session, commit: TickSliceCommit
    ) -> tuple[ActivityEvent, ...]:
        records = [
            _resolve_activity(session, commit, (position, draft))
            for position, draft in enumerate(commit.activity)
        ]
        return tuple(records)

    @staticmethod
    def _persist_ground_truth(
        session: Session, commit: TickSliceCommit
    ) -> tuple[GroundTruthRecord, ...]:
        records = [
            _resolve_ground_truth(session, commit, (position, draft))
            for position, draft in enumerate(commit.ground_truth)
        ]
        return tuple(records)

    @staticmethod
    def _persist_projection(
        session: Session, commit: TickSliceCommit
    ) -> tuple[ProjectionIntent, ...]:
        records = [
            _resolve_projection(session, commit, (position, draft))
            for position, draft in enumerate(commit.projection_intents)
        ]
        return tuple(records)


def _raise_authoritative_error(error: Exception) -> NoReturn:
    if isinstance(error, CounterClaimStaleError):
        raise StaleSemanticCounter(str(error)) from error
    if isinstance(error, NaturalClaimConflictError):
        raise NaturalEligibilityConflict(str(error)) from error
    if isinstance(error, ScrumStateConflictError):
        raise SemanticDeduplicationConflict(str(error)) from error
    raise error


def _envelope_values(commit: TickSliceCommit, draft, position: int) -> dict[str, object]:
    return {
        "id": str(draft.id),
        "semantic_key": draft.semantic_key,
        "team_id": str(commit.team_id),
        "run_id": str(commit.run_id),
        "commit_id": str(commit.commit_id),
        "transaction_sequence": position,
        "schema_version": draft.schema_version,
        "occurred_at": draft.occurred_at,
        "recorded_at": commit.recorded_at,
        "canonical_payload": draft.canonical_payload,
        "payload_sha256": draft.payload_sha256,
    }


def _resolve_activity(
    session: Session,
    commit: TickSliceCommit,
    positioned_draft: tuple[int, ActivityEventDraft],
) -> ActivityEvent:
    position, draft = positioned_draft
    existing = session.scalar(
        select(V2ActivityEventModel).where(V2ActivityEventModel.semantic_key == draft.semantic_key)
    )
    if existing is not None:
        record = _map_activity(existing)
        _require_identical(record, draft, commit)
        return record
    model = V2ActivityEventModel(
        **_envelope_values(commit, draft, position),
        event_type=draft.event_type,
        aggregate_type=draft.aggregate_type,
        aggregate_id=str(draft.aggregate_id),
        aggregate_version=draft.aggregate_version,
    )
    record = _map_activity(_insert_or_find(session, model, draft.semantic_key))
    _require_identical(record, draft, commit)
    return record


def _resolve_ground_truth(
    session: Session,
    commit: TickSliceCommit,
    positioned_draft: tuple[int, GroundTruthRecordDraft],
) -> GroundTruthRecord:
    position, draft = positioned_draft
    existing = session.scalar(
        select(V2GroundTruthRecordModel).where(
            V2GroundTruthRecordModel.semantic_key == draft.semantic_key
        )
    )
    if existing is not None:
        record = _map_ground_truth(existing)
        _require_identical(record, draft, commit)
        return record
    model = V2GroundTruthRecordModel(
        **_envelope_values(commit, draft, position),
        record_type=draft.record_type,
        provenance_type=draft.provenance_type,
    )
    record = _map_ground_truth(_insert_or_find(session, model, draft.semantic_key))
    _require_identical(record, draft, commit)
    return record


def _resolve_projection(
    session: Session,
    commit: TickSliceCommit,
    positioned_draft: tuple[int, ProjectionIntentDraft],
) -> ProjectionIntent:
    position, draft = positioned_draft
    existing = session.scalar(
        select(V2ProjectionIntentModel).where(
            V2ProjectionIntentModel.semantic_key == draft.semantic_key
        )
    )
    if existing is not None:
        record = _map_projection(existing)
        _require_identical(record, draft, commit)
        return record
    model = V2ProjectionIntentModel(
        **_envelope_values(commit, draft, position),
        target_kind=draft.target_kind,
        operation_type=draft.operation_type,
        aggregate_id=str(draft.aggregate_id),
        aggregate_version=draft.aggregate_version,
        status=draft.status,
    )
    record = _map_projection(_insert_or_find(session, model, draft.semantic_key))
    _require_identical(record, draft, commit)
    return record


def _insert_or_find(session: Session, model, semantic_key: str):
    try:
        with session.begin_nested():
            session.add(model)
            session.flush()
    except IntegrityError as error:
        existing = session.scalar(
            select(type(model)).where(type(model).semantic_key == semantic_key)
        )
        if existing is None:
            raise error
        return existing
    return model


def _require_identical(record, draft, commit: TickSliceCommit) -> None:
    same_owner = record.team_id == commit.team_id and record.run_id == commit.run_id
    same_identity = record.id == draft.id and record.semantic_key == draft.semantic_key
    same_content = record.deduplication_content() == draft.deduplication_content()
    if not same_owner or not same_identity or not same_content:
        raise SemanticDeduplicationConflict(
            f"semantic key {draft.semantic_key!r} identifies different immutable content"
        )


def _page_rows(session: Session, model, query) -> tuple[Sequence[Any], int | None]:
    statement = select(model).where(model.team_id == str(query.team_id))
    if query.run_id is not None:
        statement = statement.where(model.run_id == str(query.run_id))
    if query.after_sequence is not None:
        statement = statement.where(model.append_sequence > query.after_sequence)
    statement = statement.order_by(model.append_sequence).limit(query.limit + 1)
    rows = tuple(session.scalars(statement))
    visible = rows[: query.limit]
    cursor = visible[-1].append_sequence if len(rows) > query.limit else None
    return visible, cursor


def _map_runtime(model: V2TeamRuntimeModel) -> TeamRuntime:
    return TeamRuntime(
        id=UUID(model.id),
        team_id=UUID(model.team_id),
        run_id=UUID(model.run_id),
        version=model.version,
        state=model.state,
        simulation_time=model.simulation_time,
        next_wake_at=model.next_wake_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _stored_envelope(model) -> dict[str, object]:
    return {
        "id": UUID(model.id),
        "semantic_key": model.semantic_key,
        "schema_version": model.schema_version,
        "occurred_at": model.occurred_at,
        "canonical_payload": model.canonical_payload,
        "payload_sha256": model.payload_sha256,
        "append_sequence": model.append_sequence,
        "team_id": UUID(model.team_id),
        "run_id": UUID(model.run_id),
        "commit_id": UUID(model.commit_id),
        "transaction_sequence": model.transaction_sequence,
        "recorded_at": model.recorded_at,
    }


def _map_activity(model: V2ActivityEventModel) -> ActivityEvent:
    return ActivityEvent(
        **_stored_envelope(model),
        event_type=model.event_type,
        aggregate_type=model.aggregate_type,
        aggregate_id=UUID(model.aggregate_id),
        aggregate_version=model.aggregate_version,
    )


def _map_ground_truth(model: V2GroundTruthRecordModel) -> GroundTruthRecord:
    return GroundTruthRecord(
        **_stored_envelope(model),
        record_type=model.record_type,
        provenance_type=model.provenance_type,
    )


def _map_projection(model: V2ProjectionIntentModel) -> ProjectionIntent:
    return ProjectionIntent(
        **_stored_envelope(model),
        target_kind=model.target_kind,
        operation_type=model.operation_type,
        aggregate_id=UUID(model.aggregate_id),
        aggregate_version=model.aggregate_version,
        status=model.status,
    )
