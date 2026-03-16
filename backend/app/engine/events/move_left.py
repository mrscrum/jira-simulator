"""Move left event — issue transitions back to earlier step."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction


class MoveLeftEvent(BaseEvent):
    event_type = "move_left"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        base_probability = kwargs.get("base_probability", 0.1)
        rng = kwargs.get("rng", random)
        outcomes = []
        for issue in context.issues:
            if issue.get("status") != "IN_PROGRESS":
                continue
            if rng.random() > base_probability:
                continue
            target_step = kwargs.get("target_step", "Previous Step")
            reason = "Quality issues found during review"
            worker = issue.get("worker_name", "Team Member")
            role = issue.get("role", "Unknown")
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": issue.get("issue_key", ""),
                    "body": (
                        f"[{worker} - {role}] Sending back to"
                        f" {target_step} — {reason}"
                    ),
                },
            )
            outcomes.append(EventOutcome(
                jira_actions=[comment],
                log_entry={
                    "team_id": context.team_id,
                    "sprint_id": context.sprint["id"],
                    "issue_id": issue["id"],
                    "event_type": self.event_type,
                    "sim_day": context.sim_day,
                    "payload": {"target_step": target_step},
                },
                issue_mutations={
                    "issue_id": issue["id"],
                    "new_status": "MOVED_LEFT",
                },
            ))
        return outcomes
