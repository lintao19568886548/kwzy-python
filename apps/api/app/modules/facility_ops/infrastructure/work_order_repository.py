"""功能说明：WorkOrder 仓储。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.facility_ops import (
    TenantServicePrincipal,
    TenantServicePrincipalPark,
    WorkOrder,
    WorkOrderAcceptance,
    WorkOrderAssignmentRule,
    WorkOrderCostEntry,
    WorkOrderEvent,
    WorkOrderQuote,
    WorkOrderQuoteLine,
    WorkOrderRating,
)
from app.infrastructure.database.models.identity import User, UserParkScope
from app.infrastructure.database.models.park_property import Park, Unit
from app.infrastructure.database.models.party import Party, PartyContact, PartyParkRelation
from app.shared.tenant_context import ParkScopeMode, TenantContext


class WorkOrderRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(WorkOrder.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(WorkOrder.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        park_id: int | None = None,
        party_id: int | None = None,
        category: str | None = None,
        assignee_user_id: int | None = None,
    ) -> Sequence[WorkOrder]:
        stmt = self._scope(select(WorkOrder))
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        if park_id is not None:
            stmt = stmt.where(WorkOrder.park_id == int(park_id))
        if party_id is not None:
            stmt = stmt.where(WorkOrder.party_id == int(party_id))
        if category:
            stmt = stmt.where(WorkOrder.category == str(category))
        if assignee_user_id is not None:
            stmt = stmt.where(WorkOrder.assignee_user_id == int(assignee_user_id))
        return list(
            self.session.scalars(stmt.order_by(WorkOrder.id.desc()).offset(offset).limit(limit)).all()
        )

    def count(
        self,
        *,
        status: str | None = None,
        park_id: int | None = None,
        party_id: int | None = None,
        category: str | None = None,
        assignee_user_id: int | None = None,
    ) -> int:
        vis = self._scope(select(WorkOrder.id))
        if status:
            vis = vis.where(WorkOrder.status == status)
        if park_id is not None:
            vis = vis.where(WorkOrder.park_id == int(park_id))
        if party_id is not None:
            vis = vis.where(WorkOrder.party_id == int(party_id))
        if category:
            vis = vis.where(WorkOrder.category == str(category))
        if assignee_user_id is not None:
            vis = vis.where(WorkOrder.assignee_user_id == int(assignee_user_id))
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, work_order_id: int, *, for_update: bool = False) -> WorkOrder | None:
        stmt = self._scope(select(WorkOrder).where(WorkOrder.id == work_order_id))
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get_by_source(self, source_type: str, source_id: str) -> WorkOrder | None:
        return self.session.scalars(
            self._scope(
                select(WorkOrder).where(
                    WorkOrder.source_type == source_type,
                    WorkOrder.source_id == source_id,
                )
            )
        ).first()

    def add(self, model: WorkOrder) -> WorkOrder:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def create(
        self,
        *,
        park_id: int,
        order_no: str,
        party_id: int | None,
        contact_id: int | None,
        contact_name: str | None,
        contact_phone_masked: str | None,
        title: str,
        description: str | None,
        category: str,
        priority: str,
        reporter_user_id: int | None,
        assignee_user_id: int | None,
        unit_id: int | None,
        due_at,
        source_type: str,
        source_id: str,
        quote_required: bool,
        status: str,
        assignment_rule_id: int | None,
        assignment_rule_version: int | None,
        response_due_at: datetime | None,
        resolution_due_at: datetime | None,
    ) -> WorkOrder:
        model = WorkOrder(
            park_id=park_id,
            order_no=order_no,
            party_id=party_id,
            contact_id=contact_id,
            contact_name=contact_name,
            contact_phone_masked=contact_phone_masked,
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status,
            reporter_user_id=reporter_user_id,
            assignee_user_id=assignee_user_id,
            unit_id=unit_id,
            due_at=due_at,
            source_type=source_type,
            source_id=source_id,
            quote_required=quote_required,
            assignment_rule_id=assignment_rule_id,
            assignment_rule_version=assignment_rule_version,
            response_due_at=response_due_at,
            resolution_due_at=resolution_due_at,
            evidence_refs_json=[],
            lock_version=1,
        )
        return self.add(model)

    def save(self, model: WorkOrder) -> WorkOrder:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class ServiceLifecycleRepository:
    """Persistence gateway for principal, dispatch, timeline, quote and acceptance evidence."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return int(self.ctx.tenant_id)

    def user(self, user_id: int) -> User | None:
        return self.session.scalar(
            select(User).where(
                User.tenant_id == self.tenant_id,
                User.id == int(user_id),
                User.status == "ACTIVE",
            )
        )

    def user_allows_park(self, user: User, park_id: int) -> bool:
        if bool(user.all_parks):
            return True
        return bool(
            self.session.scalar(
                select(UserParkScope.id).where(
                    UserParkScope.tenant_id == self.tenant_id,
                    UserParkScope.user_id == int(user.id),
                    UserParkScope.park_id == int(park_id),
                )
            )
        )

    def party(self, party_id: int) -> Party | None:
        return self.session.scalar(
            select(Party).where(
                Party.tenant_id == self.tenant_id,
                Party.id == int(party_id),
                Party.party_type == "ORGANIZATION",
                Party.status == "ACTIVE",
            )
        )

    def park(self, park_id: int) -> Park | None:
        return self.session.scalar(
            select(Park).where(
                Park.tenant_id == self.tenant_id,
                Park.id == int(park_id),
                Park.is_deleted.is_(False),
            )
        )

    def party_has_park(self, party_id: int, park_id: int) -> bool:
        return bool(
            self.session.scalar(
                select(PartyParkRelation.id).where(
                    PartyParkRelation.tenant_id == self.tenant_id,
                    PartyParkRelation.party_id == int(party_id),
                    PartyParkRelation.park_id == int(park_id),
                    PartyParkRelation.status == "ACTIVE",
                    PartyParkRelation.deleted_at.is_(None),
                )
            )
        )

    def contact(self, party_id: int, contact_id: int) -> PartyContact | None:
        return self.session.scalar(
            select(PartyContact).where(
                PartyContact.tenant_id == self.tenant_id,
                PartyContact.party_id == int(party_id),
                PartyContact.id == int(contact_id),
                PartyContact.is_deleted.is_(False),
            )
        )

    def unit_in_park(self, unit_id: int, park_id: int) -> Unit | None:
        return self.session.scalar(
            select(Unit).where(
                Unit.tenant_id == self.tenant_id,
                Unit.id == int(unit_id),
                Unit.park_id == int(park_id),
                Unit.is_deleted.is_(False),
            )
        )

    def principal_for_user(self, user_id: int, *, active_only: bool = True):
        stmt = select(TenantServicePrincipal).where(
            TenantServicePrincipal.tenant_id == self.tenant_id,
            TenantServicePrincipal.user_id == int(user_id),
        )
        if active_only:
            stmt = stmt.where(TenantServicePrincipal.status == "ACTIVE")
        principal = self.session.scalar(stmt)
        if principal is None:
            return None
        parks = list(
            self.session.scalars(
                select(TenantServicePrincipalPark.park_id).where(
                    TenantServicePrincipalPark.tenant_id == self.tenant_id,
                    TenantServicePrincipalPark.principal_id == int(principal.id),
                )
            ).all()
        )
        return principal, sorted(int(value) for value in parks)

    def list_principals(self) -> list[tuple[TenantServicePrincipal, list[int]]]:
        principals = list(
            self.session.scalars(
                select(TenantServicePrincipal)
                .where(TenantServicePrincipal.tenant_id == self.tenant_id)
                .order_by(TenantServicePrincipal.id.desc())
            ).all()
        )
        if not principals:
            return []
        park_rows = self.session.execute(
            select(TenantServicePrincipalPark.principal_id, TenantServicePrincipalPark.park_id)
            .where(
                TenantServicePrincipalPark.tenant_id == self.tenant_id,
                TenantServicePrincipalPark.principal_id.in_([int(row.id) for row in principals]),
            )
            .order_by(TenantServicePrincipalPark.park_id)
        ).all()
        parks_by_principal: dict[int, list[int]] = {}
        for principal_id, park_id in park_rows:
            parks_by_principal.setdefault(int(principal_id), []).append(int(park_id))
        return [(row, parks_by_principal.get(int(row.id), [])) for row in principals]

    def grant_principal(
        self, *, user_id: int, party_id: int, park_ids: Sequence[int], created_by: int | None
    ) -> TenantServicePrincipal:
        existing = self.session.scalar(
            select(TenantServicePrincipal).where(
                TenantServicePrincipal.tenant_id == self.tenant_id,
                TenantServicePrincipal.user_id == int(user_id),
            )
        )
        if existing is not None and int(existing.party_id) != int(party_id):
            raise AppError(
                "用户已绑定其他主体",
                code="TENANT_SERVICE_PRINCIPAL_PARTY_CONFLICT",
                status_code=409,
            )
        principal = existing or TenantServicePrincipal(
            tenant_id=self.tenant_id,
            user_id=int(user_id),
            party_id=int(party_id),
            created_by=created_by,
        )
        principal.status = "ACTIVE"
        principal.disabled_at = None
        principal.disabled_by = None
        self.session.add(principal)
        self.session.flush()
        existing_parks = set(
            self.session.scalars(
                select(TenantServicePrincipalPark.park_id).where(
                    TenantServicePrincipalPark.tenant_id == self.tenant_id,
                    TenantServicePrincipalPark.principal_id == int(principal.id),
                )
            ).all()
        )
        removed_parks = existing_parks - {int(value) for value in park_ids}
        if removed_parks:
            self.session.execute(
                delete(TenantServicePrincipalPark).where(
                    TenantServicePrincipalPark.tenant_id == self.tenant_id,
                    TenantServicePrincipalPark.principal_id == int(principal.id),
                    TenantServicePrincipalPark.park_id.in_(removed_parks),
                )
            )
        for park_id in sorted({int(value) for value in park_ids} - existing_parks):
            self.session.add(
                TenantServicePrincipalPark(
                    tenant_id=self.tenant_id,
                    principal_id=int(principal.id),
                    park_id=park_id,
                )
            )
        self.session.flush()
        return principal

    def disable_principal(self, principal_id: int, *, user_id: int | None, at: datetime):
        principal = self.session.scalar(
            select(TenantServicePrincipal).where(
                TenantServicePrincipal.tenant_id == self.tenant_id,
                TenantServicePrincipal.id == int(principal_id),
            )
        )
        if principal is None:
            return None
        principal.status = "DISABLED"
        principal.disabled_by = user_id
        principal.disabled_at = at
        self.session.add(principal)
        self.session.flush()
        return principal

    def create_rule(self, data: dict[str, Any], *, created_by: int | None) -> WorkOrderAssignmentRule:
        code = str(data["code"])
        version_no = int(
            self.session.scalar(
                select(func.coalesce(func.max(WorkOrderAssignmentRule.version_no), 0)).where(
                    WorkOrderAssignmentRule.tenant_id == self.tenant_id,
                    WorkOrderAssignmentRule.code == code,
                )
            )
            or 0
        ) + 1
        model = WorkOrderAssignmentRule(
            tenant_id=self.tenant_id,
            code=code,
            version_no=version_no,
            status="DRAFT",
            name=str(data["name"]),
            park_id=data.get("park_id"),
            category=data.get("category"),
            priority=data.get("priority"),
            assignee_user_id=int(data["assignee_user_id"]),
            response_minutes=int(data["response_minutes"]),
            resolution_minutes=int(data["resolution_minutes"]),
            sort_order=int(data.get("sort_order") or 100),
            created_by=created_by,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def get_rule(self, rule_id: int, *, for_update: bool = False):
        stmt = select(WorkOrderAssignmentRule).where(
            WorkOrderAssignmentRule.tenant_id == self.tenant_id,
            WorkOrderAssignmentRule.id == int(rule_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def list_rules(self) -> list[WorkOrderAssignmentRule]:
        return list(
            self.session.scalars(
                select(WorkOrderAssignmentRule)
                .where(WorkOrderAssignmentRule.tenant_id == self.tenant_id)
                .order_by(
                    WorkOrderAssignmentRule.code,
                    WorkOrderAssignmentRule.version_no.desc(),
                )
            ).all()
        )

    def publish_rule(self, model: WorkOrderAssignmentRule, *, user_id: int | None, at: datetime) -> None:
        published = list(
            self.session.scalars(
                select(WorkOrderAssignmentRule).where(
                    WorkOrderAssignmentRule.tenant_id == self.tenant_id,
                    WorkOrderAssignmentRule.code == model.code,
                    WorkOrderAssignmentRule.status == "PUBLISHED",
                    WorkOrderAssignmentRule.id != model.id,
                )
            ).all()
        )
        for row in published:
            row.status = "RETIRED"
            row.retired_by = user_id
            row.retired_at = at
            self.session.add(row)
        model.status = "PUBLISHED"
        model.published_by = user_id
        model.published_at = at
        self.session.add(model)
        self.session.flush()

    def retire_rule(
        self,
        model: WorkOrderAssignmentRule,
        *,
        user_id: int | None,
        at: datetime,
    ) -> None:
        model.status = "RETIRED"
        model.retired_by = user_id
        model.retired_at = at
        self.session.add(model)
        self.session.flush()

    def match_rule(self, *, park_id: int, category: str, priority: str):
        return self.session.scalar(
            select(WorkOrderAssignmentRule)
            .where(
                WorkOrderAssignmentRule.tenant_id == self.tenant_id,
                WorkOrderAssignmentRule.status == "PUBLISHED",
                or_(
                    WorkOrderAssignmentRule.park_id.is_(None),
                    WorkOrderAssignmentRule.park_id == int(park_id),
                ),
                or_(
                    WorkOrderAssignmentRule.category.is_(None),
                    WorkOrderAssignmentRule.category == category,
                ),
                or_(
                    WorkOrderAssignmentRule.priority.is_(None),
                    WorkOrderAssignmentRule.priority == priority,
                ),
            )
            .order_by(
                case((WorkOrderAssignmentRule.park_id == int(park_id), 0), else_=1),
                case((WorkOrderAssignmentRule.category == category, 0), else_=1),
                case((WorkOrderAssignmentRule.priority == priority, 0), else_=1),
                WorkOrderAssignmentRule.sort_order,
                WorkOrderAssignmentRule.id,
            )
        )

    def event_by_key(self, key: str):
        return self.session.scalar(
            select(WorkOrderEvent).where(
                WorkOrderEvent.tenant_id == self.tenant_id,
                WorkOrderEvent.idempotency_key == key,
            )
        )

    def add_event(
        self,
        *,
        order: WorkOrder,
        event_type: str,
        actor_type: str,
        actor_user_id: int | None,
        from_status: str | None,
        to_status: str | None,
        reason: str | None,
        detail: dict[str, Any],
        idempotency_key: str,
        occurred_at: datetime,
    ) -> WorkOrderEvent:
        existing = self.event_by_key(idempotency_key)
        if existing is not None:
            return existing
        model = WorkOrderEvent(
            tenant_id=self.tenant_id,
            park_id=int(order.park_id),
            work_order_id=int(order.id),
            event_type=event_type,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            detail_json=detail,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def events(self, work_order_id: int) -> list[WorkOrderEvent]:
        return list(
            self.session.scalars(
                select(WorkOrderEvent)
                .where(
                    WorkOrderEvent.tenant_id == self.tenant_id,
                    WorkOrderEvent.work_order_id == int(work_order_id),
                )
                .order_by(WorkOrderEvent.occurred_at, WorkOrderEvent.id)
            ).all()
        )

    def next_quote_version(self, work_order_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.coalesce(func.max(WorkOrderQuote.version_no), 0)).where(
                    WorkOrderQuote.tenant_id == self.tenant_id,
                    WorkOrderQuote.work_order_id == int(work_order_id),
                )
            )
            or 0
        ) + 1

    def create_quote(
        self,
        *,
        order: WorkOrder,
        lines: Sequence[dict[str, Any]],
        total: Decimal,
        currency: str,
        remark: str | None,
        created_by: int | None,
    ) -> WorkOrderQuote:
        quote = WorkOrderQuote(
            tenant_id=self.tenant_id,
            park_id=int(order.park_id),
            work_order_id=int(order.id),
            version_no=self.next_quote_version(int(order.id)),
            status="DRAFT",
            currency=currency,
            total_amount=total,
            remark=remark,
            lock_version=1,
            created_by=created_by,
        )
        self.session.add(quote)
        self.session.flush()
        for item in lines:
            self.session.add(
                WorkOrderQuoteLine(
                    tenant_id=self.tenant_id,
                    quote_id=int(quote.id),
                    **item,
                )
            )
        self.session.flush()
        return quote

    def quote(self, order_id: int, quote_id: int, *, for_update: bool = False):
        stmt = select(WorkOrderQuote).where(
            WorkOrderQuote.tenant_id == self.tenant_id,
            WorkOrderQuote.work_order_id == int(order_id),
            WorkOrderQuote.id == int(quote_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def quote_by_decision_key(self, key: str):
        return self.session.scalar(
            select(WorkOrderQuote).where(
                WorkOrderQuote.tenant_id == self.tenant_id,
                WorkOrderQuote.decision_key == key,
            )
        )

    def quote_lines(self, quote_id: int) -> list[WorkOrderQuoteLine]:
        return list(
            self.session.scalars(
                select(WorkOrderQuoteLine)
                .where(
                    WorkOrderQuoteLine.tenant_id == self.tenant_id,
                    WorkOrderQuoteLine.quote_id == int(quote_id),
                )
                .order_by(WorkOrderQuoteLine.id)
            ).all()
        )

    def quotes(self, work_order_id: int) -> list[WorkOrderQuote]:
        return list(
            self.session.scalars(
                select(WorkOrderQuote)
                .where(
                    WorkOrderQuote.tenant_id == self.tenant_id,
                    WorkOrderQuote.work_order_id == int(work_order_id),
                )
                .order_by(WorkOrderQuote.version_no.desc())
            ).all()
        )

    def accepted_quote(self, work_order_id: int):
        return self.session.scalar(
            select(WorkOrderQuote).where(
                WorkOrderQuote.tenant_id == self.tenant_id,
                WorkOrderQuote.work_order_id == int(work_order_id),
                WorkOrderQuote.status == "ACCEPTED",
            )
        )

    def add_cost(self, data: dict[str, Any]) -> WorkOrderCostEntry:
        existing = self.cost_by_key(str(data["idempotency_key"]))
        if existing is not None:
            return existing
        model = WorkOrderCostEntry(tenant_id=self.tenant_id, **data)
        self.session.add(model)
        self.session.flush()
        return model

    def cost_by_key(self, key: str) -> WorkOrderCostEntry | None:
        return self.session.scalar(
            select(WorkOrderCostEntry).where(
                WorkOrderCostEntry.tenant_id == self.tenant_id,
                WorkOrderCostEntry.idempotency_key == key,
            )
        )

    def cost(self, order_id: int, cost_id: int):
        return self.session.scalar(
            select(WorkOrderCostEntry).where(
                WorkOrderCostEntry.tenant_id == self.tenant_id,
                WorkOrderCostEntry.work_order_id == int(order_id),
                WorkOrderCostEntry.id == int(cost_id),
            )
        )

    def costs(self, work_order_id: int) -> list[WorkOrderCostEntry]:
        return list(
            self.session.scalars(
                select(WorkOrderCostEntry)
                .where(
                    WorkOrderCostEntry.tenant_id == self.tenant_id,
                    WorkOrderCostEntry.work_order_id == int(work_order_id),
                )
                .order_by(WorkOrderCostEntry.occurred_at, WorkOrderCostEntry.id)
            ).all()
        )

    def acceptance_by_key(self, key: str):
        return self.session.scalar(
            select(WorkOrderAcceptance).where(
                WorkOrderAcceptance.tenant_id == self.tenant_id,
                WorkOrderAcceptance.idempotency_key == key,
            )
        )

    def add_acceptance(self, data: dict[str, Any]) -> WorkOrderAcceptance:
        existing = self.acceptance_by_key(str(data["idempotency_key"]))
        if existing is not None:
            return existing
        model = WorkOrderAcceptance(tenant_id=self.tenant_id, **data)
        self.session.add(model)
        self.session.flush()
        return model

    def next_acceptance_attempt(self, work_order_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.coalesce(func.max(WorkOrderAcceptance.attempt_no), 0)).where(
                    WorkOrderAcceptance.tenant_id == self.tenant_id,
                    WorkOrderAcceptance.work_order_id == int(work_order_id),
                )
            )
            or 0
        ) + 1

    def acceptances(self, work_order_id: int) -> list[WorkOrderAcceptance]:
        return list(
            self.session.scalars(
                select(WorkOrderAcceptance)
                .where(
                    WorkOrderAcceptance.tenant_id == self.tenant_id,
                    WorkOrderAcceptance.work_order_id == int(work_order_id),
                )
                .order_by(WorkOrderAcceptance.attempt_no)
            ).all()
        )

    def rating(self, work_order_id: int):
        return self.session.scalar(
            select(WorkOrderRating).where(
                WorkOrderRating.tenant_id == self.tenant_id,
                WorkOrderRating.work_order_id == int(work_order_id),
            )
        )

    def add_rating(self, data: dict[str, Any]) -> WorkOrderRating:
        model = WorkOrderRating(tenant_id=self.tenant_id, **data)
        self.session.add(model)
        self.session.flush()
        return model

    def sla_candidates(self, now: datetime) -> list[WorkOrder]:
        return list(
            self.session.scalars(
                select(WorkOrder)
                .where(
                    WorkOrder.tenant_id == self.tenant_id,
                    WorkOrder.status.not_in(("COMPLETED", "CANCELLED")),
                    or_(
                        WorkOrder.response_due_at < now,
                        WorkOrder.resolution_due_at < now,
                    ),
                )
                .order_by(WorkOrder.id)
            ).all()
        )
