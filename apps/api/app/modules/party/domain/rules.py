"""功能说明：
    Party 领域规则与状态校验（纯函数，无框架依赖）。

业务职责：
    Domain 层；提供类型/状态/信用代码/地址策略等不变量校验。
"""

from __future__ import annotations

import re

PARTY_TYPES = frozenset({"ORGANIZATION", "PERSON"})
PARTY_STATUSES = frozenset({"ACTIVE", "INACTIVE", "ARCHIVED"})
RISK_STATUSES = frozenset({"NORMAL", "BLACKLISTED"})
ROLE_CODES = frozenset(
    {"PROPERTY_OWNER", "LESSEE", "BROKER", "SUPPLIER", "PARTNER", "CUSTOMER"}
)
ADDRESS_TYPES = frozenset({"REGISTERED", "OFFICE", "MAILING", "BILLING", "OTHER"})
RELATION_STATUSES = frozenset({"ACTIVE", "ENDED"})
ROLE_STATUSES = frozenset({"ACTIVE", "INACTIVE"})

# Lifecycle transitions allowed
_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "ACTIVE": frozenset({"INACTIVE", "ARCHIVED"}),
    "INACTIVE": frozenset({"ACTIVE", "ARCHIVED"}),
    "ARCHIVED": frozenset({"ACTIVE", "INACTIVE"}),
}

# Loose USCC check: 18 chars alphanumeric (GB 32100 simplified)
_CREDIT_CODE_RE = re.compile(r"^[0-9A-Z]{18}$")


def normalize_credit_code(raw: str | None) -> str | None:
    """功能说明：
        规范化统一社会信用代码（trim + upper，空串→None）。

    业务职责：
        Domain 规则；写入前消除大小写与空白差异。

    输入参数：
        raw：原始信用代码，可空。

    返回结果：
        规范化后的 18 位大写字符串；空输入返回 None。

    异常说明：
        无（不校验格式，格式由 validate_credit_code_format 负责）。

    业务规则：
        1. None 或仅空白 → None。
        2. 仅 strip + upper，不截断、不补位。
    """

    if raw is None:
        return None
    value = str(raw).strip().upper()
    if not value:
        return None
    return value


def validate_credit_code_format(code: str | None) -> None:
    """功能说明：
        非空时校验统一社会信用代码格式。

    业务职责：
        Domain 规则；简化 GB 32100（18 位大写字母数字）。

    输入参数：
        code：已规范化或待校验代码，可空。

    返回结果：
        None；校验通过不返回值。

    异常说明：
        ValueError：非空且不符合 ^[0-9A-Z]{18}$。

    业务规则：
        1. code 为 None 时跳过（允许无信用代码主体）。
        2. 不负责唯一性（唯一性由仓储/数据库约束保证）。
    """

    if code is None:
        return
    if not _CREDIT_CODE_RE.match(code):
        raise ValueError("credit_code format invalid")


def assert_party_type(party_type: str) -> str:
    """功能说明：
        校验并规范化主体类型枚举。

    业务职责：
        Domain 不变量；允许 ORGANIZATION / PERSON。

    输入参数：
        party_type：原始类型字符串。

    返回结果：
        大写规范化后的 party_type。

    异常说明：
        ValueError：不在 PARTY_TYPES 内。

    业务规则：
        strip + upper 后必须属于 {ORGANIZATION, PERSON}。
    """

    t = (party_type or "").strip().upper()
    if t not in PARTY_TYPES:
        raise ValueError(f"invalid party_type: {party_type}")
    return t


def assert_party_status(status: str) -> str:
    """功能说明：
        校验并规范化主体生命周期状态。

    业务职责：
        Domain 不变量；ACTIVE / INACTIVE / ARCHIVED。

    输入参数：
        status：原始状态字符串。

    返回结果：
        大写规范化后的 status。

    异常说明：
        ValueError：不在 PARTY_STATUSES 内。

    业务规则：
        strip + upper 后必须属于 {ACTIVE, INACTIVE, ARCHIVED}。
    """

    s = (status or "").strip().upper()
    if s not in PARTY_STATUSES:
        raise ValueError(f"invalid party status: {status}")
    return s


