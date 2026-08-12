"""Short-transaction persistence for v2 Jira delivery."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.v2.domain.jira_delivery import (
    JiraDeliveryFailure,
    JiraDeliverySuccess,
    JiraResourceMapping,
    PendingJiraIntent,
)
from app.v2.domain.live_slice import ProjectionIntent
from app.v2.persistence.jira_delivery_models import (
    V2JiraDeliveryReceiptModel,
    V2JiraResourceMappingModel,
)
from app.v2.persistence.live_models import V2ProjectionIntentModel

DELIVERED = "DELIVERED"
RETRYABLE = "RETRYABLE"
MAX_PENDING_LIMIT = 50


class SqlAlchemyJiraDeliveryStore:
    """Open and close one database session around each delivery state operation."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def pending(
        self, as_of: datetime, limit: int = MAX_PENDING_LIMIT
    ) -> tuple[PendingJiraIntent, ...]:
        instant = _utc(as_of)
        invalid_limit = isinstance(limit, bool) or not isinstance(limit, int)
        if invalid_limit or not 1 <= limit <= MAX_PENDING_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_PENDING_LIMIT}")
        with self._session_factory() as session:
            candidates = _first_outstanding_by_team(session)
            ready = [
                (intent, receipt)
                for intent, receipt in candidates
                if _due(receipt, instant) and _dependencies_delivered(session, intent)
            ]
            return tuple(_pending_intent(intent, receipt) for intent, receipt in ready[:limit])

    def record_success(self, result: JiraDeliverySuccess) -> None:
        with self._session_factory() as session:
            try:
                _require_intent(session, result.intent_id)
                for mapping in result.mappings:
                    _ensure_mapping(session, mapping)
                receipt = session.get(V2JiraDeliveryReceiptModel, str(result.intent_id))
                if receipt is None:
                    session.add(_delivered_receipt(result))
                elif receipt.state != DELIVERED:
                    receipt.state = DELIVERED
                    receipt.attempts += 1
                    receipt.next_attempt_at = None
                    receipt.last_attempt_at = result.delivered_at
                    receipt.delivered_at = result.delivered_at
                    receipt.last_error = None
                session.commit()
            except Exception:
                session.rollback()
                raise

    def record_failure(self, result: JiraDeliveryFailure) -> None:
        with self._session_factory() as session:
            try:
                _require_intent(session, result.intent_id)
                receipt = session.get(V2JiraDeliveryReceiptModel, str(result.intent_id))
                if receipt is not None and receipt.state == DELIVERED:
                    return
                if receipt is None:
                    session.add(_retryable_receipt(result))
                else:
                    receipt.attempts += 1
                    receipt.next_attempt_at = result.retry_at
                    receipt.last_attempt_at = result.failed_at
                    receipt.last_error = result.error
                session.commit()
            except Exception:
                session.rollback()
                raise

    def find_mapping(
        self, team_id: UUID, internal_kind: str, internal_id: UUID
    ) -> JiraResourceMapping | None:
        with self._session_factory() as session:
            model = session.get(
                V2JiraResourceMappingModel,
                (str(team_id), internal_kind, str(internal_id)),
            )
            return None if model is None else _mapping(model)


def _first_outstanding_by_team(
    session: Session,
) -> list[tuple[V2ProjectionIntentModel, V2JiraDeliveryReceiptModel | None]]:
    statement = (
        select(V2ProjectionIntentModel, V2JiraDeliveryReceiptModel)
        .outerjoin(
            V2JiraDeliveryReceiptModel,
            V2JiraDeliveryReceiptModel.intent_id == V2ProjectionIntentModel.id,
        )
        .where(
            (V2JiraDeliveryReceiptModel.intent_id.is_(None))
            | (V2JiraDeliveryReceiptModel.state != DELIVERED)
        )
        .order_by(V2ProjectionIntentModel.append_sequence)
    )
    rows = session.execute(statement).all()
    first_by_team: dict[str, tuple[V2ProjectionIntentModel, V2JiraDeliveryReceiptModel | None]] = {}
    for intent, receipt in rows:
        first_by_team.setdefault(intent.team_id, (intent, receipt))
    return list(first_by_team.values())


