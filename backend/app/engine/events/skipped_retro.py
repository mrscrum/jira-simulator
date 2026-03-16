"""Skipped retrospective event — retro phase skipped entirely."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext


class SkippedRetroEvent(BaseEvent):
    event_type = "skipped_retro"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        probability = kwargs.get("probability", 0.20)
        rng = kwargs.get("rng", random)
        if rng.random() > probability:
            return []

        return [EventOutcome(
            log_entry={
                "team_id": context.team_id,
                "sprint_id": context.sprint["id"],
                "event_type": self.event_type,
                "sim_day": context.sim_day,
                "payload": {"skipped": True},
            },
            issue_mutations={"skip_retro": True},
        )]
