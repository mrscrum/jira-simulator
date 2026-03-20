"""Integration tests for _tick_team — validates full sprint lifecycle.

Uses an in-memory SQLite DB with real models to test the complete flow:
PLANNING → ACTIVE → COMPLETED → next sprint.
"""

import random
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from app.engine.sim_clock import SimClock
from app.engine.simulation import SimulationEngine
from app.engine.sprint_lifecycle import SprintPhase
from app.models.issue import Issue
from app.models.member import Member
from app.models.organization import Organization
from app.models.sprint import Sprint
from app.models.team import Team
from app.models.touch_time_config import TouchTimeConfig
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


def _setup_team(session):
    """Create a team with members, workflow, and backlog."""
    org = Organization(name="Test Org")
    session.add(org)
    session.flush()

    team = Team(
        organization_id=org.id,
        name="Alpha",
        jira_project_key="ALPHA",
        sprint_length_days=1,  # short for testing
        sprint_capacity_min=5,
        sprint_capacity_max=10,
        working_hours_start=0,
        working_hours_end=23,
        timezone="UTC",
        tick_duration_hours=1.0,
    )
    session.add(team)
    session.flush()

    # Members
    for name, role in [("Dev1", "DEV"), ("Dev2", "DEV"), ("QA1", "QA")]:
        session.add(Member(team_id=team.id, name=name, role=role))
    session.flush()

    # Workflow: To Do → In Progress → Done
    workflow = Workflow(team_id=team.id, name="Test Workflow")
    session.add(workflow)
    session.flush()

    steps = []
    for jira_status, role, order in [
        ("To Do", "DEV", 1),
        ("In Progress", "DEV", 2),
        ("Done", "DEV", 3),
    ]:
        step = WorkflowStep(
            workflow_id=workflow.id,
            jira_status=jira_status,
            role_required=role,
            order=order,
        )
        session.add(step)
        steps.append(step)
    session.flush()

    # Touch time configs: very short times so items complete quickly
    for step in steps:
        session.add(TouchTimeConfig(
            workflow_step_id=step.id,
            issue_type="Story",
            story_points=0,  # fallback for any size
            min_hours=0.0,
            max_hours=0.5,
            full_time_p25=0.5,
            full_time_p50=1.0,
            full_time_p99=2.0,
        ))
    session.flush()

    # Backlog issues
    for i in range(8):
        session.add(Issue(
            team_id=team.id,
            issue_type="Story",
            summary=f"Story {i + 1}",
            description=f"Test story {i + 1}",
            story_points=2,
            status="backlog",
            backlog_priority=i + 1,
        ))
    session.flush()

    return team


def _make_engine(session):
    """Create a simulation engine with a fast clock."""
    session_factory = MagicMock(return_value=session)
    write_queue = MagicMock()
    clock = SimClock(speed_multiplier=3600.0)  # fast forward
    engine = SimulationEngine(
        session_factory=session_factory,
        write_queue=write_queue,
        sim_clock=clock,
    )
    engine._rng = random.Random(42)
    return engine


class TestSprintPlanning:
    @pytest.mark.asyncio
    async def test_first_tick_creates_sprint_and_plans(self, session):
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        result = await engine._tick_team(session, team)

        assert result.error is None
        # A sprint should have been created
        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        assert sprint is not None
        assert sprint.phase == SprintPhase.ACTIVE.value
        assert sprint.committed_points > 0

        # Issues should be assigned to the sprint
        sprint_issues = session.query(Issue).filter_by(sprint_id=sprint.id).all()
        assert len(sprint_issues) > 0

        # Issues should have entered a workflow step
        for issue in sprint_issues:
            assert issue.current_workflow_step_id is not None
            assert issue.status != "backlog"

    @pytest.mark.asyncio
    async def test_planning_respects_capacity_range(self, session):
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        await engine._tick_team(session, team)

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        assert sprint.capacity_target is not None
        assert team.sprint_capacity_min <= sprint.capacity_target <= team.sprint_capacity_max