def _due(receipt: V2JiraDeliveryReceiptModel | None, as_of: datetime) -> bool:
    return receipt is None or (
        receipt.state == RETRYABLE
        and receipt.next_attempt_at is not None
        and receipt.next_attempt_at <= as_of
    )


def _dependencies_delivered(session: Session, intent: V2ProjectionIntentModel) -> bool:
    dependencies = _dependency_keys(intent.canonical_payload)
    if not dependencies:
        return True
    delivered = set(
        session.scalars(
            select(V2ProjectionIntentModel.semantic_key)
            .join(
                V2JiraDeliveryReceiptModel,
                V2JiraDeliveryReceiptModel.intent_id == V2ProjectionIntentModel.id,
            )
            .where(V2ProjectionIntentModel.semantic_key.in_(dependencies))
            .where(V2JiraDeliveryReceiptModel.state == DELIVERED)
        )
    )
    return delivered == set(dependencies)


def _dependency_keys(canonical_payload: str) -> tuple[str, ...]:
    document = json.loads(canonical_payload)
    values = document.get("depends_on", [])
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError("depends_on must be a list of semantic-key strings")
    return tuple(values)


def _pending_intent(
    model: V2ProjectionIntentModel,
    receipt: V2JiraDeliveryReceiptModel | None,
) -> PendingJiraIntent:
    return PendingJiraIntent(
        _projection(model),
        _dependency_keys(model.canonical_payload),
        0 if receipt is None else receipt.attempts,
    )


def _projection(model: V2ProjectionIntentModel) -> ProjectionIntent:
    return ProjectionIntent(
        id=UUID(model.id),
        semantic_key=model.semantic_key,
        schema_version=model.schema_version,
        occurred_at=model.occurred_at,
        canonical_payload=model.canonical_payload,
        payload_sha256=model.payload_sha256,
        target_kind=model.target_kind,
        operation_type=model.operation_type,
        aggregate_id=UUID(model.aggregate_id),
        aggregate_version=model.aggregate_version,
        status=model.status,
        append_sequence=model.append_sequence,
        team_id=UUID(model.team_id),
        run_id=UUID(model.run_id),
        commit_id=UUID(model.commit_id),
        transaction_sequence=model.transaction_sequence,
        recorded_at=model.recorded_at,
    )


def _ensure_mapping(session: Session, value: JiraResourceMapping) -> None:
    identity = (str(value.team_id), value.internal_kind, str(value.internal_id))
    existing = session.get(V2JiraResourceMappingModel, identity)
    if existing is None:
        session.add(
            V2JiraResourceMappingModel(
                team_id=identity[0],
                internal_kind=value.internal_kind,
                internal_id=identity[2],
                jira_id=value.jira_id,
                jira_key=value.jira_key,
            )
        )
        return
    if (existing.jira_id, existing.jira_key) != (value.jira_id, value.jira_key):
        raise ValueError("resource mapping conflicts with its persisted Jira identity")


def _mapping(model: V2JiraResourceMappingModel) -> JiraResourceMapping:
    return JiraResourceMapping(
        UUID(model.team_id),
        model.internal_kind,
        UUID(model.internal_id),
        model.jira_id,
        model.jira_key,
    )


def _delivered_receipt(result: JiraDeliverySuccess) -> V2JiraDeliveryReceiptModel:
    return V2JiraDeliveryReceiptModel(
        intent_id=str(result.intent_id),
        state=DELIVERED,
        attempts=1,
        next_attempt_at=None,
        last_attempt_at=result.delivered_at,
        delivered_at=result.delivered_at,
        last_error=None,
    )


def _retryable_receipt(result: JiraDeliveryFailure) -> V2JiraDeliveryReceiptModel:
    return V2JiraDeliveryReceiptModel(
        intent_id=str(result.intent_id),
        state=RETRYABLE,
        attempts=1,
        next_attempt_at=result.retry_at,
        last_attempt_at=result.failed_at,
        delivered_at=None,
        last_error=result.error,
    )


def _require_intent(session: Session, intent_id: UUID) -> None:
    exists = session.scalar(
        select(V2ProjectionIntentModel.id).where(V2ProjectionIntentModel.id == str(intent_id))
    )
    if exists is None:
        raise LookupError(f"projection intent not found: {intent_id}")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be an aware datetime")
    return value.astimezone(UTC)
