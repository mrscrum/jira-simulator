import pytest
from sqlalchemy import func, select

from app.v2.application.create_team import CreateTeamCommand, CreateTeamService
from app.v2.persistence.team_models import (
    V2RunModel,
    V2TeamBlueprintModel,
    V2TeamModel,
    V2TeamRuntimeModel,
)
from app.v2.persistence.team_repository import SqlAlchemyV2TeamRepository


def test_repository_creates_all_rows_and_restart_reloads(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    repository = SqlAlchemyV2TeamRepository(v2_session_factory)
    aggregate = CreateTeamService(repository).create(
        CreateTeamCommand("request-1", resolved_blueprint_json, requested_at)
    )

    with v2_session_factory() as session:
        counts = [
            session.scalar(select(func.count(model.id)))
            for model in (V2TeamModel, V2TeamBlueprintModel, V2RunModel, V2TeamRuntimeModel)
        ]
    reloaded = SqlAlchemyV2TeamRepository(v2_session_factory).get_by_id(aggregate.team.id)

    assert counts == [1, 1, 1, 1]
    assert reloaded == aggregate


def test_final_insert_failure_rolls_back_every_v2_row(
    v2_session_factory, resolved_blueprint_json, requested_at, monkeypatch
):
    repository = SqlAlchemyV2TeamRepository(v2_session_factory)
    monkeypatch.setattr(
        repository,
        "_add_runtime",
        lambda session, aggregate: (_ for _ in ()).throw(
            RuntimeError("injected final insert failure")
        ),
    )

    with pytest.raises(RuntimeError, match="injected"):
        CreateTeamService(repository).create(
            CreateTeamCommand("request-1", resolved_blueprint_json, requested_at)
        )

    with v2_session_factory() as session:
        counts = [
            session.scalar(select(func.count(model.id)))
            for model in (V2TeamModel, V2TeamBlueprintModel, V2RunModel, V2TeamRuntimeModel)
        ]
    assert counts == [0, 0, 0, 0]
