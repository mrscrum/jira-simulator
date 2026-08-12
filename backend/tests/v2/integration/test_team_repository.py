from dataclasses import replace
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_session
from app.api.routers.teams import router as teams_router
from app.models import Base
from app.models.organization import Organization
from app.models.team import Team
from app.v2.application.create_team import CreateTeamCommand, CreateTeamService
from app.v2.persistence.team_models import (
    V2RunModel,
    V2TeamBlueprintModel,
    V2TeamModel,
    V2TeamRuntimeModel,
)
from app.v2.persistence.team_repository import SqlAlchemyV2TeamRepository

V2_MODELS = (V2TeamModel, V2TeamBlueprintModel, V2RunModel, V2TeamRuntimeModel)


def _create_aggregate(session_factory, blueprint_json, requested_at):
    repository = SqlAlchemyV2TeamRepository(session_factory)
    command = CreateTeamCommand("request-1", blueprint_json, requested_at)
    return CreateTeamService(repository).create(command)


def _row_counts(session_factory) -> list[int]:
    with session_factory() as session:
        return [session.scalar(select(func.count(model.id))) for model in V2_MODELS]


def test_repository_restart_uses_disposed_and_new_engine(
    tmp_path, resolved_blueprint_json, requested_at
):
    database_url = f"sqlite:///{tmp_path / 'restart.db'}"
    first_engine = create_engine(database_url)
    Base.metadata.create_all(first_engine)
    aggregate = _create_aggregate(
        sessionmaker(bind=first_engine), resolved_blueprint_json, requested_at
    )
    first_engine.dispose()

    restarted_engine = create_engine(database_url)
    restarted_factory = sessionmaker(bind=restarted_engine)
    reloaded = SqlAlchemyV2TeamRepository(restarted_factory).get_by_id(aggregate.team.id)

    assert reloaded == aggregate
    assert _row_counts(restarted_factory) == [1, 1, 1, 1]
    restarted_engine.dispose()


def test_actual_final_runtime_insert_failure_rolls_back_every_row(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    engine = v2_session_factory.kw["bind"]

    def fail_runtime_insert(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith("INSERT INTO V2_TEAM_RUNTIMES"):
            raise RuntimeError("injected runtime INSERT failure")

    event.listen(engine, "before_cursor_execute", fail_runtime_insert)
    try:
        with pytest.raises(RuntimeError, match="runtime INSERT"):
            _create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    finally:
        event.remove(engine, "before_cursor_execute", fail_runtime_insert)

    assert _row_counts(v2_session_factory) == [0, 0, 0, 0]


def test_repository_rejects_naive_runtime_datetime_atomically(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    class CaptureRepository:
        def create(self, aggregate):
            return aggregate

    command = CreateTeamCommand("request-1", resolved_blueprint_json, requested_at)
    aggregate = CreateTeamService(CaptureRepository()).create(command)
    invalid_runtime = replace(aggregate.runtime, simulation_time=datetime(2026, 8, 10))

    with pytest.raises(StatementError, match="aware datetime"):
        SqlAlchemyV2TeamRepository(v2_session_factory).create(
            replace(aggregate, runtime=invalid_runtime)
        )

    assert _row_counts(v2_session_factory) == [0, 0, 0, 0]


def test_v1_team_and_route_cannot_see_v2_aggregate(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    with v2_session_factory.begin() as session:
        organization = Organization(name="Legacy Organization")
        session.add(organization)
        session.flush()
        session.add(Team(organization_id=organization.id, name="Legacy", jira_project_key="LEG"))
    aggregate = _create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)

    with v2_session_factory() as session:
        legacy_teams = session.scalars(select(Team)).all()
    response = _legacy_teams_response(v2_session_factory)
    reloaded = SqlAlchemyV2TeamRepository(v2_session_factory).get_by_id(aggregate.team.id)

    assert [team.name for team in legacy_teams] == ["Legacy"]
    assert [team["name"] for team in response.json()] == ["Legacy"]
    assert reloaded == aggregate


def _legacy_teams_response(session_factory):
    application = FastAPI()
    application.include_router(teams_router)

    def override_session():
        with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    with TestClient(application) as client:
        return client.get("/teams")
