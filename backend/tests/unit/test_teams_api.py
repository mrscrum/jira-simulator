import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_session
from app.api.routers.teams import router as teams_router
from app.models import Base  # noqa: F401 — importing models registers them with Base


def _create_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(teams_router)
    return test_app


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    yield session_factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(test_db):
    test_app = _create_test_app()

    def override_get_session():
        session = test_db()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_session] = override_get_session
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client
    test_app.dependency_overrides.clear()


class TestListTeams:
    def test_returns_empty_list_when_no_teams(self, client):
        response = client.get("/teams")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_created_teams(self, client):
        client.post("/teams", json={"name": "Alpha", "jira_project_key": "ALPHA"})
        client.post("/teams", json={"name": "Beta", "jira_project_key": "BETA"})
        response = client.get("/teams")
        assert response.status_code == 200
        teams = response.json()
        assert len(teams) == 2


class TestCreateTeam:
    def test_creates_team_with_valid_data(self, client):
        response = client.post(
            "/teams",
            json={"name": "Alpha", "jira_project_key": "ALPHA"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Alpha"
        assert data["jira_project_key"] == "ALPHA"
        assert "id" in data

    def test_auto_creates_organization(self, client):
        response = client.post(
            "/teams",
            json={"name": "Alpha", "jira_project_key": "ALPHA"},
        )
        assert response.status_code == 201
        assert response.json()["organization_id"] is not None

    def test_auto_creates_dysfunction_config(self, client, test_db):
        response = client.post(
            "/teams",
            json={"name": "Alpha", "jira_project_key": "ALPHA"},
        )
        team_id = response.json()["id"]
        session = test_db()
        from app.models.dysfunction_config import DysfunctionConfig

        config = session.query(DysfunctionConfig).filter_by(team_id=team_id).first()
        session.close()
        assert config is not None

    def test_auto_creates_workflow(self, client, test_db):
        response = client.post(
            "/teams",
            json={"name": "Alpha", "jira_project_key": "ALPHA"},
        )
        team_id = response.json()["id"]
        session = test_db()
        from app.models.workflow import Workflow

        workflow = session.query(Workflow).filter_by(team_id=team_id).first()
        session.close()
        assert workflow is not None

    def test_rejects_missing_name(self, client):
        response = client.post(
            "/teams",
            json={"jira_project_key": "ALPHA"},
        )
        assert response.status_code == 422

    def test_rejects_missing_project_key(self, client):
        response = client.post(
            "/teams",
            json={"name": "Alpha"},
        )
        assert response.status_code == 422

    def test_rejects_duplicate_project_key(self, client):
        client.post("/teams", json={"name": "Alpha", "jira_project_key": "ALPHA"})
        response = client.post(
            "/teams",
            json={"name": "Beta", "jira_project_key": "ALPHA"},
        )
        assert response.status_code == 409


class TestGetTeam:
    def test_returns_team_by_id(self, client):
        create_response = client.post(
            "/teams",
            json={"name": "Alpha", "jira_project_key": "ALPHA"},
        )
        team_id = create_response.json()["id"]
        response = client.get(f"/teams/{team_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Alpha"

    def test_returns_404_for_nonexistent_team(self, client):
        response = client.get("/teams/999")
        assert response.status_code == 404


class TestUpdateTeam:
    def test_updates_team_name(self, client):
        create_response = client.post(
            "/teams",
            json={"name": "Alpha", "jira_project_key": "ALPHA"},
        )
        team_id = create_response.json()["id"]
        response = client.put(
            f"/teams/{team_id}",
            json={"name": "Alpha Renamed"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Alpha Renamed"

    def test_returns_404_for_nonexistent_team(self, client):
        response = client.put("/teams/999", json={"name": "X"})
        assert response.status_code == 404


class TestDeleteTeam:
    def test_soft_deletes_team(self, client):
        create_response = client.post(
            "/teams",
            json={"name": "Alpha", "jira_project_key": "ALPHA"},
        )
        team_id = create_response.json()["id"]
        response = client.delete(f"/teams/{team_id}")
        assert response.status_code == 200

        get_response = client.get(f"/teams/{team_id}")
        assert get_response.json()["is_active"] is False

    def test_returns_404_for_nonexistent_team(self, client):
        response = client.delete("/teams/999")
        assert response.status_code == 404
