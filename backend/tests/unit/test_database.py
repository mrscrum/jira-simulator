import os
import tempfile

from sqlalchemy import text


class TestDatabaseEngine:
    def test_creates_engine_from_url(self):
        from app.database import create_engine_from_url

        engine = create_engine_from_url("sqlite:///:memory:")
        assert engine is not None

    def test_sqlite_enables_wal_mode(self):
        from app.database import create_engine_from_url

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        try:
            engine = create_engine_from_url(f"sqlite:///{db_path}")
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA journal_mode")).scalar()
                assert result == "wal"
            engine.dispose()
        finally:
            for ext in ("", "-wal", "-shm"):
                path = db_path + ext
                if os.path.exists(path):
                    os.unlink(path)

    def test_sqlite_enables_foreign_keys(self):
        from app.database import create_engine_from_url

        engine = create_engine_from_url("sqlite:///:memory:")
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
            assert result == 1


    def test_postgresql_url_sets_pool_config(self):
        """Verify PostgreSQL URLs get connection pool settings (without connecting)."""
        from app.database import create_engine_from_url

        # Use a dummy URL — we're not actually connecting
        engine = create_engine_from_url(
            "postgresql://user:pass@localhost:5432/testdb"
        )
        assert engine.pool.size() == 10
        engine.dispose()


class TestSessionFactory:
    def test_creates_session(self):
        from app.database import create_engine_from_url, create_session_factory

        engine = create_engine_from_url("sqlite:///:memory:")
        session_factory = create_session_factory(engine)
        session = session_factory()
        assert session is not None
        session.close()


class TestGetDb:
    def test_yields_session_and_closes(self):
        from app.database import create_engine_from_url, create_session_factory, get_db

        engine = create_engine_from_url("sqlite:///:memory:")
        session_factory = create_session_factory(engine)
        gen = get_db(session_factory)
        session = next(gen)
        assert session is not None
        try:
            next(gen)
        except StopIteration:
            pass
