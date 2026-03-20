"""Tests for the workflow engine — enter_status, process_item_tick, transitions."""

import random
from dataclasses import dataclass, field

from app.engine.capacity import build_member_states
from app.engine.workflow_engine import (
    check_transition_ready,
    enter_status,
    get_touch_time_config,
    process_item_tick,
    roll_direction,
)

# ---------------------------------------------------------------------------
# Fakes — lightweight stand-ins for ORM models
# ---------------------------------------------------------------------------

@dataclass
class FakeWorkflowStep:
    id: int
    jira_status: str
    order: int
    role_required: str = "DEV"
    roles_json: str | None = None

    @property
    def roles(self) -> list[str]:
        if self.roles_json:
            import json
            return json.loads(self.roles_json)
        return [self.role_required]


@dataclass
class FakeTouchTimeConfig:
    min_hours: float = 1.0
    max_hours: float = 4.0
    full_time_p25: float | None = 2.0
    full_time_p50: float | None = 4.0
    full_time_p99: float | None = 16.0


@dataclass
class FakeIssue:
    id: int = 1
    jira_issue_key: str = "PROJ-1"
    issue_type: str = "Story"
    story_points: int = 3
    status: str = "To Do"
    current_workflow_step_id: int | None = None
    current_worker_id: int | None = None
    sampled_full_time: float = 0.0
    sampled_work_time: float = 0.0
    elapsed_full_time: float = 0.0
    elapsed_work_time: float = 0.0
    work_started: bool = False
    completed_at: object = None


@dataclass
class FakeMoveLeftConfig:
    from_step_id: int
    base_probability: float
    issue_type: str | None = None
    targets: list = field(default_factory=list)


@dataclass
class FakeMoveLeftTarget:
    to_step_id: int
    weight: float = 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _three_step_workflow():
    """To Do → In Progress → Done"""
    return [
        FakeWorkflowStep(id=10, jira_status="To Do", order=1, role_required="DEV"),
        FakeWorkflowStep(id=20, jira_status="In Progress", order=2, role_required="DEV"),
        FakeWorkflowStep(id=30, jira_status="Done", order=3, role_required="DEV"),
    ]


def _members(*roles_and_ids):
    result = []
    for item in roles_and_ids:
        result.append({"id": item[0], "role": item[1], "assigned_issue_id": None})
    return result


# ---------------------------------------------------------------------------
# enter_status
# ---------------------------------------------------------------------------

class TestEnterStatus:
    def test_sets_status_and_step(self):
        issue = FakeIssue()
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        ttc = FakeTouchTimeConfig()
        enter_status(issue, step, ttc, random.Random(42))
        assert issue.status == "In Progress"
        assert issue.current_workflow_step_id == 20

    def test_samples_times_from_config(self):
        issue = FakeIssue()
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        ttc = FakeTouchTimeConfig(
            min_hours=2.0, max_hours=6.0,
            full_time_p25=2.0, full_time_p50=4.0, full_time_p99=16.0,
        )
        enter_status(issue, step, ttc, random.Random(42))
        assert issue.sampled_work_time >= 2.0
        assert issue.sampled_work_time <= 6.0
        assert issue.sampled_full_time > 0

    def test_resets_elapsed_and_worker(self):
        issue = FakeIssue(
            elapsed_full_time=5.0, elapsed_work_time=3.0,
            work_started=True, current_worker_id=7,
        )
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        enter_status(issue, step, FakeTouchTimeConfig(), random.Random(42))
        assert issue.elapsed_full_time == 0.0
        assert issue.elapsed_work_time == 0.0
        assert issue.work_started is False
        assert issue.current_worker_id is None

    def test_emits_transition_action(self):
        issue = FakeIssue()
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        actions = enter_status(issue, step, FakeTouchTimeConfig(), random.Random(42))
        assert len(actions) == 1
        assert actions[0].operation_type == "TRANSITION_ISSUE"
        assert actions[0].payload["target_status"] == "In Progress"
        assert actions[0].payload["issue_key"] == "PROJ-1"
        assert actions[0].issue_id == 1

    def test_no_config_uses_zero_defaults(self):
        issue = FakeIssue()
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        enter_status(issue, step, None, random.Random(42))
        assert issue.sampled_full_time == 0.0
        assert issue.sampled_work_time == 0.0

    def test_config_without_percentiles_uses_zero_full_time(self):
        issue = FakeIssue()
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        ttc = FakeTouchTimeConfig(full_time_p25=None, full_time_p50=None, full_time_p99=None)
        enter_status(issue, step, ttc, random.Random(42))
        assert issue.sampled_full_time == 0.0
        assert issue.sampled_work_time >= 1.0  # min_hours default


