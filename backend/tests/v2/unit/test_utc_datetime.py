from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.v2.persistence.team_models import V2TeamModel


def test_utc_datetime_normalizes_and_reloads_as_aware_utc():
    engine = create_engine("sqlite://")
    from app.models import Base

    Base.metadata.create_all(engine)
    original = datetime(2026, 8, 10, 12, tzinfo=timezone(timedelta(hours=-7)))
    with Session(engine) as session:
        session.add(
            V2TeamModel(
                id="id",
                idempotency_key="key",
                blueprint_sha256="hash",
                name="name",
                methodology="SCRUM",
                created_at=original,
            )
        )
        session.commit()
        restored = session.scalar(select(V2TeamModel))

    assert restored is not None
    assert restored.created_at == datetime(2026, 8, 10, 19, tzinfo=UTC)


def test_utc_datetime_rejects_naive_orm_value():
    engine = create_engine("sqlite://")
    from app.models import Base

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            V2TeamModel(
                id="id",
                idempotency_key="key",
                blueprint_sha256="hash",
                name="name",
                methodology="SCRUM",
                created_at=datetime(2026, 8, 10, 19),
            )
        )
        with pytest.raises(StatementError):
            session.commit()
