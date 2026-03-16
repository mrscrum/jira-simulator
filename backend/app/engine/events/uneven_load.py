"""Uneven load event — detection of role queue imbalance."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

CONSECUTIVE_TICKS_THRESHOLD = 3


class UnevenLoadEvent(BaseEvent):
    event_type = "uneven_load"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        role_queues = kwargs.get("role_queues", {})
        wip_ceilings = kwargs.get("wip_ceilings", {})
        outcomes = []

        overloaded_roles = []
        idle_roles = []
        for role, queue_size in role_queues.items():
            ceiling = wip_ceilings.get(role, 3)
            if queue_size >= ceiling:
                overloaded_roles.append((role, queue_size))
            elif queue_size == 0:
                idle_roles.append(role)

        if not overloaded_roles or not idle_roles:
            return []

        for role, queue_size in overloaded_roles:
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": "",
                    "body": (
                        f"[SM] {role} queue is backing up."
                        f" {queue_size} issues waiting."
                    ),
                },
            )
            outcomes.append(EventOutcome(
                jira_actions=[comment],
                log_entry={
                    "team_id": context.team_id,
                    "sprint_id": context.sprint["id"],
                    "event_type": self.event_type,
                    "sim_day": context.sim_day,
                    "payload": {
                        "overloaded_role": role,
                        "queue_size": queue_size,
                        "idle_roles": idle_roles,
                    },
                },
            ))
        return outcomes
