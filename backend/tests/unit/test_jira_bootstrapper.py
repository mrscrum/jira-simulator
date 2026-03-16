import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.alerting import AlertEvent
from app.integrations.jira_bootstrapper import JiraBootstrapper
from app.models.jira_config import JiraConfig
from app.models.organization import Organization
from app.models.team import Team
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


def _create_team_with_workflow(session, statuses=None):
    org = Organization(name="Test Org")
    session.add(org)
    session.flush()
    team = Team(
        organization_id=org.id,
        name="Alpha",
        jira_project_key="ALPHA",
    )
    session.add(team)
    session.flush()
    workflow = Workflow(team_id=team.id, name="Default")
    session.add(workflow)
    session.flush()
    if statuses is None:
        statuses = ["To Do", "In Progress", "Done"]
    for i, status in enumerate(statuses):
        step = WorkflowStep(
            workflow_id=workflow.id,
            jira_status=status,
            role_required="developer",
            order=i,
        )
        session.add(step)
    session.flush()
    return team


@pytest.fixture
def mock_jira():
    client = AsyncMock()
    client.get_project = AsyncMock(return_value=None)
    client.create_project = AsyncMock(
        return_value={"key": "ALPHA", "id": "10001"}
    )
    # First call returns None (board not found), retry returns the board.
    client.get_board = AsyncMock(side_effect=[None, {"id": 42, "name": "ALPHA board"}])
    client.get_custom_fields = AsyncMock(return_value=[])
    client.create_custom_field = AsyncMock(
        return_value={"id": "customfield_10001"}
    )
    client.get_project_statuses = AsyncMock(
        return_value=[
            {"name": "To Do", "statusCategory": {"key": "new"}},
            {"name": "In Progress", "statusCategory": {"key": "indeterminate"}},
            {"name": "Done", "statusCategory": {"key": "done"}},
        ]
    )
    client.get_issue_transitions = AsyncMock(
        return_value=[
            {"id": "11", "name": "To Do"},
            {"id": "21", "name": "In Progress"},
            {"id": "31", "name": "Done"},
        ]
    )
    return client


@pytest.fixture
def mock_alerting():
    return AsyncMock()


@pytest.fixture
def bootstrapper(session, mock_jira, mock_alerting):
    session_factory = MagicMock(return_value=session)
    return JiraBootstrapper(mock_jira, session_factory, mock_alerting)


class TestBootstrapNewProject:
    @pytest.mark.asyncio
    async def test_creates_project_when_not_found(
        self, session, bootstrapper, mock_jira
    ):
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        mock_jira.create_project.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_finds_board_on_retry_after_creation(
        self, session, bootstrapper, mock_jira
    ):
        team = _create_team_with_workflow(session)
        # First call: board not found. Second call (retry): board created by Jira.
        mock_jira.get_board.side_effect = [None, {"id": 42, "name": "ALPHA board"}]
        await bootstrapper.bootstrap_team(team.id)
        assert team.jira_board_id == 42

    @pytest.mark.asyncio
    async def test_creates_custom_fields_when_missing(
        self, session, bootstrapper, mock_jira
    ):
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        # Only sim_assignee and sim_reporter are custom-created (story_points uses built-in).
        assert mock_jira.create_custom_field.await_count == 2

    @pytest.mark.asyncio
    async def test_marks_team_bootstrapped(
        self, session, bootstrapper
    ):
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        session.refresh(team)
        assert team.jira_bootstrapped is True
        assert team.jira_bootstrapped_at is not None


class TestBootstrapExistingProject:
    @pytest.mark.asyncio
    async def test_skips_project_creation(
        self, session, bootstrapper, mock_jira
    ):
        mock_jira.get_project.return_value = {"key": "ALPHA"}
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        mock_jira.create_project.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_board_creation_when_exists(
        self, session, bootstrapper, mock_jira
    ):
        mock_jira.get_project.return_value = {"key": "ALPHA"}
        mock_jira.get_board.side_effect = None
        mock_jira.get_board.return_value = {"id": 99}
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        assert team.jira_board_id == 99


