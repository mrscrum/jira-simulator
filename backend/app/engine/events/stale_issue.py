"""Stale issue event — detection when an issue waits too long in queue."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

DEFAULT_STALE_THRESHOLD_HOURS = 24.0


class StaleIssueEvent(BaseEvent):
    event_type = "stale_issue"

    def evaluate(
        self,
        context: TickContext,
        stale_threshold_hours: float = DEFAULT_STALE_THRESHOLD_HOURS,
        **kwargs,
    ) -> list[EventOutcome]:
        outcomes = []
        for issue in context.issues:
            if issue.get("status") != "QUEUED_FOR_ROLE":
                continue
            wait_hours = issue.get("wait_time_accumulated_hours", 0.0)
            if wait_hours < stale_threshold_hours:
                continue

            role = issue.get("role", "Unknown")
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": issue.get("issue_key", ""),
                    "body": (
                        f"[SM] This issue has been waiting for {role}"
                        f" for {wait_hours:.0f} hours."
                        " Is there a blocker?"
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
                        "wait_hours": wait_hours,
                        "role": role,
                    },
                },
            )
            outcomes.append(outcome)
        return outcomes
