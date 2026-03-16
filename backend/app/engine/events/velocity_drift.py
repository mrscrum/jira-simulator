"""Velocity drift event — tracks velocity trend at sprint end."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext


class VelocityDriftEvent(BaseEvent):
    event_type = "velocity_drift"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        committed = context.sprint.get("committed_points", 0)
        completed = context.sprint.get("completed_points", 0)
        velocity = completed / committed if committed > 0 else 0.0

        outcome = EventOutcome(
            log_entry={
                "team_id": context.team_id,
                "sprint_id": context.sprint["id"],
                "event_type": self.event_type,
                "sim_day": context.sim_day,
                "payload": {
                    "velocity": velocity,
                    "committed": committed,
                    "completed": completed,
                },
            },
        )
        return [outcome]
