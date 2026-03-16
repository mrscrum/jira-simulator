"""External block event — issue blocked by external dependency."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction


class ExternalBlockEvent(BaseEvent):
    event_type = "external_block"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        probability = kwargs.get("probability", 0.12)
        rng = kwargs.get("rng", random)
        outcomes = []
        for issue in context.issues:
            if issue.get("status") != "IN_PROGRESS":
                continue
            if rng.random() > probability:
                continue
            duration_days = rng.randint(1, 5)
            worker = issue.get("worker_name", "Team Member")
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": issue.get("issue_key", ""),
                    "body": (
                        f"[{worker}] Blocked by external dependency."
                        " Waiting on third-party team."
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
                    "payload": {"duration_days": duration_days},
                },
                issue_mutations={
                    "issue_id": issue["id"],
                    "new_status": "EXTERNALLY_BLOCKED",
                    "block_duration_days": duration_days,
                },
            ))
        return outcomes
