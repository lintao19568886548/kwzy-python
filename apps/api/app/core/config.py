from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Production: mysql+pymysql://user:pass@host:3306/kwzy?charset=utf8mb4
    database_url: str = "sqlite+pysqlite:///./kwzy_step1.db"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins: str = "*"

    # Local/test admin seed only; never hardcode password in source.
    # Empty = skip creating admin user (log ERROR). Never used in production.
    local_admin_password: str = ""
    # If true and local password missing while no admin exists, refuse startup seed path.
    local_admin_password_required: bool = False

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """生产环境禁止默认 JWT 密钥与通配 CORS。"""

        if self.app_env.lower() != "production":
            return self
        if self.jwt_secret == "change-me-in-production":
            raise ValueError("production requires an explicit JWT_SECRET")
        origins = [origin.strip() for origin in self.cors_origins.split(",")]
        if "*" in origins:
            raise ValueError("production requires explicit CORS_ORIGINS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
