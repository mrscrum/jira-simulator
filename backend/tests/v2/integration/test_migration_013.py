from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, inspect, select

from alembic import command

V2_TABLES = {"v2_teams", "v2_team_blueprints", "v2_runs", "v2_team_runtimes"}


def _alembic_config(backend_root: Path, database_path: Path) -> Config:
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    return config


def _dependency_order(metadata: MetaData) -> list[sa.Table]:
    remaining = set(metadata.tables.values())
    ordered: list[sa.Table] = []
    while remaining:
        ready = [table for table in remaining if _external_dependencies(table) <= set(ordered)]
        assert ready, f"cyclic legacy tables: {sorted(table.name for table in remaining)}"
        for table in sorted(ready, key=lambda item: item.name):
            ordered.append(table)
            remaining.remove(table)
    return ordered


def _external_dependencies(table: sa.Table) -> set[sa.Table]:
    return {
        foreign_key.column.table
        for foreign_key in table.foreign_keys
        if foreign_key.column.table is not table
    }


def _seed_value(column: sa.Column, primary_values: dict[tuple[str, str], object]):
    if column.foreign_keys:
        target = next(iter(column.foreign_keys)).column
        if target.table is column.table:
            return None
        return primary_values[(target.table.name, target.name)]
    if isinstance(column.type, sa.Boolean):
        return False
    if isinstance(column.type, sa.DateTime):
        return datetime(2026, 8, 10, 12, tzinfo=UTC)
    if isinstance(column.type, sa.JSON):
        return {"seeded": True}
    if isinstance(column.type, sa.Float):
        return 1.0
    if isinstance(column.type, sa.Integer):
        return 1
    return f"{column.table.name}_{column.name}"


def _seed_every_legacy_table(engine) -> None:
    metadata = MetaData()
    metadata.reflect(engine)
    metadata.remove(metadata.tables["alembic_version"])
    primary_values: dict[tuple[str, str], object] = {}
    with engine.begin() as connection:
        for table in _dependency_order(metadata):
            values = _row_values(table, primary_values)
            connection.execute(table.insert().values(**values))
            for column in table.primary_key.columns:
                primary_values[(table.name, column.name)] = values[column.name]


def _row_values(table: sa.Table, primary_values) -> dict[str, object]:
    values: dict[str, object] = {}
    for column in table.columns:
        value = _seed_value(column, primary_values)
        if value is not None or not column.nullable:
            values[column.name] = value
    return values


def _snapshot(engine) -> tuple[dict[str, object], dict[str, object]]:
    inspector = inspect(engine)
    table_names = sorted(set(inspector.get_table_names()) - V2_TABLES - {"alembic_version"})
    content = {name: _table_rows(engine, name) for name in table_names}
    metadata = {name: _table_metadata(inspector, name) for name in table_names}
    return content, metadata


def _table_rows(engine, table_name: str) -> tuple[tuple[object, ...], ...]:
    table = sa.Table(table_name, MetaData(), autoload_with=engine)
    order = list(table.primary_key.columns) or list(table.columns)
    with engine.connect() as connection:
        return tuple(tuple(row) for row in connection.execute(select(table).order_by(*order)))


def _table_metadata(inspector, table_name: str) -> dict[str, object]:
    columns = tuple(
        (item["name"], str(item["type"]), item["nullable"], item["default"], item["primary_key"])
        for item in inspector.get_columns(table_name)
    )
    indexes = tuple(sorted(_normalized_index(item) for item in inspector.get_indexes(table_name)))
    foreign_keys = tuple(
        sorted(_normalized_foreign_key(item) for item in inspector.get_foreign_keys(table_name))
    )
    return {"columns": columns, "indexes": indexes, "foreign_keys": foreign_keys}


def _normalized_index(item) -> tuple[object, ...]:
    return (item["name"], item["unique"], tuple(item["column_names"]))


def _normalized_foreign_key(item) -> tuple[object, ...]:
    return (
        tuple(item["constrained_columns"]),
        item["referred_table"],
        tuple(item["referred_columns"]),
        item.get("options", {}).get("ondelete"),
    )


def test_populated_012_round_trip_preserves_all_legacy_content_and_metadata(tmp_path):
    database_path = tmp_path / "migration.db"
    backend_root = Path(__file__).parents[3]
    config = _alembic_config(backend_root, database_path)
    command.upgrade(config, "012")
    engine = create_engine(f"sqlite:///{database_path}")
    _seed_every_legacy_table(engine)
    expected = _snapshot(engine)

    command.upgrade(config, "013")
    assert _snapshot(engine) == expected
    assert V2_TABLES <= set(inspect(engine).get_table_names())
    command.downgrade(config, "012")
    assert _snapshot(engine) == expected
    assert V2_TABLES.isdisjoint(inspect(engine).get_table_names())
    command.upgrade(config, "013")

    assert _snapshot(engine) == expected
    assert _v2_counts(engine) == {name: 0 for name in V2_TABLES}
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "013"
    engine.dispose()


def _v2_counts(engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            table_name: connection.scalar(sa.text(f'SELECT COUNT(*) FROM "{table_name}"'))
            for table_name in V2_TABLES
        }
