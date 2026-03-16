"""Late planning event — planning phase runs long."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction


class LatePlanningEvent(BaseEvent):
    event_type = "late_planning"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        probability = kwargs.get("probability", 0.15)
        rng = kwargs.get("rng", random)
        if rng.random() > probability:
            return []

        extra_hours = rng.randint(2, 4)
        comment = JiraWriteAction(
            operation_type="ADD_COMMENT",
            payload={
                "issue_key": "",
                "body": (
                    "[SM] Planning ran long today."
                    " Starting sprint slightly behind schedule."
                ),
            },
        )
        return [EventOutcome(
            jira_actions=[comment],
            log_entry={
                "team_id": context.team_id,
                "sprint_id": context.sprint["id"],
                "event_type": self.event_type,
                "sim_day": context.sim_day,
                "payload": {"extra_hours": extra_hours},
            },
            capacity_mutations={
                "planning_extra_hours": extra_hours,
            },
        )]
