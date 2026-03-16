"""Issue state machine — all state transitions per the spec.

Each transition validates preconditions and produces JiraWriteActions.
The engine never calls Jira directly — it collects actions for the write queue.
"""

from dataclasses import dataclass
from enum import StrEnum


class IssueState(StrEnum):
    BACKLOG = "BACKLOG"
    SPRINT_COMMITTED = "SPRINT_COMMITTED"
    QUEUED_FOR_ROLE = "QUEUED_FOR_ROLE"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_HANDOFF = "PENDING_HANDOFF"
    DONE = "DONE"
    MOVED_LEFT = "MOVED_LEFT"
    EXTERNALLY_BLOCKED = "EXTERNALLY_BLOCKED"
    DESCOPED = "DESCOPED"


class InvalidTransitionError(Exception):
    pass


@dataclass(frozen=True)
class JiraWriteAction:
    operation_type: str
    payload: dict
    issue_id: int | None = None


# Valid transitions: source_state -> set of allowed events
VALID_TRANSITIONS: dict[IssueState, set[str]] = {
    IssueState.BACKLOG: {"commit_to_sprint"},
    IssueState.SPRINT_COMMITTED: {"queue_for_role", "descope"},
    IssueState.QUEUED_FOR_ROLE: {"start_work", "descope"},
    IssueState.IN_PROGRESS: {
        "complete_step",
        "move_left",
        "block_externally",
        "descope",
    },
    IssueState.PENDING_HANDOFF: {"queue_for_role"},
    IssueState.DONE: set(),
    IssueState.MOVED_LEFT: {"queue_for_role"},
    IssueState.EXTERNALLY_BLOCKED: {"unblock"},
    IssueState.DESCOPED: set(),
}


def transition_issue(
    current_state: IssueState,
    event: str,
    context: dict,
) -> tuple[IssueState, list[JiraWriteAction]]:
    """Execute a state transition, returning new state and Jira actions."""
    allowed = VALID_TRANSITIONS.get(current_state, set())
    if event not in allowed:
        raise InvalidTransitionError(
            f"Cannot apply '{event}' from state '{current_state}'"
        )

    handler = _EVENT_HANDLERS.get(event)
    if handler is None:
        raise InvalidTransitionError(f"Unknown event: {event}")
    return handler(current_state, context)


def _handle_commit_to_sprint(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    return IssueState.SPRINT_COMMITTED, []


def _handle_queue_for_role(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    return IssueState.QUEUED_FOR_ROLE, []


def _handle_start_work(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    worker = context.get("worker_name", "Unknown")
    role = context.get("role", "Unknown")
    issue_key = context.get("issue_key", "")
    comment = JiraWriteAction(
        operation_type="ADD_COMMENT",
        payload={
            "issue_key": issue_key,
            "body": f"[{worker} - {role}] Picked up for work.",
        },
    )
    return IssueState.IN_PROGRESS, [comment]


def _handle_complete_step(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    is_last = context.get("is_last_step", False)
    issue_key = context.get("issue_key", "")
    if is_last:
        transition_action = JiraWriteAction(
            operation_type="TRANSITION_ISSUE",
            payload={"issue_key": issue_key, "target_status": "Done"},
        )
        return IssueState.DONE, [transition_action]
    return IssueState.PENDING_HANDOFF, []


def _handle_move_left(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    worker = context.get("worker_name", "Unknown")
    role = context.get("role", "Unknown")
    target = context.get("target_step", "Unknown")
    reason = context.get("reason", "")
    issue_key = context.get("issue_key", "")
    comment = JiraWriteAction(
        operation_type="ADD_COMMENT",
        payload={
            "issue_key": issue_key,
            "body": (
                f"[{worker} - {role}] Sending back to {target}"
                f" — {reason}"
            ),
        },
    )
    return IssueState.MOVED_LEFT, [comment]


def _handle_block_externally(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    worker = context.get("worker_name", "Unknown")
    reason = context.get("reason", "")
    issue_key = context.get("issue_key", "")
    comment = JiraWriteAction(
        operation_type="ADD_COMMENT",
        payload={
            "issue_key": issue_key,
            "body": f"[{worker}] Blocked by external dependency: {reason}",
        },
    )
    return IssueState.EXTERNALLY_BLOCKED, [comment]


def _handle_unblock(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    return IssueState.IN_PROGRESS, []


def _handle_descope(
    current_state: IssueState, context: dict
) -> tuple[IssueState, list[JiraWriteAction]]:
    sm = context.get("sm_name", "SM")
    sprint = context.get("sprint_name", "Sprint")
    issue_key = context.get("issue_key", "")
    comment = JiraWriteAction(
        operation_type="ADD_COMMENT",
        payload={
            "issue_key": issue_key,
            "body": (
                f"[{sm}] Descoped from {sprint} due to"
                " capacity constraints. Returning to backlog."
            ),
        },
    )
    return IssueState.DESCOPED, [comment]


_EVENT_HANDLERS = {
    "commit_to_sprint": _handle_commit_to_sprint,
    "queue_for_role": _handle_queue_for_role,
    "start_work": _handle_start_work,
    "complete_step": _handle_complete_step,
    "move_left": _handle_move_left,
    "block_externally": _handle_block_externally,
    "unblock": _handle_unblock,
    "descope": _handle_descope,
}
