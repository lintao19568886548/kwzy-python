"""Fail-closed guard against ambiguous HTTP query parameter pollution."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl

from starlette.responses import JSONResponse


class QueryParameterGuardMiddleware:
    """Reject duplicate names because endpoints only accept scalar query values."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        raw = scope.get("query_string") or b""
        try:
            pairs = parse_qsl(raw.decode("utf-8", errors="strict"), keep_blank_values=True)
        except (UnicodeDecodeError, ValueError):
            response = JSONResponse(
                status_code=400,
                content={
                    "code": "INVALID_QUERY_STRING",
                    "message": "查询参数编码无效",
                    "data": None,
                },
            )
            await response(scope, receive, send)
            return

        seen: set[str] = set()
        duplicate = next((name for name, _ in pairs if name in seen or seen.add(name)), None)
        if duplicate is not None:
            response = JSONResponse(
                status_code=400,
                content={
                    "code": "DUPLICATE_QUERY_PARAMETER",
                    "message": "查询参数不得重复",
                    "data": {"parameter": duplicate},
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
