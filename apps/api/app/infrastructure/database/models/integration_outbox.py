"""功能说明：外部集成失败/出站持久化。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class IntegrationOutbox(Base, PrimaryKeyMixin, TimestampMixin):
    """外部调用出站记录（成功/失败均可追踪）。"""

    __tablename__ = "integration_outbox"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
