from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AllowedAppEnv = Literal["local", "test", "staging", "production"]
ALLOWED_APP_ENVS = frozenset({"local", "test", "staging", "production"})
ANON_DEV_ENVS = frozenset({"local", "test"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "kwzy-api"
    app_env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # Step1 default: local SQLite (never touch old Java MySQL)
    database_url: str = "sqlite+pysqlite:///./kwzy_step1.db"
    database_pool_size: int = Field(default=10, ge=1, le=200)
    database_max_overflow: int = Field(default=20, ge=0, le=400)
    database_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    workbench_worker_poll_seconds: int = Field(default=5, ge=1, le=300)
    workbench_worker_batch_size: int = Field(default=100, ge=1, le=500)

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    refresh_cookie_name: str = "kwzy_refresh"
    auth_login_window_seconds: int = 300
    auth_login_max_failures: int = 5
    auth_login_ip_max_failures: int = 20
    verification_code_ttl_seconds: int = 300
    verification_code_send_window_seconds: int = 60
    verification_code_max_sends_per_window: int = 1
    verification_code_max_attempts: int = 5
    page_access_proof_ttl_seconds: int = 300

    cors_origins: str = "*"
    trusted_hosts: str = "*"

    # Local/test admin seed only; never hardcode password in source.
    local_admin_password: str = ""
    local_admin_password_required: bool = False
    # Local/test identity seed is opt-in and assumes Alembic already ran.
    bootstrap_local_identity: bool = False

    # Explicit opt-in for anonymous local/test identity (default closed).
    allow_anon_dev: bool = False

    # External integrations (empty = fake/local; production may require when used)
    sms_provider: str = "auto"  # auto|fake|production
    sms_api_key: str = ""
    sms_endpoint: str = ""
    sms_timeout_seconds: int = 5
    sms_max_retries: int = 2

    wechat_provider: str = "auto"
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    oss_provider: str = "auto"  # auto|local|s3
    oss_local_root: str = "./data/attachments"
    oss_endpoint: str = ""
    oss_bucket: str = ""
    oss_access_key: str = ""
    oss_secret_key: str = ""
    oss_max_bytes: int = 10 * 1024 * 1024

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        if text not in ALLOWED_APP_ENVS:
            raise ValueError(
                f"invalid APP_ENV={value!r}; allowed: {sorted(ALLOWED_APP_ENVS)}"
            )
        return text

    @model_validator(mode="after")
    def validate_security_by_env(self) -> "Settings":
        """生产/预发禁止默认 JWT 与通配 CORS；非法环境已在 field 校验拒绝。"""

        if self.app_env in {"production", "staging"}:
            if self.jwt_secret == "change-me-in-production":
                raise ValueError(f"{self.app_env} requires an explicit JWT_SECRET")
            if len(self.jwt_secret.encode("utf-8")) < 32:
                raise ValueError(f"{self.app_env} requires JWT_SECRET of at least 32 bytes")
            if self.jwt_algorithm not in {"HS256", "HS384", "HS512"}:
                raise ValueError(f"{self.app_env} requires an approved HMAC JWT_ALGORITHM")
            origins = [origin.strip() for origin in self.cors_origins.split(",")]
            if "*" in origins:
                raise ValueError(f"{self.app_env} requires explicit CORS_ORIGINS")
            hosts = [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]
            if not hosts or "*" in hosts:
                raise ValueError(f"{self.app_env} requires explicit TRUSTED_HOSTS")
            if self.allow_anon_dev:
                raise ValueError(f"{self.app_env} forbids ALLOW_ANON_DEV")
            if self.bootstrap_local_identity:
                raise ValueError(f"{self.app_env} forbids BOOTSTRAP_LOCAL_IDENTITY")
            if self.database_url.startswith("sqlite"):
                raise ValueError(f"{self.app_env} requires PostgreSQL DATABASE_URL")
            # 生产若显式选择 production provider 则必须有密钥
            if self.sms_provider == "production" and not (self.sms_api_key or "").strip():
                raise ValueError("production sms_provider requires SMS_API_KEY")
            if self.wechat_provider == "production" and (
                not self.wechat_app_id or not self.wechat_app_secret
            ):
                raise ValueError("production wechat_provider requires WECHAT_APP_ID/SECRET")
            if self.oss_provider == "s3" and (
                not self.oss_endpoint or not self.oss_bucket or not self.oss_access_key
            ):
                raise ValueError("oss_provider=s3 requires OSS endpoint/bucket/access_key")
        return self

    def allows_anonymous_dev_identity(self) -> bool:
        """仅 local/test 且显式 ALLOW_ANON_DEV 才允许匿名开发身份。"""

        return bool(self.allow_anon_dev) and self.app_env in ANON_DEV_ENVS


@lru_cache
def get_settings() -> Settings:
    return Settings()
