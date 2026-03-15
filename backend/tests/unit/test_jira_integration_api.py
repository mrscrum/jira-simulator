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
from app.api.routers.jira_integration import (
    router as jira_router,
)
from app.api.routers.teams import router as teams_router
from app.models import Base


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
def mock_jira_client():
    client = AsyncMock()
    client.get_project_statuses = AsyncMock(
        return_value=[
            {"name": "To Do", "statusCategory": {"key": "new"}},
            {"name": "Done", "statusCategory": {"key": "done"}},
        ]
    )
    return client


@pytest.fixture
def mock_health():
    health = MagicMock()
    health.status = "ONLINE"
    health.last_checked = None
    health.last_online = None
    health.consecutive_failures = 0
    health.outage_start = None
    return health


@pytest.fixture
def mock_bootstrapper():
    return AsyncMock()


@pytest.fixture
def mock_queue():
    queue = MagicMock()
    queue.retry_failed = MagicMock(return_value=3)
    return queue


@pytest.fixture
def client(
    test_db,
    mock_jira_client,
    mock_health,
    mock_bootstrapper,
    mock_queue,
):
    test_app = FastAPI()
    test_app.include_router(teams_router)
    test_app.include_router(jira_router)

    def override_session():
        session = test_db()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_jira_client] = lambda: mock_jira_client
    test_app.dependency_overrides[get_health_monitor] = lambda: mock_health
    test_app.dependency_overrides[get_bootstrapper] = lambda: mock_bootstrapper
    test_app.dependency_overrides[get_write_queue] = lambda: mock_queue

    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c
    test_app.dependency_overrides.clear()


@pytest.fixture
def team_id(client):
    response = client.post(
        "/teams", json={"name": "Alpha", "jira_project_key": "ALPHA"}
    )
    return response.json()["id"]


class TestBootstrapEndpoint:
    def test_triggers_bootstrap(self, client, team_id, mock_bootstrapper):
        response = client.post(f"/jira/bootstrap/{team_id}")
        assert response.status_code == 200
        mock_bootstrapper.bootstrap_team.assert_awaited_once_with(team_id)

    def test_returns_404_for_nonexistent_team(self, client):
        response = client.post("/jira/bootstrap/999")
        assert response.status_code == 404


class TestBootstrapStatus:
    def test_returns_status(self, client, team_id):
        response = client.get(f"/jira/bootstrap/{team_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["bootstrapped"] is False

    def test_returns_404_for_missing_team(self, client):
        response = client.get("/jira/bootstrap/999/status")
        assert response.status_code == 404


class TestHealthEndpoint:
    def test_returns_health_status(self, client, mock_health):
        mock_health.status = "ONLINE"
        response = client.get("/jira/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ONLINE"


class TestQueueStatus:
    def test_returns_queue_counts(self, client, test_db):
        response = client.get("/jira/queue/status")
        assert response.status_code == 200
        data = response.json()
        assert "pending" in data
        assert "total" in data


class TestRetryFailed:
    def test_retries_failed_items(self, client, mock_queue):
        response = client.post("/jira/queue/retry-failed")
        assert response.status_code == 200
        data = response.json()
        assert data["retried"] == 3
        mock_queue.retry_failed.assert_called_once()


class TestProjectStatuses:
    def test_returns_statuses_from_jira(self, client, mock_jira_client):
        response = client.get("/jira/projects/ALPHA/statuses")
        assert response.status_code == 200
        statuses = response.json()
        assert len(statuses) == 2
        mock_jira_client.get_project_statuses.assert_awaited_once()

    def test_falls_back_on_error(self, client, mock_jira_client):
        mock_jira_client.get_project_statuses.side_effect = Exception("offline")
        response = client.get("/jira/projects/TEST/statuses")
        assert response.status_code == 200
        statuses = response.json()
        assert len(statuses) > 0
