"""Base event interface and shared types for the simulation event system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from app.engine.issue_state_machine import JiraWriteAction


@dataclass(frozen=True)
class TickContext:
    team_id: int
    sprint: dict
    issues: list[dict]
    members: list[dict]
    capacity_states: dict
    sim_day: int
    now: datetime


@dataclass
class EventOutcome:
    jira_actions: list[JiraWriteAction] = field(default_factory=list)
    log_entry: dict = field(default_factory=dict)
    issue_mutations: dict = field(default_factory=dict)
    capacity_mutations: dict = field(default_factory=dict)


class BaseEvent(ABC):
    event_type: str = ""

    @abstractmethod
    def evaluate(self, context: TickContext, **kwargs) -> list[EventOutcome]:
        """Evaluate the event against current tick context.

        Returns a list of outcomes to apply.
        """
