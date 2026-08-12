from copy import deepcopy
from datetime import datetime

import pytest

from app.v2.application.create_team import (
    CreateTeamCommand,
    CreateTeamService,
    InvalidResolvedBlueprint,
    TeamCreationConflict,
)
from app.v2.domain.canonical_json import canonical_json, canonical_sha256
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


def test_create_team_hashes_original_canonical_offset_document(
    blueprint_document: dict[str, object], requested_at
):
    class ReturningRepository:
        def create(self, aggregate):
            return aggregate

    changed = deepcopy(blueprint_document)
    changed["scrum"]["first_boundary"] = "2026-08-13T09:00:00-07:00"
    availability = changed["members"][1]["availability"][0]
    availability["starts_at"] = "2026-08-20T09:00:00-07:00"
    availability["ends_at"] = "2026-08-20T17:00:00-07:00"
    document = canonical_json(changed)

    aggregate = CreateTeamService(ReturningRepository()).create(
        CreateTeamCommand("offset-request", document, requested_at)
    )

    assert aggregate.blueprint.canonical_json() == document
    assert aggregate.blueprint_sha256 == canonical_sha256(changed)
