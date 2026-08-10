from __future__ import annotations

import os

# Force isolated sqlite DB for tests — never touch production/old MySQL
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
# Explicit local/test anonymous identity for fixtures that omit JWT.
os.environ["ALLOW_ANON_DEV"] = "true"
# Test fixture credential only — not a production password
os.environ["LOCAL_ADMIN_PASSWORD"] = "admin123"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.identity.application.bootstrap import ensure_default_tenant

# Clear settings cache so env takes effect
get_settings.cache_clear()


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _fk(dbapi_connection, _):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    import app.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db_session(engine) -> Session:
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    ensure_default_tenant(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine, db_session: Session):
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    application = create_app()
    application.dependency_overrides[get_db] = _override_db
    with TestClient(application) as c:
        yield c
    application.dependency_overrides.clear()
