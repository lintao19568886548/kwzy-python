"""标准库 JSON 日志配置。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

# LogRecord.module 是保留字段，业务模块写入 business_module，JSON 输出 module。
# 过渡期双写 business_module 兼容旧消费方。
BUSINESS_FIELDS = {
    "request_id": "request_id",
    "user_id": "user_id",
    "tenant_id": "tenant_id",
    "park_id": "park_id",
    "action": "action",
    "resource_id": "resource_id",
    "code": "code",
}


class JsonFormatter(logging.Formatter):
    """输出稳定字段的单行 JSON 日志。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for output_field, record_field in BUSINESS_FIELDS.items():
            value = getattr(record, record_field, None)
            if value is not None:
                payload[output_field] = value

        business_module = getattr(record, "business_module", None)
        if business_module is not None:
            payload["module"] = business_module
            # 过渡期双写
            payload["business_module"] = business_module

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(debug: bool = False) -> None:
    """幂等配置应用 JSON 日志处理器。"""

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    if any(getattr(handler, "_kwzy_json", False) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._kwzy_json = True  # type: ignore[attr-defined]
    root.addHandler(handler)
