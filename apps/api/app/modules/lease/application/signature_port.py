"""Electronic-signature boundary for Lease documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SignatureResult:
    provider: str
    signature_ref: str
    live_verified: bool


class SignaturePort(Protocol):
    def sign(self, *, document_id: int, checksum: str) -> SignatureResult: ...
