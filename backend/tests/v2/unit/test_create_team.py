from datetime import datetime

import pytest

from app.v2.application.create_team import (
    CreateTeamCommand,
    CreateTeamService,
    InvalidResolvedBlueprint,
    TeamCreationConflict,
)
from app.v2.persistence.team_repository import SqlAlchemyV2TeamRepository


def test_create_team_persists_initial_aggregate(
    v2_session_factory, resolved_blueprint_json: str, requested_at
):
    service = CreateTeamService(SqlAlchemyV2TeamRepository(v2_session_factory))

    aggregate = service.create(
        CreateTeamCommand("request-1", resolved_blueprint_json, requested_at)
    )

    assert aggregate.run.team_id == aggregate.team.id
    assert aggregate.runtime.simulation_time == requested_at
    assert aggregate.run.ordinal == 0


def test_create_team_is_idempotent_and_conflicts_on_different_blueprint(
    v2_session_factory, resolved_blueprint_json: str, requested_at
):
    service = CreateTeamService(SqlAlchemyV2TeamRepository(v2_session_factory))
    command = CreateTeamCommand("request-1", resolved_blueprint_json, requested_at)

    first = service.create(command)
    second = service.create(command)

    assert second == first
    with pytest.raises(TeamCreationConflict, match="idempotency"):
        service.create(
            CreateTeamCommand(
                "request-1",
                resolved_blueprint_json.replace("Payments Platform", "Revenue Platform"),
                requested_at,
            )
        )


def test_create_team_rejects_naive_timestamp_before_opening_repository(
    resolved_blueprint_json: str,
):
    class RepositoryThatMustNotOpen:
        def create(self, aggregate):
            raise AssertionError("repository opened")

    service = CreateTeamService(RepositoryThatMustNotOpen())
    with pytest.raises(InvalidResolvedBlueprint, match="aware"):
        service.create(
            CreateTeamCommand("request-1", resolved_blueprint_json, datetime(2026, 8, 10, 18, 30))
        )
