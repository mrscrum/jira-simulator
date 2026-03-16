"""Tests for Stage 4 model additions — new columns and new tables."""

import json
from datetime import UTC, datetime

from app.models.daily_capacity_log import DailyCapacityLog
from app.models.issue import Issue
from app.models.member import Member
from app.models.move_left_config import (
    MoveLeftConfig,
    MoveLeftSameStepStatus,
    MoveLeftTarget,
)
from app.models.organization import Organization
from app.models.simulation_event_config import SimulationEventConfig
from app.models.simulation_event_log import SimulationEventLog
from app.models.sprint import Sprint
from app.models.team import Team
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


def _create_team(session):
    org = Organization(name="Org")
    session.add(org)
    session.commit()
    team = Team(organization_id=org.id, name="T", jira_project_key="TP")
    session.add(team)
    session.commit()
    return team


def _create_team_with_workflow(session):
    team = _create_team(session)
    workflow = Workflow(team_id=team.id, name="Default")
    session.add(workflow)
    session.commit()
    step = WorkflowStep(
        workflow_id=workflow.id,
        jira_status="To Do",
        role_required="DEV",
        order=1,
    )
    session.add(step)
    session.commit()
    return team, workflow, step


def _create_sprint(session, team):
    sprint = Sprint(
        team_id=team.id,
        name="Sprint 1",
        start_date=datetime(2026, 3, 1, tzinfo=UTC),
        end_date=datetime(2026, 3, 15, tzinfo=UTC),
    )
    session.add(sprint)
    session.commit()
    return sprint


class TestTeamStage4Columns:
    def test_sprint_length_days_defaults_to_ten(self, session):
        team = _create_team(session)
        assert team.sprint_length_days == 10

    def test_sprint_planning_strategy_defaults_to_capacity_fitted(self, session):
        team = _create_team(session)
        assert team.sprint_planning_strategy == "capacity_fitted"

    def test_backlog_depth_target_defaults_to_forty(self, session):
        team = _create_team(session)
        assert team.backlog_depth_target == 40

    def test_pause_before_planning_defaults_to_false(self, session):
        team = _create_team(session)
        assert team.pause_before_planning is False

    def test_working_hours_start_defaults_to_nine(self, session):
        team = _create_team(session)
        assert team.working_hours_start == 9

    def test_working_hours_end_defaults_to_seventeen(self, session):
        team = _create_team(session)
        assert team.working_hours_end == 17

    def test_timezone_defaults_to_utc(self, session):
        team = _create_team(session)
        assert team.timezone == "UTC"

    def test_holidays_defaults_to_empty_list(self, session):
        team = _create_team(session)
        assert team.holidays == "[]"

    def test_holidays_stores_json(self, session):
        team = _create_team(session)
        team.holidays = json.dumps(["2026-01-01", "2026-12-25"])
        session.commit()
        session.refresh(team)
        assert json.loads(team.holidays) == ["2026-01-01", "2026-12-25"]

    def test_custom_working_hours(self, session):
        org = Organization(name="Org2")
        session.add(org)
        session.commit()
        team = Team(
            organization_id=org.id,
            name="Custom",
            jira_project_key="CU",
            working_hours_start=10,
            working_hours_end=18,
            timezone="America/New_York",
        )
        session.add(team)
        session.commit()
        assert team.working_hours_start == 10
        assert team.working_hours_end == 18
        assert team.timezone == "America/New_York"


class TestMemberStage4Columns:
    def test_timezone_is_nullable(self, session):
        team = _create_team(session)
        member = Member(team_id=team.id, name="Alice", role="DEV")
        session.add(member)
        session.commit()
        assert member.timezone is None

    def test_timezone_can_be_set(self, session):
        team = _create_team(session)
        member = Member(
            team_id=team.id,
            name="Bob",
            role="QA",
            timezone="Europe/London",
        )
        session.add(member)
        session.commit()
        assert member.timezone == "Europe/London"


