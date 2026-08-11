from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_migration_013_adds_and_removes_only_v2_tables(tmp_path):
    database_path = tmp_path / "migration.db"
    backend_root = Path(__file__).parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "012")
    engine = create_engine(f"sqlite:///{database_path}")
    legacy_tables = set(inspect(engine).get_table_names())

    command.upgrade(config, "013")
    assert {"v2_teams", "v2_team_blueprints", "v2_runs", "v2_team_runtimes"}.issubset(
        inspect(engine).get_table_names()
    )
    command.downgrade(config, "012")

    assert set(inspect(engine).get_table_names()) == legacy_tables
    engine.dispose()
