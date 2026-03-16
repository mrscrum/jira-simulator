"""Tests for 12 remaining event handlers (Task 7)."""

import random
from datetime import UTC, datetime

from app.engine.events.base import TickContext
from app.engine.events.descope import DescopeEvent
from app.engine.events.external_block import ExternalBlockEvent
from app.engine.events.late_planning import LatePlanningEvent
from app.engine.events.move_left import MoveLeftEvent
from app.engine.events.onboarding_tax import OnboardingTaxEvent
from app.engine.events.priority_change import PriorityChangeEvent
from app.engine.events.registry import get_all_event_types, get_event_handler
from app.engine.events.review_bottleneck import ReviewBottleneckEvent
from app.engine.events.scope_commitment_miss import ScopeCommitmentMissEvent
from app.engine.events.skipped_retro import SkippedRetroEvent
from app.engine.events.split_story import SplitStoryEvent
from app.engine.events.uneven_load import UnevenLoadEvent
from app.engine.events.unplanned_absence import UnplannedAbsenceEvent


def _ctx(issues=None, sprint=None, members=None, sim_day=5):
    return TickContext(
        team_id=1,
        sprint=sprint or {"id": 1, "committed_points": 20, "completed_points": 10},
        issues=issues or [],
        members=members or [],
        capacity_states={},
        sim_day=sim_day,
        now=datetime(2026, 3, 16, 12, 0, tzinfo=UTC),
    )


def _seeded_rng(seed=42):
    return random.Random(seed)


def _always_trigger_rng():
    """RNG that always returns 0.0 so probability checks pass."""
    r = random.Random()
    r.random = lambda: 0.0
    return r


def _never_trigger_rng():
    """RNG that always returns 1.0 so probability checks fail."""
    r = random.Random()
    r.random = lambda: 1.0
    return r


# ── Registry completeness ──


class TestAllEventsRegistered:
    def test_sixteen_events_registered(self):
        all_types = get_all_event_types()
        assert len(all_types) == 16

    def test_move_left_registered(self):
        assert isinstance(get_event_handler("move_left"), MoveLeftEvent)

    def test_descope_registered(self):
        assert isinstance(get_event_handler("descope"), DescopeEvent)

    def test_unplanned_absence_registered(self):
        assert isinstance(get_event_handler("unplanned_absence"), UnplannedAbsenceEvent)

    def test_priority_change_registered(self):
        assert isinstance(get_event_handler("priority_change"), PriorityChangeEvent)

    def test_split_story_registered(self):
        assert isinstance(get_event_handler("split_story"), SplitStoryEvent)

    def test_external_block_registered(self):
        assert isinstance(get_event_handler("external_block"), ExternalBlockEvent)

    def test_uneven_load_registered(self):
        assert isinstance(get_event_handler("uneven_load"), UnevenLoadEvent)

    def test_review_bottleneck_registered(self):
        assert isinstance(get_event_handler("review_bottleneck"), ReviewBottleneckEvent)

    def test_onboarding_tax_registered(self):
        assert isinstance(get_event_handler("onboarding_tax"), OnboardingTaxEvent)

    def test_late_planning_registered(self):
        assert isinstance(get_event_handler("late_planning"), LatePlanningEvent)

    def test_skipped_retro_registered(self):
        assert isinstance(get_event_handler("skipped_retro"), SkippedRetroEvent)

    def test_scope_commitment_miss_registered(self):
        assert isinstance(get_event_handler("scope_commitment_miss"), ScopeCommitmentMissEvent)


# ── MoveLeftEvent ──


class TestMoveLeftEvent:
    def test_triggers_on_in_progress_issue(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "worker_name": "Alice", "role": "DEV"}]
        ctx = _ctx(issues=issues)
        outcomes = MoveLeftEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 1
        assert outcomes[0].issue_mutations["new_status"] == "MOVED_LEFT"

    def test_skips_non_in_progress(self):
        issues = [{"id": 1, "status": "QUEUED_FOR_ROLE", "issue_key": "TP-1"}]
        ctx = _ctx(issues=issues)
        outcomes = MoveLeftEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0

    def test_no_trigger_on_failed_probability(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1"}]
        ctx = _ctx(issues=issues)
        outcomes = MoveLeftEvent().evaluate(ctx, rng=_never_trigger_rng())
        assert len(outcomes) == 0

    def test_comment_includes_worker_and_role(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "worker_name": "Bob", "role": "QA"}]
        ctx = _ctx(issues=issues)
        outcomes = MoveLeftEvent().evaluate(ctx, rng=_always_trigger_rng())
        body = outcomes[0].jira_actions[0].payload["body"]
        assert "Bob" in body
        assert "QA" in body


# ── DescopeEvent ──


