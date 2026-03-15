import os
import tempfile

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


class TestAlembicMigration:
    def test_migration_creates_all_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            alembic_cfg = Config(
                os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
            )
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
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
            alembic_cfg = Config(
                os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
            )
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
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
