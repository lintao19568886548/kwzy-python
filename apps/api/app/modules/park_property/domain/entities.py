"""ParkProperty 领域实体（无 SQLAlchemy）。

功能说明：
    定义园区与可租单元的纯领域对象。

业务职责：
    domain 层；承载业务字段与不变量相关数据形状，不依赖 ORM。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class ParkEntity:
    """功能说明：
        园区聚合根领域对象。

    业务职责：
        表示租户内园区主数据；id 未持久化前可为 None。
    """

    tenant_id: int
    name: str
    address: str = ""
    area: Decimal = field(default_factory=lambda: Decimal("0"))
    contact: Optional[str] = None
    manager: Optional[str] = None
    description: Optional[str] = None
    status: str = "ACTIVE"
    id: Optional[int] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class BuildingEntity:
    """功能说明：
        楼栋领域对象（支撑 Unit 外键）。

    业务职责：
        归属园区；默认「主楼」由应用层编排创建。
    """

    tenant_id: int
    park_id: int
    name: str
    code: str = ""
    parent_id: Optional[int] = None
    node_type: str = "BUILDING"
    building_type: str = "FACTORY"
    sort_order: int = 0
    status: str = "ACTIVE"
    address: str = ""
    description: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None
    id: Optional[int] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class UnitEntity:
    """功能说明：
        可租单元聚合根领域对象。

    业务职责：
        绑定 park_id/building_id；used_area 为投影字段。
    """

    tenant_id: int
    park_id: int
    building_id: int
    code: str
    name: str
    logical_id: str = ""
    version_no: int = 1
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    supersedes_id: Optional[int] = None
    lock_version: int = 1
    usage_type: str = "FACTORY"
    billing_unit: str = "SQM"
    available_from: Optional[date] = None
    rentable_area: Decimal = field(default_factory=lambda: Decimal("0"))
    used_area: Decimal = field(default_factory=lambda: Decimal("0"))
    base_rent_price: Decimal = field(default_factory=lambda: Decimal("0"))
    status: str = "VACANT"
    attributes: Optional[dict[str, Any]] = None
    id: Optional[int] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