class TestDescopeEvent:
    def test_descopes_eligible_issue(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "story_points": 5}]
        ctx = _ctx(issues=issues)
        outcomes = DescopeEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 1
        assert outcomes[0].issue_mutations["descoped"] is True

    def test_skips_done_issues(self):
        issues = [{"id": 1, "status": "DONE", "issue_key": "TP-1", "story_points": 3}]
        ctx = _ctx(issues=issues)
        outcomes = DescopeEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0

    def test_skips_already_descoped(self):
        issues = [{"id": 1, "status": "DESCOPED", "issue_key": "TP-1"}]
        ctx = _ctx(issues=issues)
        outcomes = DescopeEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0

    def test_skips_backlog(self):
        issues = [{"id": 1, "status": "BACKLOG", "issue_key": "TP-1"}]
        ctx = _ctx(issues=issues)
        outcomes = DescopeEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0


# ── UnplannedAbsenceEvent ──


class TestUnplannedAbsenceEvent:
    def test_triggers_for_member(self):
        members = [{"id": 1, "name": "Alice"}]
        ctx = _ctx(members=members)
        outcomes = UnplannedAbsenceEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 1
        assert outcomes[0].capacity_mutations["capacity_zero_days"] >= 1

    def test_no_trigger_on_failed_probability(self):
        members = [{"id": 1, "name": "Alice"}]
        ctx = _ctx(members=members)
        outcomes = UnplannedAbsenceEvent().evaluate(ctx, rng=_never_trigger_rng())
        assert len(outcomes) == 0

    def test_duration_between_one_and_two(self):
        members = [{"id": 1, "name": "Alice"}]
        ctx = _ctx(members=members)
        rng = _always_trigger_rng()
        rng.randint = lambda a, b: 2
        outcomes = UnplannedAbsenceEvent().evaluate(ctx, rng=rng)
        assert outcomes[0].capacity_mutations["capacity_zero_days"] == 2


# ── PriorityChangeEvent ──


class TestPriorityChangeEvent:
    def test_elevates_in_progress_issue(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "priority": "Medium"}]
        ctx = _ctx(issues=issues)
        outcomes = PriorityChangeEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 1
        assert outcomes[0].issue_mutations["priority"] == "Highest"

    def test_elevates_queued_for_role(self):
        issues = [{"id": 1, "status": "QUEUED_FOR_ROLE", "issue_key": "TP-1",
                    "priority": "Low"}]
        ctx = _ctx(issues=issues)
        outcomes = PriorityChangeEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 1

    def test_skips_done_issues(self):
        issues = [{"id": 1, "status": "DONE", "issue_key": "TP-1"}]
        ctx = _ctx(issues=issues)
        outcomes = PriorityChangeEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0


# ── SplitStoryEvent ──


class TestSplitStoryEvent:
    def test_splits_large_story(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "story_points": 8}]
        ctx = _ctx(issues=issues)
        outcomes = SplitStoryEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 1
        mutations = outcomes[0].issue_mutations
        assert mutations["split_a_points"] == 4
        assert mutations["split_b_points"] == 4

    def test_skips_small_story(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "story_points": 3}]
        ctx = _ctx(issues=issues)
        outcomes = SplitStoryEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0

    def test_odd_points_split_correctly(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "story_points": 5}]
        ctx = _ctx(issues=issues)
        outcomes = SplitStoryEvent().evaluate(ctx, rng=_always_trigger_rng())
        m = outcomes[0].issue_mutations
        assert m["split_a_points"] + m["split_b_points"] == 5

    def test_skips_non_in_progress(self):
        issues = [{"id": 1, "status": "DONE", "issue_key": "TP-1",
                    "story_points": 8}]
        ctx = _ctx(issues=issues)
        outcomes = SplitStoryEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0


# ── ExternalBlockEvent ──


class TestExternalBlockEvent:
    def test_blocks_in_progress_issue(self):
        issues = [{"id": 1, "status": "IN_PROGRESS", "issue_key": "TP-1",
                    "worker_name": "Eve"}]
        ctx = _ctx(issues=issues)
        rng = _always_trigger_rng()
        rng.randint = lambda a, b: 3
        outcomes = ExternalBlockEvent().evaluate(ctx, rng=rng)
        assert len(outcomes) == 1
        assert outcomes[0].issue_mutations["new_status"] == "EXTERNALLY_BLOCKED"
        assert outcomes[0].issue_mutations["block_duration_days"] == 3

    def test_skips_non_in_progress(self):
        issues = [{"id": 1, "status": "DONE", "issue_key": "TP-1"}]
        ctx = _ctx(issues=issues)
        outcomes = ExternalBlockEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 0


# ── UnevenLoadEvent ──


class TestUnevenLoadEvent:
    def test_detects_overloaded_with_idle(self):
        ctx = _ctx()
        outcomes = UnevenLoadEvent().evaluate(
            ctx,
            role_queues={"DEV": 5, "QA": 0},
            wip_ceilings={"DEV": 3, "QA": 3},
        )
        assert len(outcomes) == 1
        assert outcomes[0].log_entry["payload"]["overloaded_role"] == "DEV"

    def test_no_detection_when_no_idle(self):
        ctx = _ctx()
        outcomes = UnevenLoadEvent().evaluate(
            ctx,
            role_queues={"DEV": 5, "QA": 2},
            wip_ceilings={"DEV": 3, "QA": 3},
        )
        assert len(outcomes) == 0

    def test_no_detection_when_no_overload(self):
        ctx = _ctx()
        outcomes = UnevenLoadEvent().evaluate(
            ctx,
            role_queues={"DEV": 1, "QA": 0},
            wip_ceilings={"DEV": 3, "QA": 3},
        )
        assert len(outcomes) == 0