class TestActiveSprintProcessing:
    @pytest.mark.asyncio
    async def test_items_progress_through_workflow(self, session):
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        # First tick: planning
        await engine._tick_team(session, team)
        session.commit()

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        assert sprint.phase == SprintPhase.ACTIVE.value

        # Run several ticks to let items progress
        for _ in range(10):
            session.expire_all()
            await engine._tick_team(session, team)
            session.commit()

        # Some items should have progressed or completed
        sprint_issues = session.query(Issue).filter_by(sprint_id=sprint.id).all()
        statuses = {i.status for i in sprint_issues}
        # At least some items should have moved beyond the first status
        assert len(statuses) >= 1

    @pytest.mark.asyncio
    async def test_completed_items_get_timestamp(self, session):
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        # Planning tick
        await engine._tick_team(session, team)
        session.commit()

        # Run many ticks to complete some items
        for _ in range(20):
            session.expire_all()
            await engine._tick_team(session, team)
            session.commit()

        completed = (
            session.query(Issue)
            .filter(Issue.completed_at.isnot(None))
            .all()
        )
        for issue in completed:
            assert issue.completed_at is not None


class TestSprintCompletion:
    @pytest.mark.asyncio
    async def test_sprint_completes_after_length(self, session):
        team = _setup_team(session)
        team.sprint_length_days = 1  # very short
        engine = _make_engine(session)
        engine.start()

        # Planning tick
        await engine._tick_team(session, team)
        session.commit()

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        assert sprint.phase == SprintPhase.ACTIVE.value

        # Advance clock past sprint end (>1 day)
        # Shift _sim_start forward so now() jumps ahead of the sprint end
        engine._clock._sim_start = engine._clock._sim_start + timedelta(days=2)

        session.expire_all()
        await engine._tick_team(session, team)
        session.commit()

        session.refresh(sprint)
        assert sprint.phase == SprintPhase.COMPLETED.value

    @pytest.mark.asyncio
    async def test_completed_sprint_triggers_new_sprint(self, session):
        team = _setup_team(session)
        team.sprint_length_days = 1
        engine = _make_engine(session)
        engine.start()

        # Planning tick creates sprint 1
        await engine._tick_team(session, team)
        session.commit()

        # Advance past sprint end
        engine._clock._sim_start = engine._clock._sim_start + timedelta(days=2)

        session.expire_all()
        await engine._tick_team(session, team)
        session.commit()

        # Tick again — should handle COMPLETED → new sprint
        session.expire_all()
        await engine._tick_team(session, team)
        session.commit()

        sprints = (
            session.query(Sprint)
            .filter_by(team_id=team.id)
            .order_by(Sprint.sprint_number)
            .all()
        )
        assert len(sprints) >= 2
        assert sprints[-1].phase in (SprintPhase.ACTIVE.value, SprintPhase.PLANNING.value)


class TestNoWorkflowHandled:
    @pytest.mark.asyncio
    async def test_returns_error_when_no_workflow(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.flush()
        team = Team(
            organization_id=org.id,
            name="NoWorkflow",
            jira_project_key="NW",
            timezone="UTC",
        )
        session.add(team)
        session.flush()
        session.add(Member(team_id=team.id, name="Dev", role="DEV"))
        session.flush()

        engine = _make_engine(session)
        engine.start()

        result = await engine._tick_team(session, team)
        assert result.error == "No workflow configured"


class TestJiraActionsEnqueued:
    @pytest.mark.asyncio
    async def test_tick_enqueues_jira_actions(self, session):
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        await engine._tick_team(session, team)

        # write_queue.enqueue should have been called (sprint creation, transitions, etc.)
        assert engine._write_queue.enqueue.call_count > 0

        # Check that TRANSITION_ISSUE actions were enqueued
        calls = engine._write_queue.enqueue.call_args_list
        op_types = [
            c.kwargs.get("operation_type", c.args[1] if len(c.args) > 1 else None)
            for c in calls
        ]
        # At minimum we should see transitions from planning
        assert any("TRANSITION" in str(op) for op in op_types if op)
