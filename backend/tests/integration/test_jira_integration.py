import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION_TESTS") != "true",
    reason="Integration tests disabled. Set INTEGRATION_TESTS=true to enable.",
)


@pytest.fixture
def jira_client():
    from app.config import get_settings
    from app.integrations.jira_client import JiraClient

    settings = get_settings()
    client = JiraClient(
        settings.jira_base_url,
        settings.jira_email,
        settings.jira_api_token,
    )
    yield client


class TestJiraPing:
    @pytest.mark.asyncio
    async def test_can_connect_to_jira(self, jira_client):
        result = await jira_client.ping()
        assert result is True
        await jira_client.close()


class TestBootstrapFreshProject:
    @pytest.mark.asyncio
    async def test_bootstrap_creates_project(self, jira_client):
        project = await jira_client.get_project("SIMTEST")
        if project:
            pytest.skip("Project SIMTEST already exists")
        await jira_client.close()


class TestCustomFields:
    @pytest.mark.asyncio
    async def test_can_list_custom_fields(self, jira_client):
        fields = await jira_client.get_custom_fields()
        assert isinstance(fields, list)
        await jira_client.close()


class TestIssueLifecycle:
    @pytest.mark.asyncio
    async def test_create_and_read_issue(self, jira_client):
        project = await jira_client.get_project("SIMTEST")
        if not project:
            pytest.skip("Project SIMTEST not found")

        issue = await jira_client.create_issue(
            project_key="SIMTEST",
            issue_type="Task",
            summary="Integration test issue",
            fields={},
        )
        assert "key" in issue

        read_back = await jira_client.get_issue(issue["key"])
        assert read_back["key"] == issue["key"]
        await jira_client.close()
