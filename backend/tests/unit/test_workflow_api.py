import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_session
from app.api.routers.teams import router as teams_router
from app.api.routers.workflow import router as workflow_router
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
    test_app.include_router(teams_router)
    test_app.include_router(workflow_router)

    def override():
        session = test_db()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_session] = override
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c
    test_app.dependency_overrides.clear()


@pytest.fixture
def team_id(client):
    response = client.post("/teams", json={"name": "Alpha", "jira_project_key": "ALPHA"})
    return response.json()["id"]


class TestGetWorkflow:
    def test_returns_workflow_for_team(self, client, team_id):
        response = client.get(f"/teams/{team_id}/workflow")
        assert response.status_code == 200
        data = response.json()
        assert data["team_id"] == team_id
        assert "steps" in data
        assert data["steps"] == []

    def test_returns_404_for_nonexistent_team(self, client):
        response = client.get("/teams/999/workflow")
        assert response.status_code == 404


class TestAddStep:
    def test_adds_step_to_workflow(self, client, team_id):
        response = client.post(
            f"/teams/{team_id}/workflow/steps",
            json={
                "jira_status": "In Dev",
                "role_required": "Dev",
                "order": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["jira_status"] == "In Dev"
        assert data["role_required"] == "Dev"

    def test_rejects_missing_jira_status(self, client, team_id):
        response = client.post(
            f"/teams/{team_id}/workflow/steps",
            json={"role_required": "Dev", "order": 1},
        )
        assert response.status_code == 422


class TestUpdateStep:
    def test_updates_step(self, client, team_id):
        create = client.post(
            f"/teams/{team_id}/workflow/steps",
            json={"jira_status": "In Dev", "role_required": "Dev", "order": 1},
        )
        step_id = create.json()["id"]
        response = client.put(
            f"/teams/{team_id}/workflow/steps/{step_id}",
            json={"max_wait_hours": 48.0},
        )
        assert response.status_code == 200
        assert response.json()["max_wait_hours"] == 48.0

    def test_returns_404_for_nonexistent_step(self, client, team_id):
        response = client.put(
            f"/teams/{team_id}/workflow/steps/999",
            json={"max_wait_hours": 48.0},
        )
        assert response.status_code == 404


class TestDeleteStep:
    def test_deletes_step(self, client, team_id):
        create = client.post(
            f"/teams/{team_id}/workflow/steps",
            json={"jira_status": "In Dev", "role_required": "Dev", "order": 1},
        )
        step_id = create.json()["id"]
        response = client.delete(f"/teams/{team_id}/workflow/steps/{step_id}")
        assert response.status_code == 200

        wf = client.get(f"/teams/{team_id}/workflow").json()
        assert len(wf["steps"]) == 0

    def test_returns_404_for_nonexistent_step(self, client, team_id):
        response = client.delete(f"/teams/{team_id}/workflow/steps/999")
        assert response.status_code == 404


class TestFullWorkflowReplace:
    def test_replaces_entire_workflow(self, client, team_id):
        client.post(
            f"/teams/{team_id}/workflow/steps",
            json={"jira_status": "Old Status", "role_required": "Dev", "order": 1},
        )
        response = client.put(
            f"/teams/{team_id}/workflow",
            json={
                "steps": [
                    {
                        "jira_status": "To Do",
                        "role_required": "BA",
                        "order": 1,
                    },
                    {
                        "jira_status": "In Dev",
                        "role_required": "Dev",
                        "order": 2,
                        "touch_time_configs": [
                            {
                                "issue_type": "Story", "story_points": 5,
                                "min_hours": 4.0, "max_hours": 8.0,
                            },
                        ],
                    },
                    {
                        "jira_status": "Done",
                        "role_required": "QA",
                        "order": 3,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["steps"]) == 3
        assert data["steps"][0]["jira_status"] == "To Do"
        assert data["steps"][1]["jira_status"] == "In Dev"

    def test_replace_includes_touch_time_configs(self, client, team_id):
        response = client.put(
            f"/teams/{team_id}/workflow",
            json={
                "steps": [
                    {
                        "jira_status": "In Dev",
                        "role_required": "Dev",
                        "order": 1,
                        "touch_time_configs": [
                            {
                                "issue_type": "Story", "story_points": 5,
                                "min_hours": 4.0, "max_hours": 8.0,
                            },
                            {
                                "issue_type": "Bug", "story_points": 3,
                                "min_hours": 2.0, "max_hours": 4.0,
                            },
                        ],
                    },
                ],
            },
        )
        assert response.status_code == 200
        steps = response.json()["steps"]
        assert len(steps[0]["touch_time_configs"]) == 2


class TestWorkflowStepNesting:
    def test_get_workflow_includes_nested_touch_time_configs(self, client, team_id):
        client.put(
            f"/teams/{team_id}/workflow",
            json={
                "steps": [
                    {
                        "jira_status": "In Dev",
                        "role_required": "Dev",
                        "order": 1,
                        "touch_time_configs": [
                            {
                                "issue_type": "Story", "story_points": 5,
                                "min_hours": 4.0, "max_hours": 8.0,
                            },
                        ],
                    },
                ],
            },
        )
        response = client.get(f"/teams/{team_id}/workflow")
        assert response.status_code == 200
        steps = response.json()["steps"]
        assert len(steps) == 1
        assert len(steps[0]["touch_time_configs"]) == 1
        ttc = steps[0]["touch_time_configs"][0]
        assert ttc["issue_type"] == "Story"
        assert ttc["story_points"] == 5