# ── ReviewBottleneckEvent ──


class TestReviewBottleneckEvent:
    def test_detects_bottleneck(self):
        ctx = _ctx()
        outcomes = ReviewBottleneckEvent().evaluate(
            ctx, review_queue_size=5, reviewer_name="Bob",
        )
        assert len(outcomes) == 1
        assert outcomes[0].capacity_mutations["touch_time_multiplier"] == 1.2

    def test_no_bottleneck_below_threshold(self):
        ctx = _ctx()
        outcomes = ReviewBottleneckEvent().evaluate(
            ctx, review_queue_size=2,
        )
        assert len(outcomes) == 0

    def test_comment_mentions_reviewer(self):
        ctx = _ctx()
        outcomes = ReviewBottleneckEvent().evaluate(
            ctx, review_queue_size=4, reviewer_name="Carol",
        )
        body = outcomes[0].jira_actions[0].payload["body"]
        assert "Carol" in body


# ── OnboardingTaxEvent ──


class TestOnboardingTaxEvent:
    def test_early_ramp_factor(self):
        ctx = _ctx()
        outcomes = OnboardingTaxEvent().evaluate(
            ctx, new_members=[{"id": 1, "name": "Newbie", "days_on_team": 2}],
        )
        assert len(outcomes) == 1
        assert outcomes[0].capacity_mutations["capacity_factor"] == 0.5

    def test_late_ramp_factor(self):
        ctx = _ctx()
        outcomes = OnboardingTaxEvent().evaluate(
            ctx, new_members=[{"id": 1, "name": "Newbie", "days_on_team": 4}],
        )
        assert outcomes[0].capacity_mutations["capacity_factor"] == 0.75

    def test_no_tax_after_ramp_up(self):
        ctx = _ctx()
        outcomes = OnboardingTaxEvent().evaluate(
            ctx, new_members=[{"id": 1, "name": "Veteran", "days_on_team": 10}],
        )
        assert len(outcomes) == 0

    def test_first_day_produces_comment(self):
        ctx = _ctx()
        outcomes = OnboardingTaxEvent().evaluate(
            ctx, new_members=[{"id": 1, "name": "Newbie", "days_on_team": 1}],
        )
        assert len(outcomes[0].jira_actions) == 1


# ── LatePlanningEvent ──


class TestLatePlanningEvent:
    def test_triggers_and_adds_extra_hours(self):
        ctx = _ctx()
        rng = _always_trigger_rng()
        rng.randint = lambda a, b: 3
        outcomes = LatePlanningEvent().evaluate(ctx, rng=rng)
        assert len(outcomes) == 1
        assert outcomes[0].capacity_mutations["planning_extra_hours"] == 3

    def test_no_trigger_on_failed_probability(self):
        ctx = _ctx()
        outcomes = LatePlanningEvent().evaluate(ctx, rng=_never_trigger_rng())
        assert len(outcomes) == 0


# ── SkippedRetroEvent ──


class TestSkippedRetroEvent:
    def test_triggers_skip(self):
        ctx = _ctx()
        outcomes = SkippedRetroEvent().evaluate(ctx, rng=_always_trigger_rng())
        assert len(outcomes) == 1
        assert outcomes[0].issue_mutations["skip_retro"] is True

    def test_no_trigger_on_failed_probability(self):
        ctx = _ctx()
        outcomes = SkippedRetroEvent().evaluate(ctx, rng=_never_trigger_rng())
        assert len(outcomes) == 0


# ── ScopeCommitmentMissEvent ──


class TestScopeCommitmentMissEvent:
    def test_detects_overcommitment(self):
        sprint = {"id": 1, "committed_points": 30, "completed_points": 0}
        ctx = _ctx(sprint=sprint)
        outcomes = ScopeCommitmentMissEvent().evaluate(ctx, recent_velocity=20)
        assert len(outcomes) == 1
        assert outcomes[0].log_entry["payload"]["ratio"] == 1.5

    def test_no_detection_within_threshold(self):
        sprint = {"id": 1, "committed_points": 22, "completed_points": 0}
        ctx = _ctx(sprint=sprint)
        outcomes = ScopeCommitmentMissEvent().evaluate(ctx, recent_velocity=20)
        assert len(outcomes) == 0

    def test_zero_velocity_returns_empty(self):
        sprint = {"id": 1, "committed_points": 30, "completed_points": 0}
        ctx = _ctx(sprint=sprint)
        outcomes = ScopeCommitmentMissEvent().evaluate(ctx, recent_velocity=0)
        assert len(outcomes) == 0

    def test_comment_mentions_committed_and_velocity(self):
        sprint = {"id": 1, "committed_points": 30, "completed_points": 0}
        ctx = _ctx(sprint=sprint)
        outcomes = ScopeCommitmentMissEvent().evaluate(ctx, recent_velocity=20)
        body = outcomes[0].jira_actions[0].payload["body"]
        assert "30" in body
        assert "20" in body
