"""Persistence for tenant-safe enterprise profile children."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import case, exists, func, or_, select, text
from sqlalchemy.orm import Session

from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.party import (
    Party,
    PartyAddress,
    PartyContact,
    PartyParkRelation,
)
from app.infrastructure.database.models.party_enterprise import (
    PartyEnterpriseCredential,
    PartyEnterpriseProfile,
    PartyEnterpriseRelationship,
    PartyEnterpriseRiskResolution,
    PartyEnterpriseRiskSignal,
    PartyEnterpriseTag,
)
from app.infrastructure.database.models.workbench_automation import BusinessEvent
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.shared.tenant_context import TenantContext


class PartyEnterpriseRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.parties = PartyRepository(session, ctx)

    @property
    def tenant_id(self) -> int:
        return self.ctx.tenant_id

    def profile(self, party_id: int, *, for_update: bool = False) -> PartyEnterpriseProfile | None:
        stmt = select(PartyEnterpriseProfile).where(
            PartyEnterpriseProfile.tenant_id == self.tenant_id,
            PartyEnterpriseProfile.party_id == int(party_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def add_profile(self, *, party_id: int, values: dict[str, Any]) -> PartyEnterpriseProfile:
        row = PartyEnterpriseProfile(tenant_id=self.tenant_id, party_id=party_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def completeness_dimensions(
        self, party: Party, profile: PartyEnterpriseProfile | None
    ) -> dict[str, bool]:
        registered_address = bool(
            self.session.scalar(
                select(func.count())
                .select_from(PartyAddress)
                .where(
                    PartyAddress.tenant_id == self.tenant_id,
                    PartyAddress.party_id == party.id,
                    PartyAddress.address_type == "REGISTERED",
                    PartyAddress.status == "ACTIVE",
                    PartyAddress.deleted_at.is_(None),
                )
            )
        )
        primary_contact = bool(
            self.session.scalar(
                select(func.count())
                .select_from(PartyContact)
                .where(
                    PartyContact.tenant_id == self.tenant_id,
                    PartyContact.party_id == party.id,
                    PartyContact.is_primary.is_(True),
                    PartyContact.is_deleted.is_(False),
                )
            )
        )
        business_license = bool(
            self.session.scalar(
                select(func.count())
                .select_from(PartyEnterpriseCredential)
                .where(
                    PartyEnterpriseCredential.tenant_id == self.tenant_id,
                    PartyEnterpriseCredential.party_id == party.id,
                    PartyEnterpriseCredential.credential_type == "BUSINESS_LICENSE",
                    PartyEnterpriseCredential.status == "ACTIVE",
                    or_(
                        PartyEnterpriseCredential.expires_on.is_(None),
                        PartyEnterpriseCredential.expires_on >= func.current_date(),
                    ),
                )
            )
        )
        return {
            "CREDIT_CODE": bool(party.credit_code),
            "LEGAL_REPRESENTATIVE": bool(profile and profile.legal_representative),
            "ESTABLISHED_ON": bool(profile and profile.established_on),
            "REGISTERED_CAPITAL": bool(
                profile and profile.registered_capital is not None and profile.capital_currency
            ),
            "REGISTRATION_STATUS": bool(
                profile and profile.registration_status not in {None, "", "UNKNOWN"}
            ),
            "INDUSTRY": bool(profile and (profile.industry_code or profile.industry_name)),
            "BUSINESS_SCOPE": bool(profile and profile.business_scope),
            "REGISTERED_ADDRESS": registered_address,
            "PRIMARY_CONTACT": primary_contact,
            "BUSINESS_LICENSE": business_license,
        }

    def _completeness_expression(self):
        profile = PartyEnterpriseProfile
        registered_address = exists(
            select(PartyAddress.id).where(
                PartyAddress.tenant_id == Party.tenant_id,
                PartyAddress.party_id == Party.id,
                PartyAddress.address_type == "REGISTERED",
                PartyAddress.status == "ACTIVE",
                PartyAddress.deleted_at.is_(None),
            )
        )
        primary_contact = exists(
            select(PartyContact.id).where(
                PartyContact.tenant_id == Party.tenant_id,
                PartyContact.party_id == Party.id,
                PartyContact.is_primary.is_(True),
                PartyContact.is_deleted.is_(False),
            )
        )
        license_exists = exists(
            select(PartyEnterpriseCredential.id).where(
                PartyEnterpriseCredential.tenant_id == Party.tenant_id,
                PartyEnterpriseCredential.party_id == Party.id,
                PartyEnterpriseCredential.credential_type == "BUSINESS_LICENSE",
                PartyEnterpriseCredential.status == "ACTIVE",
                or_(
                    PartyEnterpriseCredential.expires_on.is_(None),
                    PartyEnterpriseCredential.expires_on >= func.current_date(),
                ),
            )
        )
        return (
            case((Party.credit_code.is_not(None), 15), else_=0)
            + case((profile.legal_representative.is_not(None), 10), else_=0)
            + case((profile.established_on.is_not(None), 10), else_=0)
            + case(
                (
                    profile.registered_capital.is_not(None)
                    & profile.capital_currency.is_not(None),
                    10,
                ),
                else_=0,
            )
            + case((profile.registration_status.not_in(("UNKNOWN",)), 5), else_=0)
            + case(
                (or_(profile.industry_code.is_not(None), profile.industry_name.is_not(None)), 10),
                else_=0,
            )
            + case((profile.business_scope.is_not(None), 10), else_=0)
            + case((registered_address, 10), else_=0)
            + case((primary_contact, 10), else_=0)
            + case((license_exists, 10), else_=0)
        )

    def directory(
        self,
        *,
        offset: int,
        limit: int,
        keyword: str | None,
        status: str | None,
        blacklist_status: str | None,
        registration_status: str | None,
        industry: str | None,
        min_completeness: int | None,
        max_completeness: int | None,
        local_risk_level: str | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[int, Sequence[tuple[Party, PartyEnterpriseProfile | None, int]]]:
        score = self._completeness_expression().label("completeness_score")
        stmt = (
            select(Party, PartyEnterpriseProfile, score)
            .outerjoin(
                PartyEnterpriseProfile,
                (PartyEnterpriseProfile.tenant_id == Party.tenant_id)
                & (PartyEnterpriseProfile.party_id == Party.id),
            )
            .where(Party.party_type == "ORGANIZATION", Party.status != "ARCHIVED")
        )
        stmt = self.parties._visible_filter(stmt)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    Party.name.ilike(pattern),
                    Party.credit_code.ilike(pattern),
                    PartyEnterpriseProfile.short_name.ilike(pattern),
                    PartyEnterpriseProfile.industry_name.ilike(pattern),
                )
            )
        if status:
            stmt = stmt.where(Party.status == status)
        if blacklist_status:
            stmt = stmt.where(Party.risk_status == blacklist_status)
        if registration_status:
            stmt = stmt.where(PartyEnterpriseProfile.registration_status == registration_status)
        if industry:
            pattern = f"%{industry.strip()}%"
            stmt = stmt.where(
                or_(
                    PartyEnterpriseProfile.industry_code.ilike(pattern),
                    PartyEnterpriseProfile.industry_name.ilike(pattern),
                )
            )
        if min_completeness is not None:
            stmt = stmt.where(score >= int(min_completeness))
        if max_completeness is not None:
            stmt = stmt.where(score <= int(max_completeness))
        if local_risk_level:
            unresolved = (
                select(PartyEnterpriseRiskSignal.severity)
                .where(
                    PartyEnterpriseRiskSignal.tenant_id == Party.tenant_id,
                    PartyEnterpriseRiskSignal.party_id == Party.id,
                    ~exists(
                        select(PartyEnterpriseRiskResolution.id).where(
                            PartyEnterpriseRiskResolution.tenant_id
                            == PartyEnterpriseRiskSignal.tenant_id,
                            PartyEnterpriseRiskResolution.signal_id == PartyEnterpriseRiskSignal.id,
                        )
                    ),
                )
                .correlate(Party)
            )
            if local_risk_level == "NONE":
                stmt = stmt.where(~exists(unresolved))
            else:
                order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
                target = order[local_risk_level]
                stmt = stmt.where(exists(unresolved.where(PartyEnterpriseRiskSignal.severity == local_risk_level)))
                higher = [severity for severity, value in order.items() if value > target]
                if higher:
                    stmt = stmt.where(
                        ~exists(unresolved.where(PartyEnterpriseRiskSignal.severity.in_(higher)))
                    )
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self.session.scalar(count_stmt) or 0)
        sorts = {
            "name": Party.name,
            "updated_at": func.coalesce(PartyEnterpriseProfile.updated_at, Party.updated_at, Party.created_at),
            "completeness": score,
        }
        sort_column = sorts[sort_by]
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        rows = self.session.execute(
            stmt.order_by(order_clause, Party.id.desc()).offset(offset).limit(limit)
        ).all()
        return total, [(row[0], row[1], int(row[2] or 0)) for row in rows]

    def lock_relationship_graph(self) -> None:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": 2_100_000_000 + int(self.tenant_id)},
            )

    def parent_cycle_exists(self, *, source_party_id: int, target_party_id: int) -> bool:
        return bool(
            self.session.scalar(
                text(
                    """
                    WITH RECURSIVE descendants(party_id) AS (
                        SELECT target_party_id
                        FROM party_enterprise_relationships
                        WHERE tenant_id = :tenant_id
                          AND source_party_id = :target_party_id
                          AND relationship_type = 'PARENT_OF'
                          AND status = 'ACTIVE'
                        UNION
                        SELECT relation.target_party_id
                        FROM party_enterprise_relationships relation
                        JOIN descendants parent ON relation.source_party_id = parent.party_id
                        WHERE relation.tenant_id = :tenant_id
                          AND relation.relationship_type = 'PARENT_OF'
                          AND relation.status = 'ACTIVE'
                    )
                    SELECT EXISTS(
                        SELECT 1 FROM descendants WHERE party_id = :source_party_id
                    )
                    """
                ),
                {
                    "tenant_id": self.tenant_id,
                    "source_party_id": int(source_party_id),
                    "target_party_id": int(target_party_id),
                },
            )
        )

    def active_relationship(
        self, *, source_party_id: int, target_party_id: int, relationship_type: str
    ) -> PartyEnterpriseRelationship | None:
        return self.session.scalars(
            select(PartyEnterpriseRelationship).where(
                PartyEnterpriseRelationship.tenant_id == self.tenant_id,
                PartyEnterpriseRelationship.source_party_id == source_party_id,
                PartyEnterpriseRelationship.target_party_id == target_party_id,
                PartyEnterpriseRelationship.relationship_type == relationship_type,
                PartyEnterpriseRelationship.status == "ACTIVE",
            )
        ).first()

    def add_relationship(self, values: dict[str, Any]) -> PartyEnterpriseRelationship:
        row = PartyEnterpriseRelationship(tenant_id=self.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def relationships(self, party_id: int, *, include_ended: bool) -> Sequence[PartyEnterpriseRelationship]:
        stmt = select(PartyEnterpriseRelationship).where(
            PartyEnterpriseRelationship.tenant_id == self.tenant_id,
            or_(
                PartyEnterpriseRelationship.source_party_id == party_id,
                PartyEnterpriseRelationship.target_party_id == party_id,
            ),
        )
        if not include_ended:
            stmt = stmt.where(PartyEnterpriseRelationship.status == "ACTIVE")
        return list(self.session.scalars(stmt.order_by(PartyEnterpriseRelationship.id.desc())).all())

    def relationship(
        self, relationship_id: int, party_id: int, *, for_update: bool = False
    ) -> PartyEnterpriseRelationship | None:
        stmt = select(PartyEnterpriseRelationship).where(
            PartyEnterpriseRelationship.tenant_id == self.tenant_id,
            PartyEnterpriseRelationship.id == relationship_id,
            or_(
                PartyEnterpriseRelationship.source_party_id == party_id,
                PartyEnterpriseRelationship.target_party_id == party_id,
            ),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def attachment(self, attachment_id: int) -> Attachment | None:
        return self.session.scalars(
            select(Attachment).where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.id == int(attachment_id),
                Attachment.status == "ACTIVE",
            )
        ).first()

    def party_active_park_ids(self, party_id: int) -> set[int]:
        return set(
            self.session.scalars(
                select(PartyParkRelation.park_id).where(
                    PartyParkRelation.tenant_id == self.tenant_id,
                    PartyParkRelation.party_id == party_id,
                    PartyParkRelation.status == "ACTIVE",
                    PartyParkRelation.deleted_at.is_(None),
                )
            ).all()
        )

    def party_active_park_ids_many(self, party_ids: Sequence[int]) -> dict[int, set[int]]:
        normalized_ids = sorted({int(party_id) for party_id in party_ids})
        if not normalized_ids:
            return {}
        rows = self.session.execute(
            select(PartyParkRelation.party_id, PartyParkRelation.park_id).where(
                PartyParkRelation.tenant_id == self.tenant_id,
                PartyParkRelation.party_id.in_(normalized_ids),
                PartyParkRelation.status == "ACTIVE",
                PartyParkRelation.deleted_at.is_(None),
            )
        ).all()
        result: defaultdict[int, set[int]] = defaultdict(set)
        for party_id, park_id in rows:
            result[int(party_id)].add(int(park_id))
        return dict(result)

    def credentials(self, party_id: int, *, include_archived: bool) -> Sequence[PartyEnterpriseCredential]:
        stmt = select(PartyEnterpriseCredential).where(
            PartyEnterpriseCredential.tenant_id == self.tenant_id,
            PartyEnterpriseCredential.party_id == party_id,
        )
        if not include_archived:
            stmt = stmt.where(PartyEnterpriseCredential.status != "ARCHIVED")
        return list(self.session.scalars(stmt.order_by(PartyEnterpriseCredential.id.desc())).all())

    def credential(
        self, credential_id: int, party_id: int, *, for_update: bool = False
    ) -> PartyEnterpriseCredential | None:
        stmt = select(PartyEnterpriseCredential).where(
            PartyEnterpriseCredential.tenant_id == self.tenant_id,
            PartyEnterpriseCredential.party_id == party_id,
            PartyEnterpriseCredential.id == credential_id,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def add_credential(self, values: dict[str, Any]) -> PartyEnterpriseCredential:
        row = PartyEnterpriseCredential(tenant_id=self.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def tags(self, party_id: int, *, include_inactive: bool) -> Sequence[PartyEnterpriseTag]:
        stmt = select(PartyEnterpriseTag).where(
            PartyEnterpriseTag.tenant_id == self.tenant_id,
            PartyEnterpriseTag.party_id == party_id,
        )
        if not include_inactive:
            stmt = stmt.where(PartyEnterpriseTag.status == "ACTIVE")
        return list(self.session.scalars(stmt.order_by(PartyEnterpriseTag.id.desc())).all())

    def active_tag(self, party_id: int, tag_type: str, normalized_name: str) -> PartyEnterpriseTag | None:
        return self.session.scalars(
            select(PartyEnterpriseTag).where(
                PartyEnterpriseTag.tenant_id == self.tenant_id,
                PartyEnterpriseTag.party_id == party_id,
                PartyEnterpriseTag.tag_type == tag_type,
                PartyEnterpriseTag.normalized_name == normalized_name,
                PartyEnterpriseTag.status == "ACTIVE",
            )
        ).first()

    def tag(self, tag_id: int, party_id: int, *, for_update: bool = False) -> PartyEnterpriseTag | None:
        stmt = select(PartyEnterpriseTag).where(
            PartyEnterpriseTag.tenant_id == self.tenant_id,
            PartyEnterpriseTag.party_id == party_id,
            PartyEnterpriseTag.id == tag_id,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def add_tag(self, values: dict[str, Any]) -> PartyEnterpriseTag:
        row = PartyEnterpriseTag(tenant_id=self.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def risk_signal_by_source(
        self, party_id: int, source_type: str, source_reference: str
    ) -> PartyEnterpriseRiskSignal | None:
        return self.session.scalars(
            select(PartyEnterpriseRiskSignal).where(
                PartyEnterpriseRiskSignal.tenant_id == self.tenant_id,
                PartyEnterpriseRiskSignal.party_id == party_id,
                PartyEnterpriseRiskSignal.source_type == source_type,
                PartyEnterpriseRiskSignal.source_reference == source_reference,
            )
        ).first()

    def add_risk_signal(self, values: dict[str, Any]) -> PartyEnterpriseRiskSignal:
        row = PartyEnterpriseRiskSignal(tenant_id=self.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def risk_signal(
        self, signal_id: int, party_id: int, *, for_update: bool = False
    ) -> PartyEnterpriseRiskSignal | None:
        stmt = select(PartyEnterpriseRiskSignal).where(
            PartyEnterpriseRiskSignal.tenant_id == self.tenant_id,
            PartyEnterpriseRiskSignal.party_id == party_id,
            PartyEnterpriseRiskSignal.id == signal_id,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def risk_signals(
        self, party_id: int
    ) -> Sequence[tuple[PartyEnterpriseRiskSignal, PartyEnterpriseRiskResolution | None]]:
        return list(
            self.session.execute(
                select(PartyEnterpriseRiskSignal, PartyEnterpriseRiskResolution)
                .outerjoin(
                    PartyEnterpriseRiskResolution,
                    (PartyEnterpriseRiskResolution.tenant_id == PartyEnterpriseRiskSignal.tenant_id)
                    & (PartyEnterpriseRiskResolution.signal_id == PartyEnterpriseRiskSignal.id),
                )
                .where(
                    PartyEnterpriseRiskSignal.tenant_id == self.tenant_id,
                    PartyEnterpriseRiskSignal.party_id == party_id,
                )
                .order_by(PartyEnterpriseRiskSignal.occurred_at.desc(), PartyEnterpriseRiskSignal.id.desc())
            ).all()
        )

    def unresolved_risk_rows_many(
        self, party_ids: Sequence[int]
    ) -> dict[int, list[tuple[str, str]]]:
        normalized_ids = sorted({int(party_id) for party_id in party_ids})
        if not normalized_ids:
            return {}
        rows = self.session.execute(
            select(
                PartyEnterpriseRiskSignal.party_id,
                PartyEnterpriseRiskSignal.severity,
                PartyEnterpriseRiskSignal.category,
            )
            .outerjoin(
                PartyEnterpriseRiskResolution,
                (PartyEnterpriseRiskResolution.tenant_id == PartyEnterpriseRiskSignal.tenant_id)
                & (PartyEnterpriseRiskResolution.signal_id == PartyEnterpriseRiskSignal.id),
            )
            .where(
                PartyEnterpriseRiskSignal.tenant_id == self.tenant_id,
                PartyEnterpriseRiskSignal.party_id.in_(normalized_ids),
                PartyEnterpriseRiskResolution.id.is_(None),
            )
        ).all()
        result: defaultdict[int, list[tuple[str, str]]] = defaultdict(list)
        for party_id, severity, category in rows:
            result[int(party_id)].append((str(severity), str(category)))
        return dict(result)

    def resolution(self, signal_id: int) -> PartyEnterpriseRiskResolution | None:
        return self.session.scalars(
            select(PartyEnterpriseRiskResolution).where(
                PartyEnterpriseRiskResolution.tenant_id == self.tenant_id,
                PartyEnterpriseRiskResolution.signal_id == signal_id,
            )
        ).first()

    def add_resolution(self, values: dict[str, Any]) -> PartyEnterpriseRiskResolution:
        row = PartyEnterpriseRiskResolution(tenant_id=self.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def add_event(
        self,
        *,
        event_type: str,
        source_type: str,
        source_id: str,
        park_id: int | None,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> BusinessEvent:
        existing = self.session.scalars(
            select(BusinessEvent).where(
                BusinessEvent.tenant_id == self.tenant_id,
                BusinessEvent.idempotency_key == idempotency_key,
            )
        ).first()
        if existing is not None:
            return existing
        row = BusinessEvent(
            tenant_id=self.tenant_id,
            park_id=park_id,
            event_type=event_type,
            source_type=source_type,
            source_id=str(source_id),
            schema_version=1,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            idempotency_key=idempotency_key,
            occurred_at=utc_now(),
        )
        self.session.add(row)
        self.session.flush()
        return row