class TestCustomFieldIdempotency:
    @pytest.mark.asyncio
    async def test_skips_fields_when_already_exist(
        self, session, bootstrapper, mock_jira
    ):
        mock_jira.get_custom_fields.return_value = [
            {"id": "cf_1", "name": "sim_assignee"},
            {"id": "cf_2", "name": "sim_reporter"},
            {"id": "cf_3", "name": "story_points"},
        ]
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        mock_jira.create_custom_field.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stores_field_ids_in_jira_config(
        self, session, bootstrapper, mock_jira
    ):
        mock_jira.get_custom_fields.return_value = [
            {"id": "cf_1", "name": "sim_assignee"},
            {"id": "cf_2", "name": "sim_reporter"},
            {"id": "cf_3", "name": "story_points"},
        ]
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        config = session.query(JiraConfig).filter(
            JiraConfig.key == "field_id_sim_assignee"
        ).first()
        assert config is not None
        assert config.value == "cf_1"

    @pytest.mark.asyncio
    async def test_stores_story_points_field_id(
        self, session, bootstrapper, mock_jira
    ):
        mock_jira.get_custom_fields.return_value = [
            {"id": "cf_1", "name": "sim_assignee"},
            {"id": "cf_2", "name": "sim_reporter"},
            {"id": "customfield_10100", "name": "story_points"},
        ]
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        config = session.query(JiraConfig).filter(
            JiraConfig.key == "field_id_story_points"
        ).first()
        assert config is not None
        assert config.value == "customfield_10100"


class TestMissingStatuses:
    @pytest.mark.asyncio
    async def test_logs_warning_for_missing_status(
        self, session, bootstrapper, mock_jira
    ):
        mock_jira.get_project_statuses.return_value = [
            {"name": "To Do", "statusCategory": {"key": "new"}},
            {"name": "Done", "statusCategory": {"key": "done"}},
        ]
        team = _create_team_with_workflow(
            session, statuses=["To Do", "In Progress", "Done"]
        )
        await bootstrapper.bootstrap_team(team.id)
        session.refresh(team)
        warnings = json.loads(team.jira_bootstrap_warnings)
        assert any("In Progress" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_still_marks_bootstrapped(
        self, session, bootstrapper, mock_jira
    ):
        mock_jira.get_project_statuses.return_value = [
            {"name": "To Do", "statusCategory": {"key": "new"}},
        ]
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        session.refresh(team)
        assert team.jira_bootstrapped is True

    @pytest.mark.asyncio
    async def test_sends_bootstrap_incomplete_alert(
        self, session, bootstrapper, mock_jira, mock_alerting
    ):
        mock_jira.get_project_statuses.return_value = []
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        mock_alerting.assert_awaited_once()
        call_args = mock_alerting.call_args
        assert call_args[0][0] == AlertEvent.BOOTSTRAP_INCOMPLETE


class TestIdempotentRerun:
    @pytest.mark.asyncio
    async def test_rerun_is_safe(self, session, bootstrapper, mock_jira):
        mock_jira.get_project.return_value = {"key": "ALPHA"}
        mock_jira.get_board.side_effect = None
        mock_jira.get_board.return_value = {"id": 42}
        mock_jira.get_custom_fields.return_value = [
            {"id": "cf_1", "name": "sim_assignee"},
            {"id": "cf_2", "name": "sim_reporter"},
            {"id": "cf_3", "name": "story_points"},
        ]
        team = _create_team_with_workflow(session)
        await bootstrapper.bootstrap_team(team.id)
        await bootstrapper.bootstrap_team(team.id)
        mock_jira.create_project.assert_not_awaited()
        mock_jira.create_custom_field.assert_not_awaited()
