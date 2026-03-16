"""Tests for the issue state machine — all state transitions."""

import pytest

from app.engine.issue_state_machine import (
    InvalidTransitionError,
    IssueState,
    transition_issue,
)


class TestCommitToSprint:
    def test_backlog_to_sprint_committed(self):
        state, actions = transition_issue(
            current_state=IssueState.BACKLOG,
            event="commit_to_sprint",
            context={"sprint_name": "Sprint 1", "issue_key": "TP-1"},
        )
        assert state == IssueState.SPRINT_COMMITTED

    def test_non_backlog_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_issue(
                current_state=IssueState.IN_PROGRESS,
                event="commit_to_sprint",
                context={"sprint_name": "Sprint 1", "issue_key": "TP-1"},
            )


class TestQueueForRole:
    def test_sprint_committed_to_queued(self):
        state, actions = transition_issue(
            current_state=IssueState.SPRINT_COMMITTED,
            event="queue_for_role",
            context={"role": "DEV", "issue_key": "TP-1"},
        )
        assert state == IssueState.QUEUED_FOR_ROLE

    def test_pending_handoff_to_queued(self):
        state, actions = transition_issue(
            current_state=IssueState.PENDING_HANDOFF,
            event="queue_for_role",
            context={"role": "QA", "issue_key": "TP-1"},
        )
        assert state == IssueState.QUEUED_FOR_ROLE

    def test_moved_left_to_queued(self):
        state, actions = transition_issue(
            current_state=IssueState.MOVED_LEFT,
            event="queue_for_role",
            context={"role": "DEV", "issue_key": "TP-1"},
        )
        assert state == IssueState.QUEUED_FOR_ROLE


class TestStartWork:
    def test_queued_to_in_progress(self):
        state, actions = transition_issue(
            current_state=IssueState.QUEUED_FOR_ROLE,
            event="start_work",
            context={
                "worker_name": "Alice",
                "role": "DEV",
                "issue_key": "TP-1",
            },
        )
        assert state == IssueState.IN_PROGRESS
        assert any(a.operation_type == "ADD_COMMENT" for a in actions)


class TestCompleteStep:
    def test_in_progress_to_pending_handoff(self):
        state, actions = transition_issue(
            current_state=IssueState.IN_PROGRESS,
            event="complete_step",
            context={"issue_key": "TP-1", "is_last_step": False},
        )
        assert state == IssueState.PENDING_HANDOFF

    def test_last_step_to_done(self):
        state, actions = transition_issue(
            current_state=IssueState.IN_PROGRESS,
            event="complete_step",
            context={"issue_key": "TP-1", "is_last_step": True},
        )
        assert state == IssueState.DONE
        assert any(a.operation_type == "TRANSITION_ISSUE" for a in actions)


class TestMoveLeft:
    def test_in_progress_to_moved_left(self):
        state, actions = transition_issue(
            current_state=IssueState.IN_PROGRESS,
            event="move_left",
            context={
                "worker_name": "Alice",
                "role": "QA",
                "target_step": "Development",
                "reason": "Found bug",
                "issue_key": "TP-1",
            },
        )
        assert state == IssueState.MOVED_LEFT
        assert any(a.operation_type == "ADD_COMMENT" for a in actions)

    def test_non_in_progress_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_issue(
                current_state=IssueState.BACKLOG,
                event="move_left",
                context={
                    "worker_name": "Alice",
                    "role": "QA",
                    "target_step": "Development",
                    "reason": "Found bug",
                    "issue_key": "TP-1",
                },
            )


class TestBlockExternally:
    def test_in_progress_to_blocked(self):
        state, actions = transition_issue(
            current_state=IssueState.IN_PROGRESS,
            event="block_externally",
            context={
                "worker_name": "Bob",
                "reason": "Waiting on API team",
                "issue_key": "TP-1",
            },
        )
        assert state == IssueState.EXTERNALLY_BLOCKED
        assert any(a.operation_type == "ADD_COMMENT" for a in actions)


class TestUnblock:
    def test_blocked_to_in_progress(self):
        state, actions = transition_issue(
            current_state=IssueState.EXTERNALLY_BLOCKED,
            event="unblock",
            context={"issue_key": "TP-1"},
        )
        assert state == IssueState.IN_PROGRESS


class TestDescope:
    def test_any_sprint_state_to_descoped(self):
        for source_state in [
            IssueState.SPRINT_COMMITTED,
            IssueState.QUEUED_FOR_ROLE,
            IssueState.IN_PROGRESS,
        ]:
            state, actions = transition_issue(
                current_state=source_state,
                event="descope",
                context={
                    "sm_name": "Charlie",
                    "sprint_name": "Sprint 1",
                    "issue_key": "TP-1",
                },
            )
            assert state == IssueState.DESCOPED

    def test_backlog_cannot_be_descoped(self):
        with pytest.raises(InvalidTransitionError):
            transition_issue(
                current_state=IssueState.BACKLOG,
                event="descope",
                context={
                    "sm_name": "Charlie",
                    "sprint_name": "Sprint 1",
                    "issue_key": "TP-1",
                },
            )


class TestJiraWriteActions:
    def test_start_work_produces_comment(self):
        _, actions = transition_issue(
            current_state=IssueState.QUEUED_FOR_ROLE,
            event="start_work",
            context={
                "worker_name": "Alice",
                "role": "DEV",
                "issue_key": "TP-1",
            },
        )
        comments = [a for a in actions if a.operation_type == "ADD_COMMENT"]
        assert len(comments) == 1
        assert "Alice" in comments[0].payload["body"]

    def test_move_left_produces_comment_with_reason(self):
        _, actions = transition_issue(
            current_state=IssueState.IN_PROGRESS,
            event="move_left",
            context={
                "worker_name": "Alice",
                "role": "QA",
                "target_step": "Development",
                "reason": "Found bug in logic",
                "issue_key": "TP-1",
            },
        )
        comments = [a for a in actions if a.operation_type == "ADD_COMMENT"]
        assert len(comments) == 1
        assert "Found bug in logic" in comments[0].payload["body"]

    def test_descope_produces_comment(self):
        _, actions = transition_issue(
            current_state=IssueState.IN_PROGRESS,
            event="descope",
            context={
                "sm_name": "SM",
                "sprint_name": "Sprint 1",
                "issue_key": "TP-1",
            },
        )
        comments = [a for a in actions if a.operation_type == "ADD_COMMENT"]
        assert len(comments) == 1
        assert "Descoped" in comments[0].payload["body"]

    def test_done_produces_transition(self):
        _, actions = transition_issue(
            current_state=IssueState.IN_PROGRESS,
            event="complete_step",
            context={"issue_key": "TP-1", "is_last_step": True},
        )
        transitions = [
            a for a in actions if a.operation_type == "TRANSITION_ISSUE"
        ]
        assert len(transitions) >= 1


class TestUnknownEvent:
    def test_unknown_event_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_issue(
                current_state=IssueState.BACKLOG,
                event="nonexistent_event",
                context={},
            )
