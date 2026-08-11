"""Atomic persistence port and SQLAlchemy adapter for v2 team creation."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.v2.application.create_team import TeamCreationConflict
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint
from app.v2.domain.team_runtime import PersistedTeamAggregate, TeamRuntime, V2Run, V2Team
from app.v2.persistence.team_models import (
    V2RunModel,
    V2TeamBlueprintModel,
    V2TeamModel,
    V2TeamRuntimeModel,
)


class V2TeamRepository(ABC):
    """Persistence port that never exposes an ORM model to callers."""

    @abstractmethod
    def create(self, aggregate: PersistedTeamAggregate) -> PersistedTeamAggregate:
        """Atomically store or replay a team aggregate."""

    @abstractmethod
    def get_by_id(self, team_id: UUID) -> PersistedTeamAggregate | None:
        """Return a detached aggregate by semantic team UUID."""

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> PersistedTeamAggregate | None:
        """Return a detached aggregate by client idempotency key."""


class SqlAlchemyV2TeamRepository(V2TeamRepository):
    """Short-transaction SQLAlchemy implementation of the v2 team port."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def create(self, aggregate: PersistedTeamAggregate) -> PersistedTeamAggregate:
        try:
            with self._session_factory.begin() as session:
                existing = self._get_by_key(session, aggregate.team.idempotency_key)
                if existing is not None:
                    return self._resolve_existing(
                        self._load_aggregate(session, existing), aggregate
                    )
                self._add_models(session, aggregate)
        except IntegrityError:
            existing = self.get_by_idempotency_key(aggregate.team.idempotency_key)
            if existing is not None:
                return self._resolve_existing(existing, aggregate)
            raise
        return aggregate

    def get_by_id(self, team_id: UUID) -> PersistedTeamAggregate | None:
        with self._session_factory() as session:
            team = session.get(V2TeamModel, str(team_id))
            return self._load_aggregate(session, team) if team else None

    def get_by_idempotency_key(self, key: str) -> PersistedTeamAggregate | None:
        with self._session_factory() as session:
            team = self._get_by_key(session, key)
            return self._load_aggregate(session, team) if team else None

    def _get_by_key(self, session: Session, key: str) -> V2TeamModel | None:
        return session.scalar(select(V2TeamModel).where(V2TeamModel.idempotency_key == key))

    @staticmethod
    def _resolve_existing(
        existing: PersistedTeamAggregate, submitted: PersistedTeamAggregate
    ) -> PersistedTeamAggregate:
        if existing.blueprint_sha256 != submitted.blueprint_sha256:
            raise TeamCreationConflict(
                "idempotency key is already associated with a different blueprint"
            )
        return existing

    def _add_models(self, session: Session, aggregate: PersistedTeamAggregate) -> None:
        self._add_team(session, aggregate)
        self._add_blueprint(session, aggregate)
        self._add_run(session, aggregate)
        self._add_runtime(session, aggregate)

    @staticmethod
    def _add_team(session: Session, aggregate: PersistedTeamAggregate) -> None:
        team = aggregate.team
        session.add(
            V2TeamModel(
                id=str(team.id),
                idempotency_key=team.idempotency_key,
                blueprint_sha256=team.blueprint_sha256,
                name=team.name,
                methodology=team.methodology,
                created_at=team.created_at,
            )
        )

    @staticmethod
    def _add_blueprint(session: Session, aggregate: PersistedTeamAggregate) -> None:
        session.add(
            V2TeamBlueprintModel(
                id=str(aggregate.blueprint_id),
                team_id=str(aggregate.team.id),
                schema_version=aggregate.blueprint.schema_version,
                canonical_json=aggregate.blueprint.canonical_json(),
                sha256=aggregate.blueprint_sha256,
                recorded_at=aggregate.blueprint_recorded_at,
            )
        )

    @staticmethod
    def _add_run(session: Session, aggregate: PersistedTeamAggregate) -> None:
        run = aggregate.run
        session.add(
            V2RunModel(
                id=str(run.id),
                team_id=str(run.team_id),
                ordinal=run.ordinal,
                state=run.state,
                created_at=run.created_at,
            )
        )

    @staticmethod
    def _add_runtime(session: Session, aggregate: PersistedTeamAggregate) -> None:
        runtime = aggregate.runtime
        session.add(
            V2TeamRuntimeModel(
                id=str(runtime.id),
                team_id=str(runtime.team_id),
                run_id=str(runtime.run_id),
                state=runtime.state,
                simulation_time=runtime.simulation_time,
                next_wake_at=runtime.next_wake_at,
                created_at=runtime.created_at,
                updated_at=runtime.updated_at,
            )
        )

    @staticmethod
    def _load_aggregate(session: Session, team: V2TeamModel) -> PersistedTeamAggregate:
        blueprint = session.scalar(
            select(V2TeamBlueprintModel).where(V2TeamBlueprintModel.team_id == team.id)
        )
        run = session.scalar(select(V2RunModel).where(V2RunModel.team_id == team.id))
        runtime = session.scalar(
            select(V2TeamRuntimeModel).where(V2TeamRuntimeModel.team_id == team.id)
        )
        if blueprint is None or run is None or runtime is None:
            raise RuntimeError("persisted v2 team aggregate is incomplete")
        return PersistedTeamAggregate(
            team=SqlAlchemyV2TeamRepository._map_team(team),
            blueprint_id=UUID(blueprint.id),
            blueprint=ResolvedTeamBlueprint.from_canonical_json(blueprint.canonical_json),
            blueprint_sha256=blueprint.sha256,
            blueprint_recorded_at=blueprint.recorded_at,
            run=SqlAlchemyV2TeamRepository._map_run(run),
            runtime=SqlAlchemyV2TeamRepository._map_runtime(runtime),
        )

    @staticmethod
    def _map_team(team: V2TeamModel) -> V2Team:
        return V2Team(
            UUID(team.id),
            team.idempotency_key,
            team.blueprint_sha256,
            team.name,
            team.methodology,
            team.created_at,
        )

    @staticmethod
    def _map_run(run: V2RunModel) -> V2Run:
        return V2Run(UUID(run.id), UUID(run.team_id), run.ordinal, run.state, run.created_at)

    @staticmethod
    def _map_runtime(runtime: V2TeamRuntimeModel) -> TeamRuntime:
        return TeamRuntime(
            UUID(runtime.id),
            UUID(runtime.team_id),
            UUID(runtime.run_id),
            runtime.state,
            runtime.simulation_time,
            runtime.next_wake_at,
            runtime.created_at,
            runtime.updated_at,
        )
