"""Onboarding tax event — new member capacity reduced during ramp-up."""

from app.engine.events.base import BaseEvent, EventOutcome, TickContext
from app.engine.issue_state_machine import JiraWriteAction

DEFAULT_RAMP_DAYS = 5
EARLY_RAMP_FACTOR = 0.5
LATE_RAMP_FACTOR = 0.75
EARLY_RAMP_CUTOFF = 3


class OnboardingTaxEvent(BaseEvent):
    event_type = "onboarding_tax"

    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        new_members = kwargs.get("new_members", [])
        outcomes = []
        for member in new_members:
            days_on_team = member.get("days_on_team", 0)
            if days_on_team > DEFAULT_RAMP_DAYS:
                continue
            if days_on_team <= EARLY_RAMP_CUTOFF:
                factor = EARLY_RAMP_FACTOR
            else:
                factor = LATE_RAMP_FACTOR

            actions = []
            if days_on_team == 1:
                actions.append(JiraWriteAction(
                    operation_type="ADD_COMMENT",
                    payload={
                        "issue_key": "",
                        "body": (
                            f"[{member.get('name', 'New Member')}]"
                            " Getting up to speed — may take"
                            " slightly longer on first few items."
                        ),
                    },
                ))
            outcomes.append(EventOutcome(
                jira_actions=actions,
                log_entry={
                    "team_id": context.team_id,
                    "sprint_id": context.sprint["id"],
                    "event_type": self.event_type,
                    "sim_day": context.sim_day,
                    "payload": {
                        "member_id": member.get("id"),
                        "days_on_team": days_on_team,
                        "capacity_factor": factor,
                    },
                },
                capacity_mutations={
                    "member_id": member.get("id"),
                    "capacity_factor": factor,
                },
            ))
        return outcomes