def assert_status_transition(current: str, new: str) -> str:
    """功能说明：
        校验主体生命周期状态迁移是否合法。

    业务职责：
        Domain 状态机；禁止非法迁移。

    输入参数：
        current：当前状态。
        new：目标状态。

    返回结果：
        规范化后的目标状态。

    异常说明：
        ValueError：状态非法或迁移不在允许表内。

    业务规则：
        1. ACTIVE ↔ INACTIVE；二者均可 → ARCHIVED；ARCHIVED → ACTIVE/INACTIVE。
        2. 相同状态视为合法（幂等）。
    """

    cur = assert_party_status(current)
    nxt = assert_party_status(new)
    if cur == nxt:
        return nxt
    allowed = _STATUS_TRANSITIONS.get(cur, frozenset())
    if nxt not in allowed:
        raise ValueError(f"illegal status transition {cur} -> {nxt}")
    return nxt


def assert_risk_status(status: str) -> str:
    """功能说明：
        校验并规范化风险状态枚举。

    业务职责：
        Domain 不变量；NORMAL / BLACKLISTED。

    输入参数：
        status：原始风险状态。

    返回结果：
        大写规范化后的 risk_status。

    异常说明：
        ValueError：不在 RISK_STATUSES 内。

    业务规则：
        风险状态变更应走专用用例（blacklist/remove-blacklist），本函数仅校验枚举。
    """

    s = (status or "").strip().upper()
    if s not in RISK_STATUSES:
        raise ValueError(f"invalid risk_status: {status}")
    return s


def assert_role_code(code: str) -> str:
    """功能说明：
        校验并规范化 Party 业务角色码（非 RBAC）。

    业务职责：
        Domain 不变量；限定 ROLE_CODES 集合。

    输入参数：
        code：原始角色码。

    返回结果：
        大写规范化后的 role_code。

    异常说明：
        ValueError：不在 ROLE_CODES 内。

    业务规则：
        角色码与权限码独立；仅表示业务身份（如 LESSEE）。
    """

    c = (code or "").strip().upper()
    if c not in ROLE_CODES:
        raise ValueError(f"invalid role_code: {code}")
    return c


def assert_address_type(address_type: str) -> str:
    """功能说明：
        校验并规范化地址类型枚举。

    业务职责：
        Domain 不变量；REGISTERED/OFFICE/MAILING/BILLING/OTHER。

    输入参数：
        address_type：原始地址类型。

    返回结果：
        大写规范化后的 address_type。

    异常说明：
        ValueError：不在 ADDRESS_TYPES 内。

    业务规则：
        与 party_addresses.address_type 及同类型 primary 唯一约束配合使用。
    """

    t = (address_type or "").strip().upper()
    if t not in ADDRESS_TYPES:
        raise ValueError(f"invalid address_type: {address_type}")
    return t


def is_person_address_forbidden(party_type: str) -> bool:
    """功能说明：
        v1 是否对 PERSON 主体禁用全部地址读写。

    业务职责：
        Domain 策略判定；供 Application 在读写地址前强制执行。

    输入参数：
        party_type：主体类型（可大小写混用）。

    返回结果：
        True 表示禁止 PERSON 地址访问；False 表示 ORGANIZATION 等不受此限。

    异常说明：
        ValueError：party_type 非法（经 assert_party_type）。

    业务规则：
        1. KMS/字段加密/专用 PII 权限落地前，PERSON 地址一律不可访问。
        2. ORGANIZATION 不受此规则限制。
        3. 不引入临时 party:pii:* 权限码。
    """

    return assert_party_type(party_type) == "PERSON"
