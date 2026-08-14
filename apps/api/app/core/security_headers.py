"""Small ASGI middleware for response security headers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class SecurityHeadersMiddleware:
    def __init__(self, app, *, production_like: bool = False) -> None:
        self.app = app
        self.production_like = production_like

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (b"content-security-policy", b"frame-ancestors 'none'; base-uri 'none'"),
                    ]
                )
                if path.startswith("/api/v1/auth/"):
                    headers.append((b"cache-control", b"no-store"))
                if self.production_like:
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
