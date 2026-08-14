"""功能说明：
    Party ORM 模型（租户级主档与子表）。

业务职责：
    Infrastructure 持久化模型；无业务权限逻辑。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    FK_TYPE,
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
)


class Party(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：
        入驻方/主体主档表 parties。

    业务职责：
        ORM；tenant 隔离；无主档 park_id/模糊 address 列。

    输入参数：
        无（表映射）。

    返回结果：
        无。

    异常说明：
        无。

    业务规则：
        1. (tenant_id, credit_code) 唯一。
        2. 地址见 PartyAddress，不在本表。
    """

    __tablename__ = "parties"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_parties_tenant_id_id"),
        UniqueConstraint("tenant_id", "credit_code", name="uk_parties_tenant_credit"),
        Index("idx_parties_tenant_status", "tenant_id", "status"),
        Index("idx_parties_tenant_risk", "tenant_id", "risk_status"),
        Index("idx_parties_tenant_name", "tenant_id", "name"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    party_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ORGANIZATION")
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    credit_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    risk_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL")
    blacklist_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    blacklisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    blacklisted_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    blacklist_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    blacklist_removed_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PartyRole(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：
        Party 业务角色表 party_roles（非 RBAC）。

    业务职责：
        ORM；租户内 party_id+role_code 唯一。

    输入参数：
        无。

    返回结果：
        无。

    异常说明：
        无。

    业务规则：
        与权限码 party:* 相互独立。
    """

    __tablename__ = "party_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "party_id", "role_code", name="uk_party_role_code"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PartyParkRelation(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：
        Party–Park 多对多关系表 party_park_relations。

    业务职责：
        ORM；party_role_id 外键关联角色。

    输入参数：
        无。

    返回结果：
        无。

    异常说明：
        无。

    业务规则：
        ACTIVE 关系参与 park scope 可见性；支持软删 deleted_at。
    """

    __tablename__ = "party_park_relations"
    __table_args__ = (
        Index(
            "uk_ppr_active",
            "tenant_id",
            "party_id",
            "park_id",
            "party_role_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE' AND deleted_at IS NULL"),
            sqlite_where=text("status = 'ACTIVE' AND deleted_at IS NULL"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_role_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("party_roles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PartyContact(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：
        联系人表 party_contacts。

    业务职责：
        ORM；软删 is_deleted/deleted_at。

    输入参数：
        无。

    返回结果：
        无。

    异常说明：
        无。

    业务规则：
        租户 + party 归属；主联系人策略在 Application。
    """

    __tablename__ = "party_contacts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "party_id",
            "id",
            name="uk_party_contacts_tenant_party_id",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linked_person_party_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PartyAddress(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：
        结构化地址表 party_addresses。

    业务职责：
        ORM；地址事实来源独立于主档。

    输入参数：
        无。

    返回结果：
        无。

    异常说明：
        无。

    业务规则：
        1. PERSON 读写拒绝在 Application，不在 ORM。
        2. 软删 deleted_at；primary 按类型唯一由库索引约束。
    """

    __tablename__ = "party_addresses"
    __table_args__ = (
        Index(
            "uk_party_addr_primary",
            "tenant_id",
            "party_id",
            "address_type",
            unique=True,
            postgresql_where=text(
                "is_primary = true AND deleted_at IS NULL AND status = 'ACTIVE'"
            ),
            sqlite_where=text(
                "is_primary = 1 AND deleted_at IS NULL AND status = 'ACTIVE'"
            ),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    address_type: Mapped[str] = mapped_column(String(32), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    district: Mapped[str | None] = mapped_column(String(64), nullable=True)
    street: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PartyRiskEvent(Base, PrimaryKeyMixin):
    """功能说明：
        不可变风险事件表 party_risk_events。

    业务职责：
        ORM；只追加，无 updated_at 混入。

    输入参数：
        无。

    返回结果：
        无。

    异常说明：
        无。

    业务规则：
        仓储层不提供 update/delete。
    """

    __tablename__ = "party_risk_events"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_risk_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_risk_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    operator_user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
