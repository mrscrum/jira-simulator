"""Tests for Stage 4 simulation API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_session
from app.api.routers.jira_integration import (
    get_bootstrapper,
    get_health_monitor,
    get_jira_client,
    get_write_queue,
)
from app.api.routers.simulation import router as sim_router
from app.api.routers.teams import router as teams_router
from app.engine.simulation import SimulationEngine
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
    test_app.include_router(sim_router)
    test_app.include_router(teams_router)

    def override():
        session = test_db()
        try:
            yield session
        finally:
            session.close()

    mock_jira = AsyncMock()
    mock_health = MagicMock()
    mock_health.status = "ONLINE"

    test_app.dependency_overrides[get_session] = override
    test_app.dependency_overrides[get_jira_client] = lambda: mock_jira
    test_app.dependency_overrides[get_health_monitor] = lambda: mock_health
    test_app.dependency_overrides[get_bootstrapper] = lambda: AsyncMock()
    test_app.dependency_overrides[get_write_queue] = lambda: MagicMock()

    test_app.state.simulation_engine = SimulationEngine(
        session_factory=test_db,
        write_queue=MagicMock(),
    )

    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c
    test_app.dependency_overrides.clear()


class TestSimulationControl:
    def test_start_then_status_is_running(self, client):
        client.post("/simulation/start")
        resp = client.get("/simulation/status")
        assert resp.json()["status"] == "running"

    def test_pause_and_resume(self, client):
        client.post("/simulation/start")
        client.post("/simulation/pause")
        resp = client.get("/simulation/status")
        assert resp.json()["status"] == "paused"

        client.post("/simulation/resume")
        resp = client.get("/simulation/status")
        assert resp.json()["status"] == "running"

    def test_reset_stops_engine(self, client):
        client.post("/simulation/start")
        client.post("/simulation/reset")
        resp = client.get("/simulation/status")
        assert resp.json()["status"] == "stopped"

    def test_tick_interval_update(self, client):
        resp = client.put("/simulation/tick-interval", json={"minutes": 10})
        assert resp.status_code == 200
        assert resp.json()["minutes"] == 10


class TestPerTeamControl:
    def test_pause_team(self, client):
        client.post("/teams", json={"name": "Alpha", "jira_project_key": "A"})
        resp = client.post("/simulation/1/pause")
        assert resp.status_code == 200

    def test_resume_team(self, client):
        client.post("/teams", json={"name": "Alpha", "jira_project_key": "A"})
        client.post("/simulation/1/pause")
        resp = client.post("/simulation/1/resume")
        assert resp.status_code == 200


class TestEngineHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/simulation/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "stopped"
        assert data["tick_count"] == 0
        assert data["paused_teams"] == []


class TestBacklogAPI:
    def test_get_backlog_empty(self, client):
        client.post("/teams", json={"name": "Alpha", "jira_project_key": "A"})
        resp = client.get("/simulation/1/backlog")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_generate_backlog(self, client):
        client.post("/teams", json={"name": "Alpha", "jira_project_key": "A"})
        resp = client.post(
            "/simulation/1/backlog/generate",
            json={"count": 3},
        )
        assert resp.status_code == 200
        assert resp.json()["generated"] == 3
        assert len(resp.json()["issues"]) == 3


class TestSprintControl:
    def test_get_current_sprint_404(self, client):
        client.post("/teams", json={"name": "Alpha", "jira_project_key": "A"})
        resp = client.get("/simulation/1/sprint/current")
        assert resp.status_code == 404
