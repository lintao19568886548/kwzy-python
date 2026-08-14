"""Request-scoped tenant / data-scope context.

功能说明：
    承载请求级租户、动作权限与园区数据范围。

业务职责：
    横切共享；Repository 与鉴权依赖的唯一数据范围来源。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ParkScopeMode(str, Enum):
    """园区数据范围模式：与动作权限完全正交。"""

    NONE = "NONE"
    LIST = "LIST"
    ALL = "ALL"


@dataclass
class TenantContext:
    """功能说明：
        多租户 + 动作权限 + 园区范围上下文。

    业务职责：
        1. tenant_id 始终由鉴权解析并强制 > 0。
        2. permissions 仅表示动作权限；`*` 仅表示全部动作。
        3. 园区范围由 park_scope_mode 表达，不得由 `*` 推导。
        4. NONE 或 LIST 空列表均拒绝园区数据访问。
    """

    tenant_id: int
    user_id: int = 0
    username: str = "system"
    park_ids: list[int] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    database_permissions: list[str] | None = None
    park_scope_mode: ParkScopeMode = ParkScopeMode.NONE
    is_platform_admin: bool = False
    request_id: str = ""
    client_ip: str | None = None

    def __post_init__(self) -> None:
        if self.tenant_id is None or int(self.tenant_id) <= 0:
            raise ValueError("tenant_id must be a positive integer")
        self.tenant_id = int(self.tenant_id)
        self.park_ids = [int(p) for p in (self.park_ids or [])]
        if isinstance(self.park_scope_mode, str):
            self.park_scope_mode = ParkScopeMode(self.park_scope_mode)
        # Normalize mode if list non-empty but mode unset incorrectly
        if self.park_scope_mode == ParkScopeMode.NONE and self.park_ids:
            self.park_scope_mode = ParkScopeMode.LIST

    @property
    def has_all_park_access(self) -> bool:
        """功能说明：是否拥有租户内全部园区数据范围。"""

        return self.park_scope_mode == ParkScopeMode.ALL

    def allows_park(self, park_id: int) -> bool:
        """功能说明：判断是否可访问指定园区数据。"""

        if self.park_scope_mode == ParkScopeMode.ALL:
            return True
        if self.park_scope_mode == ParkScopeMode.LIST:
            return int(park_id) in self.park_ids
        return False

    def has_permission(self, permission_code: str) -> bool:
        """判断动作权限；高风险平台权限同时受当前数据库授权约束。"""

        permissions = self.permissions or []
        token_allows = "*" in permissions or permission_code in permissions
        if not token_allows:
            return False
        sensitive = permission_code.startswith(
            (
                "automation.",
                "scheduler.",
                "event.",
                "workbench.layout.",
                "notification.",
                "asset.template.",
                "lead.assignment_rule.",
                "lead.viewing.",
                "lead.intent.",
                "lead.channel.",
                "party:credential_",
                "work_order:",
                "tenant_service:",
                "facility_device:",
                "inspection:",
                "iot:",
                "record:",
                "seal:",
                "signature:",
            )
        ) or permission_code in {
            "party:risk_read",
            "party:risk_manage",
            "work_item:reassign",
            "work_item:override_source",
        }
        if not sensitive or self.database_permissions is None:
            return True
        grants = self.database_permissions or []
        return "*" in grants or permission_code in grants
