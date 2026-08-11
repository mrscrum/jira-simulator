"""Caller-owned-session mapping for detached authoritative Scrum state."""

from dataclasses import fields
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.domain.deterministic_rng import CreationKind, DecisionType
from app.v2.domain.scrum_state import (
    FactorKind,
    MemberAvailabilityOverlay,
    MemberBusinessDateConsumption,
    MemberIdentity,
    NaturalDecisionEvaluation,
    ScrumStateQuery,
    ScrumStateSnapshot,
    ScrumStateWriteSet,
    SemanticCounter,
    SemanticCounterKind,
    SemanticCounterScope,
    SprintLifecycle,
    SprintScopeEntry,
    SprintState,
    StatusVisitLifecycle,
    StatusVisitSample,
    StatusVisitState,
    WorkItemFactor,
    WorkItemLifecycle,
    WorkItemState,
    WorkPriority,
)
from app.v2.persistence.scrum_state_models import (
    V2MemberAvailabilityOverlayModel,
    V2MemberBusinessDateConsumptionModel,
    V2MemberIdentityModel,
    V2NaturalDecisionEvaluationModel,
    V2SemanticCounterModel,
    V2SprintModel,
    V2SprintScopeModel,
    V2StatusVisitModel,
    V2StatusVisitSampleModel,
    V2WorkItemFactorModel,
    V2WorkItemModel,
)

ENUM_FIELDS = {
    "creation_kind": CreationKind,
    "decision_type": DecisionType,
    "kind": FactorKind,
    "lifecycle": WorkItemLifecycle,
    "priority": WorkPriority,
}
LOAD_SPECS = (
    (V2MemberIdentityModel, MemberIdentity, ("blueprint_index", "id")),
    (V2MemberAvailabilityOverlayModel, MemberAvailabilityOverlay, ("starts_at", "id")),
    (
        V2MemberBusinessDateConsumptionModel,
        MemberBusinessDateConsumption,
        ("business_date", "member_id"),
    ),
    (V2WorkItemModel, WorkItemState, ("creation_kind", "creation_sequence", "id")),
    (V2WorkItemFactorModel, WorkItemFactor, ("work_item_id", "kind", "id")),
    (V2SprintModel, SprintState, ("ordinal", "id")),
    (V2SprintScopeModel, SprintScopeEntry, ("sprint_id", "work_item_id", "id")),
    (V2StatusVisitModel, StatusVisitState, ("work_item_id", "ordinal", "id")),
    (V2StatusVisitSampleModel, StatusVisitSample, ("visit_id",)),
    (V2SemanticCounterModel, SemanticCounter, ("kind", "scope_id", "scope_key")),
    (
        V2NaturalDecisionEvaluationModel,
        NaturalDecisionEvaluation,
        ("decision_type", "semantic_entity_id", "business_date", "id"),
    ),
)


class SqlAlchemyScrumStateMapper:
    """Maps authoritative state without owning a session or transaction."""

    def add(self, session: Session, state: ScrumStateWriteSet) -> ScrumStateSnapshot:
        if not isinstance(session, Session):
            raise TypeError("session must be a caller-owned Session")
        if not isinstance(state, ScrumStateWriteSet):
            raise TypeError("state must be a ScrumStateWriteSet")
        state.validate()
        for spec, items in zip(LOAD_SPECS, state._collection_values(), strict=True):
            _add_collection(session, items, spec[0])
            session.flush()
        return _ordered_snapshot(state)

    def load(self, session: Session, query: ScrumStateQuery) -> ScrumStateSnapshot:
        if not isinstance(session, Session):
            raise TypeError("session must be a caller-owned Session")
        if not isinstance(query, ScrumStateQuery):
            raise TypeError("query must be a ScrumStateQuery")
        collections = tuple(_load_collection(session, query, spec) for spec in LOAD_SPECS)
        return ScrumStateSnapshot(*collections)


def _add_collection(session: Session, items: tuple[object, ...], model_type: type) -> None:
    models = [model_type(**_record_values(item)) for item in items]
    session.add_all(models)


def _ordered_snapshot(state: ScrumStateWriteSet) -> ScrumStateSnapshot:
    collections = tuple(
        tuple(sorted(items, key=lambda item: _semantic_order(item, spec[2])))
        for spec, items in zip(LOAD_SPECS, state._collection_values(), strict=True)
    )
    return ScrumStateSnapshot(*collections)


def _semantic_order(record: object, names: tuple[str, ...]) -> tuple[object, ...]:
    if isinstance(record, SemanticCounter):
        scope = record.scope
        return scope.kind.value, str(scope.scope_id), scope.scope_key
    return tuple(_sortable(getattr(record, name)) for name in names)


def _sortable(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _record_values(record: object) -> dict[str, object]:
    if isinstance(record, SemanticCounter):
        return {
            "team_id": str(record.team_id),
            "run_id": str(record.run_id),
            "kind": record.scope.kind.value,
            "scope_id": str(record.scope.scope_id),
            "scope_key": record.scope.scope_key,
            "next_value": record.next_value,
        }
    return {field.name: _stored_value(getattr(record, field.name)) for field in fields(record)}


def _stored_value(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _load_collection(session: Session, query: ScrumStateQuery, spec: tuple) -> tuple:
    model_type, value_type, order_names = spec
    statement = select(model_type).where(model_type.team_id == str(query.team_id))
    if hasattr(model_type, "run_id"):
        statement = statement.where(model_type.run_id == str(query.run_id))
    order_columns = tuple(getattr(model_type, name) for name in order_names)
    models = session.scalars(statement.order_by(*order_columns)).all()
    return tuple(_domain_record(model, value_type) for model in models)


def _domain_record(model: object, value_type: type) -> object:
    if value_type is SemanticCounter:
        scope = SemanticCounterScope(
            SemanticCounterKind(model.kind), UUID(model.scope_id), model.scope_key
        )
        return SemanticCounter(UUID(model.team_id), UUID(model.run_id), scope, model.next_value)
    values = {
        field.name: _domain_value(field.name, getattr(model, field.name), value_type)
        for field in fields(value_type)
    }
    return value_type(**values)


def _domain_value(field_name: str, value: object, value_type: type) -> object:
    if value is None:
        return None
    enum_type = _enum_type(field_name, value_type)
    if enum_type is not None:
        return enum_type(value)
    if field_name == "story_points":
        return value
    if field_name.endswith("_id") or field_name == "id":
        return UUID(value)
    return value


def _enum_type(field_name: str, value_type: type) -> type[StrEnum] | None:
    if field_name != "lifecycle":
        return ENUM_FIELDS.get(field_name)
    lifecycle_types = (
        (WorkItemState, WorkItemLifecycle),
        (SprintState, SprintLifecycle),
        (StatusVisitState, StatusVisitLifecycle),
    )
    return next(
        (enum_type for domain_type, enum_type in lifecycle_types if value_type is domain_type), None
    )
