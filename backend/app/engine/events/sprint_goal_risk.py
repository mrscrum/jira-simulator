"""Sprint goal risk event — detection when remaining work exceeds capacity."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

DEFAULT_RISK_THRESHOLD = 1.2


class SprintGoalRiskEvent(BaseEvent):
    event_type = "sprint_goal_risk"

    def evaluate(
        self,
        context: TickContext,
        remaining_capacity_hours: float = 0.0,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
        **kwargs,
    ) -> list[EventOutcome]:
        committed = context.sprint.get("committed_points", 0)
        completed = context.sprint.get("completed_points", 0)
        remaining_points = committed - completed

        if remaining_capacity_hours <= 0:
            return []

        ratio = remaining_points / remaining_capacity_hours
        if ratio <= risk_threshold:
            return []

        comment = JiraWriteAction(
            operation_type="ADD_COMMENT",
            payload={
                "issue_key": "",
                "body": (
                    f"[SM] Sprint goal is at risk."
                    f" {remaining_points} points remain with"
                    f" {remaining_capacity_hours:.0f}h of capacity left."
                ),
            },
        )
        outcome = EventOutcome(
            jira_actions=[comment],
            log_entry={
                "team_id": context.team_id,
                "sprint_id": context.sprint["id"],
                "event_type": self.event_type,
                "sim_day": context.sim_day,
                "payload": {
                    "remaining_points": remaining_points,
                    "remaining_capacity": remaining_capacity_hours,
                    "ratio": round(ratio, 2),
                },
            },
        )
        return [outcome]
