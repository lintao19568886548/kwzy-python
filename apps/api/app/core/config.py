from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
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

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins: str = "*"

    # Local/test admin seed only; never hardcode password in source.
    local_admin_password: str = ""
    local_admin_password_required: bool = False

    # Explicit opt-in for anonymous local/test identity (default closed).
    allow_anon_dev: bool = False

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
            origins = [origin.strip() for origin in self.cors_origins.split(",")]
            if "*" in origins:
                raise ValueError(f"{self.app_env} requires explicit CORS_ORIGINS")
            if self.allow_anon_dev:
                raise ValueError(f"{self.app_env} forbids ALLOW_ANON_DEV")
        return self

    def allows_anonymous_dev_identity(self) -> bool:
        """仅 local/test 且显式 ALLOW_ANON_DEV 才允许匿名开发身份。"""

        return bool(self.allow_anon_dev) and self.app_env in ANON_DEV_ENVS


@lru_cache
def get_settings() -> Settings:
    return Settings()
