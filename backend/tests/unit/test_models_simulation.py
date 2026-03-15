from datetime import UTC

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.dysfunction_config import DysfunctionConfig
from app.models.issue import Issue
from app.models.member import Member
from app.models.organization import Organization
from app.models.sprint import Sprint
from app.models.team import Team
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


def _create_team_with_workflow(session):
    org = Organization(name="Org")
    session.add(org)
    session.commit()
    team = Team(organization_id=org.id, name="T", jira_project_key="T1")
    session.add(team)
    session.commit()
    wf = Workflow(team_id=team.id, name="W")
    session.add(wf)
    session.commit()
    step = WorkflowStep(
        workflow_id=wf.id, jira_status="In Dev", role_required="DEV", order=1
    )
    session.add(step)
    session.commit()
    member = Member(team_id=team.id, name="Alice", role="DEV")
    session.add(member)
    session.commit()
    return team, step, member


class TestDysfunctionConfig:
    def test_creates_with_defaults(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        dc = DysfunctionConfig(team_id=team.id)
        session.add(dc)
        session.commit()
        assert dc.id is not None
        assert dc.low_quality_probability == 0.15
        assert dc.scope_creep_probability == 0.10
        assert dc.blocking_dependency_probability == 0.12
        assert dc.dark_teammate_probability == 0.05
        assert dc.re_estimation_probability == 0.10
        assert dc.bug_injection_probability == 0.20
        assert dc.cross_team_block_probability == 0.08
        assert dc.cross_team_handoff_lag_probability == 0.10
        assert dc.cross_team_bug_probability == 0.05

    def test_one_config_per_team(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        session.add(DysfunctionConfig(team_id=team.id))
        session.commit()
        session.add(DysfunctionConfig(team_id=team.id))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_team_relationship(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        dc = DysfunctionConfig(team_id=team.id)
        session.add(dc)
        session.commit()
        session.refresh(dc)
        assert dc.team.name == "T"


class TestSprint:
    def test_creates_with_required_fields(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        from datetime import datetime

        sprint = Sprint(
            team_id=team.id,
            name="Sprint 1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        session.add(sprint)
        session.commit()
        assert sprint.id is not None
        assert sprint.name == "Sprint 1"

    def test_status_defaults_to_future(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        from datetime import datetime

        sprint = Sprint(
            team_id=team.id,
            name="S1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        session.add(sprint)
        session.commit()
        assert sprint.status == "future"

    def test_scope_change_points_defaults_to_zero(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        from datetime import datetime

        sprint = Sprint(
            team_id=team.id,
            name="S1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        session.add(sprint)
        session.commit()
        assert sprint.scope_change_points == 0

    def test_team_relationship(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="Team Sprint", jira_project_key="TS")
        session.add(team)
        session.commit()
        from datetime import datetime

        sprint = Sprint(
            team_id=team.id,
            name="S1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        session.add(sprint)
        session.commit()
        session.refresh(sprint)
        assert sprint.team.name == "Team Sprint"


class TestIssue:
    def test_creates_with_required_fields(self, session):
        team, step, member = _create_team_with_workflow(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Build feature X",
        )
        session.add(issue)
        session.commit()
        assert issue.id is not None
        assert issue.summary == "Build feature X"

    def test_jira_issue_key_is_unique(self, session):
        team, step, member = _create_team_with_workflow(session)
        session.add(Issue(
            team_id=team.id, issue_type="Story", summary="A",
            jira_issue_key="T1-1",
        ))
        session.commit()
        session.add(Issue(
            team_id=team.id, issue_type="Story", summary="B",
            jira_issue_key="T1-1",
        ))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_defaults(self, session):
        team, step, member = _create_team_with_workflow(session)
        issue = Issue(
            team_id=team.id, issue_type="Story", summary="S",
        )
        session.add(issue)
        session.commit()
        assert issue.priority == "Medium"
        assert issue.touch_time_remaining_hours == 0.0
        assert issue.wait_time_accumulated_hours == 0.0
        assert issue.total_cycle_time_hours == 0.0
        assert issue.is_blocked is False
        assert issue.status == "backlog"

    def test_self_referential_blocked_by(self, session):
        team, step, member = _create_team_with_workflow(session)
        blocker = Issue(
            team_id=team.id, issue_type="Story", summary="Blocker",
        )
        session.add(blocker)
        session.commit()
        blocked = Issue(
            team_id=team.id, issue_type="Story", summary="Blocked",
            is_blocked=True, blocked_by_issue_id=blocker.id,
        )
        session.add(blocked)
        session.commit()
        session.refresh(blocked)
        assert blocked.blocked_by.summary == "Blocker"

    def test_workflow_step_relationship(self, session):
        team, step, member = _create_team_with_workflow(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="S",
            current_workflow_step_id=step.id,
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)
        assert issue.current_workflow_step.jira_status == "In Dev"

    def test_worker_and_assignee_relationships(self, session):
        team, step, member = _create_team_with_workflow(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="S",
            current_worker_id=member.id,
            jira_assignee_id=member.id,
            jira_reporter_id=member.id,
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)
        assert issue.current_worker.name == "Alice"
        assert issue.jira_assignee.name == "Alice"
        assert issue.jira_reporter.name == "Alice"

    def test_sprint_relationship(self, session):
        team, step, member = _create_team_with_workflow(session)
        from datetime import datetime

        sprint = Sprint(
            team_id=team.id,
            name="S1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        session.add(sprint)
        session.commit()
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="S",
            sprint_id=sprint.id,
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)
        assert issue.sprint.name == "S1"

    def test_sprint_issues_relationship(self, session):
        team, step, member = _create_team_with_workflow(session)
        from datetime import datetime

        sprint = Sprint(
            team_id=team.id,
            name="S1",
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        session.add(sprint)
        session.commit()
        session.add(Issue(
            team_id=team.id, issue_type="Story", summary="A", sprint_id=sprint.id,
        ))
        session.add(Issue(
            team_id=team.id, issue_type="Bug", summary="B", sprint_id=sprint.id,
        ))
        session.commit()
        session.refresh(sprint)
        assert len(sprint.issues) == 2