# ---------------------------------------------------------------------------
# check_transition_ready
# ---------------------------------------------------------------------------

class TestCheckTransitionReady:
    def test_both_zero_means_ready(self):
        issue = FakeIssue(sampled_work_time=0, sampled_full_time=0, elapsed_full_time=0)
        assert check_transition_ready(issue) is True

    def test_work_not_done(self):
        issue = FakeIssue(
            sampled_work_time=4.0, elapsed_work_time=2.0,
            sampled_full_time=0, elapsed_full_time=0,
        )
        assert check_transition_ready(issue) is False

    def test_full_time_not_done(self):
        issue = FakeIssue(sampled_work_time=0, sampled_full_time=8.0, elapsed_full_time=5.0)
        assert check_transition_ready(issue) is False

    def test_both_done(self):
        issue = FakeIssue(
            sampled_work_time=4.0, elapsed_work_time=4.0,
            sampled_full_time=8.0, elapsed_full_time=8.0,
        )
        assert check_transition_ready(issue) is True

    def test_exceeded_both(self):
        issue = FakeIssue(
            sampled_work_time=4.0, elapsed_work_time=5.0,
            sampled_full_time=8.0, elapsed_full_time=10.0,
        )
        assert check_transition_ready(issue) is True

    def test_work_done_full_not(self):
        issue = FakeIssue(
            sampled_work_time=4.0, elapsed_work_time=4.0,
            sampled_full_time=8.0, elapsed_full_time=5.0,
        )
        assert check_transition_ready(issue) is False


# ---------------------------------------------------------------------------
# roll_direction
# ---------------------------------------------------------------------------

class TestRollDirection:
    def test_no_config_returns_forward(self):
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        direction, target = roll_direction("Story", step, [], random.Random(42))
        assert direction == "forward"
        assert target is None

    def test_zero_probability_always_forward(self):
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        cfg = FakeMoveLeftConfig(
            from_step_id=20, base_probability=0.0,
            targets=[FakeMoveLeftTarget(to_step_id=10)],
        )
        for seed in range(100):
            direction, _ = roll_direction("Story", step, [cfg], random.Random(seed))
            assert direction == "forward"

    def test_probability_one_always_left(self):
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        cfg = FakeMoveLeftConfig(
            from_step_id=20, base_probability=1.0,
            targets=[FakeMoveLeftTarget(to_step_id=10)],
        )
        for seed in range(20):
            direction, target = roll_direction("Story", step, [cfg], random.Random(seed))
            assert direction == "left"
            assert target == 10

    def test_type_specific_overrides_generic(self):
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        generic = FakeMoveLeftConfig(from_step_id=20, base_probability=0.0)
        specific = FakeMoveLeftConfig(
            from_step_id=20, base_probability=1.0, issue_type="Bug",
            targets=[FakeMoveLeftTarget(to_step_id=10)],
        )
        direction, target = roll_direction("Bug", step, [generic, specific], random.Random(42))
        assert direction == "left"
        assert target == 10

    def test_weighted_target_selection(self):
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        cfg = FakeMoveLeftConfig(
            from_step_id=20, base_probability=1.0,
            targets=[
                FakeMoveLeftTarget(to_step_id=10, weight=9.0),
                FakeMoveLeftTarget(to_step_id=15, weight=1.0),
            ],
        )
        results = {10: 0, 15: 0}
        for seed in range(500):
            _, target = roll_direction("Story", step, [cfg], random.Random(seed))
            results[target] += 1
        # target 10 should be picked ~90% of the time
        assert results[10] > results[15] * 3

    def test_no_targets_returns_forward(self):
        step = FakeWorkflowStep(id=20, jira_status="In Progress", order=2)
        cfg = FakeMoveLeftConfig(from_step_id=20, base_probability=1.0, targets=[])
        direction, _ = roll_direction("Story", step, [cfg], random.Random(42))
        assert direction == "forward"


# ---------------------------------------------------------------------------
# get_touch_time_config
# ---------------------------------------------------------------------------

