"""Tests for event system base + 4 core events."""

from datetime import UTC, datetime

from app.engine.events.base import TickContext
from app.engine.events.carry_over import CarryOverEvent
from app.engine.events.registry import get_event_handler
from app.engine.events.sprint_goal_risk import SprintGoalRiskEvent
from app.engine.events.stale_issue import StaleIssueEvent
from app.engine.events.velocity_drift import VelocityDriftEvent


def _make_context(
    issues=None,
    sprint=None,
    sim_day=5,
    members=None,
):
    return TickContext(
        team_id=1,
        sprint=sprint or {"id": 1, "committed_points": 20, "completed_points": 10},
        issues=issues or [],
        members=members or [],
        capacity_states={},
        sim_day=sim_day,
        now=datetime(2026, 3, 16, 12, 0, tzinfo=UTC),
    )


class TestRegistry:
    def test_carry_over_registered(self):
        handler = get_event_handler("carry_over")
        assert isinstance(handler, CarryOverEvent)

    def test_velocity_drift_registered(self):
        handler = get_event_handler("velocity_drift")
        assert isinstance(handler, VelocityDriftEvent)

    def test_sprint_goal_risk_registered(self):
        handler = get_event_handler("sprint_goal_risk")
        assert isinstance(handler, SprintGoalRiskEvent)

    def test_stale_issue_registered(self):
        handler = get_event_handler("stale_issue")
        assert isinstance(handler, StaleIssueEvent)

    def test_unknown_returns_none(self):
        handler = get_event_handler("nonexistent_event")
        assert handler is None


class TestCarryOverEvent:
    def test_detects_incomplete_issues(self):
        issues = [
            {"id": 1, "status": "IN_PROGRESS", "story_points": 3, "issue_key": "TP-1"},
            {"id": 2, "status": "DONE", "story_points": 5, "issue_key": "TP-2"},
            {"id": 3, "status": "QUEUED_FOR_ROLE", "story_points": 2, "issue_key": "TP-3"},
        ]
        ctx = _make_context(issues=issues)
        event = CarryOverEvent()
        outcomes = event.evaluate(ctx)
        assert len(outcomes) == 2

    def test_all_done_produces_no_outcomes(self):
        issues = [
            {"id": 1, "status": "DONE", "story_points": 5, "issue_key": "TP-1"},
        ]
        ctx = _make_context(issues=issues)
        event = CarryOverEvent()
        outcomes = event.evaluate(ctx)
        assert len(outcomes) == 0

    def test_outcome_has_jira_comment(self):
        issues = [
            {"id": 1, "status": "IN_PROGRESS", "story_points": 3, "issue_key": "TP-1"},
        ]
        ctx = _make_context(issues=issues)
        event = CarryOverEvent()
        outcomes = event.evaluate(ctx)
        assert len(outcomes) == 1
        assert any(
            a.operation_type == "ADD_COMMENT"
            for a in outcomes[0].jira_actions
        )


class TestVelocityDriftEvent:
    def test_calculates_velocity(self):
        sprint = {
            "id": 1,
            "committed_points": 20,
            "completed_points": 15,
        }
        ctx = _make_context(sprint=sprint)
        event = VelocityDriftEvent()
        outcomes = event.evaluate(ctx)
        assert len(outcomes) == 1
        assert outcomes[0].log_entry["payload"]["velocity"] == 0.75

    def test_zero_committed_handled(self):
        sprint = {"id": 1, "committed_points": 0, "completed_points": 0}
        ctx = _make_context(sprint=sprint)
        event = VelocityDriftEvent()
        outcomes = event.evaluate(ctx)
        assert len(outcomes) == 1
        assert outcomes[0].log_entry["payload"]["velocity"] == 0.0


class TestSprintGoalRiskEvent:
    def test_risk_detected_when_ratio_exceeds_threshold(self):
        sprint = {
            "id": 1,
            "committed_points": 20,
            "completed_points": 5,
        }
        # 15 remaining points, 10 remaining capacity → ratio 1.5 > 1.2
        ctx = _make_context(sprint=sprint)
        event = SprintGoalRiskEvent()
        outcomes = event.evaluate(
            ctx,
            remaining_capacity_hours=10.0,
            risk_threshold=1.2,
        )
        assert len(outcomes) == 1
        assert outcomes[0].log_entry["event_type"] == "sprint_goal_risk"

    def test_no_risk_when_on_track(self):
        sprint = {
            "id": 1,
            "committed_points": 20,
            "completed_points": 18,
        }
        # 2 remaining points, 10 capacity → ratio 0.2 < 1.2
        ctx = _make_context(sprint=sprint)
        event = SprintGoalRiskEvent()
        outcomes = event.evaluate(
            ctx,
            remaining_capacity_hours=10.0,
            risk_threshold=1.2,
        )
        assert len(outcomes) == 0


class TestStaleIssueEvent:
    def test_detects_stale_issues(self):
        issues = [
            {
                "id": 1,
                "status": "QUEUED_FOR_ROLE",
                "wait_time_accumulated_hours": 30.0,
                "issue_key": "TP-1",
                "role": "DEV",
            },
            {
                "id": 2,
                "status": "QUEUED_FOR_ROLE",
                "wait_time_accumulated_hours": 10.0,
                "issue_key": "TP-2",
                "role": "QA",
            },
        ]
        ctx = _make_context(issues=issues)
        event = StaleIssueEvent()
        outcomes = event.evaluate(ctx, stale_threshold_hours=24.0)
        assert len(outcomes) == 1
        assert outcomes[0].log_entry["issue_id"] == 1

    def test_no_stale_when_below_threshold(self):
        issues = [
            {
                "id": 1,
                "status": "QUEUED_FOR_ROLE",
                "wait_time_accumulated_hours": 10.0,
                "issue_key": "TP-1",
                "role": "DEV",
            },
        ]
        ctx = _make_context(issues=issues)
        event = StaleIssueEvent()
        outcomes = event.evaluate(ctx, stale_threshold_hours=24.0)
        assert len(outcomes) == 0

    def test_stale_comment_mentions_role(self):
        issues = [
            {
                "id": 1,
                "status": "QUEUED_FOR_ROLE",
                "wait_time_accumulated_hours": 48.0,
                "issue_key": "TP-1",
                "role": "QA",
            },
        ]
        ctx = _make_context(issues=issues)
        event = StaleIssueEvent()
        outcomes = event.evaluate(ctx, stale_threshold_hours=24.0)
        comment = outcomes[0].jira_actions[0]
        assert "QA" in comment.payload["body"]
