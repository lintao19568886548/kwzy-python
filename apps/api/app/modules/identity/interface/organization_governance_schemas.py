"""平台组织治理 API 请求 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

LifecycleStatus = Literal["ACTIVE", "DISABLED"]
FieldAccessMode = Literal["VISIBLE", "MASKED", "HIDDEN"]


class GroupCreateRequest(BaseModel):
    """创建经营集团。"""

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = Field(default=0, ge=-100000, le=100000)
    remark: str | None = Field(default=None, max_length=500)


class GroupUpdateRequest(BaseModel):
    """更新经营集团；编码保持不可变。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: LifecycleStatus | None = None
    sort_order: int | None = Field(default=None, ge=-100000, le=100000)
    remark: str | None = Field(default=None, max_length=500)


class RegionCreateRequest(BaseModel):
    """创建集团下经营区域。"""

    group_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = Field(default=0, ge=-100000, le=100000)
    remark: str | None = Field(default=None, max_length=500)


class RegionUpdateRequest(BaseModel):
    """更新经营区域。"""

    group_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: LifecycleStatus | None = None
    sort_order: int | None = Field(default=None, ge=-100000, le=100000)
    remark: str | None = Field(default=None, max_length=500)


class ParkAssignmentRequest(BaseModel):
    """调区命令；同园区当前关系由数据库唯一约束保护。"""

    region_id: int = Field(gt=0)
    park_id: int = Field(gt=0)
    effective_from: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class PositionCreateRequest(BaseModel):
    """创建岗位主档。"""

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=128)
    org_unit_id: int | None = Field(default=None, gt=0)
    sort_order: int = Field(default=0, ge=-100000, le=100000)
    responsibilities: str | None = Field(default=None, max_length=5000)


class PositionUpdateRequest(BaseModel):
    """更新岗位主档。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    org_unit_id: int | None = Field(default=None, gt=0)
    clear_org_unit: bool = False
    status: LifecycleStatus | None = None
    sort_order: int | None = Field(default=None, ge=-100000, le=100000)
    responsibilities: str | None = Field(default=None, max_length=5000)


class UserPositionAssignmentRequest(BaseModel):
    """创建有效期用户任职。"""

    user_id: int = Field(gt=0)
    position_id: int = Field(gt=0)
    park_id: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    is_primary: bool = False
    remark: str | None = Field(default=None, max_length=500)


class AssignmentEndRequest(BaseModel):
    """结束当前任职。"""

    ends_at: datetime | None = None
    remark: str | None = Field(default=None, max_length=500)


class FieldPolicyUpsertRequest(BaseModel):
    """创建或更新角色字段访问策略。"""

    role_id: int = Field(gt=0)
    resource_type: str = Field(min_length=1, max_length=64)
    field_name: str = Field(min_length=1, max_length=64)
    access_mode: FieldAccessMode
    mask_strategy: str = Field(default="PHONE", min_length=1, max_length=32)
    status: LifecycleStatus = "ACTIVE"

    @model_validator(mode="after")
    def normalize_codes(self) -> FieldPolicyUpsertRequest:
        """规范化策略代码，避免大小写形成重复语义。"""

        self.resource_type = self.resource_type.strip().upper()
        self.field_name = self.field_name.strip().lower()
        self.mask_strategy = self.mask_strategy.strip().upper()
        return self
