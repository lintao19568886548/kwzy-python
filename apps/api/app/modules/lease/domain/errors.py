"""Stable Lease domain error codes without transport-layer dependencies."""

from __future__ import annotations


class LeaseDomainError(ValueError):
    """A pure-domain validation failure with a stable application error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
