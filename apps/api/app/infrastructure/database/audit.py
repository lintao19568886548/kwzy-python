"""关键业务写操作的事务内审计记录器。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models.audit import AuditLog
from app.shared.tenant_context import TenantContext


class AuditRecorder:
    """使用业务 Session 写入审计，随业务事务一起提交或回滚。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: int | str | None,
        park_id: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditLog:
        """创建并 flush 一条不含敏感信息的审计记录。"""

        audit = AuditLog(
            tenant_id=self.ctx.tenant_id,
            user_id=self.ctx.user_id or None,
            request_id=self.ctx.request_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            park_id=park_id,
            detail_json=detail,
            client_ip=self.ctx.client_ip,
        )
        self.session.add(audit)
        self.session.flush()
        return audit
