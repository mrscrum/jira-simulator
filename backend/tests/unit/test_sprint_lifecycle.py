"""Tests for sprint lifecycle — 3-phase management, planning, carryover."""

import random
from datetime import UTC, datetime, timedelta

from app.engine.sprint_lifecycle import (
    SprintPhase,
    calculate_velocity,
    check_sprint_end,
    create_next_sprint_dates,
    handle_carryover,
    plan_sprint,
)


def _make_issue(
    issue_id: int,
    story_points: int = 3,
    backlog_priority: int | None = None,
):
    return {
        "id": issue_id,
        "story_points": story_points,
        "backlog_priority": backlog_priority,
    }


def _make_carryover_issue(
    issue_id: int,
    sampled_work: float = 10.0,
    elapsed_work: float = 4.0,
    sampled_full: float = 12.0,
    elapsed_full: float = 5.0,
):
    return {
        "id": issue_id,
        "sampled_work_time": sampled_work,
        "elapsed_work_time": elapsed_work,
        "sampled_full_time": sampled_full,
        "elapsed_full_time": elapsed_full,
        "work_started": True,
        "current_worker_id": 1,
        "carried_over": False,
    }


class TestSprintPhase:
    def test_three_phases_only(self):
        assert set(SprintPhase) == {"PLANNING", "ACTIVE", "COMPLETED"}


class TestPlanSprint:
    def test_selects_items_up_to_capacity(self):
        backlog = [
            _make_issue(1, story_points=3, backlog_priority=1),
            _make_issue(2, story_points=5, backlog_priority=2),
            _make_issue(3, story_points=8, backlog_priority=3),
            _make_issue(4, story_points=3, backlog_priority=4),
        ]
        selected, target = plan_sprint(
            backlog, capacity_min=8, capacity_max=12,
            priority_randomization=False, rng=random.Random(42),
        )
        total = sum(i["story_points"] for i in selected)
        assert total <= target
        assert total >= 8

    def test_respects_priority_order(self):
        backlog = [
            _make_issue(1, story_points=3, backlog_priority=2),
            _make_issue(2, story_points=3, backlog_priority=1),
            _make_issue(3, story_points=3, backlog_priority=3),
        ]
        selected, _ = plan_sprint(
            backlog, capacity_min=5, capacity_max=20,
            priority_randomization=False, rng=random.Random(42),
        )
        assert selected[0]["id"] == 2  # highest priority (lowest number)

    def test_stops_when_next_exceeds_target_and_above_min(self):
        backlog = [
            _make_issue(1, story_points=5, backlog_priority=1),
            _make_issue(2, story_points=5, backlog_priority=2),
            _make_issue(3, story_points=13, backlog_priority=3),
        ]
        # With target potentially 10, first two items = 10, third would exceed
        selected, target = plan_sprint(
            backlog, capacity_min=10, capacity_max=10,
            priority_randomization=False, rng=random.Random(42),
        )
        total = sum(i["story_points"] for i in selected)
        assert total == 10
        assert len(selected) == 2

    def test_continues_past_target_if_below_min(self):
        backlog = [
            _make_issue(1, story_points=3, backlog_priority=1),
            _make_issue(2, story_points=5, backlog_priority=2),
            _make_issue(3, story_points=8, backlog_priority=3),
        ]
        # Target could be 5, but min is 10 so we keep pulling
        selected, _ = plan_sprint(
            backlog, capacity_min=10, capacity_max=10,
            priority_randomization=False, rng=random.Random(42),
        )
        total = sum(i["story_points"] for i in selected)
        assert total >= 10

    def test_priority_randomization_shuffles_order(self):
        backlog = [
            _make_issue(i, story_points=1, backlog_priority=i)
            for i in range(1, 21)
        ]
        orders = set()
        for seed in range(20):
            selected, _ = plan_sprint(
                backlog, capacity_min=5, capacity_max=10,
                priority_randomization=True, rng=random.Random(seed),
            )
            order = tuple(i["id"] for i in selected)
            orders.add(order)
        assert len(orders) > 1  # different seeds produce different orderings

    def test_empty_backlog(self):
        selected, target = plan_sprint(
            [], capacity_min=10, capacity_max=20,
            priority_randomization=False, rng=random.Random(42),
        )
        assert selected == []
        assert 10 <= target <= 20

    def test_single_large_item_exceeding_target(self):
        backlog = [_make_issue(1, story_points=50, backlog_priority=1)]
        selected, target = plan_sprint(
            backlog, capacity_min=10, capacity_max=20,
            priority_randomization=False, rng=random.Random(42),
        )
        # Item exceeds target, but total (0) < min, so it gets included
        assert len(selected) == 1
        assert selected[0]["story_points"] == 50

    def test_capacity_target_within_range(self):
        for seed in range(50):
            _, target = plan_sprint(
                [_make_issue(1, story_points=1, backlog_priority=1)],
                capacity_min=15, capacity_max=30,
                priority_randomization=False, rng=random.Random(seed),
            )
            assert 15 <= target <= 30


