"""HTTP 请求关联 ID 的上下文传播。"""

from __future__ import annotations

from contextvars import ContextVar
import logging
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-Id"
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
logger = logging.getLogger(__name__)


def get_request_id() -> str:
    """返回当前请求关联 ID；非请求上下文返回空字符串。"""

    return request_id_var.get()


def _resolve_request_id(raw: str | None) -> str:
    value = (raw or "").strip()
    if value and len(value) <= 64:
        return value
    return uuid4().hex


class RequestIdMiddleware:
    """读取或生成请求 ID，并在响应头中回写。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = _resolve_request_id(headers.get(REQUEST_ID_HEADER))
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception(
                "未处理的服务器异常",
                extra={
                    "request_id": request_id,
                    "business_module": "api",
                    "action": "request",
                    "code": "INTERNAL_ERROR",
                },
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误",
                    "data": None,
                },
                headers={REQUEST_ID_HEADER: request_id},
            )
            await response(scope, receive, send)
        finally:
            request_id_var.reset(token)
