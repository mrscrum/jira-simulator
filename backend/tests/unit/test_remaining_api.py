from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_session
from app.api.routers.dependencies import router as deps_router
from app.api.routers.dysfunctions import router as dysf_router
from app.api.routers.jira_integration import (
    get_bootstrapper,
    get_health_monitor,
    get_jira_client,
    get_write_queue,
)
from app.api.routers.jira_integration import (
    router as jira_router,
)
from app.api.routers.simulation import router as sim_router
from app.api.routers.teams import router as teams_router
from app.models import Base  # noqa: F401


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(test_db):
    test_app = FastAPI()
    for r in [teams_router, dysf_router, deps_router, sim_router, jira_router]:
        test_app.include_router(r)

    def override():
        session = test_db()
        try:
            yield session
        finally:
            session.close()

    mock_jira = AsyncMock()
    mock_jira.get_project_statuses = AsyncMock(return_value=[
        {"name": "To Do", "statusCategory": {"key": "new"}},
        {"name": "Done", "statusCategory": {"key": "done"}},
    ])
    mock_health = MagicMock()
    mock_health.status = "ONLINE"
    mock_health.last_checked = None
    mock_health.last_online = None
    mock_health.consecutive_failures = 0
    mock_health.outage_start = None

    test_app.dependency_overrides[get_session] = override
    test_app.dependency_overrides[get_jira_client] = lambda: mock_jira
    test_app.dependency_overrides[get_health_monitor] = lambda: mock_health
    test_app.dependency_overrides[get_bootstrapper] = lambda: AsyncMock()
    test_app.dependency_overrides[get_write_queue] = lambda: MagicMock()
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c
    test_app.dependency_overrides.clear()


@pytest.fixture
def two_teams(client):
    r1 = client.post("/teams", json={"name": "Alpha", "jira_project_key": "ALPHA"})
    r2 = client.post("/teams", json={"name": "Beta", "jira_project_key": "BETA"})
    return r1.json()["id"], r2.json()["id"]


class TestGetDysfunctions:
    def test_returns_config_for_team(self, client, two_teams):
        team_id = two_teams[0]
        response = client.get(f"/teams/{team_id}/dysfunctions")
        assert response.status_code == 200
        data = response.json()
        assert data["team_id"] == team_id
        assert data["low_quality_probability"] == 0.15

    def test_returns_404_for_nonexistent_team(self, client):
        response = client.get("/teams/999/dysfunctions")
        assert response.status_code == 404


class TestUpdateDysfunction:
    def test_updates_low_quality_fields(self, client, two_teams):
        team_id = two_teams[0]
        response = client.put(
            f"/teams/{team_id}/dysfunctions/low_quality",
            json={
                "low_quality_probability": 0.30,
                "low_quality_ba_po_touch_min": 2.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["low_quality_probability"] == 0.30
        assert data["low_quality_ba_po_touch_min"] == 2.0

    def test_updates_scope_creep_fields(self, client, two_teams):
        team_id = two_teams[0]
        response = client.put(
            f"/teams/{team_id}/dysfunctions/scope_creep",
            json={"scope_creep_probability": 0.25},
        )
        assert response.status_code == 200
        assert response.json()["scope_creep_probability"] == 0.25

    def test_returns_404_for_invalid_type(self, client, two_teams):
        team_id = two_teams[0]
        response = client.put(
            f"/teams/{team_id}/dysfunctions/nonexistent",
            json={"low_quality_probability": 0.5},
        )
        assert response.status_code == 404


class TestDependencies:
    def test_list_empty(self, client):
        response = client.get("/dependencies")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_dependency(self, client, two_teams):
        response = client.post(
            "/dependencies",
            json={
                "source_team_id": two_teams[0],
                "target_team_id": two_teams[1],
                "dependency_type": "blocks",
            },
        )
        assert response.status_code == 201
        assert response.json()["dependency_type"] == "blocks"

    def test_rejects_same_team(self, client, two_teams):
        response = client.post(
            "/dependencies",
            json={
                "source_team_id": two_teams[0],
                "target_team_id": two_teams[0],
                "dependency_type": "blocks",
            },
        )
        assert response.status_code == 400

    def test_rejects_duplicate(self, client, two_teams):
        payload = {
            "source_team_id": two_teams[0],
            "target_team_id": two_teams[1],
            "dependency_type": "blocks",
        }
        client.post("/dependencies", json=payload)
        response = client.post("/dependencies", json=payload)
        assert response.status_code == 409

    def test_delete_dependency(self, client, two_teams):
        create = client.post(
            "/dependencies",
            json={
                "source_team_id": two_teams[0],
                "target_team_id": two_teams[1],
                "dependency_type": "blocks",
            },
        )
        dep_id = create.json()["id"]
        response = client.delete(f"/dependencies/{dep_id}")
        assert response.status_code == 200

        deps = client.get("/dependencies").json()
        assert len(deps) == 0

    def test_delete_returns_404(self, client):
        response = client.delete("/dependencies/999")
        assert response.status_code == 404


class TestSimulationStubs:
    def test_get_status(self, client):
        response = client.get("/simulation/status")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"

    def test_start(self, client):
        response = client.post("/simulation/start")
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_pause(self, client):
        response = client.post("/simulation/pause")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    def test_reset(self, client):
        response = client.post("/simulation/reset")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"

    def test_update_tick_interval(self, client):
        response = client.put(
            "/simulation/tick-interval",
            json={"minutes": 15},
        )
        assert response.status_code == 200
        assert response.json()["minutes"] == 15

    def test_inject(self, client):
        response = client.post(
            "/simulate/inject",
            json={
                "team_id": 1,
                "dysfunction_type": "low_quality",
            },
        )
        assert response.status_code == 200
        assert response.json()["injected"] is True


class TestJiraProxyStub:
    def test_returns_sample_statuses(self, client):
        response = client.get("/jira/projects/ALPHA/statuses")
        assert response.status_code == 200
        statuses = response.json()
        assert len(statuses) > 0
        assert "name" in statuses[0]
        assert "category" in statuses[0]
