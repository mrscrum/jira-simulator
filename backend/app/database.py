from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def _enable_sqlite_pragmas(dbapi_connection, _connection_record):
    """Enable WAL mode and foreign keys for SQLite (test environments)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_engine_from_url(url: str) -> Engine:
    """Create a SQLAlchemy engine with dialect-appropriate settings.

    - SQLite: enables WAL mode and foreign keys via PRAGMA.
    - PostgreSQL: uses connection pooling with sensible defaults.
    """
    if url.startswith("sqlite"):
        engine = create_engine(url)
        event.listen(engine, "connect", _enable_sqlite_pragmas)
    else:
        engine = create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)


def get_db(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