class TestSprintStage4Columns:
    def test_phase_defaults_to_backlog_prep(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        assert sprint.phase == "BACKLOG_PREP"

    def test_sprint_number_can_be_set(self, session):
        team = _create_team(session)
        sprint = Sprint(
            team_id=team.id,
            name="Sprint 1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
            sprint_number=1,
        )
        session.add(sprint)
        session.commit()
        assert sprint.sprint_number == 1

    def test_committed_points_is_nullable(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        assert sprint.committed_points is None

    def test_completed_points_is_nullable(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        assert sprint.completed_points is None

    def test_carried_over_points_defaults_to_zero(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        assert sprint.carried_over_points == 0

    def test_velocity_is_nullable(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        assert sprint.velocity is None

    def test_goal_at_risk_defaults_to_false(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        assert sprint.goal_at_risk is False


class TestIssueStage4Columns:
    def test_backlog_priority_is_nullable(self, session):
        team = _create_team(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Test",
        )
        session.add(issue)
        session.commit()
        assert issue.backlog_priority is None

    def test_carried_over_defaults_to_false(self, session):
        team = _create_team(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Test",
        )
        session.add(issue)
        session.commit()
        assert issue.carried_over is False

    def test_descoped_defaults_to_false(self, session):
        team = _create_team(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Test",
        )
        session.add(issue)
        session.commit()
        assert issue.descoped is False

    def test_split_from_id_is_nullable(self, session):
        team = _create_team(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Test",
        )
        session.add(issue)
        session.commit()
        assert issue.split_from_id is None

    def test_split_from_self_reference(self, session):
        team = _create_team(session)
        parent = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Parent",
        )
        session.add(parent)
        session.commit()
        child = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Child",
            split_from_id=parent.id,
        )
        session.add(child)
        session.commit()
        assert child.split_from_id == parent.id


class TestSimulationEventConfig:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        config = SimulationEventConfig(
            team_id=team.id,
            event_type="move_left",
            params="{}",
        )
        session.add(config)
        session.commit()
        assert config.id is not None

    def test_enabled_defaults_to_true(self, session):
        team = _create_team(session)
        config = SimulationEventConfig(
            team_id=team.id,
            event_type="descope",
            params="{}",
        )
        session.add(config)
        session.commit()
        assert config.enabled is True

    def test_probability_is_nullable(self, session):
        team = _create_team(session)
        config = SimulationEventConfig(
            team_id=team.id,
            event_type="uneven_load",
            params="{}",
        )
        session.add(config)
        session.commit()
        assert config.probability is None

    def test_stores_json_params(self, session):
        team = _create_team(session)
        params = json.dumps({"threshold_hours": 24})
        config = SimulationEventConfig(
            team_id=team.id,
            event_type="stale_issue",
            probability=0.5,
            params=params,
        )
        session.add(config)
        session.commit()
        assert json.loads(config.params) == {"threshold_hours": 24}


class TestSimulationEventLog:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        log = SimulationEventLog(
            team_id=team.id,
            sprint_id=sprint.id,
            event_type="carry_over",
            occurred_at=datetime.now(UTC),
            sim_day=3,
            payload="{}",
        )
        session.add(log)
        session.commit()
        assert log.id is not None

    def test_issue_id_is_nullable(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        log = SimulationEventLog(
            team_id=team.id,
            sprint_id=sprint.id,
            event_type="velocity_drift",
            occurred_at=datetime.now(UTC),
            sim_day=10,
            payload="{}",
        )
        session.add(log)
        session.commit()
        assert log.issue_id is None

    def test_jira_written_defaults_to_false(self, session):
        team = _create_team(session)
        sprint = _create_sprint(session, team)
        log = SimulationEventLog(
            team_id=team.id,
            sprint_id=sprint.id,
            event_type="stale_issue",
            occurred_at=datetime.now(UTC),
            sim_day=5,
            payload="{}",
        )
        session.add(log)
        session.commit()
        assert log.jira_written is False


class TestMoveLeftConfig:
    def test_creates_with_required_fields(self, session):
        team, workflow, step = _create_team_with_workflow(session)
        config = MoveLeftConfig(
            team_id=team.id,
            from_step_id=step.id,
            base_probability=0.1,
        )
        session.add(config)
        session.commit()
        assert config.id is not None

    def test_target_relationship(self, session):
        team, workflow, step = _create_team_with_workflow(session)
        step2 = WorkflowStep(
            workflow_id=workflow.id,
            jira_status="In Progress",
            role_required="DEV",
            order=2,
        )
        session.add(step2)
        session.commit()
        config = MoveLeftConfig(
            team_id=team.id,
            from_step_id=step2.id,
            base_probability=0.15,
        )
        session.add(config)
        session.commit()
        target = MoveLeftTarget(
            move_left_config_id=config.id,
            to_step_id=step.id,
            weight=1.0,
        )
        session.add(target)
        session.commit()
        session.refresh(config)
        assert len(config.targets) == 1
        assert config.targets[0].to_step_id == step.id

    def test_same_step_statuses(self, session):
        team, workflow, step = _create_team_with_workflow(session)
        config = MoveLeftConfig(
            team_id=team.id,
            from_step_id=step.id,
            base_probability=0.1,
        )
        session.add(config)
        session.commit()
        status = MoveLeftSameStepStatus(
            move_left_config_id=config.id,
            status_name="In Review",
        )
        session.add(status)
        session.commit()
        session.refresh(config)
        assert len(config.same_step_statuses) == 1
        assert config.same_step_statuses[0].status_name == "In Review"


class TestDailyCapacityLog:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        member = Member(team_id=team.id, name="Alice", role="DEV")
        session.add(member)
        session.commit()
        log = DailyCapacityLog(
            member_id=member.id,
            date=datetime(2026, 3, 15, tzinfo=UTC),
            total_hours=6.0,
            consumed_hours=2.5,
            active_wip_count=2,
        )
        session.add(log)
        session.commit()
        assert log.id is not None
        assert log.total_hours == 6.0
        assert log.consumed_hours == 2.5
        assert log.active_wip_count == 2
