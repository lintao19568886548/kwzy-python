"""功能说明：催缴案件 ORM（最小可运行）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class CollectionCase(Base, PrimaryKeyMixin, TimestampMixin):
    """催缴案件（过程记录，不替代 Payment）。"""

    __tablename__ = "collection_cases"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    party_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parties.id"), nullable=False, index=True
    )
    bill_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("bills.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="L1")
    assignee_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
