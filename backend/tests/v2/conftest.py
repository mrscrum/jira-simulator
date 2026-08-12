import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def resolved_blueprint_json() -> str:
    fixture_path = Path(__file__).parent / "fixtures" / "resolved_scrum_blueprint.json"
    return fixture_path.read_text(encoding="utf-8").strip()


@pytest.fixture
def requested_at() -> datetime:
    return datetime(2026, 8, 10, 18, 30, tzinfo=UTC)


@pytest.fixture
def blueprint_document(resolved_blueprint_json: str) -> dict[str, object]:
    return json.loads(resolved_blueprint_json)


@pytest.fixture
def v2_session_factory(tmp_path):
    from app.models import Base

    database_path = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{database_path}")
    event.listen(engine, "connect", _enable_foreign_keys)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()


def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
