import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.models import Base
from app.v2.domain.canonical_json import canonical_sha256
from tests.v2.integration.test_migration_013 import (
    _alembic_config,
    _seed_every_legacy_table,
)
from tests.v2.scrum_state_support import ITEM_ID, MEMBER_ID, MEMBER_INDEX, NOW, RUN_ID, TEAM_ID

TASK5_TABLES = {
    "v2_member_identities",
    "v2_member_availability_overlays",
    "v2_member_business_date_consumption",
    "v2_work_items",
    "v2_work_item_factors",
    "v2_sprints",
    "v2_sprint_scope",
    "v2_status_visits",
    "v2_status_visit_samples",
    "v2_semantic_counters",
    "v2_natural_decision_evaluations",
}


def test_migration_graph_loads_with_one_linear_015_head():
    backend_root = Path(__file__).parents[3]
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "heads"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "015 (head)"


def test_revision_015_matches_every_task5_orm_schema_detail(tmp_path):
    orm_engine = _foreign_key_engine(f"sqlite:///{tmp_path / 'orm-015.db'}")
    migrated_path = tmp_path / "migrated-015.db"
    Base.metadata.create_all(orm_engine)
    config = _alembic_config(Path(__file__).parents[3], migrated_path)
    command.upgrade(config, "015")
    migrated_engine = _foreign_key_engine(f"sqlite:///{migrated_path}")

    orm_inspector = inspect(orm_engine)
    migrated_inspector = inspect(migrated_engine)
    for table_name in TASK5_TABLES:
        assert _metadata(orm_inspector, table_name) == _metadata(migrated_inspector, table_name)

    orm_engine.dispose()
    migrated_engine.dispose()


def test_migrated_015_rejects_missing_typed_counter_and_evaluation_owners(tmp_path):
    database_path = tmp_path / "migrated-owner-fks.db"
    config = _alembic_config(Path(__file__).parents[3], database_path)
    command.upgrade(config, "015")
    engine = _foreign_key_engine(f"sqlite:///{database_path}")
    _seed_migrated_owner_parents(engine)
    for statement, values in _invalid_owner_inserts():
        with engine.begin() as connection, pytest.raises(IntegrityError):
            assert connection.scalar(sa.text("PRAGMA foreign_keys")) == 1
            connection.execute(sa.text(statement), values)
    engine.dispose()


def test_populated_014_round_trip_preserves_every_prior_row_and_schema(tmp_path):
    database_path = tmp_path / "migration-015.db"
    backend_root = Path(__file__).parents[3]
    config = _alembic_config(backend_root, database_path)
    command.upgrade(config, "012")
    engine = _foreign_key_engine(f"sqlite:///{database_path}")
    _seed_every_legacy_table(engine)
    command.upgrade(config, "014")
    _seed_task_one_and_two(engine)
    expected = _snapshot_revision_014(engine)

    command.upgrade(config, "015")
    _assert_prior_schema_plus_run_ownership(engine, expected)
    _assert_task5_schema(engine)
    _seed_one_task5_row(engine)
    command.downgrade(config, "014")

    assert _snapshot_revision_014(engine) == expected
    assert TASK5_TABLES.isdisjoint(inspect(engine).get_table_names())
    _assert_revision(engine, "014")
    command.upgrade(config, "015")

    _assert_prior_schema_plus_run_ownership(engine, expected)
    assert _task5_counts(engine) == {name: 0 for name in TASK5_TABLES}
    _assert_revision(engine, "015")
    engine.dispose()


def _seed_task_one_and_two(engine) -> None:
    timestamp = NOW.isoformat()
    payload_hash = canonical_sha256({})
    with engine.begin() as connection:
        _seed_team_and_blueprint(connection, timestamp, payload_hash)
        _seed_run_and_runtime(connection, timestamp)
        _seed_ledgers(connection, timestamp, payload_hash)


def _seed_migrated_owner_parents(engine) -> None:
    timestamp = NOW.isoformat()
    with engine.begin() as connection:
        _seed_team_and_blueprint(connection, timestamp, canonical_sha256({}))
        connection.execute(
            sa.text("INSERT INTO v2_runs VALUES (:run,:team,0,'ACTIVE',:at)"),
            {"run": str(RUN_ID), "team": str(TEAM_ID), "at": timestamp},
        )
        connection.execute(
            sa.text("INSERT INTO v2_member_identities VALUES (:member,:team,:position)"),
            {"member": str(MEMBER_ID), "team": str(TEAM_ID), "position": MEMBER_INDEX},
        )
        _seed_migrated_work_item(connection, timestamp)


def _seed_migrated_work_item(connection, timestamp: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO v2_work_items VALUES "
            "(:item,:team,:run,'INITIAL_BACKLOG',0,'STORY',3,'HIGH',0,'ACTIVE',"
            "'DEVELOPMENT',:at,:at)"
        ),
        {"item": str(ITEM_ID), "team": str(TEAM_ID), "run": str(RUN_ID), "at": timestamp},
    )


