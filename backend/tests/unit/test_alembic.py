import os
import tempfile

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _get_alembic_cfg(db_path: str) -> Config:
    """Build alembic config running from the backend root so relative paths work."""
    ini_path = os.path.join(_BACKEND_DIR, "alembic.ini")
    if not os.path.isfile(ini_path):
        pytest.skip("alembic.ini not found")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    # Ensure script_location resolves relative to backend dir.
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    return cfg


class TestAlembicMigration:
    def test_migration_creates_all_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            alembic_cfg = _get_alembic_cfg(db_path)
            command.upgrade(alembic_cfg, "head")

            engine = create_engine(f"sqlite:///{db_path}")
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())

            expected_tables = {
                "alembic_version",
                "organizations",
                "teams",
                "members",
                "workflows",
                "workflow_steps",
                "touch_time_configs",
                "dysfunction_configs",
                "sprints",
                "issues",
            }
            assert expected_tables.issubset(table_names)
            engine.dispose()
        finally:
            for ext in ("", "-wal", "-shm"):
                path = db_path + ext
                if os.path.exists(path):
                    os.unlink(path)

    def test_migration_is_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            alembic_cfg = _get_alembic_cfg(db_path)
            command.upgrade(alembic_cfg, "head")
            command.upgrade(alembic_cfg, "head")

            engine = create_engine(f"sqlite:///{db_path}")
            inspector = inspect(engine)
            assert "organizations" in inspector.get_table_names()
            engine.dispose()
        finally:
            for ext in ("", "-wal", "-shm"):
                path = db_path + ext
                if os.path.exists(path):
                    os.unlink(path)
