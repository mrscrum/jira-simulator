"""One-transaction coherent reads and idempotent Scrum bootstrap persistence."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.v2.application.jira_provisioning import compose_jira_provisioning
from app.v2.application.live_team import LiveTeamState
from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.scrum_bootstrap import build_initial_scrum_state
from app.v2.domain.scrum_state import ScrumStateQuery
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint
from app.v2.domain.team_runtime import PersistedTeamAggregate, TeamRuntime, V2Run, V2Team
from app.v2.persistence.scrum_state_mapper import SqlAlchemyScrumStateMapper
from app.v2.persistence.team_models import (
    V2RunModel,
    V2TeamBlueprintModel,
    V2TeamModel,
    V2TeamRuntimeModel,
)
from app.v2.persistence.unit_of_work import append_projection_intents_in_session


class LiveTeamStore(Protocol):
    """Provides coherent persisted live-team state."""

    def load(self, team_id: UUID) -> LiveTeamState:
        """Load runtime and Scrum state in one transaction."""

    def ensure_bootstrapped(self, team_id: UUID, started_at: datetime) -> LiveTeamState:
        """Create initial Scrum state once, then return the coherent result."""


class SqlAlchemyLiveTeamStore:
    """SQLAlchemy implementation that owns exactly one short transaction per operation."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory
        self._scrum_mapper = SqlAlchemyScrumStateMapper()

    def load(self, team_id: UUID) -> LiveTeamState:
        with self._session_factory.begin() as session:
            aggregate = _load_aggregate(session, team_id)
            scrum = self._scrum_mapper.load(
                session, ScrumStateQuery(team_id, aggregate.runtime.run_id)
            )
            return LiveTeamState(aggregate, scrum)

    def ensure_bootstrapped(self, team_id: UUID, started_at: datetime) -> LiveTeamState:
        started = _utc(started_at)
        with self._session_factory.begin() as session:
            aggregate = _load_aggregate(session, team_id)
            scrum = self._scrum_mapper.load(
                session, ScrumStateQuery(team_id, aggregate.runtime.run_id)
            )
            if aggregate.runtime.state != "CREATED":
                live_state = LiveTeamState(aggregate, scrum)
            else:
                state = build_initial_scrum_state(aggregate, started, SeededDrawSource(aggregate))
                snapshot = self._scrum_mapper.add(session, state)
                runtime = _running_runtime(session, aggregate, started)
                self._after_scrum_persisted(session, state)
                live_state = LiveTeamState(replace(aggregate, runtime=runtime), snapshot)
            append_projection_intents_in_session(session, compose_jira_provisioning(live_state))
            return live_state

    def _after_scrum_persisted(self, session: Session, state: object) -> None:
        """Provide a narrow failure seam while preserving one transaction boundary."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("started_at must be aware")
    return value.astimezone(UTC)


def _load_aggregate(session: Session, team_id: UUID) -> PersistedTeamAggregate:
    team = session.get(V2TeamModel, str(team_id), populate_existing=True)
    if team is None:
        raise ValueError("persisted live team does not exist")
    blueprint = session.scalar(
        select(V2TeamBlueprintModel)
        .where(V2TeamBlueprintModel.team_id == team.id)
        .execution_options(populate_existing=True)
    )
    runtime = session.scalar(
        select(V2TeamRuntimeModel)
        .where(V2TeamRuntimeModel.team_id == team.id)
        .execution_options(populate_existing=True)
    )
    if blueprint is None or runtime is None:
        raise RuntimeError("persisted live team aggregate is incomplete")
    run = session.get(V2RunModel, runtime.run_id, populate_existing=True)
    if run is None or run.team_id != team.id:
        raise RuntimeError("runtime does not reference a team run")
    return PersistedTeamAggregate(
        V2Team(
            UUID(team.id),
            team.idempotency_key,
            team.blueprint_sha256,
            team.name,
            team.methodology,
            team.created_at,
        ),
        UUID(blueprint.id),
        ResolvedTeamBlueprint.from_canonical_json(blueprint.canonical_json),
        blueprint.sha256,
        blueprint.recorded_at,
        V2Run(UUID(run.id), UUID(run.team_id), run.ordinal, run.state, run.created_at),
        TeamRuntime(
            UUID(runtime.id),
            UUID(runtime.team_id),
            UUID(runtime.run_id),
            runtime.version,
            runtime.state,
            runtime.simulation_time,
            runtime.next_wake_at,
            runtime.created_at,
            runtime.updated_at,
        ),
    )


def _running_runtime(
    session: Session, aggregate: PersistedTeamAggregate, started_at: datetime
) -> TeamRuntime:
    runtime = session.get(V2TeamRuntimeModel, str(aggregate.runtime.id), populate_existing=True)
    if runtime is None:
        raise RuntimeError("persisted runtime disappeared during bootstrap")
    runtime.state = "RUNNING"
    runtime.simulation_time = started_at
    runtime.next_wake_at = _first_wake_at(aggregate, started_at)
    runtime.updated_at = started_at
    return TeamRuntime(
        UUID(runtime.id),
        UUID(runtime.team_id),
        UUID(runtime.run_id),
        runtime.version,
        runtime.state,
        runtime.simulation_time,
        runtime.next_wake_at,
        runtime.created_at,
        runtime.updated_at,
    )


def _first_wake_at(aggregate: PersistedTeamAggregate, started_at: datetime) -> datetime:
    boundary = aggregate.blueprint.scrum.first_boundary
    return boundary if started_at < boundary else started_at
