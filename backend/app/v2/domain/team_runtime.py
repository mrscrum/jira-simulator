"""Immutable persisted v2 team aggregate contracts."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.v2.domain.team_blueprint import ResolvedTeamBlueprint


@dataclass(frozen=True)
class V2Team:
    id: UUID
    idempotency_key: str
    blueprint_sha256: str
    name: str
    methodology: str
    created_at: datetime


@dataclass(frozen=True)
class V2Run:
    id: UUID
    team_id: UUID
    ordinal: int
    state: str
    created_at: datetime


@dataclass(frozen=True)
class TeamRuntime:
    id: UUID
    team_id: UUID
    run_id: UUID
    state: str
    simulation_time: datetime
    next_wake_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PersistedTeamAggregate:
    team: V2Team
    blueprint_id: UUID
    blueprint: ResolvedTeamBlueprint
    blueprint_sha256: str
    blueprint_recorded_at: datetime
    run: V2Run
    runtime: TeamRuntime
