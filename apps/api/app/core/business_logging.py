"""业务日志字段统一封装。"""

from __future__ import annotations

import logging

from app.shared.tenant_context import TenantContext


def log_business_success(
    logger: logging.Logger,
    message: str,
    *,
    ctx: TenantContext,
    module: str,
    action: str,
    resource_id: int | str | None,
    park_id: int | None = None,
) -> None:
    """输出符合冻结字段契约的成功 INFO 日志。

    规范字段名为 module；LogRecord 保留属性 module 冲突，
    因此记录业务模块到 business_module，并由 formatter 输出 module，
    过渡期双写 business_module 便于旧消费者。
    """

    logger.info(
        message,
        extra={
            "request_id": ctx.request_id,
            "user_id": ctx.user_id,
            "tenant_id": ctx.tenant_id,
            "park_id": park_id,
            # 规范主字段：经 formatter 映射为 JSON module
            "business_module": module,
            "action": action,
            "resource_id": resource_id,
        },
    )
