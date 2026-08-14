"""Strict HTTP boundary for receipts, matching, dunning and treatments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.collection.application.collection_case_service import CollectionCaseService
from app.modules.collection.application.payment_service import PaymentService
from app.modules.collection.application.receivables_service import ReceivablesService
from app.modules.collection.interface.schemas import (
    CollectionRecordCreate,
    DunningRun,
    PaymentAllocate,
    ReceiptConfirm,
    ReceiptCreate,
    ReceiptDispute,
    ReceiptDisputeDecision,
    ReceiptException,
    ReceiptImport,
    ReceivableAdjustmentCreate,
    VersionCommand,
)
from app.shared.deps import get_tenant_context
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Receivables"])


def _svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> ReceivablesService:
    return ReceivablesService(db, ctx)


def _payment_svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> PaymentService:
    return PaymentService(db, ctx)


def _case_svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> CollectionCaseService:
    return CollectionCaseService(db, ctx)


@router.get("/receipts/capabilities")
def receipt_capabilities(svc: ReceivablesService = Depends(_svc)) -> dict:
    return ok(svc.capabilities())


@router.get("/receipts")
def list_receipts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    park_id: int | None = Query(default=None, gt=0),
    svc: ReceivablesService = Depends(_svc),
) -> dict:
    return ok(svc.list_receipts(page=page, page_size=page_size, status=status, park_id=park_id))


@router.post("/receipts")
def create_receipt(body: ReceiptCreate, svc: ReceivablesService = Depends(_svc)) -> dict:
    return ok(svc.ingest_receipt(body.model_dump()), message="ingested")


@router.post("/receipts/import")
def import_receipts(body: ReceiptImport, svc: ReceivablesService = Depends(_svc)) -> dict:
    return ok(svc.import_receipts([row.model_dump() for row in body.rows]), message="imported")


@router.get("/receipts/{receipt_id}")
def receipt_detail(receipt_id: int, svc: ReceivablesService = Depends(_svc)) -> dict:
    return ok(svc.receipt_detail(receipt_id))


@router.post("/receipts/{receipt_id}/match")
def match_receipt(
    receipt_id: int, body: VersionCommand, svc: ReceivablesService = Depends(_svc)
) -> dict:
    return ok(svc.run_match(receipt_id, expected_version=body.expected_version), message="matched")


@router.post("/receipts/{receipt_id}/confirm")
def confirm_receipt(
    receipt_id: int, body: ReceiptConfirm, svc: ReceivablesService = Depends(_svc)
) -> dict:
    return ok(
        svc.confirm_receipt(
            receipt_id,
            expected_version=body.expected_version,
            party_id=body.party_id,
            allocations=[row.model_dump() for row in body.allocations]
            if body.allocations is not None
            else None,
            remark=body.remark,
        ),
        message="confirmed",
    )


@router.post("/receipts/{receipt_id}/exception")
def receipt_exception(
    receipt_id: int, body: ReceiptException, svc: ReceivablesService = Depends(_svc)
) -> dict:
    return ok(
        svc.mark_exception(
            receipt_id,
            expected_version=body.expected_version,
            code=body.code,
            remark=body.remark,
        ),
        message="exception_recorded",
    )


@router.post("/receipts/{receipt_id}/dispute")
def raise_receipt_dispute(
    receipt_id: int, body: ReceiptDispute, svc: ReceivablesService = Depends(_svc)
) -> dict:
    return ok(
        svc.raise_dispute(receipt_id, expected_version=body.expected_version, reason=body.reason),
        message="disputed",
    )


@router.post("/receipts/{receipt_id}/dispute/resolve")
def resolve_receipt_dispute(
    receipt_id: int,
    body: ReceiptDisputeDecision,
    svc: ReceivablesService = Depends(_svc),
) -> dict:
    return ok(
        svc.resolve_dispute(
            receipt_id,
            expected_version=body.expected_version,
            decision=body.decision,
            remark=body.remark,
        ),
        message="resolved",
    )


@router.post("/payments/{payment_id}/allocations")
def allocate_payment(
    payment_id: int,
    body: PaymentAllocate,
    svc: PaymentService = Depends(_payment_svc),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    return ok(
        svc.allocate_payment(
            payment_id,
            [row.model_dump() for row in body.allocations],
            idempotency_key=idempotency_key,
        ),
        message="allocated",
    )


@router.get("/collection/runs/preview")
def preview_dunning(
    as_of: str,
    park_id: int | None = Query(default=None, gt=0),
    svc: ReceivablesService = Depends(_svc),
) -> dict:
    return ok(svc.dunning_preview(as_of=as_of, park_id=park_id))


@router.post("/collection/runs")
def apply_dunning(
    body: DunningRun,
    svc: ReceivablesService = Depends(_svc),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    return ok(
        svc.dunning_apply(
            as_of=body.as_of,
            park_id=body.park_id,
            idempotency_key=idempotency_key,
        ),
        message="dunning_completed",
    )


@router.get("/collection/cases/{case_id}/records")
def list_collection_records(case_id: int, svc: CollectionCaseService = Depends(_case_svc)) -> dict:
    return ok(svc.list_records(case_id))


@router.post("/collection/cases/{case_id}/records")
def create_collection_record(
    case_id: int,
    body: CollectionRecordCreate,
    svc: CollectionCaseService = Depends(_case_svc),
) -> dict:
    return ok(svc.add_record(case_id, body.model_dump()), message="recorded")


@router.get("/receivable-adjustments")
def list_adjustments(
    bill_id: int | None = Query(default=None, gt=0),
    svc: ReceivablesService = Depends(_svc),
) -> dict:
    return ok(svc.list_adjustments(bill_id=bill_id))


@router.post("/receivable-adjustments")
def request_adjustment(
    body: ReceivableAdjustmentCreate,
    svc: ReceivablesService = Depends(_svc),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    return ok(
        svc.request_adjustment(body.model_dump(), idempotency_key=idempotency_key),
        message="submitted",
    )


@router.post("/receivable-adjustments/{adjustment_id}/apply")
def apply_adjustment(
    adjustment_id: int,
    body: VersionCommand,
    svc: ReceivablesService = Depends(_svc),
) -> dict:
    return ok(
        svc.apply_adjustment(adjustment_id, expected_version=body.expected_version),
        message="applied",
    )
