"""Unplanned absence event — member capacity drops to zero temporarily."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext


class UnplannedAbsenceEvent(BaseEvent):
    event_type = "unplanned_absence"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        probability = kwargs.get("probability", 0.02)
        rng = kwargs.get("rng", random)
        outcomes = []
        for member in context.members:
            if rng.random() > probability:
                continue
            duration_days = rng.randint(1, 2)
            outcomes.append(EventOutcome(
                log_entry={
                    "team_id": context.team_id,
                    "sprint_id": context.sprint["id"],
                    "event_type": self.event_type,
                    "sim_day": context.sim_day,
                    "payload": {
                        "member_id": member.get("id"),
                        "member_name": member.get("name", "Unknown"),
                        "duration_days": duration_days,
                    },
                },
                capacity_mutations={
                    "member_id": member.get("id"),
                    "capacity_zero_days": duration_days,
                },
            ))
        return outcomes
