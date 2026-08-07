"""SQLAlchemy declarative base and common mixins."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLite requires INTEGER PK for autoincrement; MySQL keeps BIGINT
PK_TYPE = BigInteger().with_variant(Integer, "sqlite")
FK_TYPE = BigInteger().with_variant(Integer, "sqlite")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Shared metadata base for all ORM models."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        onupdate=utc_now,
        server_default=None,
    )


class TenantMixin:
    """Row-level multi-tenant column. Filter is enforced in repositories."""

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class PrimaryKeyMixin:
    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)


class StatusMixin:
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
