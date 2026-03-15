import pytest
from sqlalchemy.exc import IntegrityError

from app.models.organization import Organization
from app.models.team import Team
from app.models.touch_time_config import TouchTimeConfig
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


def _create_team(session):
    org = Organization(name="Org")
    session.add(org)
    session.commit()
    team = Team(organization_id=org.id, name="T", jira_project_key="T1")
    session.add(team)
    session.commit()
    return team


class TestWorkflow:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="Standard")
        session.add(wf)
        session.commit()
        assert wf.id is not None
        assert wf.name == "Standard"

    def test_one_workflow_per_team(self, session):
        team = _create_team(session)
        session.add(Workflow(team_id=team.id, name="W1"))
        session.commit()
        session.add(Workflow(team_id=team.id, name="W2"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_description_is_nullable(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        assert wf.description is None

    def test_team_relationship(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        session.refresh(wf)
        assert wf.team.name == "T"

    def test_steps_relationship_ordered(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        session.add(WorkflowStep(
            workflow_id=wf.id, jira_status="Done", role_required="QA", order=2
        ))
        session.add(WorkflowStep(
            workflow_id=wf.id, jira_status="In Dev", role_required="DEV", order=1
        ))
        session.commit()
        session.refresh(wf)
        assert wf.steps[0].order == 1
        assert wf.steps[1].order == 2


class TestWorkflowStep:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        step = WorkflowStep(
            workflow_id=wf.id, jira_status="Backlog", role_required="PO", order=1
        )
        session.add(step)
        session.commit()
        assert step.id is not None

    def test_max_wait_hours_defaults_to_24(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        step = WorkflowStep(
            workflow_id=wf.id, jira_status="Backlog", role_required="PO", order=1
        )
        session.add(step)
        session.commit()
        assert step.max_wait_hours == 24.0

    def test_wip_contribution_defaults_to_one(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        step = WorkflowStep(
            workflow_id=wf.id, jira_status="Backlog", role_required="PO", order=1
        )
        session.add(step)
        session.commit()
        assert step.wip_contribution == 1.0

    def test_unique_order_per_workflow(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        session.add(WorkflowStep(
            workflow_id=wf.id, jira_status="S1", role_required="DEV", order=1
        ))
        session.commit()
        session.add(WorkflowStep(
            workflow_id=wf.id, jira_status="S2", role_required="QA", order=1
        ))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_unique_jira_status_per_workflow(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        session.add(WorkflowStep(
            workflow_id=wf.id, jira_status="In Dev", role_required="DEV", order=1
        ))
        session.commit()
        session.add(WorkflowStep(
            workflow_id=wf.id, jira_status="In Dev", role_required="QA", order=2
        ))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_workflow_relationship(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="WF")
        session.add(wf)
        session.commit()
        step = WorkflowStep(
            workflow_id=wf.id, jira_status="Backlog", role_required="PO", order=1
        )
        session.add(step)
        session.commit()
        session.refresh(step)
        assert step.workflow.name == "WF"


class TestTouchTimeConfig:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        step = WorkflowStep(
            workflow_id=wf.id, jira_status="In Dev", role_required="DEV", order=1
        )
        session.add(step)
        session.commit()
        ttc = TouchTimeConfig(
            workflow_step_id=step.id,
            issue_type="Story",
            story_points=5,
            min_hours=4.0,
            max_hours=8.0,
        )
        session.add(ttc)
        session.commit()
        assert ttc.id is not None

    def test_unique_per_step_type_points(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        step = WorkflowStep(
            workflow_id=wf.id, jira_status="In Dev", role_required="DEV", order=1
        )
        session.add(step)
        session.commit()
        session.add(TouchTimeConfig(
            workflow_step_id=step.id, issue_type="Story", story_points=5,
            min_hours=4.0, max_hours=8.0,
        ))
        session.commit()
        session.add(TouchTimeConfig(
            workflow_step_id=step.id, issue_type="Story", story_points=5,
            min_hours=2.0, max_hours=4.0,
        ))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_step_touch_time_configs_relationship(self, session):
        team = _create_team(session)
        wf = Workflow(team_id=team.id, name="W")
        session.add(wf)
        session.commit()
        step = WorkflowStep(
            workflow_id=wf.id, jira_status="In Dev", role_required="DEV", order=1
        )
        session.add(step)
        session.commit()
        session.add(TouchTimeConfig(
            workflow_step_id=step.id, issue_type="Story", story_points=3,
            min_hours=2.0, max_hours=4.0,
        ))
        session.add(TouchTimeConfig(
            workflow_step_id=step.id, issue_type="Bug", story_points=3,
            min_hours=1.0, max_hours=3.0,
        ))
        session.commit()
        session.refresh(step)
        assert len(step.touch_time_configs) == 2
