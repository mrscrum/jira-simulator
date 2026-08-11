"""Persisted discovery of runnable v2 team runtimes."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.v2.persistence.team_models import V2TeamRuntimeModel


class DueTeamStore(Protocol):
    def due_team_ids(self, as_of: datetime, limit: int = 100) -> tuple[UUID, ...]: ...

    def running_team_ids(self) -> tuple[UUID, ...]: ...


class SqlAlchemyDueTeamStore:
    """Queries persisted runtime ownership without maintaining an in-memory clock."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def due_team_ids(self, as_of: datetime, limit: int = 100) -> tuple[UUID, ...]:
        instant = _utc(as_of)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = (
            select(V2TeamRuntimeModel.team_id)
            .where(V2TeamRuntimeModel.state == "RUNNING")
            .where(V2TeamRuntimeModel.next_wake_at.is_not(None))
            .where(V2TeamRuntimeModel.next_wake_at <= instant)
            .order_by(V2TeamRuntimeModel.team_id)
            .limit(limit)
        )
        with self._session_factory() as session:
            return tuple(UUID(value) for value in session.scalars(statement))

    def running_team_ids(self) -> tuple[UUID, ...]:
        statement = (
            select(V2TeamRuntimeModel.team_id)
            .where(V2TeamRuntimeModel.state == "RUNNING")
            .order_by(V2TeamRuntimeModel.team_id)
        )
        with self._session_factory() as session:
            return tuple(UUID(value) for value in session.scalars(statement))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be aware")
    return value.astimezone(UTC)
