"""Split story event — large story split into two smaller ones."""

import random

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

MIN_POINTS_TO_SPLIT = 5


class SplitStoryEvent(BaseEvent):
    event_type = "split_story"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        probability = kwargs.get("probability", 0.10)
        rng = kwargs.get("rng", random)
        outcomes = []
        for issue in context.issues:
            if issue.get("status") != "IN_PROGRESS":
                continue
            points = issue.get("story_points", 0) or 0
            if points < MIN_POINTS_TO_SPLIT:
                continue
            if rng.random() > probability:
                continue
            half = points // 2
            remainder = points - half
            comment = JiraWriteAction(
                operation_type="ADD_COMMENT",
                payload={
                    "issue_key": issue.get("issue_key", ""),
                    "body": (
                        f"[SM] Story split into two parts"
                        f" ({half}pts + {remainder}pts)."
                        " Original descoped."
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
                    "payload": {
                        "original_points": points,
                        "split_a_points": half,
                        "split_b_points": remainder,
                    },
                },
                issue_mutations={
                    "issue_id": issue["id"],
                    "split": True,
                    "split_a_points": half,
                    "split_b_points": remainder,
                },
            ))
        return outcomes
