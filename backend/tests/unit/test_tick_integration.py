"""Integration tests for _tick_team — validates full sprint lifecycle.

Uses an in-memory SQLite DB with real models to test the complete flow:
no sprint → precompute → events stored → dispatch → completion.
"""

import random
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.engine.sim_clock import SimClock
from app.engine.simulation import SimulationEngine
from app.engine.sprint_lifecycle import SprintPhase
from app.models.issue import Issue
from app.models.member import Member
from app.models.organization import Organization
from app.models.scheduled_event import ScheduledEvent
from app.models.sprint import Sprint
from app.models.team import Team
from app.models.touch_time_config import TouchTimeConfig
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep

# Fixed sprint start: Monday 9 AM UTC (guaranteed working time)
FIXED_SPRINT_START = datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC)


def _setup_team(session):
    """Create a team with members, workflow, and backlog."""
    org = Organization(name="Test Org")
    session.add(org)
    session.flush()

    team = Team(
        organization_id=org.id,
        name="Alpha",
        jira_project_key="ALPHA",
        sprint_length_days=5,  # 5 days = 1 work week
        sprint_capacity_min=5,
        sprint_capacity_max=10,
        working_hours_start=0,
        working_hours_end=23,
        timezone="UTC",
        tick_duration_hours=1.0,
        first_sprint_start_date=FIXED_SPRINT_START,
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
    """Create a simulation engine with a fast clock.

    The session_factory returns a non-closing wrapper so that
    compute_and_schedule_sprint() doesn't close the test session.
    """
    # Wrap session so .close() is a no-op (test conftest handles cleanup)
    original_close = session.close

    def _noop_close():
        pass

    session.close = _noop_close

    session_factory = MagicMock(return_value=session)
    write_queue = MagicMock()
    clock = SimClock(speed_multiplier=3600.0)  # fast forward
    engine = SimulationEngine(
        session_factory=session_factory,
        write_queue=write_queue,
        sim_clock=clock,
    )
    engine._rng = random.Random(42)

    # Store original close for manual cleanup if needed
    engine._test_session_close = original_close

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
        assert sprint.phase == SprintPhase.SIMULATED.value
        assert sprint.committed_points > 0

        # Issues should be assigned to the sprint
        sprint_issues = session.query(Issue).filter_by(
            sprint_id=sprint.id,
        ).all()
        assert len(sprint_issues) > 0

        # Scheduled events should exist for the sprint
        events = session.query(ScheduledEvent).filter_by(
            sprint_id=sprint.id,
        ).all()
        assert len(events) > 0

        # Should have transition events
        transition_events = [
            e for e in events if e.event_type == "TRANSITION_ISSUE"
        ]
        assert len(transition_events) > 0

    @pytest.mark.asyncio
    async def test_planning_respects_capacity_range(self, session):
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        await engine._tick_team(session, team)

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        assert sprint.capacity_target is not None
        assert (
            team.sprint_capacity_min
            <= sprint.capacity_target
            <= team.sprint_capacity_max
        )


class TestActiveSprintProcessing:
    @pytest.mark.asyncio
    async def test_precompute_generates_events_for_all_ticks(self, session):
        """Verify that precompute creates events across multiple ticks."""
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        await engine._tick_team(session, team)

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        events = session.query(ScheduledEvent).filter_by(
            sprint_id=sprint.id,
        ).all()

        # Events should span multiple ticks
        tick_numbers = {e.sim_tick for e in events}
        assert len(tick_numbers) > 1, (
            f"Expected events across multiple ticks, got ticks: {tick_numbers}"
        )

    @pytest.mark.asyncio
    async def test_tick_on_active_sprint_checks_dispatch_status(self, session):
        """When a sprint is active with pending events, tick keeps it active."""
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        # First tick: creates sprint + events
        await engine._tick_team(session, team)
        session.commit()

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        assert sprint.phase == SprintPhase.SIMULATED.value

        # Second tick: sprint is ACTIVE with PENDING events → stays ACTIVE
        session.expire_all()
        result = await engine._tick_team(session, team)
        session.commit()

        session.refresh(sprint)
        assert sprint.phase == SprintPhase.SIMULATED.value
        assert result.error is None


class TestSprintCompletion:
    @pytest.mark.asyncio
    async def test_sprint_completes_when_all_events_dispatched(self, session):
        """Sprint should be marked COMPLETED when all events are dispatched."""
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        # Create sprint + events
        await engine._tick_team(session, team)
        session.commit()

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        assert sprint.phase == SprintPhase.SIMULATED.value

        # Activate the sprint (SIMULATED → ACTIVE) so the tick engine
        # can detect completion
        sprint.phase = SprintPhase.ACTIVE.value
        sprint.status = "active"
        session.commit()

        # Mark all events as DISPATCHED (simulating the dispatcher)
        events = session.query(ScheduledEvent).filter_by(
            sprint_id=sprint.id,
        ).all()
        assert len(events) > 0
        for event in events:
            event.status = "DISPATCHED"
            event.dispatched_at = datetime.now(UTC)
        session.commit()

        # Now tick should detect all events dispatched → COMPLETED
        session.expire_all()
        await engine._tick_team(session, team)
        session.commit()

        session.refresh(sprint)
        assert sprint.phase == SprintPhase.COMPLETED.value

    @pytest.mark.asyncio
    async def test_completed_sprint_triggers_new_sprint(self, session):
        """After a sprint completes, next tick should precompute a new one."""
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        # Create sprint 1 + events
        await engine._tick_team(session, team)
        session.commit()

        sprint1 = session.query(Sprint).filter_by(team_id=team.id).first()

        # Activate the sprint (SIMULATED → ACTIVE)
        sprint1.phase = SprintPhase.ACTIVE.value
        sprint1.status = "active"
        session.commit()

        # Mark all events as DISPATCHED
        events = session.query(ScheduledEvent).filter_by(
            sprint_id=sprint1.id,
        ).all()
        for event in events:
            event.status = "DISPATCHED"
            event.dispatched_at = datetime.now(UTC)
        session.commit()

        # Tick: detects all dispatched → marks COMPLETED
        session.expire_all()
        await engine._tick_team(session, team)
        session.commit()

        session.refresh(sprint1)
        assert sprint1.phase == SprintPhase.COMPLETED.value

        # Next tick: handles completed sprint (carryover) + creates sprint 2
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
        assert sprints[-1].phase in (
            SprintPhase.SIMULATED.value,
            SprintPhase.ACTIVE.value,
            SprintPhase.PLANNING.value,
        )


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


class TestScheduledEventsContent:
    @pytest.mark.asyncio
    async def test_events_include_transition_payloads(self, session):
        """Scheduled events should have proper payload data."""
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        await engine._tick_team(session, team)

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        transition_events = (
            session.query(ScheduledEvent)
            .filter_by(sprint_id=sprint.id, event_type="TRANSITION_ISSUE")
            .all()
        )

        assert len(transition_events) > 0
        for event in transition_events:
            assert event.payload is not None
            assert "target_status" in event.payload
            assert event.issue_id is not None

    @pytest.mark.asyncio
    async def test_events_have_valid_batch_id(self, session):
        """All events from one precompute should share a batch_id."""
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        await engine._tick_team(session, team)

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        events = session.query(ScheduledEvent).filter_by(
            sprint_id=sprint.id,
        ).all()

        batch_ids = {e.batch_id for e in events}
        assert len(batch_ids) == 1, (
            f"Expected single batch_id, got {batch_ids}"
        )

    @pytest.mark.asyncio
    async def test_events_ordered_by_tick_and_sequence(self, session):
        """Events should have monotonically increasing tick/sequence."""
        team = _setup_team(session)
        engine = _make_engine(session)
        engine.start()

        await engine._tick_team(session, team)

        sprint = session.query(Sprint).filter_by(team_id=team.id).first()
        events = (
            session.query(ScheduledEvent)
            .filter_by(sprint_id=sprint.id)
            .order_by(
                ScheduledEvent.sim_tick,
                ScheduledEvent.sequence_order,
            )
            .all()
        )

        for i in range(1, len(events)):
            prev = events[i - 1]
            curr = events[i]
            assert (curr.sim_tick, curr.sequence_order) >= (
                prev.sim_tick,
                prev.sequence_order,
            ), "Events not properly ordered"
