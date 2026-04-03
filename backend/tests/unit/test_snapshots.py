"""Tests for snapshot dataclasses and factory functions."""

from app.engine.snapshots import (
    IssueSnapshot,
    MemberSnapshot,
    MoveLeftConfigSnapshot,
    MoveLeftTargetSnapshot,
    TeamSnapshot,
    TouchTimeConfigSnapshot,
    WorkflowStepSnapshot,
)


class TestIssueSnapshot:
    def test_has_all_workflow_engine_attributes(self):
        """IssueSnapshot must expose all fields that process_item_tick reads/writes."""
        snap = IssueSnapshot(
            id=1, team_id=1, issue_type="Story", story_points=3,
            summary="test", jira_issue_key="TST-1", jira_issue_id="1",
            status="To Do", current_workflow_step_id=1,
            current_worker_id=None,
        )
        # Fields read by workflow_engine.process_item_tick
        assert hasattr(snap, "sampled_work_time")
        assert hasattr(snap, "work_started")
        assert hasattr(snap, "current_worker_id")
        assert hasattr(snap, "elapsed_work_time")
        assert hasattr(snap, "elapsed_full_time")
        assert hasattr(snap, "sampled_full_time")
        assert hasattr(snap, "current_workflow_step_id")
        assert hasattr(snap, "issue_type")
        assert hasattr(snap, "story_points")
        assert hasattr(snap, "completed_at")
        assert hasattr(snap, "jira_issue_key")
        assert hasattr(snap, "status")

    def test_mutable(self):
        snap = IssueSnapshot(
            id=1, team_id=1, issue_type="Story", story_points=3,
            summary="test", jira_issue_key="TST-1", jira_issue_id="1",
            status="backlog", current_workflow_step_id=None,
            current_worker_id=None,
        )
        snap.sampled_work_time = 5.0
        snap.elapsed_work_time = 2.5
        snap.work_started = True
        assert snap.sampled_work_time == 5.0
        assert snap.elapsed_work_time == 2.5
        assert snap.work_started is True


class TestWorkflowStepSnapshot:
    def test_roles_from_json(self):
        snap = WorkflowStepSnapshot(
            id=1, workflow_id=1, jira_status="In Progress",
            order=2, roles_json='["dev", "qa"]',
        )
        assert snap.roles == ["dev", "qa"]

    def test_roles_from_role_required(self):
        snap = WorkflowStepSnapshot(
            id=1, workflow_id=1, jira_status="Review",
            order=3, role_required="qa",
        )
        assert snap.roles == ["qa"]

    def test_roles_empty_when_nothing_set(self):
        snap = WorkflowStepSnapshot(
            id=1, workflow_id=1, jira_status="Done", order=4,
        )
        assert snap.roles == []


class TestTeamSnapshot:
    def test_defaults(self):
        snap = TeamSnapshot(
            id=1, name="T", jira_project_key="T",
            jira_board_id=None, sprint_length_days=10,
            sprint_capacity_min=20, sprint_capacity_max=40,
            priority_randomization=False, tick_duration_hours=1.0,
            timezone="UTC", working_hours_start=9,
            working_hours_end=17, holidays="[]",
        )
        assert snap.sprint_auto_schedule is True
        assert snap.sprint_cadence_rule is None


class TestMoveLeftConfigSnapshot:
    def test_targets(self):
        snap = MoveLeftConfigSnapshot(
            id=1, team_id=1, from_step_id=2,
            issue_type="Story", base_probability=0.1,
            targets=[
                MoveLeftTargetSnapshot(id=1, to_step_id=1, weight=1.0),
            ],
        )
        assert len(snap.targets) == 1
        assert snap.targets[0].to_step_id == 1