class TestCheckSprintEnd:
    def test_returns_true_when_days_elapsed(self):
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        now = start + timedelta(days=10)
        assert check_sprint_end(start, sprint_length_days=10, sim_now=now) is True

    def test_returns_false_during_sprint(self):
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        now = start + timedelta(days=5)
        assert check_sprint_end(start, sprint_length_days=10, sim_now=now) is False

    def test_boundary_exactly_at_end(self):
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        now = start + timedelta(days=10)
        assert check_sprint_end(start, sprint_length_days=10, sim_now=now) is True


class TestHandleCarryover:
    def test_multiplies_remaining_work_by_125(self):
        issues = [_make_carryover_issue(1, sampled_work=10.0, elapsed_work=4.0)]
        handle_carryover(issues)
        # remaining was 6.0, new remaining = 7.5, new sampled = 4.0 + 7.5 = 11.5
        assert issues[0]["sampled_work_time"] == 11.5

    def test_multiplies_remaining_full_time_by_125(self):
        issues = [_make_carryover_issue(1, sampled_full=12.0, elapsed_full=5.0)]
        handle_carryover(issues)
        # remaining was 7.0, new remaining = 8.75, new sampled = 5.0 + 8.75 = 13.75
        assert issues[0]["sampled_full_time"] == 13.75

    def test_resets_work_started(self):
        issues = [_make_carryover_issue(1)]
        handle_carryover(issues)
        assert issues[0]["work_started"] is False

    def test_clears_worker(self):
        issues = [_make_carryover_issue(1)]
        handle_carryover(issues)
        assert issues[0]["current_worker_id"] is None

    def test_sets_carried_over_flag(self):
        issues = [_make_carryover_issue(1)]
        handle_carryover(issues)
        assert issues[0]["carried_over"] is True

    def test_no_change_when_work_already_done(self):
        issues = [_make_carryover_issue(
            1, sampled_work=5.0, elapsed_work=5.0,
            sampled_full=8.0, elapsed_full=8.0,
        )]
        handle_carryover(issues)
        # No remaining work or full time, so sampled values unchanged
        assert issues[0]["sampled_work_time"] == 5.0
        assert issues[0]["sampled_full_time"] == 8.0

    def test_multiple_issues(self):
        issues = [
            _make_carryover_issue(1, sampled_work=10.0, elapsed_work=2.0),
            _make_carryover_issue(2, sampled_work=6.0, elapsed_work=6.0),
        ]
        handle_carryover(issues)
        # Issue 1: remaining 8 * 1.25 = 10, new sampled = 2 + 10 = 12
        assert issues[0]["sampled_work_time"] == 12.0
        # Issue 2: no remaining work
        assert issues[1]["sampled_work_time"] == 6.0


class TestCreateNextSprintDates:
    def test_starts_where_previous_ended(self):
        prev_end = datetime(2026, 3, 15, 17, 0, tzinfo=UTC)
        start, end = create_next_sprint_dates(prev_end, sprint_length_days=14)
        assert start == prev_end
        assert end == prev_end + timedelta(days=14)


class TestCalculateVelocity:
    def test_normal_velocity(self):
        assert calculate_velocity(completed=15, committed=20) == 0.75

    def test_zero_committed_returns_zero(self):
        assert calculate_velocity(completed=0, committed=0) == 0.0

    def test_all_completed(self):
        assert calculate_velocity(completed=20, committed=20) == 1.0
