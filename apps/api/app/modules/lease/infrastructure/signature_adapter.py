"""Explicit local fake and production fail-closed signature adapters."""

from __future__ import annotations

import hashlib

from app.core.errors import AppError
from app.modules.lease.application.signature_port import SignatureResult


class LocalFakeSignatureAdapter:
    def sign(self, *, document_id: int, checksum: str) -> SignatureResult:
        digest = hashlib.sha256(f"fake:{document_id}:{checksum}".encode()).hexdigest()[:24]
        return SignatureResult(
            provider="fake",
            signature_ref=f"SIMULATED-{digest}",
            live_verified=False,
        )


class FailClosedSignatureAdapter:
    def sign(self, *, document_id: int, checksum: str) -> SignatureResult:
        del document_id, checksum
        raise AppError(
            "电子签章服务未配置",
            code="SIGNATURE_PROVIDER_NOT_CONFIGURED",
            status_code=503,
        )
