"""Carry-over event — flags incomplete issues at sprint end."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

DONE_STATUSES = {"DONE", "Done", "done"}


class CarryOverEvent(BaseEvent):
    event_type = "carry_over"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        outcomes = []
        for issue in context.issues:
            if issue.get("status") in DONE_STATUSES:
                continue
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": issue.get("issue_key", ""),
                    "body": (
                        "[SM] Carried over from Sprint."
                        " Not completed due to insufficient capacity."
                    ),
                },
            )
            outcome = EventOutcome(
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
                    "carried_over": True,
                },
            )
            outcomes.append(outcome)
        return outcomes
