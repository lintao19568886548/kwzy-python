"""Tenant-, park-, and Party-scoped engagement persistence boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.engagement import (
    EngagementActivity,
    EngagementActivityEvent,
    EngagementActivityFeedback,
    EngagementActivityRegistration,
    EngagementActivityVersion,
    EngagementAnnouncement,
    EngagementAnnouncementDelivery,
    EngagementAnnouncementTarget,
    EngagementAnnouncementVersion,
    EngagementPolicy,
    EngagementPolicyConsultation,
    EngagementPolicyEvent,
    EngagementPolicyFollow,
    EngagementPolicyVersion,
    EngagementServiceCase,
    EngagementServiceCaseEvent,
    EngagementServiceCatalog,
    EngagementServiceFeedback,
    EngagementServiceVersion,
)
from app.infrastructure.database.models.facility_ops import (
    TenantServicePrincipal,
    TenantServicePrincipalPark,
    WorkOrder,
)
from app.infrastructure.database.models.identity import Role, User, UserRole
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party, PartyParkRelation, PartyRole
from app.infrastructure.database.models.party_enterprise import (
    PartyEnterpriseProfile,
    PartyEnterpriseTag,
)
from app.infrastructure.database.models.workbench_automation import (
    BusinessEvent,
    InAppNotification,
)
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.shared.tenant_context import ParkScopeMode, TenantContext

T = TypeVar("T")

MODEL_TYPES = {
    "activity": EngagementActivity,
    "activity_event": EngagementActivityEvent,
    "activity_feedback": EngagementActivityFeedback,
    "activity_registration": EngagementActivityRegistration,
    "activity_version": EngagementActivityVersion,
    "announcement": EngagementAnnouncement,
    "announcement_delivery": EngagementAnnouncementDelivery,
    "announcement_target": EngagementAnnouncementTarget,
    "announcement_version": EngagementAnnouncementVersion,
    "business_event": BusinessEvent,
    "notification": InAppNotification,
    "policy": EngagementPolicy,
    "policy_consultation": EngagementPolicyConsultation,
    "policy_event": EngagementPolicyEvent,
    "policy_follow": EngagementPolicyFollow,
    "policy_version": EngagementPolicyVersion,
    "service_case": EngagementServiceCase,
    "service_case_event": EngagementServiceCaseEvent,
    "service_catalog": EngagementServiceCatalog,
    "service_feedback": EngagementServiceFeedback,
    "service_version": EngagementServiceVersion,
}


class EngagementRepository:
    """The only engagement layer that imports ORM models."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return int(self.ctx.tenant_id)

    def _lock(self, stmt, enabled: bool):  # type: ignore[no-untyped-def]
        if (
            enabled
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            return stmt.with_for_update()
        return stmt

    def _park_scope(self, stmt, model):  # type: ignore[no-untyped-def]
        stmt = stmt.where(model.tenant_id == self.tenant_id)
        if not hasattr(model, "park_id"):
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(or_(model.park_id.is_(None), model.park_id.in_(self.ctx.park_ids)))
        return stmt.where(model.park_id.is_(None))

    def add(self, row: T) -> T:
        row.tenant_id = self.tenant_id
        park_id = getattr(row, "park_id", None)
        if park_id is not None and not self.ctx.allows_park(int(park_id)):
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        self.session.add(row)
        self.session.flush()
        return row

    def create(self, kind: str, **values: Any):  # type: ignore[no-untyped-def]
        model = MODEL_TYPES.get(kind)
        if model is None:
            raise ValueError(f"unknown engagement model kind: {kind}")
        return self.add(model(tenant_id=self.tenant_id, **values))

    def save(self, row: T) -> T:
        if int(row.tenant_id) != self.tenant_id:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        park_id = getattr(row, "park_id", None)
        if park_id is not None and not self.ctx.allows_park(int(park_id)):
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        self.session.add(row)
        self.session.flush()
        return row

    def park(self, park_id: int) -> Park | None:
        if not self.ctx.allows_park(int(park_id)):
            return None
        return self.session.scalar(
            select(Park).where(
                Park.tenant_id == self.tenant_id,
                Park.id == int(park_id),
                Park.is_deleted.is_(False),
            )
        )

    def approval(self, approval_id: int | None) -> ApprovalRequest | None:
        if approval_id is None:
            return None
        return self.session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.tenant_id,
                ApprovalRequest.id == int(approval_id),
            )
        )

    def active_party(self, party_id: int) -> Party | None:
        return self.session.scalar(
            select(Party).where(
                Party.tenant_id == self.tenant_id,
                Party.id == int(party_id),
                Party.status == "ACTIVE",
            )
        )

    def active_user(self, user_id: int) -> User | None:
        return self.session.scalar(
            select(User).where(
                User.tenant_id == self.tenant_id,
                User.id == int(user_id),
                User.status == "ACTIVE",
            )
        )

    def active_role(self, code: str) -> Role | None:
        return self.session.scalar(
            select(Role).where(
                Role.tenant_id == self.tenant_id,
                Role.code == code,
                Role.status == "ACTIVE",
            )
        )

    def attachment(self, attachment_id: int) -> Attachment | None:
        return self.session.scalar(
            select(Attachment).where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.id == int(attachment_id),
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

    def principal_for_user(
        self, user_id: int, *, park_id: int | None = None
    ) -> tuple[TenantServicePrincipal, list[int]] | None:
        principal = self.session.scalar(
            select(TenantServicePrincipal).where(
                TenantServicePrincipal.tenant_id == self.tenant_id,
                TenantServicePrincipal.user_id == int(user_id),
                TenantServicePrincipal.status == "ACTIVE",
            )
        )
        if principal is None:
            return None
        parks = [
            int(value)
            for value in self.session.scalars(
                select(TenantServicePrincipalPark.park_id).where(
                    TenantServicePrincipalPark.tenant_id == self.tenant_id,
                    TenantServicePrincipalPark.principal_id == int(principal.id),
                )
            ).all()
        ]
        if park_id is not None and int(park_id) not in parks:
            return None
        return principal, sorted(parks)

    def party_projection(self, party_id: int, park_id: int) -> dict[str, Any]:
        profile = self.session.scalar(
            select(PartyEnterpriseProfile).where(
                PartyEnterpriseProfile.tenant_id == self.tenant_id,
                PartyEnterpriseProfile.party_id == int(party_id),
            )
        )
        roles = list(
            self.session.scalars(
                select(PartyRole.role_code).where(
                    PartyRole.tenant_id == self.tenant_id,
                    PartyRole.party_id == int(party_id),
                    PartyRole.status == "ACTIVE",
                )
            ).all()
        )
        tags = list(
            self.session.scalars(
                select(PartyEnterpriseTag.normalized_name).where(
                    PartyEnterpriseTag.tenant_id == self.tenant_id,
                    PartyEnterpriseTag.party_id == int(party_id),
                    PartyEnterpriseTag.status == "ACTIVE",
                )
            ).all()
        )
        return {
            "park_id": int(park_id),
            "region_code": None,
            "party_role": roles,
            "industry_code": profile.industry_code if profile else None,
            "enterprise_scale": profile.employee_size_band if profile else "UNKNOWN",
            "tag_code": tags,
        }

    def policies(self, *, published_only: bool = False) -> Sequence[EngagementPolicy]:
        stmt = self._park_scope(select(EngagementPolicy), EngagementPolicy)
        if published_only:
            stmt = stmt.where(
                EngagementPolicy.published_version.is_not(None),
                EngagementPolicy.status.notin_(["EXPIRED", "WITHDRAWN"]),
            )
        return list(self.session.scalars(stmt.order_by(EngagementPolicy.id.desc())).all())

    def policy(self, policy_id: int, *, for_update: bool = False) -> EngagementPolicy | None:
        stmt = self._park_scope(
            select(EngagementPolicy).where(EngagementPolicy.id == int(policy_id)),
            EngagementPolicy,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def policy_version(
        self, policy_id: int, version: int, *, for_update: bool = False
    ) -> EngagementPolicyVersion | None:
        stmt = select(EngagementPolicyVersion).where(
            EngagementPolicyVersion.tenant_id == self.tenant_id,
            EngagementPolicyVersion.policy_id == int(policy_id),
            EngagementPolicyVersion.version == int(version),
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def policy_events(self, policy_id: int) -> Sequence[EngagementPolicyEvent]:
        return list(
            self.session.scalars(
                select(EngagementPolicyEvent)
                .where(
                    EngagementPolicyEvent.tenant_id == self.tenant_id,
                    EngagementPolicyEvent.policy_id == int(policy_id),
                )
                .order_by(EngagementPolicyEvent.occurred_at, EngagementPolicyEvent.id)
            ).all()
        )

    def policy_event_by_key(self, key: str) -> EngagementPolicyEvent | None:
        return self.session.scalar(
            select(EngagementPolicyEvent).where(
                EngagementPolicyEvent.tenant_id == self.tenant_id,
                EngagementPolicyEvent.idempotency_key == key,
            )
        )

    def expirable_policies(self, due_on) -> Sequence[EngagementPolicy]:  # type: ignore[no-untyped-def]
        stmt = self._park_scope(
            select(EngagementPolicy)
            .join(
                EngagementPolicyVersion,
                (EngagementPolicyVersion.policy_id == EngagementPolicy.id)
                & (EngagementPolicyVersion.version == EngagementPolicy.published_version),
            )
            .where(
                EngagementPolicy.status == "PUBLISHED",
                EngagementPolicyVersion.tenant_id == self.tenant_id,
                EngagementPolicyVersion.expires_on.is_not(None),
                EngagementPolicyVersion.expires_on < due_on,
            )
            .order_by(EngagementPolicy.id),
            EngagementPolicy,
        )
        return list(self.session.scalars(self._lock(stmt, True)).all())

    def policy_follow(self, policy_id: int, party_id: int) -> EngagementPolicyFollow | None:
        return self.session.scalar(
            select(EngagementPolicyFollow).where(
                EngagementPolicyFollow.tenant_id == self.tenant_id,
                EngagementPolicyFollow.policy_id == int(policy_id),
                EngagementPolicyFollow.party_id == int(party_id),
            )
        )

    def consultation_by_key(self, key: str) -> EngagementPolicyConsultation | None:
        return self.session.scalar(
            select(EngagementPolicyConsultation).where(
                EngagementPolicyConsultation.tenant_id == self.tenant_id,
                EngagementPolicyConsultation.idempotency_key == key,
            )
        )

    def service_catalogs(
        self, *, published_only: bool = False
    ) -> Sequence[EngagementServiceCatalog]:
        stmt = self._park_scope(select(EngagementServiceCatalog), EngagementServiceCatalog)
        if published_only:
            stmt = stmt.where(
                EngagementServiceCatalog.published_version.is_not(None),
                EngagementServiceCatalog.status != "RETIRED",
            )
        return list(self.session.scalars(stmt.order_by(EngagementServiceCatalog.id.desc())).all())

    def service_catalog(
        self, catalog_id: int, *, for_update: bool = False
    ) -> EngagementServiceCatalog | None:
        stmt = self._park_scope(
            select(EngagementServiceCatalog).where(EngagementServiceCatalog.id == int(catalog_id)),
            EngagementServiceCatalog,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def service_version(
        self, catalog_id: int, version: int, *, for_update: bool = False
    ) -> EngagementServiceVersion | None:
        stmt = select(EngagementServiceVersion).where(
            EngagementServiceVersion.tenant_id == self.tenant_id,
            EngagementServiceVersion.catalog_id == int(catalog_id),
            EngagementServiceVersion.version == int(version),
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def service_version_by_id(self, version_id: int) -> EngagementServiceVersion | None:
        return self.session.scalar(
            select(EngagementServiceVersion).where(
                EngagementServiceVersion.tenant_id == self.tenant_id,
                EngagementServiceVersion.id == int(version_id),
            )
        )

    def case_by_key(self, key: str) -> EngagementServiceCase | None:
        return self.session.scalar(
            select(EngagementServiceCase).where(
                EngagementServiceCase.tenant_id == self.tenant_id,
                EngagementServiceCase.idempotency_key == key,
            )
        )

    def service_case(
        self, case_id: int, *, for_update: bool = False, party_id: int | None = None
    ) -> EngagementServiceCase | None:
        stmt = self._park_scope(
            select(EngagementServiceCase).where(EngagementServiceCase.id == int(case_id)),
            EngagementServiceCase,
        )
        if party_id is not None:
            stmt = stmt.where(EngagementServiceCase.party_id == int(party_id))
        return self.session.scalar(self._lock(stmt, for_update))

    def service_cases(self, *, party_id: int | None = None) -> Sequence[EngagementServiceCase]:
        stmt = self._park_scope(select(EngagementServiceCase), EngagementServiceCase)
        if party_id is not None:
            stmt = stmt.where(EngagementServiceCase.party_id == int(party_id))
        return list(self.session.scalars(stmt.order_by(EngagementServiceCase.id.desc())).all())

    def case_events(self, case_id: int) -> Sequence[EngagementServiceCaseEvent]:
        return list(
            self.session.scalars(
                select(EngagementServiceCaseEvent)
                .where(
                    EngagementServiceCaseEvent.tenant_id == self.tenant_id,
                    EngagementServiceCaseEvent.case_id == int(case_id),
                )
                .order_by(EngagementServiceCaseEvent.occurred_at, EngagementServiceCaseEvent.id)
            ).all()
        )

    def case_event_by_key(self, key: str) -> EngagementServiceCaseEvent | None:
        return self.session.scalar(
            select(EngagementServiceCaseEvent).where(
                EngagementServiceCaseEvent.tenant_id == self.tenant_id,
                EngagementServiceCaseEvent.idempotency_key == key,
            )
        )

    def overdue_service_cases(self, due_at, limit: int) -> Sequence[EngagementServiceCase]:  # type: ignore[no-untyped-def]
        stmt = self._park_scope(
            select(EngagementServiceCase)
            .where(
                EngagementServiceCase.sla_due_at <= due_at,
                EngagementServiceCase.status.notin_(["CONFIRMED", "CANCELLED"]),
            )
            .order_by(EngagementServiceCase.sla_due_at, EngagementServiceCase.id)
            .limit(int(limit)),
            EngagementServiceCase,
        )
        return list(self.session.scalars(self._lock(stmt, True)).all())

    def service_feedback(self, case_id: int) -> EngagementServiceFeedback | None:
        return self.session.scalar(
            select(EngagementServiceFeedback).where(
                EngagementServiceFeedback.tenant_id == self.tenant_id,
                EngagementServiceFeedback.case_id == int(case_id),
            )
        )

    def work_order(self, work_order_id: int, park_id: int) -> WorkOrder | None:
        return self.session.scalar(
            select(WorkOrder).where(
                WorkOrder.tenant_id == self.tenant_id,
                WorkOrder.park_id == int(park_id),
                WorkOrder.id == int(work_order_id),
            )
        )

    def activities(self, *, published_only: bool = False) -> Sequence[EngagementActivity]:
        stmt = self._park_scope(select(EngagementActivity), EngagementActivity)
        if published_only:
            stmt = stmt.where(
                EngagementActivity.published_version.is_not(None),
                EngagementActivity.status.notin_(["COMPLETED", "CANCELLED"]),
            )
        return list(self.session.scalars(stmt.order_by(EngagementActivity.id.desc())).all())

    def activity(self, activity_id: int, *, for_update: bool = False) -> EngagementActivity | None:
        stmt = self._park_scope(
            select(EngagementActivity).where(EngagementActivity.id == int(activity_id)),
            EngagementActivity,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def activity_version(
        self, activity_id: int, version: int, *, for_update: bool = False
    ) -> EngagementActivityVersion | None:
        stmt = select(EngagementActivityVersion).where(
            EngagementActivityVersion.tenant_id == self.tenant_id,
            EngagementActivityVersion.activity_id == int(activity_id),
            EngagementActivityVersion.version == int(version),
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def registration_by_key(self, key: str) -> EngagementActivityRegistration | None:
        return self.session.scalar(
            select(EngagementActivityRegistration).where(
                EngagementActivityRegistration.tenant_id == self.tenant_id,
                EngagementActivityRegistration.idempotency_key == key,
            )
        )

    def registration(
        self, registration_id: int, *, for_update: bool = False, party_id: int | None = None
    ) -> EngagementActivityRegistration | None:
        stmt = self._park_scope(
            select(EngagementActivityRegistration).where(
                EngagementActivityRegistration.id == int(registration_id)
            ),
            EngagementActivityRegistration,
        )
        if party_id is not None:
            stmt = stmt.where(EngagementActivityRegistration.party_id == int(party_id))
        return self.session.scalar(self._lock(stmt, for_update))

    def registrations(
        self,
        *,
        activity_id: int | None = None,
        party_id: int | None = None,
        for_update: bool = False,
    ) -> Sequence[EngagementActivityRegistration]:
        stmt = self._park_scope(
            select(EngagementActivityRegistration), EngagementActivityRegistration
        )
        if activity_id is not None:
            stmt = stmt.where(EngagementActivityRegistration.activity_id == int(activity_id))
        if party_id is not None:
            stmt = stmt.where(EngagementActivityRegistration.party_id == int(party_id))
        stmt = stmt.order_by(EngagementActivityRegistration.id.desc())
        return list(self.session.scalars(self._lock(stmt, for_update)).all())

    def next_waitlisted(
        self, activity_version_id: int, *, maximum_attendees: int | None = None
    ) -> EngagementActivityRegistration | None:
        stmt = (
            select(EngagementActivityRegistration)
            .where(
                EngagementActivityRegistration.tenant_id == self.tenant_id,
                EngagementActivityRegistration.activity_version_id == int(activity_version_id),
                EngagementActivityRegistration.status == "WAITLISTED",
            )
            .order_by(
                EngagementActivityRegistration.waitlist_position,
                EngagementActivityRegistration.id,
            )
        )
        if maximum_attendees is not None:
            stmt = stmt.where(
                EngagementActivityRegistration.attendee_count <= int(maximum_attendees)
            )
        return self.session.scalar(self._lock(stmt, True))

    def activity_event_by_key(self, key: str) -> EngagementActivityEvent | None:
        return self.session.scalar(
            select(EngagementActivityEvent).where(
                EngagementActivityEvent.tenant_id == self.tenant_id,
                EngagementActivityEvent.idempotency_key == key,
            )
        )

    def activity_feedback(self, registration_id: int) -> EngagementActivityFeedback | None:
        return self.session.scalar(
            select(EngagementActivityFeedback).where(
                EngagementActivityFeedback.tenant_id == self.tenant_id,
                EngagementActivityFeedback.registration_id == int(registration_id),
            )
        )

    def announcements(self, *, published_only: bool = False) -> Sequence[EngagementAnnouncement]:
        stmt = self._park_scope(select(EngagementAnnouncement), EngagementAnnouncement)
        if published_only:
            stmt = stmt.where(
                EngagementAnnouncement.published_version.is_not(None),
                EngagementAnnouncement.status.notin_(["EXPIRED", "WITHDRAWN"]),
            )
        return list(self.session.scalars(stmt.order_by(EngagementAnnouncement.id.desc())).all())

    def announcement(
        self, announcement_id: int, *, for_update: bool = False
    ) -> EngagementAnnouncement | None:
        stmt = self._park_scope(
            select(EngagementAnnouncement).where(EngagementAnnouncement.id == int(announcement_id)),
            EngagementAnnouncement,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def announcement_version(
        self, announcement_id: int, version: int, *, for_update: bool = False
    ) -> EngagementAnnouncementVersion | None:
        stmt = select(EngagementAnnouncementVersion).where(
            EngagementAnnouncementVersion.tenant_id == self.tenant_id,
            EngagementAnnouncementVersion.announcement_id == int(announcement_id),
            EngagementAnnouncementVersion.version == int(version),
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def recipient_candidates(self, audience: Sequence[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        candidates: dict[int, dict[str, Any]] = {}
        for rule in audience:
            source_type = str(rule.get("type") or "").upper()
            values = [int(value) for value in rule.get("ids", [])]
            if source_type == "USER" and values:
                rows = self.session.execute(
                    select(User.id).where(
                        User.tenant_id == self.tenant_id,
                        User.id.in_(values),
                        User.status == "ACTIVE",
                    )
                ).all()
                for (user_id,) in rows:
                    candidates[int(user_id)] = {
                        "source_type": "USER",
                        "source_key": str(user_id),
                        "party_id": None,
                        "park_id": None,
                    }
            elif source_type == "ROLE":
                codes = [str(value).upper() for value in rule.get("codes", [])]
                rows = self.session.execute(
                    select(UserRole.user_id, Role.code)
                    .join(Role, Role.id == UserRole.role_id)
                    .join(User, User.id == UserRole.user_id)
                    .where(
                        UserRole.tenant_id == self.tenant_id,
                        Role.tenant_id == self.tenant_id,
                        Role.code.in_(codes),
                        Role.status == "ACTIVE",
                        User.tenant_id == self.tenant_id,
                        User.status == "ACTIVE",
                    )
                ).all()
                for user_id, role_code in rows:
                    candidates[int(user_id)] = {
                        "source_type": "ROLE",
                        "source_key": str(role_code),
                        "party_id": None,
                        "park_id": None,
                    }
            elif source_type in {"PARTY", "TENANT_PRINCIPAL"}:
                stmt = select(
                    TenantServicePrincipal.user_id,
                    TenantServicePrincipal.party_id,
                ).where(
                    TenantServicePrincipal.tenant_id == self.tenant_id,
                    TenantServicePrincipal.status == "ACTIVE",
                )
                if values:
                    stmt = stmt.where(TenantServicePrincipal.party_id.in_(values))
                for user_id, party_id in self.session.execute(stmt).all():
                    candidates[int(user_id)] = {
                        "source_type": source_type,
                        "source_key": str(party_id),
                        "party_id": int(party_id),
                        "park_id": None,
                    }
            elif source_type == "PARK" and values:
                rows = self.session.execute(
                    select(
                        TenantServicePrincipal.user_id,
                        TenantServicePrincipal.party_id,
                        TenantServicePrincipalPark.park_id,
                    )
                    .join(
                        TenantServicePrincipalPark,
                        TenantServicePrincipalPark.principal_id == TenantServicePrincipal.id,
                    )
                    .where(
                        TenantServicePrincipal.tenant_id == self.tenant_id,
                        TenantServicePrincipal.status == "ACTIVE",
                        TenantServicePrincipalPark.tenant_id == self.tenant_id,
                        TenantServicePrincipalPark.park_id.in_(values),
                    )
                ).all()
                for user_id, party_id, park_id in rows:
                    candidates[int(user_id)] = {
                        "source_type": "PARK",
                        "source_key": str(park_id),
                        "party_id": int(party_id),
                        "park_id": int(park_id),
                    }
        return candidates

    def announcement_targets(
        self, announcement_version_id: int
    ) -> Sequence[EngagementAnnouncementTarget]:
        return list(
            self.session.scalars(
                select(EngagementAnnouncementTarget).where(
                    EngagementAnnouncementTarget.tenant_id == self.tenant_id,
                    EngagementAnnouncementTarget.announcement_version_id
                    == int(announcement_version_id),
                )
            ).all()
        )

    def due_announcements(self, due_at, limit: int) -> Sequence[EngagementAnnouncement]:  # type: ignore[no-untyped-def]
        stmt = self._park_scope(
            select(EngagementAnnouncement)
            .join(
                EngagementAnnouncementVersion,
                (EngagementAnnouncementVersion.announcement_id == EngagementAnnouncement.id)
                & (EngagementAnnouncementVersion.version == EngagementAnnouncement.current_version),
            )
            .where(
                EngagementAnnouncement.status == "SCHEDULED",
                EngagementAnnouncementVersion.tenant_id == self.tenant_id,
                EngagementAnnouncementVersion.publish_at.is_not(None),
                EngagementAnnouncementVersion.publish_at <= due_at,
            )
            .order_by(EngagementAnnouncementVersion.publish_at, EngagementAnnouncement.id)
            .limit(int(limit)),
            EngagementAnnouncement,
        )
        return list(self.session.scalars(self._lock(stmt, True)).all())

    def expirable_announcements(
        self, due_at, limit: int
    ) -> Sequence[EngagementAnnouncement]:  # type: ignore[no-untyped-def]
        stmt = self._park_scope(
            select(EngagementAnnouncement)
            .join(
                EngagementAnnouncementVersion,
                (EngagementAnnouncementVersion.announcement_id == EngagementAnnouncement.id)
                & (EngagementAnnouncementVersion.version == EngagementAnnouncement.published_version),
            )
            .where(
                EngagementAnnouncement.status == "PUBLISHED",
                EngagementAnnouncementVersion.tenant_id == self.tenant_id,
                EngagementAnnouncementVersion.expires_at.is_not(None),
                EngagementAnnouncementVersion.expires_at <= due_at,
            )
            .order_by(EngagementAnnouncementVersion.expires_at, EngagementAnnouncement.id)
            .limit(int(limit)),
            EngagementAnnouncement,
        )
        return list(self.session.scalars(self._lock(stmt, True)).all())

    def pending_deliveries(self, limit: int) -> Sequence[EngagementAnnouncementDelivery]:
        stmt = (
            select(EngagementAnnouncementDelivery)
            .where(
                EngagementAnnouncementDelivery.tenant_id == self.tenant_id,
                EngagementAnnouncementDelivery.status.in_(["PENDING", "FAILED"]),
            )
            .order_by(EngagementAnnouncementDelivery.id)
            .limit(int(limit))
        )
        return list(self.session.scalars(self._lock(stmt, True)).all())

    def target(self, target_id: int) -> EngagementAnnouncementTarget | None:
        return self.session.scalar(
            select(EngagementAnnouncementTarget).where(
                EngagementAnnouncementTarget.tenant_id == self.tenant_id,
                EngagementAnnouncementTarget.id == int(target_id),
            )
        )

    def delivery_for_user(
        self, delivery_id: int, user_id: int, *, for_update: bool = False
    ) -> tuple[EngagementAnnouncementDelivery, EngagementAnnouncementTarget] | None:
        stmt = (
            select(EngagementAnnouncementDelivery, EngagementAnnouncementTarget)
            .join(
                EngagementAnnouncementTarget,
                EngagementAnnouncementTarget.id == EngagementAnnouncementDelivery.target_id,
            )
            .where(
                EngagementAnnouncementDelivery.tenant_id == self.tenant_id,
                EngagementAnnouncementDelivery.id == int(delivery_id),
                EngagementAnnouncementTarget.tenant_id == self.tenant_id,
                EngagementAnnouncementTarget.recipient_user_id == int(user_id),
            )
        )
        return self.session.execute(self._lock(stmt, for_update)).first()

    def inbox(self, user_id: int) -> Sequence[tuple[Any, ...]]:
        return list(
            self.session.execute(
                select(
                    EngagementAnnouncementDelivery,
                    EngagementAnnouncementTarget,
                    EngagementAnnouncementVersion,
                    EngagementAnnouncement,
                )
                .join(
                    EngagementAnnouncementTarget,
                    EngagementAnnouncementTarget.id == EngagementAnnouncementDelivery.target_id,
                )
                .join(
                    EngagementAnnouncementVersion,
                    EngagementAnnouncementVersion.id
                    == EngagementAnnouncementTarget.announcement_version_id,
                )
                .join(
                    EngagementAnnouncement,
                    EngagementAnnouncement.id == EngagementAnnouncementTarget.announcement_id,
                )
                .where(
                    EngagementAnnouncementDelivery.tenant_id == self.tenant_id,
                    EngagementAnnouncementTarget.tenant_id == self.tenant_id,
                    EngagementAnnouncementTarget.recipient_user_id == int(user_id),
                )
                .order_by(EngagementAnnouncementDelivery.id.desc())
            ).all()
        )

    def business_event_by_key(self, key: str) -> BusinessEvent | None:
        return self.session.scalar(
            select(BusinessEvent).where(
                BusinessEvent.tenant_id == self.tenant_id,
                BusinessEvent.idempotency_key == key,
            )
        )

    def notification_by_key(self, key: str) -> InAppNotification | None:
        return self.session.scalar(
            select(InAppNotification).where(
                InAppNotification.tenant_id == self.tenant_id,
                InAppNotification.idempotency_key == key,
            )
        )

    def counts(self) -> dict[str, int]:
        def count(model, status_filter=None) -> int:  # type: ignore[no-untyped-def]
            stmt = self._park_scope(select(func.count()).select_from(model), model)
            if status_filter is not None:
                stmt = stmt.where(status_filter)
            return int(self.session.scalar(stmt) or 0)

        return {
            "published_policies": count(EngagementPolicy, EngagementPolicy.status == "PUBLISHED"),
            "published_services": count(
                EngagementServiceCatalog, EngagementServiceCatalog.status == "PUBLISHED"
            ),
            "open_service_cases": count(
                EngagementServiceCase,
                EngagementServiceCase.status.notin_(["CONFIRMED", "CANCELLED"]),
            ),
            "published_activities": count(
                EngagementActivity,
                EngagementActivity.status.in_(["PUBLISHED", "REGISTRATION_CLOSED"]),
            ),
            "published_announcements": count(
                EngagementAnnouncement, EngagementAnnouncement.status == "PUBLISHED"
            ),
        }
