"""Persistence queries for schedule billing, receipt matching and dunning."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.billing import Bill
from app.infrastructure.database.models.collection import PaymentAllocation
from app.infrastructure.database.models.collection_case import CollectionCase
from app.infrastructure.database.models.party import Party
from app.infrastructure.database.models.receivables import (
    CollectionRecord,
    DunningRun,
    ReceiptMatchCandidate,
    ReceiptTransaction,
    ReceivableAdjustment,
)
from app.shared.tenant_context import ParkScopeMode, TenantContext


class ReceivablesRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _park_scope(self, stmt, park_column):
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(park_column.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def receipt_by_source(self, provider: str, source_ref: str) -> ReceiptTransaction | None:
        return self.session.scalars(
            select(ReceiptTransaction).where(
                ReceiptTransaction.tenant_id == self.ctx.tenant_id,
                ReceiptTransaction.source_provider == provider,
                ReceiptTransaction.source_ref == source_ref,
            )
        ).first()

    def create_receipt(self, **values) -> ReceiptTransaction:
        model = ReceiptTransaction(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(model)
        self.session.flush()
        return model

    def _receipt_scope(self, stmt):
        stmt = stmt.where(ReceiptTransaction.tenant_id == self.ctx.tenant_id)
        return self._park_scope(stmt, ReceiptTransaction.park_id)

    def receipt(self, receipt_id: int, *, for_update: bool = False) -> ReceiptTransaction | None:
        stmt = self._receipt_scope(
            select(ReceiptTransaction).where(ReceiptTransaction.id == int(receipt_id))
        )
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def list_receipts(
        self,
        *,
        offset: int,
        limit: int,
        status: str | None,
        park_id: int | None,
    ) -> tuple[list[ReceiptTransaction], int]:
        stmt = self._receipt_scope(select(ReceiptTransaction))
        if status:
            stmt = stmt.where(ReceiptTransaction.status == status)
        if park_id is not None:
            stmt = stmt.where(ReceiptTransaction.park_id == int(park_id))
        total = int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        rows = list(
            self.session.scalars(
                stmt.order_by(ReceiptTransaction.received_at.desc(), ReceiptTransaction.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return rows, total

    def candidate_bills(
        self, *, park_id: int, party_id: int | None, reference: str | None
    ) -> list[tuple[Bill, str]]:
        stmt = (
            select(Bill, Party.name)
            .join(Party, Party.id == Bill.party_id)
            .where(
                Bill.tenant_id == self.ctx.tenant_id,
                Party.tenant_id == self.ctx.tenant_id,
                Bill.park_id == int(park_id),
                Bill.status.in_(["ISSUED", "PARTIALLY_PAID"]),
            )
        )
        if party_id is not None:
            stmt = stmt.where(Bill.party_id == int(party_id))
        # Reference scoring is performed in Domain/Application so exact and embedded
        # Bill numbers remain explainable; the query only applies authority bounds.
        _ = reference
        return list(self.session.execute(stmt.order_by(Bill.due_date, Bill.id)).all())

    def replace_candidates(self, receipt_id: int, candidates: Sequence[dict]) -> None:
        self.session.execute(
            delete(ReceiptMatchCandidate).where(
                ReceiptMatchCandidate.tenant_id == self.ctx.tenant_id,
                ReceiptMatchCandidate.receipt_id == int(receipt_id),
            )
        )
        self.session.add_all(
            ReceiptMatchCandidate(
                tenant_id=self.ctx.tenant_id,
                receipt_id=int(receipt_id),
                **candidate,
            )
            for candidate in candidates
        )
        self.session.flush()

    def candidates(self, receipt_id: int) -> list[ReceiptMatchCandidate]:
        return list(
            self.session.scalars(
                select(ReceiptMatchCandidate)
                .where(
                    ReceiptMatchCandidate.tenant_id == self.ctx.tenant_id,
                    ReceiptMatchCandidate.receipt_id == int(receipt_id),
                )
                .order_by(ReceiptMatchCandidate.rank, ReceiptMatchCandidate.id)
            ).all()
        )

    def active_allocated_for_payment(self, payment_id: int):
        return self.session.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
                PaymentAllocation.tenant_id == self.ctx.tenant_id,
                PaymentAllocation.payment_id == int(payment_id),
                PaymentAllocation.reversed_at.is_(None),
            )
        )

    def open_bills_for_dunning(self, *, park_id: int | None) -> list[Bill]:
        stmt = select(Bill).where(
            Bill.tenant_id == self.ctx.tenant_id,
            Bill.status.in_(["ISSUED", "PARTIALLY_PAID"]),
        )
        stmt = self._park_scope(stmt, Bill.park_id)
        if park_id is not None:
            stmt = stmt.where(Bill.park_id == int(park_id))
        return list(self.session.scalars(stmt.order_by(Bill.due_date, Bill.id)).all())

    def active_cases_for_bill(
        self, bill_id: int, *, for_update: bool = False
    ) -> list[CollectionCase]:
        stmt = select(CollectionCase).where(
            CollectionCase.tenant_id == self.ctx.tenant_id,
            CollectionCase.bill_id == int(bill_id),
            CollectionCase.status.in_(["OPEN", "PAUSED"]),
        )
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            stmt = stmt.with_for_update()
        return list(self.session.scalars(stmt.order_by(CollectionCase.id)).all())

    def create_case(self, **values) -> CollectionCase:
        model = CollectionCase(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(model)
        self.session.flush()
        return model

    def case(self, case_id: int, *, for_update: bool = False) -> CollectionCase | None:
        stmt = select(CollectionCase).where(
            CollectionCase.tenant_id == self.ctx.tenant_id,
            CollectionCase.id == int(case_id),
        )
        stmt = self._park_scope(stmt, CollectionCase.park_id)
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def create_record(self, **values) -> CollectionRecord:
        model = CollectionRecord(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(model)
        self.session.flush()
        return model

    def record_by_source(self, source_ref: str) -> CollectionRecord | None:
        return self.session.scalars(
            select(CollectionRecord).where(
                CollectionRecord.tenant_id == self.ctx.tenant_id,
                CollectionRecord.source_ref == source_ref,
            )
        ).first()

    def records(self, case_id: int) -> list[CollectionRecord]:
        return list(
            self.session.scalars(
                select(CollectionRecord)
                .where(
                    CollectionRecord.tenant_id == self.ctx.tenant_id,
                    CollectionRecord.case_id == int(case_id),
                )
                .order_by(CollectionRecord.created_at, CollectionRecord.id)
            ).all()
        )

    def create_dunning_run(self, **values) -> DunningRun:
        model = DunningRun(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(model)
        self.session.flush()
        return model

    def create_adjustment(self, **values) -> ReceivableAdjustment:
        model = ReceivableAdjustment(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(model)
        self.session.flush()
        return model

    def adjustment(
        self, adjustment_id: int, *, for_update: bool = False
    ) -> ReceivableAdjustment | None:
        stmt = select(ReceivableAdjustment).where(
            ReceivableAdjustment.tenant_id == self.ctx.tenant_id,
            ReceivableAdjustment.id == int(adjustment_id),
        )
        stmt = self._park_scope(stmt, ReceivableAdjustment.park_id)
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def list_adjustments(self, *, bill_id: int | None = None) -> list[ReceivableAdjustment]:
        stmt = select(ReceivableAdjustment).where(
            ReceivableAdjustment.tenant_id == self.ctx.tenant_id
        )
        stmt = self._park_scope(stmt, ReceivableAdjustment.park_id)
        if bill_id is not None:
            stmt = stmt.where(ReceivableAdjustment.bill_id == int(bill_id))
        return list(self.session.scalars(stmt.order_by(ReceivableAdjustment.id.desc())).all())
