"""Auth fail-closed: APP_ENV normalize + ALLOW_ANON_DEV gate."""

from __future__ import annotations

import os
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import create_app


@contextmanager
def _settings_env(**overrides: str):
    """Temporarily set env vars and clear Settings cache."""
    keys = list(overrides.keys())
    old = {k: os.environ.get(k) for k in keys}
    try:
        for k, v in overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()
        yield
    finally:
        for k, prev in old.items():
            if prev is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev
        get_settings.cache_clear()


def _prod_like_env(app_env: str) -> dict[str, str]:
    return {
        "APP_ENV": app_env,
        "JWT_SECRET": "test-prod-jwt-secret-not-default",
        "CORS_ORIGINS": "https://example.com",
        "ALLOW_ANON_DEV": "false",
        "DEBUG": "false",
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    }


@pytest.mark.parametrize("env_value", ["production", "Production", "PRODUCTION", "staging"])
def test_production_case_variants_and_staging_require_jwt(env_value: str) -> None:
    with _settings_env(**_prod_like_env(env_value)):
        settings = get_settings()
        assert settings.app_env in {"production", "staging"}
        assert settings.allows_anonymous_dev_identity() is False
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/api/v1/parks")
            assert r.status_code == 401, r.text
            body = r.json()
            assert body["code"] == "UNAUTHORIZED"
            assert "data" in body
            assert "x-request-id" in {k.lower() for k in r.headers.keys()}


def test_invalid_app_env_fails_startup() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="invalid-env",
            jwt_secret="x",
            cors_origins="https://a.com",
        )


def test_local_without_allow_anon_dev_is_401() -> None:
    with _settings_env(
        APP_ENV="local",
        ALLOW_ANON_DEV="false",
        JWT_SECRET="test-jwt-secret-not-for-production",
        CORS_ORIGINS="*",
        DEBUG="false",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    ):
        assert get_settings().allows_anonymous_dev_identity() is False
        app = create_app()
        with TestClient(app) as client:
            r = client.get("/api/v1/parks")
            assert r.status_code == 401
            assert r.json()["code"] == "UNAUTHORIZED"


def test_local_with_allow_anon_dev_allows_dev_identity() -> None:
    from unittest.mock import MagicMock

    from app.shared.deps import get_tenant_context
    from app.shared.tenant_context import ParkScopeMode

    with _settings_env(
        APP_ENV="local",
        ALLOW_ANON_DEV="true",
        JWT_SECRET="test-jwt-secret-not-for-production",
        CORS_ORIGINS="*",
        DEBUG="false",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        LOCAL_ADMIN_PASSWORD="admin123",
    ):
        assert get_settings().allows_anonymous_dev_identity() is True
        request = MagicMock()
        request.state.request_id = "test-req"
        request.client.host = "127.0.0.1"
        ctx = get_tenant_context(request, creds=None)
        assert ctx.tenant_id == 1
        assert ctx.permissions == ["*"]
        assert ctx.park_scope_mode == ParkScopeMode.ALL


def test_staging_forbids_allow_anon_dev() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="staging",
            jwt_secret="explicit-staging-secret",
            cors_origins="https://staging.example.com",
            allow_anon_dev=True,
        )


def test_production_forbids_default_jwt() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="Production",
            jwt_secret="change-me-in-production",
            cors_origins="https://app.example.com",
        )
