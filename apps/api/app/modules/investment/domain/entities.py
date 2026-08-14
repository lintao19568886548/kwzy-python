"""Investment CRM domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass(slots=True)
class LeadEntity:
    tenant_id: int
    park_id: int
    name: str
    contact_phone: str
    normalized_name: str
    normalized_phone: str
    status: str = "NEW"
    pool_status: str = "PRIVATE"
    source_type: str = "MANUAL"
    id: Optional[int] = None
    contact_name: Optional[str] = None
    agent_name: Optional[str] = None
    intent_level: Optional[str] = None
    intent_area: Optional[Decimal] = None
    desired_usage: Optional[str] = None
    budget_unit_price: Optional[Decimal] = None
    source_ref: Optional[str] = None
    duplicate_override_reason: Optional[str] = None
    remark: Optional[str] = None
    owner_user_id: Optional[int] = None
    party_id: Optional[int] = None
    lease_id: Optional[int] = None
    merged_into_lead_id: Optional[int] = None
    lost_reason: Optional[str] = None
    assigned_at: Optional[datetime] = None
    first_contact_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None
    recycle_due_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None
    lock_version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(slots=True)
class LeadActivityEntity:
    tenant_id: int
    park_id: int
    lead_id: int
    activity_type: str
    occurred_at: datetime
    id: Optional[int] = None
    actor_user_id: Optional[int] = None
    content: Optional[str] = None
    next_follow_up_at: Optional[datetime] = None
    stage_from: Optional[str] = None
    stage_to: Optional[str] = None
    attributes_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LeadAssignmentEventEntity:
    tenant_id: int
    park_id: int
    lead_id: int
    event_type: str
    occurred_at: datetime
    id: Optional[int] = None
    from_owner_user_id: Optional[int] = None
    to_owner_user_id: Optional[int] = None
    reason: Optional[str] = None
    actor_user_id: Optional[int] = None
    rule_version_id: Optional[int] = None
    trigger: Optional[str] = None
    decision_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LeadMergeLinkEntity:
    tenant_id: int
    park_id: int
    source_lead_id: int
    target_lead_id: int
    actor_user_id: Optional[int]
    reason: str
    merged_at: datetime
    id: Optional[int] = None


@dataclass(slots=True)
class LeadUnitLockEntity:
    tenant_id: int
    park_id: int
    lead_id: int
    unit_id: int
    expires_at: datetime
    id: Optional[int] = None
    lease_id: Optional[int] = None
    status: str = "ACTIVE"
    released_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None
    created_by: Optional[int] = None
    lock_version: int = 1
    intent_application_id: Optional[int] = None
    intent_version_id: Optional[int] = None


@dataclass(frozen=True, slots=True)
class AssignmentMemberSpec:
    user_id: int
    capacity: int
    weight: int = 1
    member_order: int = 1
    open_count: int = 0
    last_assigned_at: Optional[datetime] = None
    eligible: bool = True
    exclusion_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ViewingWindow:
    starts_at: datetime
    ends_at: datetime
    unit_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class IntentUnitSnapshot:
    unit_id: int
    unit_version: int
    requested_area: Decimal


@dataclass(frozen=True, slots=True)
class IntentSnapshot:
    starts_on: date
    ends_on: date
    valid_until: datetime
    proposed_unit_price: Decimal
    currency: str
    units: tuple[IntentUnitSnapshot, ...]
    remark: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ChannelSignatureEnvelope:
    timestamp: int
    external_event_id: str
    body_sha256: str

    def signing_input(self) -> bytes:
        return (
            f"v1\n{self.timestamp}\n{self.external_event_id}\n{self.body_sha256}"
        ).encode("utf-8")
