from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.infrastructure.database.session import engine_options


def test_postgres_engine_has_bounded_pool_options() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://u:p@127.0.0.1:5432/db",
        database_pool_size=7,
        database_max_overflow=9,
        database_pool_timeout_seconds=11,
        database_pool_recycle_seconds=600,
    )
    assert engine_options(settings) == {
        "pool_pre_ping": True,
        "echo": False,
        "pool_size": 7,
        "max_overflow": 9,
        "pool_timeout": 11,
        "pool_recycle": 600,
        "pool_use_lifo": True,
    }


def test_sqlite_ignores_queue_pool_options() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
    )
    options = engine_options(settings)
    assert options["connect_args"] == {"check_same_thread": False}
    assert "pool_size" not in options
    assert "max_overflow" not in options


def test_production_rejects_sqlite_database() -> None:
    with pytest.raises(ValidationError, match="requires PostgreSQL DATABASE_URL"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="sqlite+pysqlite:///prod.db",
            jwt_secret="production-jwt-secret-with-at-least-32-bytes",
            cors_origins="https://app.example.test",
            trusted_hosts="app.example.test",
            allow_anon_dev=False,
            bootstrap_local_identity=False,
        )
