import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine, inspect, select

from alembic import command
from tests.v2.integration.test_migration_013 import (
    V2_TABLES,
    _alembic_config,
    _seed_every_legacy_table,
    _snapshot,
    _table_metadata,
    _table_rows,
)

LIVE_TABLES = {
    "v2_activity_events",
    "v2_ground_truth_records",
    "v2_projection_intents",
}
RUNTIME_COLUMNS_013 = (
    "id",
    "team_id",
    "run_id",
    "state",
    "simulation_time",
    "next_wake_at",
    "created_at",
    "updated_at",
)


def _task_one_snapshot(engine) -> tuple[dict[str, object], dict[str, object]]:
    inspector = inspect(engine)
    content = {name: _table_rows(engine, name) for name in sorted(V2_TABLES)}
    metadata = {name: _table_metadata(inspector, name) for name in sorted(V2_TABLES)}
    return content, metadata


def _rows_for_columns(engine, table_name: str, column_names: tuple[str, ...]):
    table = sa.Table(table_name, MetaData(), autoload_with=engine)
    columns = [table.c[name] for name in column_names]
    with engine.connect() as connection:
        return tuple(tuple(row) for row in connection.execute(select(*columns)))


def _assert_task_one_rows_preserved(engine, expected_content) -> None:
    for table_name in V2_TABLES - {"v2_team_runtimes"}:
        assert _table_rows(engine, table_name) == expected_content[table_name]
    expected_runtime = expected_content["v2_team_runtimes"]
    assert _rows_for_columns(engine, "v2_team_runtimes", RUNTIME_COLUMNS_013) == expected_runtime


def _assert_legacy_preserved(engine, expected) -> None:
    actual_content, actual_metadata = _snapshot(engine)
    expected_content, expected_metadata = expected
    assert {name: actual_content[name] for name in expected_content} == expected_content
    assert {name: actual_metadata[name] for name in expected_metadata} == expected_metadata


def _assert_014_schema(engine) -> None:
    inspector = inspect(engine)
    assert LIVE_TABLES | V2_TABLES <= set(inspector.get_table_names())
    version = next(
        column
        for column in inspector.get_columns("v2_team_runtimes")
        if column["name"] == "version"
    )
    assert version["nullable"] is False
    assert version["default"] is None
    with engine.connect() as connection:
        versions = connection.execute(sa.text("SELECT version FROM v2_team_runtimes"))
        assert [row[0] for row in versions] == [0]


def _assert_live_tables_empty(engine) -> None:
    with engine.connect() as connection:
        counts = {
            table_name: connection.scalar(sa.text(f'SELECT COUNT(*) FROM "{table_name}"'))
            for table_name in LIVE_TABLES
        }
    assert counts == {name: 0 for name in LIVE_TABLES}


def _assert_revision(engine, expected: str) -> None:
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == expected


def test_migration_graph_remains_linear_through_current_015_head():
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


def test_populated_013_round_trip_preserves_task_one_and_legacy_rows(tmp_path):
    database_path = tmp_path / "migration-014.db"
    backend_root = Path(__file__).parents[3]
    config = _alembic_config(backend_root, database_path)
    command.upgrade(config, "013")
    engine = create_engine(f"sqlite:///{database_path}")
    _seed_every_legacy_table(engine)
    expected_legacy = _snapshot(engine)
    expected_task_one = _task_one_snapshot(engine)

    command.upgrade(config, "014")
    _assert_014_schema(engine)
    _assert_task_one_rows_preserved(engine, expected_task_one[0])
    _assert_legacy_preserved(engine, expected_legacy)
    command.downgrade(config, "013")

    assert _snapshot(engine) == expected_legacy
    assert _task_one_snapshot(engine) == expected_task_one
    assert LIVE_TABLES.isdisjoint(inspect(engine).get_table_names())
    _assert_revision(engine, "013")

    command.upgrade(config, "014")
    _assert_014_schema(engine)
    _assert_task_one_rows_preserved(engine, expected_task_one[0])
    _assert_live_tables_empty(engine)
    _assert_revision(engine, "014")
    engine.dispose()