class TestGetTouchTimeConfig:
    def test_exact_match(self):
        cfg = FakeTouchTimeConfig(min_hours=2.0)
        configs = {(20, "Story", 3): cfg}
        assert get_touch_time_config(configs, 20, "Story", 3) is cfg

    def test_fallback_to_zero_points(self):
        cfg = FakeTouchTimeConfig(min_hours=1.0)
        configs = {(20, "Story", 0): cfg}
        assert get_touch_time_config(configs, 20, "Story", 5) is cfg

    def test_returns_none_when_missing(self):
        assert get_touch_time_config({}, 20, "Story", 3) is None

    def test_exact_match_preferred_over_fallback(self):
        exact = FakeTouchTimeConfig(min_hours=5.0)
        fallback = FakeTouchTimeConfig(min_hours=1.0)
        configs = {(20, "Story", 3): exact, (20, "Story", 0): fallback}
        assert get_touch_time_config(configs, 20, "Story", 3) is exact


# ---------------------------------------------------------------------------
# process_item_tick
# ---------------------------------------------------------------------------

class TestProcessItemTick:
    def _setup(self, work_time=4.0, full_time=8.0):
        """Create a standard test setup with an issue in 'In Progress'."""
        steps = _three_step_workflow()
        issue = FakeIssue(
            current_workflow_step_id=20,
            status="In Progress",
            sampled_work_time=work_time,
            sampled_full_time=full_time,
        )
        members = build_member_states(_members((1, "DEV")))
        configs = {
            (30, "Story", 0): FakeTouchTimeConfig(
                min_hours=0.0, max_hours=0.0,
                full_time_p25=None, full_time_p50=None,
                full_time_p99=None,
            ),
        }
        return issue, steps, configs, members

    def test_assigns_worker_when_available(self):
        issue, steps, configs, members = self._setup()
        result = process_item_tick(issue, steps, configs, [], members, 1.0, random.Random(42))
        assert issue.work_started is True
        assert issue.current_worker_id == 1
        assert result.member_states[1].busy_this_tick is True

    def test_no_worker_no_work_progress(self):
        steps = _three_step_workflow()
        issue = FakeIssue(
            current_workflow_step_id=20, status="In Progress",
            sampled_work_time=4.0, sampled_full_time=8.0,
        )
        # QA member can't work on DEV step
        members = build_member_states(_members((1, "QA")))
        process_item_tick(issue, steps, {}, [], members, 1.0, random.Random(42))
        assert issue.work_started is False
        assert issue.elapsed_work_time == 0.0
        # Full time still advances
        assert issue.elapsed_full_time == 1.0

    def test_full_time_always_advances(self):
        issue, steps, configs, members = self._setup()
        process_item_tick(issue, steps, configs, [], members, 1.0, random.Random(42))
        assert issue.elapsed_full_time == 1.0

    def test_work_time_advances_with_worker(self):
        issue, steps, configs, members = self._setup()
        process_item_tick(issue, steps, configs, [], members, 1.0, random.Random(42))
        assert issue.elapsed_work_time == 1.0

    def test_transitions_forward_when_ready(self):
        steps = _three_step_workflow()
        issue = FakeIssue(
            current_workflow_step_id=20, status="In Progress",
            sampled_work_time=1.0, sampled_full_time=1.0,
            elapsed_work_time=0.5, elapsed_full_time=0.5,
            work_started=True, current_worker_id=1,
        )
        members = build_member_states(_members((1, "DEV")))
        # tick of 1.0 will push both to 1.5, exceeding 1.0 thresholds
        configs = {
            (30, "Story", 0): FakeTouchTimeConfig(
                min_hours=0.0, max_hours=0.0,
                full_time_p25=None, full_time_p50=None,
                full_time_p99=None,
            ),
        }
        result = process_item_tick(
            issue, steps, configs, [], members, 1.0, random.Random(42),
        )
        assert issue.status == "Done"
        assert result.completed is True
        assert any(a.operation_type == "TRANSITION_ISSUE" for a in result.jira_actions)

    def test_move_left_resamples_times(self):
        steps = _three_step_workflow()
        issue = FakeIssue(
            current_workflow_step_id=20, status="In Progress",
            sampled_work_time=0.0, sampled_full_time=0.5,
            elapsed_full_time=0.0,
        )
        move_cfg = FakeMoveLeftConfig(
            from_step_id=20, base_probability=1.0,
            targets=[FakeMoveLeftTarget(to_step_id=10)],
        )
        members = build_member_states(_members((1, "DEV")))
        configs = {
            (10, "Story", 0): FakeTouchTimeConfig(
                min_hours=2.0, max_hours=4.0,
                full_time_p25=2.0, full_time_p50=4.0,
                full_time_p99=16.0,
            ),
        }
        result = process_item_tick(
            issue, steps, configs, [move_cfg], members,
            1.0, random.Random(42),
        )
        # Should have moved back to "To Do" and re-sampled
        assert issue.status == "To Do"
        assert issue.current_workflow_step_id == 10
        assert issue.elapsed_full_time == 0.0
        assert issue.elapsed_work_time == 0.0
        assert result.completed is False

    def test_zero_work_time_transitions_on_full_time(self):
        steps = _three_step_workflow()
        issue = FakeIssue(
            current_workflow_step_id=20, status="In Progress",
            sampled_work_time=0.0, sampled_full_time=1.0,
            elapsed_full_time=0.5,
        )
        members = build_member_states(_members((1, "DEV")))
        configs = {
            (30, "Story", 0): FakeTouchTimeConfig(
                min_hours=0.0, max_hours=0.0,
                full_time_p25=None, full_time_p50=None,
                full_time_p99=None,
            ),
        }
        # First tick: full_time goes to 1.5, ready to transition
        result = process_item_tick(issue, steps, configs, [], members, 1.0, random.Random(42))
        assert issue.status == "Done"
        assert result.completed is True

    def test_sticky_assignment_reuses_worker(self):
        steps = _three_step_workflow()
        issue = FakeIssue(
            current_workflow_step_id=20, status="In Progress",
            sampled_work_time=4.0, sampled_full_time=8.0,
            work_started=True, current_worker_id=1,
        )
        # Member 1 is sticky-assigned to this issue
        members = build_member_states([
            {"id": 1, "role": "DEV", "assigned_issue_id": 1},
            {"id": 2, "role": "DEV", "assigned_issue_id": None},
        ])
        result = process_item_tick(issue, steps, {}, [], members, 1.0, random.Random(42))
        assert issue.current_worker_id == 1
        assert result.member_states[1].busy_this_tick is True

    def test_no_current_step_returns_empty(self):
        steps = _three_step_workflow()
        issue = FakeIssue(current_workflow_step_id=999)
        members = build_member_states(_members((1, "DEV")))
        result = process_item_tick(issue, steps, {}, [], members, 1.0, random.Random(42))
        assert result.jira_actions == []
        assert result.completed is False

    def test_forward_to_final_marks_completed(self):
        steps = _three_step_workflow()
        # Issue at "In Progress" (order 2), about to move to "Done" (order 3, final)
        issue = FakeIssue(
            current_workflow_step_id=20, status="In Progress",
            sampled_work_time=0.0, sampled_full_time=0.0,
            elapsed_full_time=0.0,
        )
        members = build_member_states(_members((1, "DEV")))
        configs = {
            (30, "Story", 0): FakeTouchTimeConfig(
                min_hours=0.0, max_hours=0.0,
                full_time_p25=None, full_time_p50=None,
                full_time_p99=None,
            ),
        }
        result = process_item_tick(
            issue, steps, configs, [], members, 1.0, random.Random(42),
        )
        assert result.completed is True
        assert issue.status == "Done"

    def test_multi_role_step_accepts_any_matching(self):
        steps = [
            FakeWorkflowStep(id=10, jira_status="To Do", order=1, role_required="DEV"),
            FakeWorkflowStep(
                id=20, jira_status="Review", order=2,
                role_required="DEV", roles_json='["DEV", "QA"]',
            ),
            FakeWorkflowStep(id=30, jira_status="Done", order=3, role_required="DEV"),
        ]
        issue = FakeIssue(
            current_workflow_step_id=20, status="Review",
            sampled_work_time=4.0, sampled_full_time=8.0,
        )
        # Only a QA member — should still be assigned because roles_json includes QA
        members = build_member_states(_members((1, "QA")))
        process_item_tick(issue, steps, {}, [], members, 1.0, random.Random(42))
        assert issue.work_started is True
        assert issue.current_worker_id == 1
