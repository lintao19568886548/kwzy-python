"""Engine / session factory."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.infrastructure.database.base import Base


def engine_options(settings: Settings) -> dict[str, Any]:
    """Return explicit, bounded pool options without applying them to SQLite."""

    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "echo": settings.debug,
    }
    if settings.database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        return options
    options.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
        pool_use_lifo=True,
    )
    return options


_settings = get_settings()

engine: Engine = create_engine(
    _settings.database_url,
    **engine_options(_settings),
)

# SQLite FK support — bind to this engine only (not all Engine instances),
# so PostgreSQL integration engines are not polluted with PRAGMA.
if _settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """Dev helper — prefer Alembic migrations in real deploys."""
    # Import models so metadata is populated
    import app.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
