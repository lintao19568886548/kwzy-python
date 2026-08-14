"""Tenant-safe persistence for CRM assignment, viewing, intent and channel completion."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.investment import (
    Lead,
    LeadAssignmentMember,
    LeadAssignmentRule,
    LeadAssignmentRuleVersion,
    LeadChannel,
    LeadChannelInboxEvent,
    LeadIntentApplication,
    LeadIntentUnit,
    LeadIntentVersion,
    LeadViewing,
    LeadViewingUnit,
)
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.shared.tenant_context import ParkScopeMode, TenantContext


class _TenantParkRepository:
    model: Any = None

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(self.model.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(self.model.park_id.in_(self.ctx.park_ids))
        return stmt.where(False)

    def add(self, model):
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class AssignmentRuleRepository(_TenantParkRepository):
    model = LeadAssignmentRule

    def list(self, *, park_id: int | None = None) -> Sequence[LeadAssignmentRule]:
        stmt = self._scope(select(LeadAssignmentRule))
        if park_id is not None:
            stmt = stmt.where(LeadAssignmentRule.park_id == int(park_id))
        return list(
            self.session.scalars(
                stmt.order_by(
                    LeadAssignmentRule.park_id,
                    LeadAssignmentRule.trigger,
                    LeadAssignmentRule.id,
                )
            ).all()
        )

    def get(self, rule_id: int, *, for_update: bool = False) -> LeadAssignmentRule | None:
        stmt = self._scope(select(LeadAssignmentRule).where(LeadAssignmentRule.id == rule_id))
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def for_trigger(
        self, park_id: int, trigger: str, *, for_update: bool = False
    ) -> LeadAssignmentRule | None:
        stmt = self._scope(
            select(LeadAssignmentRule).where(
                LeadAssignmentRule.park_id == int(park_id),
                LeadAssignmentRule.trigger == trigger,
                LeadAssignmentRule.status == "ACTIVE",
                LeadAssignmentRule.current_version > 0,
            )
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def versions(self, rule_id: int) -> Sequence[LeadAssignmentRuleVersion]:
        return list(
            self.session.scalars(
                select(LeadAssignmentRuleVersion)
                .where(
                    LeadAssignmentRuleVersion.tenant_id == self.ctx.tenant_id,
                    LeadAssignmentRuleVersion.rule_id == int(rule_id),
                )
                .order_by(LeadAssignmentRuleVersion.version.desc())
            ).all()
        )

    def version(
        self, rule_id: int, version: int, *, for_update: bool = False
    ) -> LeadAssignmentRuleVersion | None:
        stmt = select(LeadAssignmentRuleVersion).where(
            LeadAssignmentRuleVersion.tenant_id == self.ctx.tenant_id,
            LeadAssignmentRuleVersion.rule_id == int(rule_id),
            LeadAssignmentRuleVersion.version == int(version),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def draft(self, rule_id: int) -> LeadAssignmentRuleVersion | None:
        return self.session.scalars(
            select(LeadAssignmentRuleVersion).where(
                LeadAssignmentRuleVersion.tenant_id == self.ctx.tenant_id,
                LeadAssignmentRuleVersion.rule_id == int(rule_id),
                LeadAssignmentRuleVersion.status == "DRAFT",
            )
        ).first()

    def members(self, version_id: int) -> Sequence[LeadAssignmentMember]:
        return list(
            self.session.scalars(
                select(LeadAssignmentMember)
                .where(
                    LeadAssignmentMember.tenant_id == self.ctx.tenant_id,
                    LeadAssignmentMember.version_id == int(version_id),
                )
                .order_by(LeadAssignmentMember.member_order, LeadAssignmentMember.user_id)
            ).all()
        )

    def open_counts(self, park_id: int, user_ids: list[int]) -> dict[int, int]:
        if not user_ids:
            return {}
        rows = self.session.execute(
            select(Lead.owner_user_id, func.count(Lead.id))
            .where(
                Lead.tenant_id == self.ctx.tenant_id,
                Lead.park_id == int(park_id),
                Lead.owner_user_id.in_(user_ids),
                Lead.status.in_(["NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING"]),
                Lead.pool_status == "PRIVATE",
            )
            .group_by(Lead.owner_user_id)
        ).all()
        return {int(user_id): int(count) for user_id, count in rows if user_id is not None}

    def user(self, user_id: int) -> User | None:
        return self.session.scalars(
            select(User).where(
                User.tenant_id == self.ctx.tenant_id,
                User.id == int(user_id),
            )
        ).first()

    def create_rule(self, **values: Any) -> LeadAssignmentRule:
        return self.add(LeadAssignmentRule(tenant_id=self.ctx.tenant_id, **values))

    def create_version(self, **values: Any) -> LeadAssignmentRuleVersion:
        row = LeadAssignmentRuleVersion(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def create_member(self, **values: Any) -> LeadAssignmentMember:
        row = LeadAssignmentMember(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def delete_members(self, version_id: int) -> None:
        for row in self.members(version_id):
            self.session.delete(row)

    def save(self, row):
        if int(row.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(row)
        self.session.flush()
        return row


class ViewingRepository(_TenantParkRepository):
    model = LeadViewing

    def list_for_lead(self, lead_id: int) -> Sequence[LeadViewing]:
        stmt = self._scope(select(LeadViewing).where(LeadViewing.lead_id == int(lead_id)))
        return list(
            self.session.scalars(
                stmt.order_by(LeadViewing.starts_at.desc(), LeadViewing.id.desc())
            ).all()
        )

    def get(self, viewing_id: int, *, for_update: bool = False) -> LeadViewing | None:
        stmt = self._scope(select(LeadViewing).where(LeadViewing.id == int(viewing_id)))
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def units(self, viewing_id: int) -> Sequence[LeadViewingUnit]:
        return list(
            self.session.scalars(
                select(LeadViewingUnit)
                .where(
                    LeadViewingUnit.tenant_id == self.ctx.tenant_id,
                    LeadViewingUnit.viewing_id == int(viewing_id),
                )
                .order_by(LeadViewingUnit.unit_id)
            ).all()
        )

    def overlapping(
        self,
        *,
        owner_user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        exclude_id: int | None = None,
    ) -> LeadViewing | None:
        stmt = self._scope(
            select(LeadViewing).where(
                LeadViewing.owner_user_id == int(owner_user_id),
                LeadViewing.status.in_(["SCHEDULED", "CONFIRMED"]),
                LeadViewing.starts_at < ends_at,
                LeadViewing.ends_at > starts_at,
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(LeadViewing.id != int(exclude_id))
        return self.session.scalars(stmt.order_by(LeadViewing.id).limit(1)).first()

    def completion_by_key(self, key: str) -> LeadViewing | None:
        return self.session.scalars(
            self._scope(
                select(LeadViewing).where(LeadViewing.completion_idempotency_key == key)
            )
        ).first()

    def lock_owner(self, user_id: int) -> User | None:
        stmt = select(User).where(
            User.tenant_id == self.ctx.tenant_id,
            User.id == int(user_id),
            User.status == "ACTIVE",
        )
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def create(self, **values: Any) -> LeadViewing:
        return self.add(LeadViewing(tenant_id=self.ctx.tenant_id, **values))

    def add_unit(self, **values: Any) -> LeadViewingUnit:
        row = LeadViewingUnit(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def delete_units(self, viewing_id: int) -> None:
        for row in self.units(viewing_id):
            self.session.delete(row)
        self.session.flush()

    def save(self, row: LeadViewing) -> LeadViewing:
        return self.add(row)


class IntentRepository(_TenantParkRepository):
    model = LeadIntentApplication

    def get_for_lead(
        self, lead_id: int, *, for_update: bool = False
    ) -> LeadIntentApplication | None:
        stmt = self._scope(
            select(LeadIntentApplication).where(LeadIntentApplication.lead_id == int(lead_id))
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get(
        self, intent_id: int, *, for_update: bool = False
    ) -> LeadIntentApplication | None:
        stmt = self._scope(
            select(LeadIntentApplication).where(LeadIntentApplication.id == int(intent_id))
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def versions(self, intent_id: int) -> Sequence[LeadIntentVersion]:
        return list(
            self.session.scalars(
                select(LeadIntentVersion)
                .where(
                    LeadIntentVersion.tenant_id == self.ctx.tenant_id,
                    LeadIntentVersion.application_id == int(intent_id),
                )
                .order_by(LeadIntentVersion.version.desc())
            ).all()
        )

    def version(self, intent_id: int, version: int) -> LeadIntentVersion | None:
        return self.session.scalars(
            select(LeadIntentVersion).where(
                LeadIntentVersion.tenant_id == self.ctx.tenant_id,
                LeadIntentVersion.application_id == int(intent_id),
                LeadIntentVersion.version == int(version),
            )
        ).first()

    def units(self, version_id: int) -> Sequence[LeadIntentUnit]:
        return list(
            self.session.scalars(
                select(LeadIntentUnit)
                .where(
                    LeadIntentUnit.tenant_id == self.ctx.tenant_id,
                    LeadIntentUnit.intent_version_id == int(version_id),
                )
                .order_by(LeadIntentUnit.unit_id)
            ).all()
        )

    def approval(self, approval_id: int) -> ApprovalRequest | None:
        return self.session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.ctx.tenant_id,
                ApprovalRequest.id == int(approval_id),
                ApprovalRequest.biz_type == "LEAD_INTENT",
            )
        ).first()

    def create_application(self, **values: Any) -> LeadIntentApplication:
        return self.add(LeadIntentApplication(tenant_id=self.ctx.tenant_id, **values))

    def create_version(self, **values: Any) -> LeadIntentVersion:
        row = LeadIntentVersion(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def create_unit(self, **values: Any) -> LeadIntentUnit:
        row = LeadIntentUnit(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def save(self, row: LeadIntentApplication) -> LeadIntentApplication:
        return self.add(row)


class ChannelRepository(_TenantParkRepository):
    model = LeadChannel

    def list(self) -> Sequence[LeadChannel]:
        return list(
            self.session.scalars(
                self._scope(select(LeadChannel)).order_by(LeadChannel.code, LeadChannel.id)
            ).all()
        )

    def get(self, channel_id: int, *, for_update: bool = False) -> LeadChannel | None:
        stmt = self._scope(select(LeadChannel).where(LeadChannel.id == int(channel_id)))
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def events(
        self, channel_id: int, *, status: str | None = None, limit: int = 100
    ) -> Sequence[LeadChannelInboxEvent]:
        stmt = select(LeadChannelInboxEvent).where(
            LeadChannelInboxEvent.tenant_id == self.ctx.tenant_id,
            LeadChannelInboxEvent.channel_id == int(channel_id),
        )
        if status:
            stmt = stmt.where(LeadChannelInboxEvent.status == status)
        return list(
            self.session.scalars(
                stmt.order_by(LeadChannelInboxEvent.received_at.desc()).limit(limit)
            ).all()
        )

    def event(self, event_id: int, *, for_update: bool = False) -> LeadChannelInboxEvent | None:
        stmt = select(LeadChannelInboxEvent).where(
            LeadChannelInboxEvent.tenant_id == self.ctx.tenant_id,
            LeadChannelInboxEvent.id == int(event_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def create(self, **values: Any) -> LeadChannel:
        return self.add(LeadChannel(tenant_id=self.ctx.tenant_id, **values))

    def save(self, row: LeadChannel) -> LeadChannel:
        return self.add(row)


class PublicChannelRepository:
    """Lookup only by unguessable public id before a TenantContext exists."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def enabled_by_public_id(self, public_id: str) -> LeadChannel | None:
        return self.session.scalars(
            select(LeadChannel).where(
                LeadChannel.public_id == public_id,
                LeadChannel.enabled.is_(True),
            )
        ).first()

    def event_by_external_id(
        self, channel_id: int, external_event_id: str
    ) -> LeadChannelInboxEvent | None:
        return self.session.scalars(
            select(LeadChannelInboxEvent).where(
                LeadChannelInboxEvent.channel_id == int(channel_id),
                LeadChannelInboxEvent.external_event_id == external_event_id,
            )
        ).first()

    def create_event(self, *, tenant_id: int, **values: Any) -> LeadChannelInboxEvent:
        row = LeadChannelInboxEvent(tenant_id=int(tenant_id), **values)
        self.session.add(row)
        self.session.flush()
        return row

    def save_event(self, row: LeadChannelInboxEvent) -> LeadChannelInboxEvent:
        self.session.add(row)
        self.session.flush()
        return row
