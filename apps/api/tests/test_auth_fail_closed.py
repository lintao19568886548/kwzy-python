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
        "TRUSTED_HOSTS": "testserver,example.com",
        "ALLOW_ANON_DEV": "false",
        "DEBUG": "false",
        "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:5432/test",
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
            jwt_secret="explicit-staging-secret-with-32-bytes",
            cors_origins="https://staging.example.com",
            trusted_hosts="staging.example.com",
            allow_anon_dev=True,
        )


def test_production_forbids_default_jwt() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="Production",
            jwt_secret="change-me-in-production",
            cors_origins="https://app.example.com",
            trusted_hosts="app.example.com",
        )


def test_production_forbids_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(
            app_env="production",
            jwt_secret="too-short",
            cors_origins="https://app.example.com",
            trusted_hosts="app.example.com",
        )


def test_production_forbids_unapproved_jwt_algorithm() -> None:
    with pytest.raises(ValidationError, match="approved HMAC"):
        Settings(
            app_env="production",
            jwt_secret="production-jwt-secret-with-32-bytes",
            jwt_algorithm="none",
            cors_origins="https://app.example.com",
            trusted_hosts="app.example.com",
        )


def test_production_forbids_local_identity_bootstrap() -> None:
    with pytest.raises(ValidationError, match="BOOTSTRAP_LOCAL_IDENTITY"):
        Settings(
            app_env="production",
            jwt_secret="production-jwt-secret-with-32-bytes",
            cors_origins="https://app.example.com",
            trusted_hosts="app.example.com",
            allow_anon_dev=False,
            bootstrap_local_identity=True,
        )


def test_schema_bootstrap_is_disabled_by_default() -> None:
    settings = Settings(
        _env_file=None,
        app_env="local",
        jwt_secret="local-test-secret",
        cors_origins="*",
    )
    assert settings.bootstrap_local_identity is False


def test_production_requires_explicit_trusted_hosts() -> None:
    with pytest.raises(ValidationError, match="TRUSTED_HOSTS"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="production-jwt-secret-with-32-bytes",
            cors_origins="https://app.example.com",
            trusted_hosts="*",
            allow_anon_dev=False,
        )


def test_security_headers_and_production_docs_gate() -> None:
    with _settings_env(**_prod_like_env("production")):
        app = create_app()
        with TestClient(app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            assert health.headers["x-content-type-options"] == "nosniff"
            assert health.headers["x-frame-options"] == "DENY"
            assert "max-age=" in health.headers["strict-transport-security"]
            assert client.get("/docs").status_code == 404


def test_production_cookie_refresh_rejects_unapproved_origin() -> None:
    with _settings_env(**_prod_like_env("production")):
        app = create_app()
        with TestClient(app) as client:
            client.cookies.set("kwzy_refresh", "attacker-cannot-use-this-cookie-cross-site")
            response = client.post(
                "/api/v1/auth/refresh",
                json={},
                headers={"Origin": "https://evil.example"},
            )
            assert response.status_code == 403
            assert response.json()["code"] == "CSRF_ORIGIN_DENIED"
            assert response.headers["cache-control"] == "no-store"
