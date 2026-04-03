"""Tests for the sprint pre-computation engine."""

from datetime import UTC, datetime

from app.engine.precompute import (
    PrecomputeResult,
    _compute_tick_wall_times,
    precompute_sprint,
)
from app.engine.snapshots import (
    IssueSnapshot,
    MemberSnapshot,
    TeamSnapshot,
    TouchTimeConfigSnapshot,
    WorkflowStepSnapshot,
)


class TestComputeTickWallTimes:
    def test_produces_ticks_within_sprint(self):
        start = datetime(2026, 4, 6, 9, 0, tzinfo=UTC)  # Monday 9 AM
        ticks = _compute_tick_wall_times(
            sprint_start=start,
            sprint_length_days=5,
            tick_duration_hours=1.0,
            tz_name="UTC",
            start_hour=9,
            end_hour=17,
            holidays=[],
            working_days=[0, 1, 2, 3, 4],
        )
        assert len(ticks) > 0
        assert ticks[0] == start

    def test_skips_weekends(self):
        start = datetime(2026, 4, 3, 16, 0, tzinfo=UTC)  # Friday 4 PM
        ticks = _compute_tick_wall_times(
            sprint_start=start,
            sprint_length_days=7,
            tick_duration_hours=1.0,
            tz_name="UTC",
            start_hour=9,
            end_hour=17,
            holidays=[],
            working_days=[0, 1, 2, 3, 4],
        )
        # Friday 4 PM has 1 working hour left, so next tick goes to Monday
        for t in ticks:
            assert t.weekday() < 5  # no weekends

    def test_empty_when_sprint_too_short(self):
        start = datetime(2026, 4, 6, 9, 0, tzinfo=UTC)
        ticks = _compute_tick_wall_times(
            sprint_start=start,
            sprint_length_days=0,
            tick_duration_hours=1.0,
            tz_name="UTC",
            start_hour=9,
            end_hour=17,
            holidays=[],
            working_days=[0, 1, 2, 3, 4],
        )
        assert len(ticks) == 0


class TestPrecomputeSprint:
    def _make_team(self):
        return TeamSnapshot(
            id=1, name="Test", jira_project_key="TST",
            jira_board_id=100, sprint_length_days=10,
            sprint_capacity_min=5, sprint_capacity_max=10,
            priority_randomization=False, tick_duration_hours=1.0,
            timezone="UTC", working_hours_start=9, working_hours_end=17,
            holidays="[]",
        )

    def _make_issues(self, count):
        return [
            IssueSnapshot(
                id=i + 1, team_id=1, issue_type="Story",
                story_points=3, summary=f"Issue {i+1}",
                jira_issue_key=f"TST-{i+1}", jira_issue_id=str(i+1),
                status="backlog", current_workflow_step_id=None,
                current_worker_id=None, backlog_priority=i,
            )
            for i in range(count)
        ]

    def _make_workflow_steps(self):
        dev_roles = '["dev"]'
        return [
            WorkflowStepSnapshot(
                id=1, workflow_id=1, jira_status="To Do",
                order=1, roles_json=dev_roles,
            ),
            WorkflowStepSnapshot(
                id=2, workflow_id=1, jira_status="In Progress",
                order=2, roles_json=dev_roles,
            ),
            WorkflowStepSnapshot(
                id=3, workflow_id=1, jira_status="Done", order=3,
            ),
        ]

    def _make_touch_time_configs(self):
        return {
            (1, "Story", 3): TouchTimeConfigSnapshot(
                id=1, workflow_step_id=1, issue_type="Story",
                story_points=3, min_hours=1, max_hours=2,
                full_time_p25=2, full_time_p50=4, full_time_p99=8,
            ),
            (2, "Story", 3): TouchTimeConfigSnapshot(
                id=2, workflow_step_id=2, issue_type="Story",
                story_points=3, min_hours=2, max_hours=4,
                full_time_p25=4, full_time_p50=8, full_time_p99=16,
            ),
        }

    def _make_members(self):
        return [
            MemberSnapshot(id=1, role="dev", team_id=1),
            MemberSnapshot(id=2, role="dev", team_id=1),
        ]

    def test_returns_events(self):
        result = precompute_sprint(
            team=self._make_team(),
            backlog_issues=self._make_issues(5),
            workflow_steps=self._make_workflow_steps(),
            touch_time_configs=self._make_touch_time_configs(),
            move_left_configs=[],
            members=self._make_members(),
            sprint_start=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            sprint_length_days=10,
            jira_sprint_id=42,
            jira_board_id=100,
            sprint_name="Test Sprint 1",
            sprint_db_id=1,
            rng_seed=12345,
        )
        assert isinstance(result, PrecomputeResult)
        assert len(result.events) > 0
        assert result.total_ticks > 0
        assert result.rng_seed == 12345
        assert result.committed_points > 0

    def test_deterministic_with_same_seed(self):
        kwargs = dict(
            team=self._make_team(),
            backlog_issues=self._make_issues(5),
            workflow_steps=self._make_workflow_steps(),
            touch_time_configs=self._make_touch_time_configs(),
            move_left_configs=[],
            members=self._make_members(),
            sprint_start=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            sprint_length_days=10,
            rng_seed=99999,
        )
        r1 = precompute_sprint(**kwargs)
        # Reset issue snapshots (they were mutated)
        kwargs["backlog_issues"] = self._make_issues(5)
        r2 = precompute_sprint(**kwargs)

        assert len(r1.events) == len(r2.events)
        for e1, e2 in zip(r1.events, r2.events):
            assert e1.event_type == e2.event_type
            assert e1.sim_tick == e2.sim_tick

    def test_planning_events_at_tick_zero(self):
        result = precompute_sprint(
            team=self._make_team(),
            backlog_issues=self._make_issues(3),
            workflow_steps=self._make_workflow_steps(),
            touch_time_configs=self._make_touch_time_configs(),
            move_left_configs=[],
            members=self._make_members(),
            sprint_start=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            sprint_length_days=10,
            jira_board_id=100,
            jira_sprint_id=42,
            sprint_db_id=1,
            rng_seed=42,
        )
        tick_0_events = [e for e in result.events if e.sim_tick == 0]
        event_types = {e.event_type for e in tick_0_events}
        assert "CREATE_SPRINT" in event_types
        assert "TRANSITION_ISSUE" in event_types
        assert "UPDATE_SPRINT" in event_types

    def test_empty_backlog_produces_minimal_events(self):
        result = precompute_sprint(
            team=self._make_team(),
            backlog_issues=[],
            workflow_steps=self._make_workflow_steps(),
            touch_time_configs=self._make_touch_time_configs(),
            move_left_configs=[],
            members=self._make_members(),
            sprint_start=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            sprint_length_days=10,
            jira_board_id=100,
            jira_sprint_id=42,
            sprint_db_id=1,
            rng_seed=42,
        )
        assert result.committed_points == 0
        assert result.selected_issue_ids == []

    def test_no_workflow_steps_returns_empty(self):
        result = precompute_sprint(
            team=self._make_team(),
            backlog_issues=self._make_issues(3),
            workflow_steps=[],
            touch_time_configs={},
            move_left_configs=[],
            members=self._make_members(),
            sprint_start=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            sprint_length_days=10,
            rng_seed=42,
        )
        assert len(result.events) == 0
        assert result.total_ticks == 0
