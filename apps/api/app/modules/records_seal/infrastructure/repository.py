"""Tenant- and park-scoped persistence for records, signature and seal governance."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.records_seal import (
    RecordAccessRequest,
    RecordCategory,
    RecordDisposition,
    RecordDispositionConfirmation,
    RecordFile,
    RecordHold,
    RecordIntegrityEvent,
    RecordRevision,
    SealAsset,
    SealCustodyEvent,
    SealUseApplication,
    SealUseReceipt,
    SignatureEnvelope,
    SignatureEvent,
    SignatureParticipant,
    SignatureProvider,
)
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.modules.identity.infrastructure.authorization_repository import AuthorizationRepository
from app.shared.tenant_context import ParkScopeMode, TenantContext


class RecordsSealRepository:
    """The only ORM boundary used by the records/seal application service."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return int(self.ctx.tenant_id)

    def _scope(self, stmt, model):  # type: ignore[no-untyped-def]
        stmt = stmt.where(model.tenant_id == self.tenant_id)
        if not hasattr(model, "park_id"):
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(model.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def _lock(self, stmt, enabled: bool):  # type: ignore[no-untyped-def]
        if (
            enabled
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            return stmt.with_for_update()
        return stmt

    def _add(self, model):  # type: ignore[no-untyped-def]
        model.tenant_id = self.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model):  # type: ignore[no-untyped-def]
        if int(model.tenant_id) != self.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        if hasattr(model, "park_id"):
            park_id = model.park_id
            if park_id is None and not self.ctx.has_all_park_access:
                raise AppError("无租户级数据访问范围", code="PARK_SCOPE_DENIED", status_code=403)
            if park_id is not None and not self.ctx.allows_park(int(park_id)):
                raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model

    def park_exists(self, park_id: int) -> bool:
        return bool(
            self.session.scalar(
                select(Park.id).where(
                    Park.tenant_id == self.tenant_id,
                    Park.id == int(park_id),
                    Park.is_deleted.is_(False),
                )
            )
        )

    def active_user(self, user_id: int, park_id: int | None = None) -> User | None:
        user = self.session.scalar(
            select(User).where(
                User.tenant_id == self.tenant_id,
                User.id == int(user_id),
                User.status == "ACTIVE",
            )
        )
        if user is None or park_id is None:
            return user
        _, park_ids, mode = AuthorizationRepository(self.session).resolve_authorization(user)
        return user if mode == ParkScopeMode.ALL or int(park_id) in park_ids else None

    # Classification
    def list_categories(self, *, include_retired: bool = False) -> Sequence[RecordCategory]:
        stmt = select(RecordCategory).where(RecordCategory.tenant_id == self.tenant_id)
        if not include_retired:
            stmt = stmt.where(RecordCategory.status == "ACTIVE")
        return list(self.session.scalars(stmt.order_by(RecordCategory.code)).all())

    def get_category(self, category_id: int, *, for_update: bool = False) -> RecordCategory | None:
        stmt = select(RecordCategory).where(
            RecordCategory.tenant_id == self.tenant_id,
            RecordCategory.id == int(category_id),
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def create_category(self, **values: Any) -> RecordCategory:
        return self._add(RecordCategory(**values))

    def category_record_count(self, category_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(RecordFile)
                .where(
                    RecordFile.tenant_id == self.tenant_id,
                    RecordFile.category_id == int(category_id),
                    RecordFile.status != "DISPOSED",
                )
            )
            or 0
        )

    # Records and immutable revisions
    def list_records(
        self,
        *,
        offset: int,
        limit: int,
        park_id: int | None = None,
        category_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> Sequence[RecordFile]:
        stmt = self._scope(select(RecordFile), RecordFile)
        if park_id is not None:
            stmt = stmt.where(RecordFile.park_id == int(park_id))
        if category_id is not None:
            stmt = stmt.where(RecordFile.category_id == int(category_id))
        if status:
            stmt = stmt.where(RecordFile.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(RecordFile.record_no.ilike(pattern) | RecordFile.title.ilike(pattern))
        return list(
            self.session.scalars(
                stmt.order_by(RecordFile.created_at.desc(), RecordFile.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def count_records(
        self,
        *,
        park_id: int | None = None,
        category_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> int:
        stmt = self._scope(select(func.count()).select_from(RecordFile), RecordFile)
        if park_id is not None:
            stmt = stmt.where(RecordFile.park_id == int(park_id))
        if category_id is not None:
            stmt = stmt.where(RecordFile.category_id == int(category_id))
        if status:
            stmt = stmt.where(RecordFile.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(RecordFile.record_no.ilike(pattern) | RecordFile.title.ilike(pattern))
        return int(self.session.scalar(stmt) or 0)

    def get_record(self, record_id: int, *, for_update: bool = False) -> RecordFile | None:
        stmt = self._scope(select(RecordFile).where(RecordFile.id == int(record_id)), RecordFile)
        return self.session.scalar(self._lock(stmt, for_update))

    def create_record(self, **values: Any) -> RecordFile:
        return self._add(RecordFile(**values))

    def revisions(self, record_id: int) -> Sequence[RecordRevision]:
        return list(
            self.session.scalars(
                self._scope(
                    select(RecordRevision).where(RecordRevision.record_id == int(record_id)),
                    RecordRevision,
                ).order_by(RecordRevision.version_no.desc())
            ).all()
        )

    def get_revision(self, revision_id: int) -> RecordRevision | None:
        return self.session.scalar(
            self._scope(
                select(RecordRevision).where(RecordRevision.id == int(revision_id)),
                RecordRevision,
            )
        )

    def latest_revision(self, record_id: int) -> RecordRevision | None:
        return self.session.scalar(
            self._scope(
                select(RecordRevision).where(RecordRevision.record_id == int(record_id)),
                RecordRevision,
            )
            .order_by(RecordRevision.version_no.desc())
            .limit(1)
        )

    def create_revision(self, **values: Any) -> RecordRevision:
        return self._add(RecordRevision(**values))

    def get_attachment(self, attachment_id: int) -> Attachment | None:
        stmt = self._scope(
            select(Attachment).where(
                Attachment.id == int(attachment_id),
                Attachment.status == "ACTIVE",
            ),
            Attachment,
        )
        return self.session.scalar(stmt)

    def integrity_by_key(self, key: str) -> RecordIntegrityEvent | None:
        return self.session.scalar(
            select(RecordIntegrityEvent).where(
                RecordIntegrityEvent.tenant_id == self.tenant_id,
                RecordIntegrityEvent.idempotency_key == key,
            )
        )

    def create_integrity_event(self, **values: Any) -> RecordIntegrityEvent:
        return self._add(RecordIntegrityEvent(**values))

    def integrity_events(self, record_id: int) -> Sequence[RecordIntegrityEvent]:
        return list(
            self.session.scalars(
                self._scope(
                    select(RecordIntegrityEvent).where(
                        RecordIntegrityEvent.record_id == int(record_id)
                    ),
                    RecordIntegrityEvent,
                ).order_by(RecordIntegrityEvent.verified_at.desc())
            ).all()
        )

    def active_hold(self, record_id: int) -> RecordHold | None:
        return self.session.scalar(
            self._scope(
                select(RecordHold).where(
                    RecordHold.record_id == int(record_id), RecordHold.status == "ACTIVE"
                ),
                RecordHold,
            )
        )

    def get_hold(self, hold_id: int) -> RecordHold | None:
        return self.session.scalar(
            self._scope(select(RecordHold).where(RecordHold.id == int(hold_id)), RecordHold)
        )

    def holds(self, record_id: int) -> Sequence[RecordHold]:
        return list(
            self.session.scalars(
                self._scope(
                    select(RecordHold).where(RecordHold.record_id == int(record_id)), RecordHold
                ).order_by(RecordHold.placed_at.desc())
            ).all()
        )

    def create_hold(self, **values: Any) -> RecordHold:
        return self._add(RecordHold(**values))

    # Access and disposition approvals
    def list_access_requests(self, *, status: str | None = None) -> Sequence[RecordAccessRequest]:
        stmt = self._scope(select(RecordAccessRequest), RecordAccessRequest)
        if status:
            stmt = stmt.where(RecordAccessRequest.status == status)
        return list(
            self.session.scalars(stmt.order_by(RecordAccessRequest.created_at.desc())).all()
        )

    def get_access_request(
        self, request_id: int, *, for_update: bool = False
    ) -> RecordAccessRequest | None:
        stmt = self._scope(
            select(RecordAccessRequest).where(RecordAccessRequest.id == int(request_id)),
            RecordAccessRequest,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def access_by_key(self, key: str) -> RecordAccessRequest | None:
        return self.session.scalar(
            select(RecordAccessRequest).where(
                RecordAccessRequest.tenant_id == self.tenant_id,
                RecordAccessRequest.request_key == key,
            )
        )

    def create_access_request(self, **values: Any) -> RecordAccessRequest:
        return self._add(RecordAccessRequest(**values))

    def list_dispositions(self, *, status: str | None = None) -> Sequence[RecordDisposition]:
        stmt = self._scope(select(RecordDisposition), RecordDisposition)
        if status:
            stmt = stmt.where(RecordDisposition.status == status)
        return list(self.session.scalars(stmt.order_by(RecordDisposition.created_at.desc())).all())

    def get_disposition(
        self, disposition_id: int, *, for_update: bool = False
    ) -> RecordDisposition | None:
        stmt = self._scope(
            select(RecordDisposition).where(RecordDisposition.id == int(disposition_id)),
            RecordDisposition,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def disposition_by_key(self, key: str) -> RecordDisposition | None:
        return self.session.scalar(
            select(RecordDisposition).where(
                RecordDisposition.tenant_id == self.tenant_id,
                RecordDisposition.request_key == key,
            )
        )

    def create_disposition(self, **values: Any) -> RecordDisposition:
        return self._add(RecordDisposition(**values))

    def create_disposition_confirmation(self, **values: Any) -> RecordDispositionConfirmation:
        return self._add(RecordDispositionConfirmation(**values))

    def disposition_confirmations(
        self, disposition_id: int
    ) -> Sequence[RecordDispositionConfirmation]:
        return list(
            self.session.scalars(
                select(RecordDispositionConfirmation)
                .where(
                    RecordDispositionConfirmation.tenant_id == self.tenant_id,
                    RecordDispositionConfirmation.disposition_id == int(disposition_id),
                )
                .order_by(RecordDispositionConfirmation.confirmed_at)
            ).all()
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

    def approval_by_business(self, biz_type: str, biz_id: str) -> ApprovalRequest | None:
        return self.session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.tenant_id,
                ApprovalRequest.biz_type == biz_type,
                ApprovalRequest.biz_id == biz_id,
            )
        )

    # Seal registry and custody
    def list_seals(
        self, *, park_id: int | None = None, status: str | None = None
    ) -> Sequence[SealAsset]:
        stmt = self._scope(select(SealAsset), SealAsset)
        if park_id is not None:
            stmt = stmt.where(SealAsset.park_id == int(park_id))
        if status:
            stmt = stmt.where(SealAsset.status == status)
        return list(self.session.scalars(stmt.order_by(SealAsset.seal_code)).all())

    def get_seal(self, seal_id: int, *, for_update: bool = False) -> SealAsset | None:
        stmt = self._scope(select(SealAsset).where(SealAsset.id == int(seal_id)), SealAsset)
        return self.session.scalar(self._lock(stmt, for_update))

    def create_seal(self, **values: Any) -> SealAsset:
        return self._add(SealAsset(**values))

    def create_custody_event(self, **values: Any) -> SealCustodyEvent:
        return self._add(SealCustodyEvent(**values))

    def custody_events(self, seal_id: int) -> Sequence[SealCustodyEvent]:
        return list(
            self.session.scalars(
                self._scope(
                    select(SealCustodyEvent).where(SealCustodyEvent.seal_id == int(seal_id)),
                    SealCustodyEvent,
                ).order_by(SealCustodyEvent.occurred_at.desc())
            ).all()
        )

    def pending_transfer(self, seal_id: int) -> SealCustodyEvent | None:
        return self.session.scalar(
            self._scope(
                select(SealCustodyEvent).where(
                    SealCustodyEvent.seal_id == int(seal_id),
                    SealCustodyEvent.event_type == "TRANSFER_REQUESTED",
                    SealCustodyEvent.status == "PENDING",
                ),
                SealCustodyEvent,
            )
        )

    def list_seal_applications(self, *, status: str | None = None) -> Sequence[SealUseApplication]:
        stmt = self._scope(select(SealUseApplication), SealUseApplication)
        if status:
            stmt = stmt.where(SealUseApplication.status == status)
        return list(self.session.scalars(stmt.order_by(SealUseApplication.created_at.desc())).all())

    def get_seal_application(
        self, application_id: int, *, for_update: bool = False
    ) -> SealUseApplication | None:
        stmt = self._scope(
            select(SealUseApplication).where(SealUseApplication.id == int(application_id)),
            SealUseApplication,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def seal_application_by_key(self, key: str) -> SealUseApplication | None:
        return self.session.scalar(
            select(SealUseApplication).where(
                SealUseApplication.tenant_id == self.tenant_id,
                SealUseApplication.application_key == key,
            )
        )

    def create_seal_application(self, **values: Any) -> SealUseApplication:
        return self._add(SealUseApplication(**values))

    def get_seal_receipt(self, application_id: int) -> SealUseReceipt | None:
        return self.session.scalar(
            select(SealUseReceipt).where(
                SealUseReceipt.tenant_id == self.tenant_id,
                SealUseReceipt.application_id == int(application_id),
            )
        )

    def seal_receipt_by_key(self, key: str) -> SealUseReceipt | None:
        return self.session.scalar(
            select(SealUseReceipt).where(
                SealUseReceipt.tenant_id == self.tenant_id,
                SealUseReceipt.idempotency_key == key,
            )
        )

    def create_seal_receipt(self, **values: Any) -> SealUseReceipt:
        return self._add(SealUseReceipt(**values))

    # Signature providers and immutable evidence
    def list_signature_providers(self) -> Sequence[SignatureProvider]:
        return list(
            self.session.scalars(
                select(SignatureProvider)
                .where(SignatureProvider.tenant_id == self.tenant_id)
                .order_by(SignatureProvider.code)
            ).all()
        )

    def get_signature_provider(
        self, provider_id: int, *, for_update: bool = False
    ) -> SignatureProvider | None:
        stmt = select(SignatureProvider).where(
            SignatureProvider.tenant_id == self.tenant_id,
            SignatureProvider.id == int(provider_id),
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def create_signature_provider(self, **values: Any) -> SignatureProvider:
        return self._add(SignatureProvider(**values))

    def list_signature_envelopes(self, *, status: str | None = None) -> Sequence[SignatureEnvelope]:
        stmt = self._scope(select(SignatureEnvelope), SignatureEnvelope)
        if status:
            stmt = stmt.where(SignatureEnvelope.status == status)
        return list(self.session.scalars(stmt.order_by(SignatureEnvelope.created_at.desc())).all())

    def get_signature_envelope(
        self, envelope_id: int, *, for_update: bool = False
    ) -> SignatureEnvelope | None:
        stmt = self._scope(
            select(SignatureEnvelope).where(SignatureEnvelope.id == int(envelope_id)),
            SignatureEnvelope,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def create_signature_envelope(self, **values: Any) -> SignatureEnvelope:
        return self._add(SignatureEnvelope(**values))

    def create_signature_participant(self, **values: Any) -> SignatureParticipant:
        return self._add(SignatureParticipant(**values))

    def signature_participants(self, envelope_id: int) -> Sequence[SignatureParticipant]:
        return list(
            self.session.scalars(
                select(SignatureParticipant)
                .where(
                    SignatureParticipant.tenant_id == self.tenant_id,
                    SignatureParticipant.envelope_id == int(envelope_id),
                )
                .order_by(SignatureParticipant.position)
            ).all()
        )

    def create_signature_event(self, **values: Any) -> SignatureEvent:
        return self._add(SignatureEvent(**values))

    def signature_events(self, envelope_id: int) -> Sequence[SignatureEvent]:
        return list(
            self.session.scalars(
                select(SignatureEvent)
                .where(
                    SignatureEvent.tenant_id == self.tenant_id,
                    SignatureEvent.envelope_id == int(envelope_id),
                )
                .order_by(SignatureEvent.occurred_at)
            ).all()
        )
