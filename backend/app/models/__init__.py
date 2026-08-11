import importlib
import sys

from app.models.base import Base
from app.models.cross_team_dependency import CrossTeamDependency
from app.models.daily_capacity_log import DailyCapacityLog
from app.models.dysfunction_config import DysfunctionConfig
from app.models.event_audit_log import EventAuditLog
from app.models.issue import Issue
from app.models.jira_config import JiraConfig
from app.models.jira_issue_link import JiraIssueLink
from app.models.jira_issue_map import JiraIssueMap
from app.models.jira_write_queue_entry import JiraWriteQueueEntry
from app.models.member import Member
from app.models.move_left_config import (
    MoveLeftConfig,
    MoveLeftSameStepStatus,
    MoveLeftTarget,
)
from app.models.organization import Organization
from app.models.precomputation_run import PrecomputationRun
from app.models.scheduled_event import ScheduledEvent
from app.models.simulation_event_config import SimulationEventConfig
from app.models.simulation_event_log import SimulationEventLog
from app.models.sprint import Sprint
from app.models.team import Team
from app.models.timing_template import TimingTemplate, TimingTemplateEntry
from app.models.touch_time_config import TouchTimeConfig
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep

_V2_LIVE_MODULE = "app.v2.persistence.live_models"
_V2_TEAM_MODULE = "app.v2.persistence.team_models"
_V2_SCRUM_MODULE = "app.v2.persistence.scrum_state_models"
_V2_LIVE_MODELS = {
    "V2ActivityEventModel",
    "V2GroundTruthRecordModel",
    "V2ProjectionIntentModel",
}
_V2_TEAM_MODELS = {
    "V2RunModel",
    "V2TeamBlueprintModel",
    "V2TeamModel",
    "V2TeamRuntimeModel",
}
_V2_SCRUM_MODELS = {
    "V2MemberAvailabilityOverlayModel",
    "V2MemberBusinessDateConsumptionModel",
    "V2MemberIdentityModel",
    "V2NaturalDecisionEvaluationModel",
    "V2SemanticCounterModel",
    "V2SprintModel",
    "V2SprintScopeModel",
    "V2StatusVisitModel",
    "V2StatusVisitSampleModel",
    "V2WorkItemFactorModel",
    "V2WorkItemModel",
}

for _v2_module in (_V2_TEAM_MODULE, _V2_LIVE_MODULE, _V2_SCRUM_MODULE):
    if _v2_module not in sys.modules:
        importlib.import_module(_v2_module)

__all__ = [
    "Base",
    "CrossTeamDependency",
    "DailyCapacityLog",
    "DysfunctionConfig",
    "EventAuditLog",
    "Issue",
    "JiraConfig",
    "JiraIssueLink",
    "JiraIssueMap",
    "JiraWriteQueueEntry",
    "Member",
    "MoveLeftConfig",
    "MoveLeftSameStepStatus",
    "MoveLeftTarget",
    "Organization",
    "PrecomputationRun",
    "ScheduledEvent",
    "SimulationEventConfig",
    "SimulationEventLog",
    "Sprint",
    "Team",
    "TimingTemplate",
    "TimingTemplateEntry",
    "TouchTimeConfig",
    "V2ActivityEventModel",
    "V2GroundTruthRecordModel",
    "V2ProjectionIntentModel",
    "V2RunModel",
    "V2TeamBlueprintModel",
    "V2TeamModel",
    "V2TeamRuntimeModel",
    "V2MemberAvailabilityOverlayModel",
    "V2MemberBusinessDateConsumptionModel",
    "V2MemberIdentityModel",
    "V2NaturalDecisionEvaluationModel",
    "V2SemanticCounterModel",
    "V2SprintModel",
    "V2SprintScopeModel",
    "V2StatusVisitModel",
    "V2StatusVisitSampleModel",
    "V2WorkItemFactorModel",
    "V2WorkItemModel",
    "Workflow",
    "WorkflowStep",
]


def __getattr__(name: str) -> object:
    if name in _V2_LIVE_MODELS:
        from app.v2.persistence import live_models

        return getattr(live_models, name)
    if name in _V2_TEAM_MODELS:
        from app.v2.persistence import team_models

        return getattr(team_models, name)
    if name in _V2_SCRUM_MODELS:
        from app.v2.persistence import scrum_state_models

        return getattr(scrum_state_models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
