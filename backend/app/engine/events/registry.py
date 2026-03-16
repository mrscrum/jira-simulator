"""Event handler registry — maps event type strings to handler instances."""

from app.engine.events.base import BaseEvent
from app.engine.events.carry_over import CarryOverEvent
from app.engine.events.descope import DescopeEvent
from app.engine.events.external_block import ExternalBlockEvent
from app.engine.events.late_planning import LatePlanningEvent
from app.engine.events.move_left import MoveLeftEvent
from app.engine.events.onboarding_tax import OnboardingTaxEvent
from app.engine.events.priority_change import PriorityChangeEvent
from app.engine.events.review_bottleneck import ReviewBottleneckEvent
from app.engine.events.scope_commitment_miss import ScopeCommitmentMissEvent
from app.engine.events.skipped_retro import SkippedRetroEvent
from app.engine.events.split_story import SplitStoryEvent
from app.engine.events.sprint_goal_risk import SprintGoalRiskEvent
from app.engine.events.stale_issue import StaleIssueEvent
from app.engine.events.uneven_load import UnevenLoadEvent
from app.engine.events.unplanned_absence import UnplannedAbsenceEvent
from app.engine.events.velocity_drift import VelocityDriftEvent

_REGISTRY: dict[str, BaseEvent] = {
    "carry_over": CarryOverEvent(),
    "velocity_drift": VelocityDriftEvent(),
    "sprint_goal_risk": SprintGoalRiskEvent(),
    "stale_issue": StaleIssueEvent(),
    "move_left": MoveLeftEvent(),
    "descope": DescopeEvent(),
    "unplanned_absence": UnplannedAbsenceEvent(),
    "priority_change": PriorityChangeEvent(),
    "split_story": SplitStoryEvent(),
    "external_block": ExternalBlockEvent(),
    "uneven_load": UnevenLoadEvent(),
    "review_bottleneck": ReviewBottleneckEvent(),
    "onboarding_tax": OnboardingTaxEvent(),
    "late_planning": LatePlanningEvent(),
    "skipped_retro": SkippedRetroEvent(),
    "scope_commitment_miss": ScopeCommitmentMissEvent(),
}


def get_event_handler(event_type: str) -> BaseEvent | None:
    """Look up an event handler by type string."""
    return _REGISTRY.get(event_type)


def get_all_event_types() -> list[str]:
    """Return all registered event type strings."""
    return list(_REGISTRY.keys())


def register_event(event_type: str, handler: BaseEvent) -> None:
    """Register a new event handler."""
    _REGISTRY[event_type] = handler
