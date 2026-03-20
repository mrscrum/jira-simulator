"""Shared types for the simulation engine."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JiraWriteAction:
    """An action to be enqueued to the Jira write queue.

    The engine never calls Jira directly — it collects actions for the write queue.
    """

    operation_type: str
    payload: dict
    issue_id: int | None = None


@dataclass
class ItemTickResult:
    """Result of processing one item for one tick."""

    jira_actions: list[JiraWriteAction]
    member_states: dict  # updated dict[int, MemberTickState]
    completed: bool  # item reached final status this tick
