"""Priority change event — issue priority elevated mid-sprint."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction


class PriorityChangeEvent(BaseEvent):
    event_type = "priority_change"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        probability = kwargs.get("probability", 0.08)
        rng = kwargs.get("rng", random)
        outcomes = []
        eligible = [
            i for i in context.issues
            if i.get("status") in {"IN_PROGRESS", "QUEUED_FOR_ROLE"}
        ]
        for issue in eligible:
            if rng.random() > probability:
                continue
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": issue.get("issue_key", ""),
                    "body": (
                        "[SM] Priority elevated due to business urgency."
                        " Needs immediate attention."
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
                        "old_priority": issue.get("priority", "Medium"),
                        "new_priority": "Highest",
                    },
                },
                issue_mutations={
                    "issue_id": issue["id"],
                    "priority": "Highest",
                },
            ))
        return outcomes
