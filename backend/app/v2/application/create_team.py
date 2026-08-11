"""Application service for atomic v2 team aggregate creation."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.v2.domain.canonical_json import canonical_sha256, semantic_uuid
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint
from app.v2.domain.team_runtime import PersistedTeamAggregate, TeamRuntime, V2Run, V2Team


class InvalidResolvedBlueprint(ValueError):  # noqa: N818
    """The submitted snapshot or creation time is invalid for persistence."""


class TeamCreationConflict(ValueError):  # noqa: N818
    """An idempotency key has already been bound to another snapshot."""


class TeamCreator(Protocol):
    """Minimal application-facing creation port."""

    def create(self, aggregate: PersistedTeamAggregate) -> PersistedTeamAggregate:
        """Persist the aggregate atomically."""


@dataclass(frozen=True)
class CreateTeamCommand:
    idempotency_key: str
    blueprint_json: str
    requested_at: datetime


class CreateTeamService:
    """Validates a resolved snapshot and delegates one atomic persistence action."""

    def __init__(self, repository: TeamCreator):
        self._repository = repository

    def create(self, command: CreateTeamCommand) -> PersistedTeamAggregate:
        requested_at = self._normalize_request_time(command.requested_at)
        try:
            blueprint = ResolvedTeamBlueprint.from_canonical_json(command.blueprint_json)
        except ValueError as error:
            raise InvalidResolvedBlueprint(str(error)) from error
        aggregate = self._new_aggregate(command.idempotency_key, blueprint, requested_at)
        return self._repository.create(aggregate)

    @staticmethod
    def _normalize_request_time(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidResolvedBlueprint("requested_at must be aware")
        return value.astimezone(UTC)

    @staticmethod
    def _new_aggregate(
        idempotency_key: str, blueprint: ResolvedTeamBlueprint, requested_at: datetime
    ) -> PersistedTeamAggregate:
        blueprint_hash = canonical_sha256(json.loads(blueprint.canonical_json()))
        team_id = semantic_uuid(f"team/{blueprint_hash}")
        blueprint_id = semantic_uuid(f"blueprint/{team_id}/0")
        run_id = semantic_uuid(f"run/{team_id}/0")
        team = V2Team(
            team_id,
            idempotency_key,
            blueprint_hash,
            blueprint.team.name,
            blueprint.team.methodology,
            requested_at,
        )
        run = V2Run(run_id, team_id, 0, "CREATED", requested_at)
        runtime = CreateTeamService._new_runtime(team_id, run_id, requested_at)
        return PersistedTeamAggregate(
            team, blueprint_id, blueprint, blueprint_hash, requested_at, run, runtime
        )

    @staticmethod
    def _new_runtime(team_id: UUID, run_id: UUID, requested_at: datetime) -> TeamRuntime:
        runtime = TeamRuntime(
            semantic_uuid(f"runtime/{team_id}"),
            team_id,
            run_id,
            0,
            "CREATED",
            requested_at,
            None,
            requested_at,
            requested_at,
        )
        return runtime
