from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.dysfunction_config import DysfunctionConfigCreate, DysfunctionConfigRead
from app.schemas.issue import IssueCreate, IssueRead, IssueUpdate
from app.schemas.member import MemberCreate, MemberRead, MemberUpdate
from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationUpdate
from app.schemas.sprint import SprintCreate, SprintRead, SprintUpdate
from app.schemas.team import TeamCreate, TeamRead, TeamUpdate
from app.schemas.touch_time_config import TouchTimeConfigCreate, TouchTimeConfigRead
from app.schemas.workflow import WorkflowCreate, WorkflowRead
from app.schemas.workflow_step import WorkflowStepCreate, WorkflowStepRead


class TestOrganizationSchemas:
    def test_create_with_valid_data(self):
        schema = OrganizationCreate(name="Acme Corp")
        assert schema.name == "Acme Corp"

    def test_create_requires_name(self):
        with pytest.raises(ValidationError):
            OrganizationCreate()

    def test_read_includes_id_and_timestamps(self):
        now = datetime.now(UTC)
        schema = OrganizationRead(
            id=1, name="Acme", description=None, created_at=now, updated_at=now
        )
        assert schema.id == 1

    def test_update_all_fields_optional(self):
        schema = OrganizationUpdate()
        assert schema.name is None


class TestTeamSchemas:
    def test_create_with_valid_data(self):
        schema = TeamCreate(organization_id=1, name="Backend", jira_project_key="BE")
        assert schema.jira_project_key == "BE"

    def test_create_requires_name(self):
        with pytest.raises(ValidationError):
            TeamCreate(organization_id=1, jira_project_key="BE")

    def test_read_includes_id(self):
        now = datetime.now(UTC)
        schema = TeamRead(
            id=1, organization_id=1, name="T", jira_project_key="T1",
            jira_board_id=None, is_active=True, created_at=now, updated_at=now,
        )
        assert schema.id == 1

    def test_update_all_fields_optional(self):
        schema = TeamUpdate(name="New Name")
        assert schema.name == "New Name"
        assert schema.jira_project_key is None


class TestMemberSchemas:
    def test_create_with_valid_data(self):
        schema = MemberCreate(team_id=1, name="Alice", role="DEV")
        assert schema.role == "DEV"

    def test_create_requires_role(self):
        with pytest.raises(ValidationError):
            MemberCreate(team_id=1, name="Alice")

    def test_read_has_defaults(self):
        now = datetime.now(UTC)
        schema = MemberRead(
            id=1, team_id=1, name="Alice", role="DEV",
            daily_capacity_hours=6.0, max_concurrent_wip=3,
            is_active=True, created_at=now, updated_at=now,
        )
        assert schema.daily_capacity_hours == 6.0

    def test_update_all_fields_optional(self):
        schema = MemberUpdate()
        assert schema.name is None


class TestWorkflowSchemas:
    def test_create_with_valid_data(self):
        schema = WorkflowCreate(team_id=1, name="Standard")
        assert schema.name == "Standard"

    def test_create_requires_team_id(self):
        with pytest.raises(ValidationError):
            WorkflowCreate(name="Standard")

    def test_read_includes_id(self):
        now = datetime.now(UTC)
        schema = WorkflowRead(
            id=1, team_id=1, name="W", description=None,
            created_at=now, updated_at=now,
        )
        assert schema.id == 1


class TestWorkflowStepSchemas:
    def test_create_with_valid_data(self):
        schema = WorkflowStepCreate(
            workflow_id=1, jira_status="In Dev", role_required="DEV", order=1,
        )
        assert schema.order == 1

    def test_create_requires_jira_status(self):
        with pytest.raises(ValidationError):
            WorkflowStepCreate(workflow_id=1, role_required="DEV", order=1)

    def test_read_has_defaults(self):
        now = datetime.now(UTC)
        schema = WorkflowStepRead(
            id=1, workflow_id=1, jira_status="In Dev", role_required="DEV",
            order=1, max_wait_hours=24.0, wip_contribution=1.0,
            created_at=now, updated_at=now,
        )
        assert schema.max_wait_hours == 24.0


class TestTouchTimeConfigSchemas:
    def test_create_with_valid_data(self):
        schema = TouchTimeConfigCreate(
            workflow_step_id=1, issue_type="Story", story_points=5,
            min_hours=4.0, max_hours=8.0,
        )
        assert schema.story_points == 5

    def test_create_requires_min_hours(self):
        with pytest.raises(ValidationError):
            TouchTimeConfigCreate(
                workflow_step_id=1, issue_type="Story", story_points=5, max_hours=8.0,
            )

    def test_read_includes_id(self):
        now = datetime.now(UTC)
        schema = TouchTimeConfigRead(
            id=1, workflow_step_id=1, issue_type="Story", story_points=5,
            min_hours=4.0, max_hours=8.0, created_at=now, updated_at=now,
        )
        assert schema.id == 1


class TestDysfunctionConfigSchemas:
    def test_create_with_defaults(self):
        schema = DysfunctionConfigCreate(team_id=1)
        assert schema.low_quality_probability == 0.15
        assert schema.bug_injection_probability == 0.20

    def test_read_includes_id(self):
        now = datetime.now(UTC)
        schema = DysfunctionConfigRead(
            id=1, team_id=1, created_at=now, updated_at=now,
        )
        assert schema.id == 1


class TestSprintSchemas:
    def test_create_with_valid_data(self):
        schema = SprintCreate(
            team_id=1, name="Sprint 1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        assert schema.name == "Sprint 1"

    def test_create_requires_dates(self):
        with pytest.raises(ValidationError):
            SprintCreate(team_id=1, name="Sprint 1")

    def test_read_has_defaults(self):
        now = datetime.now(UTC)
        schema = SprintRead(
            id=1, team_id=1, jira_sprint_id=None, name="S1", goal=None,
            start_date=now, end_date=now, status="future",
            planned_velocity=None, actual_velocity=None,
            scope_change_points=0, created_at=now, updated_at=now,
        )
        assert schema.status == "future"

    def test_update_all_fields_optional(self):
        schema = SprintUpdate(status="active")
        assert schema.status == "active"
        assert schema.name is None


class TestIssueSchemas:
    def test_create_with_valid_data(self):
        schema = IssueCreate(team_id=1, issue_type="Story", summary="Build X")
        assert schema.summary == "Build X"

    def test_create_requires_summary(self):
        with pytest.raises(ValidationError):
            IssueCreate(team_id=1, issue_type="Story")

    def test_read_has_defaults(self):
        now = datetime.now(UTC)
        schema = IssueRead(
            id=1, team_id=1, jira_issue_key=None, jira_issue_id=None,
            issue_type="Story", summary="S", description=None,
            story_points=None, priority="Medium",
            current_workflow_step_id=None, current_worker_id=None,
            jira_assignee_id=None, jira_reporter_id=None,
            touch_time_remaining_hours=0.0, wait_time_accumulated_hours=0.0,
            total_cycle_time_hours=0.0, sprint_id=None,
            is_blocked=False, blocked_by_issue_id=None,
            dysfunction_flags=None, status="backlog",
            completed_at=None, created_at=now, updated_at=now,
        )
        assert schema.priority == "Medium"

    def test_update_all_fields_optional(self):
        schema = IssueUpdate(status="In Dev")
        assert schema.status == "In Dev"
        assert schema.summary is None

    def test_create_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            IssueCreate(team_id="not_an_int", issue_type="Story", summary="S")
