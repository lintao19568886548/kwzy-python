"""功能说明：租户内并发安全业务编号。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.platform import NumberSequence


def next_number(
    session: Session,
    *,
    tenant_id: int,
    biz_type: str,
    period_key: str = "",
) -> int:
    """分配下一个序号；PostgreSQL 使用行锁，首次插入竞态可重试。"""

    dialect = session.bind.dialect.name if session.bind is not None else ""
    for _ in range(3):
        stmt = select(NumberSequence).where(
            NumberSequence.tenant_id == tenant_id,
            NumberSequence.biz_type == biz_type,
            NumberSequence.period_key == period_key,
        )
        if dialect == "postgresql":
            stmt = stmt.with_for_update()
        row = session.scalars(stmt).first()
        if row is not None:
            value = int(row.next_val)
            row.next_val = value + 1
            row.updated_at = utc_now()
            session.add(row)
            session.flush()
            return value
        try:
            with session.begin_nested():
                row = NumberSequence(
                    tenant_id=tenant_id,
                    biz_type=biz_type,
                    period_key=period_key,
                    next_val=2,
                    updated_at=utc_now(),
                )
                session.add(row)
                session.flush()
            return 1
        except IntegrityError:
            # Concurrent first insert: retry with FOR UPDATE on winner row.
            session.expire_all()
            continue
    raise AppError(
        "业务编号分配冲突，请重试",
        code="NUMBER_SEQUENCE_CONFLICT",
        status_code=409,
    )
