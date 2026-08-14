"""Closed registries for safe workbench automation."""

from __future__ import annotations

from typing import Final

REGISTERED_EVENTS: Final[dict[str, frozenset[str]]] = {
    "LEASE_ACTIVATED": frozenset(
        {"title", "description", "priority", "assignee_user_id", "due_at", "deep_link", "park_id"}
    ),
    "LEASE_TERMINATED": frozenset({"title", "description", "deep_link", "park_id"}),
    "BILL_ISSUED": frozenset(
        {
            "title",
            "description",
            "priority",
            "assignee_user_id",
            "recipient_user_id",
            "amount",
            "due_at",
            "deep_link",
            "park_id",
        }
    ),
    "BILL_SETTLED": frozenset({"title", "description", "amount", "deep_link", "park_id"}),
    "APPROVAL_TASK_OVERDUE": frozenset(
        {"title", "description", "priority", "assignee_user_id", "deep_link", "park_id"}
    ),
    "LEAD_CREATED": frozenset(
        {"title", "description", "priority", "assignee_user_id", "due_at", "deep_link", "park_id"}
    ),
    "LEAD_CONVERTED": frozenset({"title", "description", "deep_link", "park_id"}),
    "WORK_ORDER_CREATED": frozenset(
        {"title", "description", "priority", "assignee_user_id", "due_at", "deep_link", "park_id"}
    ),
    "WORK_ORDER_COMPLETED": frozenset({"title", "description", "deep_link", "park_id"}),
    "TEST_AUTOMATION_EVENT": frozenset(
        {
            "title",
            "description",
            "priority",
            "assignee_user_id",
            "recipient_user_id",
            "amount",
            "status",
            "due_at",
            "deep_link",
            "category",
            "park_id",
        }
    ),
}

REGISTERED_CONSUMERS: Final[frozenset[str]] = frozenset({"WORKBENCH_AUTOMATION"})
REGISTERED_COMPARATORS: Final[frozenset[str]] = frozenset(
    {"EQ", "NE", "IN", "GT", "GTE", "LT", "LTE"}
)
REGISTERED_ACTIONS: Final[frozenset[str]] = frozenset(
    {"CREATE_WORK_ITEM", "CREATE_NOTIFICATION"}
)
REGISTERED_HANDLERS: Final[frozenset[str]] = frozenset(
    {"OUTBOX_DISPATCH", "LEASE_TODO_SYNC", "APPROVAL_OVERDUE_SWEEP"}
)

WIDGET_REGISTRY: Final[dict[str, dict[str, str]]] = {
    "OPERATIONS_METRICS": {"title": "运营总览", "permission": "work_item:read"},
    "MY_TODOS": {"title": "我的待办", "permission": "work_item:read"},
    "NOTIFICATIONS": {"title": "消息中心", "permission": "notification.read"},
    "AUTOMATION_HEALTH": {"title": "自动化健康", "permission": "automation.rule.read"},
    "UNPAID_BILLS": {"title": "未结账单", "permission": "bill:read"},
    "EXPIRING_CONTRACTS": {"title": "即将到期合同", "permission": "lease:read"},
}

DEFAULT_WIDGETS: Final[list[dict[str, object]]] = [
    {"widget_key": "OPERATIONS_METRICS", "position_x": 0, "position_y": 0, "width": 12, "height": 2},
    {"widget_key": "MY_TODOS", "position_x": 0, "position_y": 2, "width": 8, "height": 4},
    {"widget_key": "NOTIFICATIONS", "position_x": 8, "position_y": 2, "width": 4, "height": 4},
    {"widget_key": "AUTOMATION_HEALTH", "position_x": 0, "position_y": 6, "width": 4, "height": 2},
    {"widget_key": "UNPAID_BILLS", "position_x": 4, "position_y": 6, "width": 4, "height": 2},
    {"widget_key": "EXPIRING_CONTRACTS", "position_x": 8, "position_y": 6, "width": 4, "height": 2},
]

SAFE_DEEP_LINK_PREFIXES: Final[tuple[str, ...]] = (
    "/workbench",
    "/todos",
    "/leases",
    "/bills",
    "/approvals",
    "/leads",
    "/work-orders",
    "/facility-operations",
    "/records-seal",
    "/collection",
)


def is_safe_deep_link(value: str | None) -> bool:
    if value is None or value == "":
        return True
    return value.startswith(SAFE_DEEP_LINK_PREFIXES) and "://" not in value and "\\" not in value
