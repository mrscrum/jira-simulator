"""Tests for sprint lifecycle — phase management and transitions."""

from app.engine.sprint_lifecycle import (
    SprintPhase,
    calculate_velocity,
    check_phase_advance,
    detect_carry_over_issues,
    select_sprint_issues,
)


def _make_issue(
    issue_id: int,
    story_points: int = 3,
    status: str = "backlog",
    priority: str = "Medium",
    backlog_priority: int | None = None,
):
    return {
        "id": issue_id,
        "story_points": story_points,
        "status": status,
        "priority": priority,
        "backlog_priority": backlog_priority,
    }


class TestCheckPhaseAdvance:
    def test_backlog_prep_advances_when_depth_sufficient(self):
        result = check_phase_advance(
            phase=SprintPhase.BACKLOG_PREP,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=0,
            planning_duration_hours=4,
            sprint_days_elapsed=0,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result == SprintPhase.PLANNING

    def test_backlog_prep_stays_when_depth_insufficient(self):
        result = check_phase_advance(
            phase=SprintPhase.BACKLOG_PREP,
            backlog_depth=10,
            sprint_capacity=15,
            planning_hours_elapsed=0,
            planning_duration_hours=4,
            sprint_days_elapsed=0,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result is None

    def test_backlog_prep_pauses_when_configured(self):
        result = check_phase_advance(
            phase=SprintPhase.BACKLOG_PREP,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=0,
            planning_duration_hours=4,
            sprint_days_elapsed=0,
            sprint_length_days=10,
            pause_before_planning=True,
        )
        assert result is None  # paused

    def test_planning_advances_when_duration_elapsed(self):
        result = check_phase_advance(
            phase=SprintPhase.PLANNING,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=5,
            planning_duration_hours=4,
            sprint_days_elapsed=0,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result == SprintPhase.ACTIVE

    def test_planning_stays_when_not_elapsed(self):
        result = check_phase_advance(
            phase=SprintPhase.PLANNING,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=2,
            planning_duration_hours=4,
            sprint_days_elapsed=0,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result is None

    def test_active_advances_when_sprint_days_elapsed(self):
        result = check_phase_advance(
            phase=SprintPhase.ACTIVE,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=0,
            planning_duration_hours=4,
            sprint_days_elapsed=10,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result == SprintPhase.REVIEW

    def test_active_stays_when_days_remaining(self):
        result = check_phase_advance(
            phase=SprintPhase.ACTIVE,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=0,
            planning_duration_hours=4,
            sprint_days_elapsed=5,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result is None

    def test_review_advances_to_retro(self):
        result = check_phase_advance(
            phase=SprintPhase.REVIEW,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=0,
            planning_duration_hours=4,
            sprint_days_elapsed=10,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result == SprintPhase.RETRO

    def test_retro_advances_to_backlog_prep(self):
        result = check_phase_advance(
            phase=SprintPhase.RETRO,
            backlog_depth=30,
            sprint_capacity=15,
            planning_hours_elapsed=0,
            planning_duration_hours=4,
            sprint_days_elapsed=10,
            sprint_length_days=10,
            pause_before_planning=False,
        )
        assert result == SprintPhase.BACKLOG_PREP


class TestSelectSprintIssues:
    def test_capacity_fitted_selects_within_capacity(self):
        backlog = [
            _make_issue(1, story_points=3, backlog_priority=1),
            _make_issue(2, story_points=5, backlog_priority=2),
            _make_issue(3, story_points=8, backlog_priority=3),
            _make_issue(4, story_points=3, backlog_priority=4),
        ]
        selected = select_sprint_issues(
            backlog, strategy="capacity_fitted", capacity_points=10
        )
        total = sum(i["story_points"] for i in selected)
        assert total <= 10

    def test_capacity_fitted_respects_priority_order(self):
        backlog = [
            _make_issue(1, story_points=3, backlog_priority=2),
            _make_issue(2, story_points=3, backlog_priority=1),
        ]
        selected = select_sprint_issues(
            backlog, strategy="capacity_fitted", capacity_points=10
        )
        assert selected[0]["id"] == 2  # lower priority number = higher priority

    def test_priority_ordered_selects_all_by_priority(self):
        backlog = [
            _make_issue(1, story_points=5, backlog_priority=1),
            _make_issue(2, story_points=3, backlog_priority=2),
        ]
        selected = select_sprint_issues(
            backlog, strategy="priority_ordered", capacity_points=100
        )
        assert len(selected) == 2
        assert selected[0]["id"] == 1

    def test_empty_backlog_returns_empty(self):
        selected = select_sprint_issues(
            [], strategy="capacity_fitted", capacity_points=10
        )
        assert selected == []


class TestDetectCarryOver:
    def test_incomplete_issues_detected(self):
        issues = [
            _make_issue(1, status="IN_PROGRESS"),
            _make_issue(2, status="DONE"),
            _make_issue(3, status="QUEUED_FOR_ROLE"),
        ]
        carry = detect_carry_over_issues(issues)
        assert len(carry) == 2
        carry_ids = {i["id"] for i in carry}
        assert carry_ids == {1, 3}

    def test_all_done_returns_empty(self):
        issues = [
            _make_issue(1, status="DONE"),
            _make_issue(2, status="DONE"),
        ]
        carry = detect_carry_over_issues(issues)
        assert carry == []


class TestCalculateVelocity:
    def test_normal_velocity(self):
        assert calculate_velocity(completed=15, committed=20) == 0.75

    def test_zero_committed_returns_zero(self):
        assert calculate_velocity(completed=0, committed=0) == 0.0

    def test_all_completed(self):
        assert calculate_velocity(completed=20, committed=20) == 1.0
