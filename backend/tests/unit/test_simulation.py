"""Tests for the tick orchestrator (simulation engine)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.engine.simulation import SimulationEngine, SimulationState, TeamTickResult


class TestSimulationState:
    def test_initial_state_is_stopped(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        assert engine.state == SimulationState.STOPPED

    def test_start_transitions_to_running(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.start()
        assert engine.state == SimulationState.RUNNING

    def test_pause_transitions_to_paused(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.start()
        engine.pause()
        assert engine.state == SimulationState.PAUSED

    def test_resume_transitions_to_running(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.start()
        engine.pause()
        engine.resume()
        assert engine.state == SimulationState.RUNNING

    def test_stop_transitions_to_stopped(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.start()
        engine.stop()
        assert engine.state == SimulationState.STOPPED

    def test_pause_team(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.pause_team(1)
        assert 1 in engine.paused_teams

    def test_resume_team(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.pause_team(1)
        engine.resume_team(1)
        assert 1 not in engine.paused_teams


class TestTickSkipping:
    def test_tick_skipped_when_stopped(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        # state is STOPPED
        result = engine.should_tick()
        assert result is False

    def test_tick_allowed_when_running(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.start()
        result = engine.should_tick()
        assert result is True

    def test_tick_skipped_when_paused(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        engine.start()
        engine.pause()
        assert engine.should_tick() is False


class TestTeamTickResult:
    def test_result_captures_team_id(self):
        result = TeamTickResult(
            team_id=1,
            jira_actions_count=5,
            events_fired=["carry_over"],
            error=None,
        )
        assert result.team_id == 1
        assert result.jira_actions_count == 5
        assert "carry_over" in result.events_fired

    def test_result_captures_error(self):
        result = TeamTickResult(
            team_id=2,
            jira_actions_count=0,
            events_fired=[],
            error="Database timeout",
        )
        assert result.error == "Database timeout"


class TestEnqueueActions:
    def test_enqueues_jira_write_actions(self):
        write_queue = MagicMock()
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=write_queue,
        )
        from app.engine.types import JiraWriteAction
        actions = [
            JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={"issue_key": "TP-1", "body": "test"},
                issue_id=1,
            ),
            JiraWriteAction(
                operation_type="TRANSITION_ISSUE",
                payload={"issue_key": "TP-2", "target_status": "Done"},
                issue_id=2,
            ),
        ]
        engine.enqueue_actions(team_id=1, actions=actions)
        assert write_queue.enqueue.call_count == 2

    def test_enqueue_passes_correct_params(self):
        write_queue = MagicMock()
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=write_queue,
        )
        from app.engine.types import JiraWriteAction
        action = JiraWriteAction(
            operation_type="ADD_COMMENT",
            payload={"issue_key": "TP-1", "body": "hello"},
            issue_id=42,
        )
        engine.enqueue_actions(team_id=7, actions=[action])
        write_queue.enqueue.assert_called_once_with(
            team_id=7,
            operation_type="ADD_COMMENT",
            payload={"issue_key": "TP-1", "body": "hello"},
            issue_id=42,
            session=None,
        )


class TestLastSuccessfulTick:
    def test_records_last_successful_tick(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
        engine.record_tick_success(now)
        assert engine.last_successful_tick == now

    def test_tick_count_increments(self):
        engine = SimulationEngine(
            session_factory=MagicMock(),
            write_queue=MagicMock(),
        )
        assert engine.tick_count == 0
        engine.record_tick_success(datetime.now(UTC))
        assert engine.tick_count == 1
        engine.record_tick_success(datetime.now(UTC))
        assert engine.tick_count == 2
