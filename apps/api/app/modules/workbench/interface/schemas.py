"""功能说明：WorkItem 请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    park_id: Optional[int] = None
    item_type: str = "MANUAL"
    priority: str = "MEDIUM"
    assignee_user_id: Optional[int] = None
    due_at: Optional[str] = None
    sort_order: int = 0
    deep_link: Optional[str] = Field(default=None, max_length=512)


class WorkItemTransition(BaseModel):
    expected_version: int = Field(..., ge=1)
    override_reason: Optional[str] = Field(default=None, max_length=500)


class WorkItemReassign(BaseModel):
    expected_version: int = Field(..., ge=1)
    assignee_user_id: int = Field(..., gt=0)
    reason: str = Field(..., min_length=5, max_length=500)


class BusinessEventEmit(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=96)
    source_type: str = Field(..., min_length=1, max_length=64)
    source_id: str = Field(..., min_length=1, max_length=96)
    idempotency_key: str = Field(..., min_length=8, max_length=192)
    park_id: Optional[int] = Field(default=None, gt=0)
    schema_version: int = Field(default=1, ge=1, le=20)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class RuleCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=1000)
    park_id: Optional[int] = Field(default=None, gt=0)
    event_type: str = Field(..., min_length=1, max_length=96)
    priority: int = Field(default=100, ge=0, le=1000)
    conditions: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    actions: list[dict[str, Any]] = Field(..., min_length=1, max_length=10)


class RuleDraftUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=1000)
    park_id: Optional[int] = Field(default=None, gt=0)
    event_type: Optional[str] = Field(default=None, min_length=1, max_length=96)
    priority: Optional[int] = Field(default=None, ge=0, le=1000)
    conditions: Optional[list[dict[str, Any]]] = Field(default=None, max_length=20)
    actions: Optional[list[dict[str, Any]]] = Field(default=None, min_length=1, max_length=10)


class WorkbenchVersionCommand(BaseModel):
    expected_version: int = Field(..., ge=1)


class NotificationBulkRead(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=100)


class ScheduleCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=128)
    handler_key: str = Field(..., min_length=1, max_length=96)
    parameters: dict[str, Any] = Field(default_factory=dict)
    cadence_seconds: int = Field(..., ge=10, le=2_678_400)
    enabled: bool = False
    concurrency_policy: str = Field(default="FORBID", pattern=r"^(FORBID|ALLOW)$")
    next_run_at: Optional[str] = None
    timeout_seconds: int = Field(default=300, ge=10, le=86_400)
    max_attempts: int = Field(default=3, ge=1, le=10)


class ScheduleUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    parameters: Optional[dict[str, Any]] = None
    cadence_seconds: Optional[int] = Field(default=None, ge=10, le=2_678_400)
    enabled: Optional[bool] = None
    concurrency_policy: Optional[str] = Field(default=None, pattern=r"^(FORBID|ALLOW)$")
    next_run_at: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=10, le=86_400)
    max_attempts: Optional[int] = Field(default=None, ge=1, le=10)


class ScheduleRunRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=192)


class LayoutWidget(BaseModel):
    widget_key: str = Field(..., min_length=1, max_length=64)
    position_x: int = Field(..., ge=0, le=11)
    position_y: int = Field(..., ge=0, le=99)
    width: int = Field(..., ge=1, le=12)
    height: int = Field(..., ge=1, le=12)
    visible: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class LayoutSave(BaseModel):
    expected_version: int = Field(..., ge=0)
    name: str = Field(default="我的工作台", min_length=1, max_length=128)
    widgets: list[LayoutWidget] = Field(..., min_length=1, max_length=20)


class RoleLayoutSave(LayoutSave):
    role_id: int = Field(..., gt=0)
    priority: int = Field(default=100, ge=0, le=1000)
