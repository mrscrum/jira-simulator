"""Review bottleneck event — single reviewer with too many queued items."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

QUEUE_THRESHOLD = 3
TOUCH_TIME_MULTIPLIER = 1.2


class ReviewBottleneckEvent(BaseEvent):
    event_type = "review_bottleneck"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        review_queue_size = kwargs.get("review_queue_size", 0)
        reviewer_name = kwargs.get("reviewer_name", "Reviewer")
        if review_queue_size < QUEUE_THRESHOLD:
            return []

        comment = JiraWriteAction(
            operation_type="ADD_COMMENT",
            payload={
                "issue_key": "",
                "body": (
                    f"[{reviewer_name}] Working through review queue"
                    f" — {review_queue_size} items ahead."
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
                    "queue_size": review_queue_size,
                    "multiplier": TOUCH_TIME_MULTIPLIER,
                },
            },
            capacity_mutations={
                "touch_time_multiplier": TOUCH_TIME_MULTIPLIER,
            },
        )]
