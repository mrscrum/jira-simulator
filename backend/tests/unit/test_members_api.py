import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_session
from app.api.routers.members import router as members_router
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
    test_app.include_router(teams_router)
    test_app.include_router(members_router)

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


class TestListMembers:
    def test_returns_empty_list(self, client, team_id):
        response = client.get(f"/teams/{team_id}/members")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_team_members(self, client, team_id):
        client.post(f"/teams/{team_id}/members", json={"name": "Alice", "role": "Dev"})
        client.post(f"/teams/{team_id}/members", json={"name": "Bob", "role": "QA"})
        response = client.get(f"/teams/{team_id}/members")
        assert len(response.json()) == 2

    def test_returns_404_for_nonexistent_team(self, client):
        response = client.get("/teams/999/members")
        assert response.status_code == 404


class TestCreateMember:
    def test_creates_member(self, client, team_id):
        response = client.post(
            f"/teams/{team_id}/members",
            json={"name": "Alice", "role": "Dev"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Alice"
        assert data["role"] == "Dev"
        assert data["daily_capacity_hours"] == 6.0
        assert data["max_concurrent_wip"] == 3

    def test_creates_member_with_custom_capacity(self, client, team_id):
        response = client.post(
            f"/teams/{team_id}/members",
            json={
                "name": "Alice", "role": "Dev",
                "daily_capacity_hours": 7.0, "max_concurrent_wip": 5,
            },
        )
        assert response.status_code == 201
        assert response.json()["daily_capacity_hours"] == 7.0
        assert response.json()["max_concurrent_wip"] == 5

    def test_rejects_missing_name(self, client, team_id):
        response = client.post(f"/teams/{team_id}/members", json={"role": "Dev"})
        assert response.status_code == 422


class TestUpdateMember:
    def test_updates_member(self, client, team_id):
        create = client.post(f"/teams/{team_id}/members", json={"name": "Alice", "role": "Dev"})
        member_id = create.json()["id"]
        response = client.put(
            f"/teams/{team_id}/members/{member_id}",
            json={"name": "Alice Smith"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Alice Smith"

    def test_returns_404_for_nonexistent_member(self, client, team_id):
        response = client.put(f"/teams/{team_id}/members/999", json={"name": "X"})
        assert response.status_code == 404


class TestDeleteMember:
    def test_deletes_member(self, client, team_id):
        create = client.post(f"/teams/{team_id}/members", json={"name": "Alice", "role": "Dev"})
        member_id = create.json()["id"]
        response = client.delete(f"/teams/{team_id}/members/{member_id}")
        assert response.status_code == 200

        members = client.get(f"/teams/{team_id}/members").json()
        assert len(members) == 0

    def test_returns_404_for_nonexistent_member(self, client, team_id):
        response = client.delete(f"/teams/{team_id}/members/999")
        assert response.status_code == 404
