import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine, inspect, select

from alembic import command
from app.models import Base
from tests.v2.integration.test_migration_013 import _alembic_config, _seed_every_legacy_table
from tests.v2.integration.test_migration_015 import _seed_task_one_and_two

DELIVERY_TABLES = {"v2_jira_delivery_receipts", "v2_jira_resource_mappings"}


def test_revision_016_is_the_only_alembic_head():
    backend_root = Path(__file__).parents[3]
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "heads"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "016 (head)"


def test_revision_016_matches_delivery_orm_schema(tmp_path):
    orm_engine = create_engine(f"sqlite:///{tmp_path / 'orm-016.db'}")
    migrated_path = tmp_path / "migrated-016.db"
    Base.metadata.create_all(orm_engine)
    command.upgrade(_alembic_config(Path(__file__).parents[3], migrated_path), "016")
    migrated_engine = create_engine(f"sqlite:///{migrated_path}")

    orm_inspector = inspect(orm_engine)
    migrated_inspector = inspect(migrated_engine)
    for table_name in DELIVERY_TABLES:
        assert _metadata(orm_inspector, table_name) == _metadata(migrated_inspector, table_name)

    orm_engine.dispose()
    migrated_engine.dispose()


def test_populated_015_round_trip_preserves_all_prior_rows(tmp_path):
    database_path = tmp_path / "round-trip-016.db"
    config = _alembic_config(Path(__file__).parents[3], database_path)
    command.upgrade(config, "012")
    engine = create_engine(f"sqlite:///{database_path}")
    _seed_every_legacy_table(engine)
    command.upgrade(config, "015")
    _seed_task_one_and_two(engine)
    expected = _snapshot_without_delivery(engine)

    command.upgrade(config, "016")
    _seed_delivery_rows(engine)
    command.downgrade(config, "015")

    assert _snapshot_without_delivery(engine) == expected
    assert DELIVERY_TABLES.isdisjoint(inspect(engine).get_table_names())
    assert _revision(engine) == "015"

    command.upgrade(config, "016")
    assert _delivery_counts(engine) == {name: 0 for name in DELIVERY_TABLES}
    assert _revision(engine) == "016"
    engine.dispose()


def _seed_delivery_rows(engine) -> None:
    with engine.begin() as connection:
        intent = connection.execute(
            sa.text("SELECT id, team_id, recorded_at FROM v2_projection_intents LIMIT 1")
        ).one()
        connection.execute(
            sa.text(
                "INSERT INTO v2_jira_delivery_receipts "
                "(intent_id,state,attempts,next_attempt_at,last_attempt_at,"
                "delivered_at,last_error) "
                "VALUES (:intent,'DELIVERED',1,NULL,:at,:at,NULL)"
            ),
            {"intent": intent.id, "at": intent.recorded_at},
        )
        connection.execute(
            sa.text(
                "INSERT INTO v2_jira_resource_mappings "
                "(team_id,internal_kind,internal_id,jira_id,jira_key) "
                "VALUES (:team,'ISSUE',:internal,'10001','SIM-1')"
            ),
            {"team": intent.team_id, "internal": intent.id},
        )


def _snapshot_without_delivery(engine) -> dict[str, tuple[tuple[object, ...], ...]]:
    names = sorted(set(inspect(engine).get_table_names()) - DELIVERY_TABLES - {"alembic_version"})
    return {name: _rows(engine, name) for name in names}


def _rows(engine, table_name: str) -> tuple[tuple[object, ...], ...]:
    table = sa.Table(table_name, MetaData(), autoload_with=engine)
    order = list(table.primary_key.columns) or list(table.columns)
    with engine.connect() as connection:
        return tuple(tuple(row) for row in connection.execute(select(table).order_by(*order)))


def _delivery_counts(engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            name: connection.scalar(sa.text(f'SELECT COUNT(*) FROM "{name}"'))
            for name in DELIVERY_TABLES
        }


def _revision(engine) -> str:
    with engine.connect() as connection:
        return connection.scalar(sa.text("SELECT version_num FROM alembic_version"))


def _metadata(inspector, table_name: str) -> dict[str, object]:
    return {
        "columns": tuple(
            (item["name"], str(item["type"]), item["nullable"], item["primary_key"])
            for item in inspector.get_columns(table_name)
        ),
        "indexes": tuple(
            sorted(
                (item["name"], item["unique"], tuple(item["column_names"]))
                for item in inspector.get_indexes(table_name)
            )
        ),
        "unique": tuple(
            sorted(
                (item["name"] or "", tuple(item["column_names"]))
                for item in inspector.get_unique_constraints(table_name)
            )
        ),
        "foreign_keys": tuple(
            sorted(
                (
                    item["name"] or "",
                    tuple(item["constrained_columns"]),
                    item["referred_table"],
                    tuple(item["referred_columns"]),
                    item.get("options", {}).get("ondelete"),
                )
                for item in inspector.get_foreign_keys(table_name)
            )
        ),
        "checks": tuple(
            sorted(
                (item["name"], " ".join(item["sqltext"].split()))
                for item in inspector.get_check_constraints(table_name)
            )
        ),
    }
