"""REST endpoints for records, signature and seal governance."""

# FastAPI dependency defaults intentionally call Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.records_seal.application.service import RecordsSealService
from app.modules.records_seal.interface.schemas import (
    AccessRequestCreate,
    CategoryCreate,
    CategoryUpdate,
    DispositionCreate,
    ExpectedReason,
    IntegrityVerify,
    RecordCreate,
    RevisionCreate,
    SealCreate,
    SealTransfer,
    SealUseCreate,
    SealUseExecute,
    SignatureEnvelopeCreate,
    SignatureProviderCreate,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["RecordsSignatureSeal"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> RecordsSealService:
    return RecordsSealService(db, ctx)


@router.get("/record-categories", dependencies=[Depends(require_permissions("record:read"))])
def list_categories(include_retired: bool = False, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.list_categories(include_retired=include_retired))


@router.post("/record-categories", dependencies=[Depends(require_permissions("record:manage"))])
def create_category(body: CategoryCreate, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.create_category(body.model_dump()), message="created")


@router.patch(
    "/record-categories/{category_id}",
    dependencies=[Depends(require_permissions("record:manage"))],
)
def update_category(
    category_id: int, body: CategoryUpdate, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(
        svc.update_category(category_id, body.model_dump(exclude_unset=True)), message="updated"
    )


@router.post(
    "/record-categories/{category_id}/retire",
    dependencies=[Depends(require_permissions("record:manage"))],
)
def retire_category(
    category_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.retire_category(category_id, body.model_dump()), message="retired")


@router.get("/records", dependencies=[Depends(require_permissions("record:read"))])
def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: int | None = None,
    category_id: int | None = None,
    status: str | None = None,
    keyword: str | None = Query(default=None, max_length=100),
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_records(
            page=page,
            page_size=page_size,
            park_id=park_id,
            category_id=category_id,
            status=status,
            keyword=keyword,
        )
    )


@router.post("/records", dependencies=[Depends(require_permissions("record:write"))])
def create_record(body: RecordCreate, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.create_record(body.model_dump()), message="created")


@router.get("/records/{record_id}", dependencies=[Depends(require_permissions("record:read"))])
def get_record(record_id: int, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.get_record(record_id))


@router.post(
    "/records/{record_id}/revisions",
    dependencies=[Depends(require_permissions("record:write"))],
)
def add_revision(
    record_id: int, body: RevisionCreate, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.add_revision(record_id, body.model_dump()), message="created")


@router.post(
    "/records/{record_id}/file",
    dependencies=[Depends(require_permissions("record:write"))],
)
def file_record(
    record_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.file_record(record_id, body.model_dump()), message="filed")


@router.post(
    "/records/{record_id}/verify",
    dependencies=[Depends(require_permissions("record:verify"))],
)
def verify_record(
    record_id: int,
    body: IntegrityVerify,
    idempotency_key: IdempotencyKey,
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(
        svc.verify_integrity(record_id, body.model_dump(), idempotency_key=idempotency_key),
        message="verified",
    )


@router.post(
    "/records/{record_id}/holds",
    dependencies=[Depends(require_permissions("record:hold"))],
)
def place_hold(
    record_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.place_hold(record_id, body.model_dump()), message="held")


@router.post(
    "/records/{record_id}/holds/{hold_id}/release",
    dependencies=[Depends(require_permissions("record:hold"))],
)
def release_hold(
    record_id: int,
    hold_id: int,
    body: ExpectedReason,
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(svc.release_hold(record_id, hold_id, body.model_dump()), message="released")


@router.post(
    "/records/{record_id}/access-requests",
    dependencies=[Depends(require_permissions("record:access_request", "approval:write"))],
)
def request_access(
    record_id: int,
    body: AccessRequestCreate,
    idempotency_key: IdempotencyKey,
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(
        svc.request_access(record_id, body.model_dump(), request_key=idempotency_key),
        message="submitted",
    )


@router.get("/record-access-requests")
def list_access_requests(
    status: str | None = None, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.list_access_requests(status=status))


@router.post("/record-access-requests/{request_id}/refresh-approval")
def refresh_access(request_id: int, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.refresh_access(request_id), message="refreshed")


@router.post(
    "/record-access-requests/{request_id}/checkout",
    dependencies=[Depends(require_permissions("record:access_execute"))],
)
def checkout_access(
    request_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.checkout_access(request_id, body.model_dump()), message="checked_out")


@router.post(
    "/record-access-requests/{request_id}/return",
    dependencies=[Depends(require_permissions("record:access_execute"))],
)
def return_access(
    request_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.return_access(request_id, body.model_dump()), message="returned")


@router.post(
    "/records/{record_id}/dispositions",
    dependencies=[Depends(require_permissions("record:dispose_request", "approval:write"))],
)
def request_disposition(
    record_id: int,
    body: DispositionCreate,
    idempotency_key: IdempotencyKey,
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(
        svc.request_disposition(record_id, body.model_dump(), request_key=idempotency_key),
        message="submitted",
    )


@router.get("/record-dispositions")
def list_dispositions(status: str | None = None, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.list_dispositions(status=status))


@router.post("/record-dispositions/{disposition_id}/refresh-approval")
def refresh_disposition(disposition_id: int, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.refresh_disposition(disposition_id), message="refreshed")


@router.post(
    "/record-dispositions/{disposition_id}/confirm",
    dependencies=[Depends(require_permissions("record:dispose_confirm"))],
)
def confirm_disposition(
    disposition_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.confirm_disposition(disposition_id, body.model_dump()), message="confirmed")


@router.get("/seals", dependencies=[Depends(require_permissions("seal:read"))])
def list_seals(
    park_id: int | None = None,
    status: str | None = None,
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(svc.list_seals(park_id=park_id, status=status))


@router.post("/seals", dependencies=[Depends(require_permissions("seal:manage"))])
def create_seal(body: SealCreate, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.create_seal(body.model_dump()), message="created")


@router.get("/seals/{seal_id}", dependencies=[Depends(require_permissions("seal:read"))])
def get_seal(seal_id: int, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.get_seal(seal_id))


@router.post(
    "/seals/{seal_id}/transfer", dependencies=[Depends(require_permissions("seal:custody"))]
)
def transfer_seal(
    seal_id: int, body: SealTransfer, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.transfer_seal(seal_id, body.model_dump()), message="submitted")


@router.post(
    "/seals/{seal_id}/accept-transfer",
    dependencies=[Depends(require_permissions("seal:custody"))],
)
def accept_transfer(
    seal_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.accept_seal_transfer(seal_id, body.model_dump()), message="accepted")


@router.post(
    "/seals/{seal_id}/mark-lost", dependencies=[Depends(require_permissions("seal:manage"))]
)
def mark_lost(seal_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.transition_seal_state(seal_id, "LOST", "LOST", body.model_dump()), message="lost")


@router.post("/seals/{seal_id}/recover", dependencies=[Depends(require_permissions("seal:manage"))])
def recover_seal(
    seal_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(
        svc.transition_seal_state(seal_id, "SUSPENDED", "RECOVERED", body.model_dump()),
        message="recovered",
    )


@router.post("/seals/{seal_id}/retire", dependencies=[Depends(require_permissions("seal:manage"))])
def retire_seal(
    seal_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(
        svc.transition_seal_state(seal_id, "RETIRED", "RETIRED", body.model_dump()),
        message="retired",
    )


@router.get("/seal-use-applications")
def list_seal_applications(
    status: str | None = None, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.list_seal_applications(status=status))


@router.post(
    "/seal-use-applications",
    dependencies=[Depends(require_permissions("seal:apply", "approval:write"))],
)
def create_seal_application(
    body: SealUseCreate,
    idempotency_key: IdempotencyKey,
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_seal_application(body.model_dump(), application_key=idempotency_key),
        message="submitted",
    )


@router.post("/seal-use-applications/{application_id}/refresh-approval")
def refresh_seal_application(application_id: int, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.refresh_seal_application(application_id), message="refreshed")


@router.post(
    "/seal-use-applications/{application_id}/execute",
    dependencies=[Depends(require_permissions("seal:execute"))],
)
def execute_seal_application(
    application_id: int,
    body: SealUseExecute,
    idempotency_key: IdempotencyKey,
    svc: RecordsSealService = Depends(_svc),
) -> dict:
    return ok(
        svc.execute_seal_application(
            application_id, body.model_dump(), idempotency_key=idempotency_key
        ),
        message="executed",
    )


@router.get("/signature-providers", dependencies=[Depends(require_permissions("signature:read"))])
def list_signature_providers(svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.list_signature_providers())


@router.post(
    "/signature-providers", dependencies=[Depends(require_permissions("signature:manage"))]
)
def create_signature_provider(
    body: SignatureProviderCreate, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.create_signature_provider(body.model_dump()), message="created")


@router.get("/signature-envelopes", dependencies=[Depends(require_permissions("signature:read"))])
def list_signature_envelopes(
    status: str | None = None, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.list_signature_envelopes(status=status))


@router.post("/signature-envelopes", dependencies=[Depends(require_permissions("signature:write"))])
def create_signature_envelope(
    body: SignatureEnvelopeCreate, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.create_signature_envelope(body.model_dump()), message="created")


@router.get(
    "/signature-envelopes/{envelope_id}",
    dependencies=[Depends(require_permissions("signature:read"))],
)
def get_signature_envelope(envelope_id: int, svc: RecordsSealService = Depends(_svc)) -> dict:
    return ok(svc.get_signature_envelope(envelope_id))


@router.post(
    "/signature-envelopes/{envelope_id}/dispatch",
    dependencies=[Depends(require_permissions("signature:dispatch"))],
)
def dispatch_signature_envelope(
    envelope_id: int, body: ExpectedReason, svc: RecordsSealService = Depends(_svc)
) -> dict:
    return ok(svc.dispatch_signature_envelope(envelope_id, body.model_dump()), message="dispatched")
