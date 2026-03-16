"""Descope event — remove issue from sprint due to capacity constraints."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction


class DescopeEvent(BaseEvent):
    event_type = "descope"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        base_probability = kwargs.get("base_probability", 0.05)
        rng = kwargs.get("rng", random)
        outcomes = []
        for issue in context.issues:
            status = issue.get("status", "")
            if status in {"DONE", "DESCOPED", "BACKLOG"}:
                continue
            if rng.random() > base_probability:
                continue
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": issue.get("issue_key", ""),
                    "body": (
                        "[SM] Descoped from sprint due to"
                        " capacity constraints. Returning to backlog."
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
                    "payload": {
                        "story_points": issue.get("story_points", 0),
                    },
                },
                issue_mutations={
                    "issue_id": issue["id"],
                    "new_status": "DESCOPED",
                    "descoped": True,
                },
            ))
        return outcomes
