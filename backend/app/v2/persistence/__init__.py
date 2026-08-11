"""SQLAlchemy persistence adapters for v2."""

from typing import Any

__all__ = [
    "NaturalEligibilityConflict",
    "SemanticDeduplicationConflict",
    "SqlAlchemyV2UnitOfWork",
    "StaleRuntimeVersion",
    "StaleSemanticCounter",
    "SqlAlchemyScrumStateMapper",
    "V2ActivityEventModel",
    "V2GroundTruthRecordModel",
    "V2ProjectionIntentModel",
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
    "V2UnitOfWork",
]

_MODEL_EXPORTS = {
    "V2ActivityEventModel",
    "V2GroundTruthRecordModel",
    "V2ProjectionIntentModel",
}
_SCRUM_MODEL_EXPORTS = {
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
_SCRUM_MAPPER_EXPORTS = {"SqlAlchemyScrumStateMapper"}
_UNIT_OF_WORK_EXPORTS = set(__all__) - (
    _MODEL_EXPORTS | _SCRUM_MODEL_EXPORTS | _SCRUM_MAPPER_EXPORTS
)


def __getattr__(name: str) -> Any:
    if name in _MODEL_EXPORTS:
        return _live_model_export(name)
    if name in _SCRUM_MODEL_EXPORTS:
        return _scrum_model_export(name)
    if name in _SCRUM_MAPPER_EXPORTS:
        return _scrum_mapper_export(name)
    if name in _UNIT_OF_WORK_EXPORTS:
        return _unit_of_work_export(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _live_model_export(name: str) -> Any:
    from app.v2.persistence import live_models

    return getattr(live_models, name)


def _unit_of_work_export(name: str) -> Any:
    from app.v2.persistence import unit_of_work

    return getattr(unit_of_work, name)


def _scrum_model_export(name: str) -> Any:
    from app.v2.persistence import scrum_state_models

    return getattr(scrum_state_models, name)


def _scrum_mapper_export(name: str) -> Any:
    from app.v2.persistence import scrum_state_mapper

    return getattr(scrum_state_mapper, name)
