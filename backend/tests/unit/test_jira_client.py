from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from app.integrations.exceptions import (
    JiraAuthError,
    JiraConnectionError,
    JiraNotFoundError,
    JiraRateLimitError,
)
from app.integrations.jira_client import JiraClient


@pytest_asyncio.fixture
async def client():
    jira = JiraClient("https://test.atlassian.net", "user@test.com", "token123")
    yield jira
    await jira.close()


def _mock_response(status_code=200, json_data=None, headers=None):
    response = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        headers=headers or {},
        request=httpx.Request("GET", "https://test.atlassian.net"),
    )
    return response


class TestJiraClientAuth:
    @pytest.mark.asyncio
    async def test_uses_basic_auth_header(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(json_data={"id": "1"})
            await client.ping()
            call_kwargs = mock_req.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Basic ")


class TestPing:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={"accountId": "123"}
            )
            result = await client.ping()
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = httpx.ConnectError("timeout")
            result = await client.ping()
            assert result is False


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=401)
            with pytest.raises(JiraAuthError):
                await client.get_project("TEST")

    @pytest.mark.asyncio
    async def test_403_raises_auth_error(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=403)
            with pytest.raises(JiraAuthError):
                await client.get_project("TEST")

    @pytest.mark.asyncio
    async def test_404_raises_not_found(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=404)
            with pytest.raises(JiraNotFoundError):
                await client.get_issue("TEST-1")

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_with_retry_after(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                status_code=429, headers={"Retry-After": "30"}
            )
            with pytest.raises(JiraRateLimitError) as exc_info:
                await client.get_project("TEST")
            assert exc_info.value.retry_after == 30.0

    @pytest.mark.asyncio
    async def test_connection_error_raises_jira_connection_error(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = httpx.ConnectError("refused")
            with pytest.raises(JiraConnectionError):
                await client.get_project("TEST")


class TestGetProject:
    @pytest.mark.asyncio
    async def test_returns_project_data(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={"key": "TEST", "name": "Test Project"}
            )
            result = await client.get_project("TEST")
            assert result["key"] == "TEST"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=404)
            result = await client.get_project("MISSING")
            assert result is None


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_sends_correct_payload(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            myself_resp = _mock_response(
                json_data={"accountId": "abc123", "displayName": "Test"},
            )
            create_resp = _mock_response(
                status_code=201,
                json_data={"key": "NEW", "id": "10001"},
            )
            mock_req.side_effect = [myself_resp, create_resp]
            result = await client.create_project("NEW", "New Project", "scrum")
            assert result["key"] == "NEW"
            create_call = mock_req.call_args_list[1]
            assert create_call.kwargs["json"]["key"] == "NEW"
            assert create_call.kwargs["json"]["leadAccountId"] == "abc123"


class TestCreateIssue:
    @pytest.mark.asyncio
    async def test_returns_created_issue(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                status_code=201,
                json_data={"key": "TEST-1", "id": "10001"},
            )
            result = await client.create_issue(
                project_key="TEST",
                issue_type="Story",
                summary="Test story",
                fields={},
            )
            assert result["key"] == "TEST-1"


class TestTransitionIssue:
    @pytest.mark.asyncio
    async def test_sends_transition_request(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=204)
            await client.transition_issue("TEST-1", "31")
            call_kwargs = mock_req.call_args
            assert call_kwargs.kwargs["json"]["transition"]["id"] == "31"


class TestGetIssueTransitions:
    @pytest.mark.asyncio
    async def test_returns_transitions(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={
                    "transitions": [
                        {"id": "31", "name": "In Progress"},
                        {"id": "41", "name": "Done"},
                    ]
                }
            )
            result = await client.get_issue_transitions("TEST-1")
            assert len(result) == 2
            assert result[0]["id"] == "31"


class TestAddComment:
    @pytest.mark.asyncio
    async def test_sends_comment(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                status_code=201, json_data={"id": "100"}
            )
            result = await client.add_comment("TEST-1", "Hello from sim")
            assert result["id"] == "100"


class TestGetBoard:
    @pytest.mark.asyncio
    async def test_returns_board(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={
                    "values": [{"id": 42, "name": "TEST board"}]
                }
            )
            result = await client.get_board("TEST")
            assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_returns_none_when_no_boards(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={"values": []}
            )
            result = await client.get_board("TEST")
            assert result is None


class TestCustomFields:
    @pytest.mark.asyncio
    async def test_get_custom_fields(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data=[
                    {"id": "cf_10001", "name": "sim_assignee"},
                ]
            )
            result = await client.get_custom_fields()
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_field_id_by_name_found(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data=[
                    {"id": "cf_10001", "name": "sim_assignee"},
                    {"id": "cf_10002", "name": "sim_reporter"},
                ]
            )
            result = await client.get_field_id_by_name("sim_assignee")
            assert result == "cf_10001"

    @pytest.mark.asyncio
    async def test_get_field_id_by_name_not_found(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(json_data=[])
            result = await client.get_field_id_by_name("nonexistent")
            assert result is None


class TestProjectStatuses:
    @pytest.mark.asyncio
    async def test_returns_statuses(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data=[
                    {
                        "statuses": [
                            {"name": "To Do", "statusCategory": {"key": "new"}},
                            {"name": "Done", "statusCategory": {"key": "done"}},
                        ]
                    }
                ]
            )
            result = await client.get_project_statuses("TEST")
            assert len(result) == 2


class TestCreateIssueLink:
    @pytest.mark.asyncio
    async def test_sends_link_request(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=201)
            await client.create_issue_link("Blocks", "TEST-1", "TEST-2")
            call_kwargs = mock_req.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["type"]["name"] == "Blocks"


class TestSprintOperations:
    @pytest.mark.asyncio
    async def test_get_active_sprint(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={
                    "values": [
                        {"id": 10, "name": "Sprint 1", "state": "active"}
                    ]
                }
            )
            result = await client.get_active_sprint(42)
            assert result["id"] == 10

    @pytest.mark.asyncio
    async def test_get_active_sprint_none(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={"values": []}
            )
            result = await client.get_active_sprint(42)
            assert result is None

    @pytest.mark.asyncio
    async def test_create_sprint(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                status_code=201,
                json_data={"id": 11, "name": "Sprint 2"},
            )
            start = datetime(2026, 3, 1, tzinfo=UTC)
            end = datetime(2026, 3, 14, tzinfo=UTC)
            result = await client.create_sprint(42, "Sprint 2", start, end)
            assert result["id"] == 11

    @pytest.mark.asyncio
    async def test_add_issues_to_sprint(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=204)
            await client.add_issues_to_sprint(10, ["TEST-1", "TEST-2"])
            call_kwargs = mock_req.call_args
            assert "issues" in call_kwargs.kwargs["json"]


class TestSearchIssues:
    @pytest.mark.asyncio
    async def test_search_returns_issues(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={
                    "issues": [
                        {"key": "TEST-1"},
                        {"key": "TEST-2"},
                    ]
                }
            )
            result = await client.search_issues("project = TEST")
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_sends_jql_payload(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={"issues": []}
            )
            await client.search_issues(
                "project = TEST", fields=["summary", "status"],
            )
            call_kwargs = mock_req.call_args
            params = call_kwargs.kwargs["params"]
            assert params["jql"] == "project = TEST"
            assert params["fields"] == "summary,status"


class TestDeleteIssue:
    @pytest.mark.asyncio
    async def test_sends_delete_request(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=204)
            await client.delete_issue("TEST-1")
            call_args = mock_req.call_args
            assert call_args.args[0] == "DELETE"


class TestMoveIssuesToBacklog:
    @pytest.mark.asyncio
    async def test_sends_backlog_request(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(status_code=204)
            await client.move_issues_to_backlog(["TEST-1", "TEST-2"])
            call_kwargs = mock_req.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["issues"] == ["TEST-1", "TEST-2"]


class TestGetSprintIssues:
    @pytest.mark.asyncio
    async def test_returns_sprint_issues(self, client):
        with patch.object(
            client._http, "request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _mock_response(
                json_data={
                    "issues": [{"key": "TEST-1"}, {"key": "TEST-2"}]
                }
            )
            result = await client.get_sprint_issues(10)
            assert len(result) == 2