def _invalid_owner_inserts() -> tuple[tuple[str, dict[str, object]], ...]:
    missing = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    counter = (
        "INSERT INTO v2_semantic_counters "
        "(team_id,run_id,kind,scope_id,scope_key,work_item_id,member_id,next_value) "
        "VALUES (:team,:run,:kind,:owner,:key,:work,:member,0)"
    )
    evaluation = (
        "INSERT INTO v2_natural_decision_evaluations "
        "(id,team_id,run_id,decision_type,semantic_entity_id,work_item_id,member_id,"
        "business_date,occurrence,commit_id,recorded_at) VALUES "
        "(:id,:team,:run,:decision,:owner,:work,:member,'2026-08-10',0,:commit,:at)"
    )
    common = {"team": str(TEAM_ID), "run": str(RUN_ID), "owner": missing}
    return _invalid_counter_rows(counter, common) + _invalid_evaluation_rows(evaluation, common)


def _invalid_counter_rows(statement: str, common: dict[str, object]):
    return (
        (statement, _counter_parameters(common, ("VISIT_ORDINAL", "VISIT"), "work")),
        (
            statement,
            _counter_parameters(
                common,
                ("NATURAL_DECISION_OCCURRENCE", "RISK_CANCELLATION_OUTCOME"),
                "work",
            ),
        ),
        (
            statement,
            _counter_parameters(
                common,
                ("NATURAL_DECISION_OCCURRENCE", "RISK_MEMBER_UNAVAILABLE_OUTCOME"),
                "member",
            ),
        ),
    )


def _counter_parameters(
    common: dict[str, object], coordinate: tuple[str, str], owner_field: str
) -> dict[str, object]:
    kind, key = coordinate
    parameters = {**common, "kind": kind, "key": key, "work": None, "member": None}
    parameters[owner_field] = common["owner"]
    return parameters


def _invalid_evaluation_rows(statement: str, common: dict[str, object]):
    base = {
        **common,
        "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "commit": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "at": NOW.isoformat(),
    }
    return (
        (
            statement,
            _evaluation_parameters(base, "RISK_CANCELLATION_OUTCOME", "work"),
        ),
        (
            statement,
            _evaluation_parameters(base, "RISK_MEMBER_UNAVAILABLE_OUTCOME", "member"),
        ),
    )


def _evaluation_parameters(
    base: dict[str, object], decision: str, owner_field: str
) -> dict[str, object]:
    parameters = {**base, "decision": decision, "work": None, "member": None}
    parameters[owner_field] = base["owner"]
    if owner_field == "member":
        parameters["id"] = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    return parameters


def _foreign_key_engine(database_url: str):
    engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _seed_team_and_blueprint(connection, timestamp: str, payload_hash: str) -> None:
    connection.execute(
        sa.text("INSERT INTO v2_teams VALUES (:id,:key,:sha,:name,:method,:at)"),
        {
            "id": str(TEAM_ID),
            "key": "migration-015",
            "sha": "1" * 64,
            "name": "Migrated",
            "method": "SCRUM",
            "at": timestamp,
        },
    )
    connection.execute(
        sa.text("INSERT INTO v2_team_blueprints VALUES (:id,:team,:version,:json,:sha,:at)"),
        {
            "id": "2f5c6cf1-7550-5521-8878-f3e34e8ece29",
            "team": str(TEAM_ID),
            "version": "1.0",
            "json": "{}",
            "sha": payload_hash,
            "at": timestamp,
        },
    )


def _seed_run_and_runtime(connection, timestamp: str) -> None:
    connection.execute(
        sa.text("INSERT INTO v2_runs VALUES (:id,:team,0,'ACTIVE',:at)"),
        {"id": str(RUN_ID), "team": str(TEAM_ID), "at": timestamp},
    )
    connection.execute(
        sa.text("INSERT INTO v2_team_runtimes VALUES (:id,:team,:run,'ACTIVE',:at,NULL,:at,:at,7)"),
        {
            "id": "145626d9-b54f-5fe8-9c9d-98482c387d90",
            "team": str(TEAM_ID),
            "run": str(RUN_ID),
            "at": timestamp,
        },
    )


def _seed_ledgers(connection, timestamp: str, payload_hash: str) -> None:
    common = {
        "id": "223c11d6-4135-5359-a13d-6fdb6553e791",
        "key": "migration/015",
        "team": str(TEAM_ID),
        "run": str(RUN_ID),
        "commit": "2fb8f389-67a8-5157-bb59-c7ea01e3070d",
        "at": timestamp,
        "payload": "{}",
        "sha": payload_hash,
    }
    _seed_activity(connection, common)
    _seed_ground_truth(connection, common)
    _seed_projection(connection, common)


def _seed_activity(connection, common: dict[str, object]) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO v2_activity_events VALUES "
            "(1,:id,:key,:team,:run,:commit,0,'1.0',:at,:at,:payload,:sha,"
            "'CREATED','ITEM',:team,0)"
        ),
        common,
    )


