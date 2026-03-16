"""Scope commitment miss — sprint starts overcommitted."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

OVERCOMMIT_THRESHOLD = 1.15


class ScopeCommitmentMissEvent(BaseEvent):
    event_type = "scope_commitment_miss"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        committed = context.sprint.get("committed_points", 0)
        recent_velocity = kwargs.get("recent_velocity", 0)

        if recent_velocity <= 0:
            return []
        if committed <= recent_velocity * OVERCOMMIT_THRESHOLD:
            return []

        comment = JiraWriteAction(
            operation_type="ADD_COMMENT",
            payload={
                "issue_key": "",
                "body": (
                    f"[SM] Sprint committed to {committed} points"
                    f" against a recent velocity of {recent_velocity}."
                    " Stretch goal — may need to descope."
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
                "payload": {
                    "committed": committed,
                    "velocity": recent_velocity,
                    "ratio": round(committed / recent_velocity, 2),
                },
            },
        )]
