from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from backend.core.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def configure_sqlite_connection(dbapi_conn, _connection_record=None) -> None:
    """Enable SQLite foreign-key enforcement on every connection."""
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


def apply_sqlite_pragmas(target_engine) -> None:
    """Register SQLite pragmas for new connections on the given engine."""
    if target_engine.dialect.name != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _on_connect(dbapi_conn, connection_record):
        configure_sqlite_connection(dbapi_conn, connection_record)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
apply_sqlite_pragmas(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
