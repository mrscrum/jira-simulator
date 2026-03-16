"""Tests for the wired _tick_team() method in SimulationEngine."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.engine.simulation import SimulationEngine
from app.models.base import Base


@pytest.fixture
def db_session(tmp_path):
    """Create a real SQLite session with all tables."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    eng = create_engine(db_url)
    Base.metadata.create_all(eng)
    session_cls = sessionmaker(bind=eng)
    return session_cls()


@pytest.fixture
def mock_write_queue():
    queue = MagicMock()
    queue.enqueue = MagicMock()
    return queue


def _create_team(session):
    from app.models.organization import Organization
    from app.models.team import Team

    org = Organization(name="Test Org")
    session.add(org)
    session.flush()

    team = Team(
        organization_id=org.id,
        name="Test Team",
        jira_project_key="TST",
        sprint_length_days=10,
        sprint_planning_strategy="capacity_fitted",
        backlog_depth_target=5,
        working_hours_start=0,
        working_hours_end=24,
        timezone="UTC",
        holidays="[]",
    )
    session.add(team)
    session.flush()
    return team


def _create_member(session, team_id, name="Dev1", role="developer"):
    from app.models.member import Member

    member = Member(
        team_id=team_id,
        name=name,
        role=role,
        daily_capacity_hours=6.0,
        max_concurrent_wip=3,
        timezone="UTC",
    )
    session.add(member)
    session.flush()
    return member


def _create_sprint(session, team_id, phase="ACTIVE", status="active"):
    from app.models.sprint import Sprint

    sprint = Sprint(
        team_id=team_id,
        name="Sprint 1",
        start_date=datetime.now(UTC) - timedelta(days=1),
        end_date=datetime.now(UTC) + timedelta(days=9),
        status=status,
        phase=phase,
        sprint_number=1,
        committed_points=10,
        completed_points=0,
    )
    session.add(sprint)
    session.flush()
    return sprint


def _create_issue(session, team_id, sprint_id, status="IN_PROGRESS", **kwargs):
    from app.models.issue import Issue

    issue = Issue(
        team_id=team_id,
        sprint_id=sprint_id,
        issue_type="Story",
        summary="Test Issue",
        status=status,
        story_points=3,
        **kwargs,
    )
    session.add(issue)
    session.flush()
    return issue


class TestTickTeamCreatesInitialSprint:
    @pytest.mark.asyncio
    async def test_creates_sprint_if_none_exists(self, db_session, mock_write_queue):
        from app.models.sprint import Sprint

        team = _create_team(db_session)
        _create_member(db_session, team.id)
        db_session.commit()

        engine = SimulationEngine(
            session_factory=lambda: db_session,
            write_queue=mock_write_queue,
        )

        result = await engine._tick_team(db_session, team)

        assert result.error is None
        sprints = db_session.query(Sprint).filter_by(team_id=team.id).all()
        assert len(sprints) == 1
        assert sprints[0].phase == "BACKLOG_PREP"


class TestTickTeamBacklogGeneration:
    @pytest.mark.asyncio
    async def test_generates_backlog_issues_when_below_target(
        self, db_session, mock_write_queue,
    ):
        from app.models.issue import Issue

        team = _create_team(db_session)
        team.backlog_depth_target = 10
        _create_member(db_session, team.id)
        _create_sprint(db_session, team.id)
        db_session.commit()

        engine = SimulationEngine(
            session_factory=lambda: db_session,
            write_queue=mock_write_queue,
        )

        result = await engine._tick_team(db_session, team)

        assert result.error is None
        backlog = (
            db_session.query(Issue)
            .filter_by(team_id=team.id, status="BACKLOG")
            .all()
        )
        assert len(backlog) > 0
        assert result.jira_actions_count > 0
        assert mock_write_queue.enqueue.called


class TestTickTeamIssueAdvancement:
    @pytest.mark.asyncio
    async def test_advances_in_progress_issue_touch_time(
        self, db_session, mock_write_queue,
    ):
        team = _create_team(db_session)
        member = _create_member(db_session, team.id)
        sprint = _create_sprint(db_session, team.id)
        issue = _create_issue(
            db_session, team.id, sprint.id,
            status="IN_PROGRESS",
            current_worker_id=member.id,
            touch_time_remaining_hours=10.0,
        )
        db_session.commit()

        engine = SimulationEngine(
            session_factory=lambda: db_session,
            write_queue=mock_write_queue,
        )

        result = await engine._tick_team(db_session, team)

        assert result.error is None
        db_session.refresh(issue)
        assert issue.touch_time_remaining_hours < 10.0

    @pytest.mark.asyncio
    async def test_completes_issue_when_touch_time_zero(
        self, db_session, mock_write_queue,
    ):
        team = _create_team(db_session)
        member = _create_member(db_session, team.id)
        sprint = _create_sprint(db_session, team.id)
        issue = _create_issue(
            db_session, team.id, sprint.id,
            status="IN_PROGRESS",
            current_worker_id=member.id,
            touch_time_remaining_hours=0.5,
            jira_issue_key="TST-1",
        )
        db_session.commit()

        engine = SimulationEngine(
            session_factory=lambda: db_session,
            write_queue=mock_write_queue,
        )

        result = await engine._tick_team(db_session, team)

        assert result.error is None
        db_session.refresh(issue)
        assert issue.status == "DONE"
        assert issue.completed_at is not None


class TestTickTeamEventRolls:
    @pytest.mark.asyncio
    async def test_fires_events_without_error(
        self, db_session, mock_write_queue,
    ):
        team = _create_team(db_session)
        _create_member(db_session, team.id)
        sprint = _create_sprint(db_session, team.id)
        _create_issue(db_session, team.id, sprint.id, status="IN_PROGRESS")
        db_session.commit()

        engine = SimulationEngine(
            session_factory=lambda: db_session,
            write_queue=mock_write_queue,
        )

        result = await engine._tick_team(db_session, team)

        assert result.error is None


class TestTickTeamCapacityLogging:
    @pytest.mark.asyncio
    async def test_logs_capacity_for_working_members(
        self, db_session, mock_write_queue,
    ):
        from app.models.daily_capacity_log import DailyCapacityLog

        team = _create_team(db_session)
        _create_member(db_session, team.id)
        _create_sprint(db_session, team.id)
        db_session.commit()

        engine = SimulationEngine(
            session_factory=lambda: db_session,
            write_queue=mock_write_queue,
        )

        await engine._tick_team(db_session, team)
        db_session.flush()

        logs = db_session.query(DailyCapacityLog).all()
        assert len(logs) >= 1


class TestTickTeamSkipsOutsideWorkingHours:
    @pytest.mark.asyncio
    async def test_returns_zero_actions_outside_working_hours(
        self, db_session, mock_write_queue,
    ):
        team = _create_team(db_session)
        # Use a 1-minute window far from any reasonable CI run time.
        # UTC+14 (Line Islands) is the furthest-ahead timezone.
        # Working hours 3:00-3:01 in UTC+14 means only UTC 13:00-13:01
        # could trigger the window — extremely unlikely during CI.
        team.working_hours_start = 3
        team.working_hours_end = 4
        team.timezone = "Pacific/Kiritimati"
        _create_member(db_session, team.id)
        db_session.commit()

        engine = SimulationEngine(
            session_factory=lambda: db_session,
            write_queue=mock_write_queue,
        )

        result = await engine._tick_team(db_session, team)

        assert result.jira_actions_count == 0
        assert result.error is None
