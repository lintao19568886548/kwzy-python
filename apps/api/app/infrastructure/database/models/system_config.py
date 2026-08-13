"""功能说明：组织、数据字典、系统参数 ORM。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class OrgUnit(Base, PrimaryKeyMixin, TimestampMixin):
    """组织架构节点（树形）。"""

    __tablename__ = "org_units"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uk_org_unit_code"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("org_units.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class DictType(Base, PrimaryKeyMixin, TimestampMixin):
    """字典类型。"""

    __tablename__ = "dict_types"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uk_dict_type_code"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class DictItem(Base, PrimaryKeyMixin, TimestampMixin):
    """字典项。"""

    __tablename__ = "dict_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dict_type_id", "item_value", name="uk_dict_item_value"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    dict_type_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("dict_types.id"), nullable=False, index=True
    )
    item_label: Mapped[str] = mapped_column(String(128), nullable=False)
    item_value: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class SystemParam(Base, PrimaryKeyMixin, TimestampMixin):
    """租户级系统参数。"""

    __tablename__ = "system_params"
    __table_args__ = (UniqueConstraint("tenant_id", "param_key", name="uk_system_param_key"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    param_key: Mapped[str] = mapped_column(String(128), nullable=False)
    param_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value_type: Mapped[str] = mapped_column(String(32), nullable=False, default="STRING")
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
