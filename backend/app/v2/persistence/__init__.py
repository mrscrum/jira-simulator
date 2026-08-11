"""SQLAlchemy persistence adapters for v2."""

from typing import Any

__all__ = [
    "SemanticDeduplicationConflict",
    "SqlAlchemyV2UnitOfWork",
    "StaleRuntimeVersion",
    "V2ActivityEventModel",
    "V2GroundTruthRecordModel",
    "V2ProjectionIntentModel",
    "V2UnitOfWork",
]

_MODEL_EXPORTS = {
    "V2ActivityEventModel",
    "V2GroundTruthRecordModel",
    "V2ProjectionIntentModel",
}
_UNIT_OF_WORK_EXPORTS = set(__all__) - _MODEL_EXPORTS


def __getattr__(name: str) -> Any:
    if name in _MODEL_EXPORTS:
        return _live_model_export(name)
    if name in _UNIT_OF_WORK_EXPORTS:
        return _unit_of_work_export(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _live_model_export(name: str) -> Any:
    from app.v2.persistence import live_models

    return getattr(live_models, name)


def _unit_of_work_export(name: str) -> Any:
    from app.v2.persistence import unit_of_work

    return getattr(unit_of_work, name)
