"""功能说明：
    Lease 领域规则：状态机、条款类型、占用投影集合。

业务职责：
    Domain 纯函数；无框架依赖。
"""

from __future__ import annotations

from decimal import Decimal

LEASE_STATUSES = frozenset(
    {
        "DRAFT",
        "PENDING_ACTIVE",
        "ACTIVE",
        "EXPIRING",
        "RENEWED",
        "TERMINATED",
        "BREACHED",
        "CANCELLED",
    }
)

# 有效占用状态：计入 used_area
OCCUPYING_STATUSES = frozenset({"ACTIVE", "EXPIRING"})

TERM_TYPES = frozenset({"INCREASE", "RENT_FREE", "OTHER"})

# 可编辑主档/行的状态
EDITABLE_STATUSES = frozenset({"DRAFT", "PENDING_ACTIVE"})

_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"PENDING_ACTIVE", "CANCELLED"}),
    "PENDING_ACTIVE": frozenset({"ACTIVE", "DRAFT", "CANCELLED"}),
    "ACTIVE": frozenset({"EXPIRING", "RENEWED", "TERMINATED", "BREACHED"}),
    "EXPIRING": frozenset({"RENEWED", "TERMINATED", "BREACHED", "ACTIVE"}),
    "RENEWED": frozenset(),
    "TERMINATED": frozenset(),
    "BREACHED": frozenset(),
    "CANCELLED": frozenset(),
}

# 单元可被新合同占用的状态
UNIT_RENTABLE_STATUSES = frozenset({"VACANT", "RESERVED", "OCCUPIED"})

DEFAULT_EXPIRING_DAYS = 30


def assert_lease_status(status: str) -> str:
    """功能说明：
        校验并规范化合同状态。

    业务职责：
        Domain 不变量。

    输入参数：
        status：原始状态。

    返回结果：
        大写状态。

    异常说明：
        ValueError：非法状态。

    业务规则：
        必须属于 LEASE_STATUSES。
    """

    s = (status or "").strip().upper()
    if s not in LEASE_STATUSES:
        raise ValueError(f"invalid lease status: {status}")
    return s


def assert_status_transition(current: str, new: str) -> str:
    """功能说明：
        校验合同状态迁移。

    业务职责：
        Domain 状态机。

    输入参数：
        current：当前状态。
        new：目标状态。

    返回结果：
        规范化目标状态。

    异常说明：
        ValueError：非法迁移。

    业务规则：
        见 _STATUS_TRANSITIONS；同态合法。
    """

    cur = assert_lease_status(current)
    nxt = assert_lease_status(new)
    if cur == nxt:
        return nxt
    allowed = _STATUS_TRANSITIONS.get(cur, frozenset())
    if nxt not in allowed:
        raise ValueError(f"illegal lease transition {cur} -> {nxt}")
    return nxt


def assert_term_type(term_type: str) -> str:
    """功能说明：
        校验条款类型枚举。

    业务职责：
        Domain 不变量。

    输入参数：
        term_type：INCREASE/RENT_FREE/OTHER。

    返回结果：
        大写类型。

    异常说明：
        ValueError。

    业务规则：
        属于 TERM_TYPES。
    """

    t = (term_type or "").strip().upper()
    if t not in TERM_TYPES:
        raise ValueError(f"invalid term_type: {term_type}")
    return t


def is_occupying_status(status: str) -> bool:
    """功能说明：
        状态是否计入 used_area 投影。

    业务职责：
        Domain 投影集合判定。

    输入参数：
        status：合同状态。

    返回结果：
        True 表示 ACTIVE/EXPIRING。

    异常说明：
        无（非法状态返回 False）。

    业务规则：
        仅 OCCUPYING_STATUSES。
    """

    try:
        return assert_lease_status(status) in OCCUPYING_STATUSES
    except ValueError:
        return False


def is_editable_status(status: str) -> bool:
    """功能说明：
        合同主档与行是否允许业务编辑。

    业务职责：
        Domain 写策略。

    输入参数：
        status：合同状态。

    返回结果：
        DRAFT/PENDING_ACTIVE 为 True。

    异常说明：
        无。

    业务规则：
        激活后不可改占用行（须先 terminate）。
    """

    try:
        return assert_lease_status(status) in EDITABLE_STATUSES
    except ValueError:
        return False


def assert_positive_area(area: Decimal | float | int | str) -> Decimal:
    """功能说明：
        校验占用面积为非负 Decimal。

    业务职责：
        Domain 数量校验。

    输入参数：
        area：面积。

    返回结果：
        Decimal。

    异常说明：
        ValueError：负数。

    业务规则：
        area >= 0。
    """

    value = Decimal(str(area))
    if value < 0:
        raise ValueError("occupied_area must be >= 0")
    return value


def assert_capacity(
    rentable_area: Decimal | None,
    current_used: Decimal,
    additional: Decimal,
) -> None:
    """功能说明：
        校验新增占用是否超过可租面积。

    业务职责：
        Domain 冲突预检辅助。

    输入参数：
        rentable_area：可租面积；None/0 时跳过容量校验。
        current_used：当前有效占用合计。
        additional：拟新增占用。

    返回结果：
        None。

    异常说明：
        ValueError：超容。

    业务规则：
        rentable>0 时 current+additional <= rentable。
    """

    if rentable_area is None:
        return
    cap = Decimal(str(rentable_area))
    if cap <= 0:
        return
    used = Decimal(str(current_used))
    add = Decimal(str(additional))
    if used + add > cap:
        raise ValueError(
            f"occupancy exceeds rentable_area: used={used} + add={add} > {cap}"
        )
