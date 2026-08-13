"""功能说明：招商线索 ORM。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class Lead(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：招商线索 leads。"""

    __tablename__ = "leads"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    intent_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    intent_area: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW", index=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True, index=True
    )
    party_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parties.id"), nullable=True, index=True
    )
    lease_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=True, index=True
    )
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
