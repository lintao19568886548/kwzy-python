"""Application ports for Lease-managed domain approvals."""

from __future__ import annotations

from typing import Any, Optional, Protocol, Sequence


class ApprovalCommandPort(Protocol):
    """Commit-free approval commands composed into a Lease transaction."""

    def submit(
        self,
        *,
        park_id: int,
        biz_type: str,
        biz_id: str,
        title: str,
        remark: Optional[str],
    ) -> Any: ...

    def decide(
        self,
        approval_id: int,
        *,
        approve: bool,
        remark: Optional[str],
        override_reason: Optional[str] = None,
    ) -> Any: ...

    def withdraw(self, approval_id: int, *, remark: Optional[str]) -> Any: ...

    def get(self, approval_id: int, *, for_update: bool = False) -> Any: ...

    def events(self, approval_id: int) -> Sequence[Any]: ...

    def timeline_for_contract(
        self, contract_id: int, *, related_approval_ids: set[int]
    ) -> Sequence[dict[str, Any]]: ...
