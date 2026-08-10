"""功能说明：写操作幂等键仓储辅助。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.platform import IdempotencyKey

IDEMPOTENCY_KEY_MAX_LEN = 128


def normalize_idempotency_key(raw: Optional[str]) -> Optional[str]:
    """校验并规范化 Idempotency-Key；None 表示调用方未提供。

    空串/纯空白 → 422；超过 128 → 422。不得依赖数据库层报错。
    """

    if raw is None:
        return None
    key = str(raw).strip()
    if not key:
        raise AppError(
            "Idempotency-Key 不能为空",
            code="VALIDATION_ERROR",
            status_code=422,
        )
    if len(key) > IDEMPOTENCY_KEY_MAX_LEN:
        raise AppError(
            f"Idempotency-Key 最长 {IDEMPOTENCY_KEY_MAX_LEN} 字符",
            code="VALIDATION_ERROR",
            status_code=422,
        )
    return key


def request_hash(payload: dict[str, Any]) -> str:
    """稳定规范化 JSON 哈希：sort_keys、紧凑分隔符、ensure_ascii=False。"""

    raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def begin_idempotent(
    session: Session,
    *,
    tenant_id: int,
    user_id: Optional[int],
    operation: str,
    idem_key: str,
    body_hash: str,
) -> Optional[dict[str, Any]]:
    """若已完成则返回缓存响应；否则插入 processing 占位。冲突时抛 409。"""

    dialect = session.bind.dialect.name if session.bind is not None else ""
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.tenant_id == tenant_id,
        IdempotencyKey.operation == operation,
        IdempotencyKey.idem_key == idem_key,
    )
    if dialect == "postgresql":
        stmt = stmt.with_for_update()
    existing = session.scalars(stmt).first()
    if existing is not None:
        if existing.request_hash and existing.request_hash != body_hash:
            raise AppError(
                "幂等键与请求内容不一致",
                code="IDEMPOTENCY_KEY_CONFLICT",
                status_code=409,
            )
        if existing.status == "COMPLETED" and existing.response_json:
            return json.loads(existing.response_json)
        if existing.status == "PROCESSING":
            raise AppError(
                "相同幂等请求正在处理",
                code="IDEMPOTENCY_IN_PROGRESS",
                status_code=409,
            )
        return None

    row = IdempotencyKey(
        tenant_id=tenant_id,
        user_id=user_id,
        operation=operation,
        idem_key=idem_key,
        request_hash=body_hash,
        status="PROCESSING",
        created_at=utc_now(),
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError as exc:
        # Concurrent first insert: re-read winner and apply same rules.
        existing = session.scalars(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.operation == operation,
                IdempotencyKey.idem_key == idem_key,
            )
        ).first()
        if existing is None:
            raise AppError(
                "相同幂等请求冲突",
                code="IDEMPOTENCY_IN_PROGRESS",
                status_code=409,
            ) from exc
        if existing.request_hash and existing.request_hash != body_hash:
            raise AppError(
                "幂等键与请求内容不一致",
                code="IDEMPOTENCY_KEY_CONFLICT",
                status_code=409,
            ) from exc
        if existing.status == "COMPLETED" and existing.response_json:
            return json.loads(existing.response_json)
        raise AppError(
            "相同幂等请求正在处理",
            code="IDEMPOTENCY_IN_PROGRESS",
            status_code=409,
        ) from exc
    return None


def complete_idempotent(
    session: Session,
    *,
    tenant_id: int,
    operation: str,
    idem_key: str,
    resource_type: str,
    resource_id: str,
    response: dict[str, Any],
) -> None:
    row = session.scalars(
        select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.operation == operation,
            IdempotencyKey.idem_key == idem_key,
        )
    ).first()
    if row is None:
        return
    row.status = "COMPLETED"
    row.resource_type = resource_type
    row.resource_id = resource_id
    # store only business data payload (no secrets)
    row.response_json = json.dumps(response, ensure_ascii=False, default=str)
    session.add(row)
    session.flush()