def _seed_ground_truth(connection, common: dict[str, object]) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO v2_ground_truth_records VALUES "
            "(1,:id,:key,:team,:run,:commit,0,'1.0',:at,:at,:payload,:sha,"
            "'STATE','SIMULATOR')"
        ),
        {**common, "id": "fcfcd73d-d21a-598e-a2d5-bba94dfb2cf4", "key": "migration/015/truth"},
    )


def _seed_projection(connection, common: dict[str, object]) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO v2_projection_intents VALUES "
            "(1,:id,:key,:team,:run,:commit,0,'1.0',:at,:at,:payload,:sha,"
            "'JIRA','UPSERT',:aggregate,0,'PENDING')"
        ),
        {
            **common,
            "id": "b250bf74-665d-52ed-95d4-bb37ff96812f",
            "key": "migration/015/projection",
            "aggregate": common["id"],
        },
    )


def _snapshot_revision_014(engine) -> dict[str, object]:
    inspector = inspect(engine)
    names = sorted(set(inspector.get_table_names()) - TASK5_TABLES - {"alembic_version"})
    return {name: (_rows(engine, name), _metadata(inspector, name)) for name in names}


def _assert_prior_schema_plus_run_ownership(engine, expected) -> None:
    actual = _snapshot_revision_014(engine)
    actual_run_rows, actual_run_metadata = actual["v2_runs"]
    expected_run_rows, expected_run_metadata = expected["v2_runs"]
    ownership = ("ux_v2_runs_team_id", 1, ("team_id", "id"), "")
    assert ownership in actual_run_metadata["indexes"]
    filtered = tuple(item for item in actual_run_metadata["indexes"] if item != ownership)
    actual["v2_runs"] = (actual_run_rows, {**actual_run_metadata, "indexes": filtered})
    assert actual_run_rows == expected_run_rows
    assert actual == expected


def _rows(engine, table_name: str) -> tuple[tuple[object, ...], ...]:
    table = sa.Table(table_name, MetaData(), autoload_with=engine)
    order = list(table.primary_key.columns) or list(table.columns)
    with engine.connect() as connection:
        return tuple(tuple(row) for row in connection.execute(select(table).order_by(*order)))


def _metadata(inspector, table_name: str) -> dict[str, object]:
    return {
        "columns": tuple(
            (
                item["name"],
                str(item["type"]),
                item["nullable"],
                item["default"],
                item["primary_key"],
            )
            for item in inspector.get_columns(table_name)
        ),
        "indexes": tuple(sorted(_index(item) for item in inspector.get_indexes(table_name))),
        "unique": tuple(
            sorted(_unique(item) for item in inspector.get_unique_constraints(table_name))
        ),
        "foreign_keys": tuple(
            sorted(_foreign_key(item) for item in inspector.get_foreign_keys(table_name))
        ),
        "checks": tuple(
            sorted(
                (item["name"], _sql(item["sqltext"]))
                for item in inspector.get_check_constraints(table_name)
            )
        ),
    }


def _index(item) -> tuple[object, ...]:
    where = item.get("dialect_options", {}).get("sqlite_where")
    return item["name"], item["unique"], tuple(item["column_names"]), _sql(where)


def _unique(item) -> tuple[object, ...]:
    return item["name"] or "", tuple(item["column_names"])


def _foreign_key(item) -> tuple[object, ...]:
    return (
        item["name"] or "",
        tuple(item["constrained_columns"]),
        item["referred_table"],
        tuple(item["referred_columns"]),
        item.get("options", {}).get("ondelete"),
    )


def _sql(value) -> str:
    return "" if value is None else " ".join(str(value).split())


def _assert_task5_schema(engine) -> None:
    inspector = inspect(engine)
    assert TASK5_TABLES <= set(inspector.get_table_names())
    assert (
        _partial_index(inspector, "v2_sprints", "ux_v2_sprints_one_active")
        == "lifecycle = 'ACTIVE'"
    )
    assert (
        _partial_index(inspector, "v2_sprint_scope", "ux_v2_sprint_scope_current_item")
        == "removed_at IS NULL"
    )
    assert (
        _partial_index(inspector, "v2_status_visits", "ux_v2_status_visits_one_open")
        == "lifecycle = 'OPEN'"
    )
    all_checks = {
        item["name"] for name in TASK5_TABLES for item in inspector.get_check_constraints(name)
    }
    assert {
        "ck_v2_work_items_story_points",
        "ck_v2_status_visits_work_balance",
        "ck_v2_semantic_counters_next_value",
    } <= all_checks


def _partial_index(inspector, table_name: str, index_name: str) -> str:
    index = next(item for item in inspector.get_indexes(table_name) if item["name"] == index_name)
    return _sql(index["dialect_options"]["sqlite_where"])


def _seed_one_task5_row(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO v2_member_identities (id,team_id,blueprint_index) "
                "VALUES (:id,:team,:position)"
            ),
            {"id": str(MEMBER_ID), "team": str(TEAM_ID), "position": MEMBER_INDEX},
        )


def _task5_counts(engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            name: connection.scalar(sa.text(f'SELECT COUNT(*) FROM "{name}"'))
            for name in TASK5_TABLES
        }


def _assert_revision(engine, revision: str) -> None:
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == revision
