"""Narrow collaboration ports owned by the Lease application boundary."""

from __future__ import annotations

from typing import Any, Optional, Protocol


class AttachmentEvidencePort(Protocol):
    def get(self, attachment_id: int) -> Any | None: ...


class PartyEligibilityPort(Protocol):
    def get_by_id(self, party_id: int) -> Any | None: ...


class LeaseWorkItemPort(Protocol):
    def ensure_from_source(self, **kwargs: Any) -> dict[str, Any]: ...

    def complete_by_source(self, **kwargs: Any) -> Optional[dict[str, Any]]: ...

    def cancel_by_source(self, **kwargs: Any) -> Optional[dict[str, Any]]: ...


class BusinessEventPublisherPort(Protocol):
    """Publish a registered event in the caller-owned transaction."""

    def emit(self, **kwargs: Any) -> dict[str, Any]: ...
