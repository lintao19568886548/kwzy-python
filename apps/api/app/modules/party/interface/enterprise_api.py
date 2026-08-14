"""HTTP boundary for governed enterprise profiles."""

# FastAPI dependency injection intentionally evaluates Depends in signatures.
# ruff: noqa: B008

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.party.application.enterprise_service import PartyEnterpriseService
from app.modules.party.interface.enterprise_schemas import (
    EnterpriseCredentialCreate,
    EnterpriseCredentialReview,
    EnterpriseCredentialTransition,
    EnterpriseProfileSave,
    EnterpriseRelationshipCreate,
    EnterpriseRiskResolve,
    EnterpriseRiskSignalCreate,
    EnterpriseTagCreate,
    VersionReason,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Party Enterprise Profiles"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> PartyEnterpriseService:
    return PartyEnterpriseService(db, ctx)


@router.get(
    "/enterprise-parties",
    dependencies=[Depends(require_permissions("party:read"))],
)
def enterprise_directory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    status: Literal["ACTIVE", "INACTIVE"] | None = None,
    blacklist_status: Literal["NORMAL", "BLACKLISTED"] | None = None,
    registration_status: Literal["ACTIVE", "SUSPENDED", "REVOKED", "CANCELLED", "UNKNOWN"]
    | None = None,
    industry: str | None = Query(default=None, max_length=128),
    min_completeness: int | None = Query(default=None, ge=0, le=100),
    max_completeness: int | None = Query(default=None, ge=0, le=100),
    local_risk_level: Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None,
    sort_by: Literal["name", "updated_at", "completeness"] = "updated_at",
    sort_order: Literal["asc", "desc"] = "desc",
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.directory(
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
            blacklist_status=blacklist_status,
            registration_status=registration_status,
            industry=industry,
            min_completeness=min_completeness,
            max_completeness=max_completeness,
            local_risk_level=local_risk_level,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )


@router.get(
    "/parties/{party_id}/enterprise-profile",
    dependencies=[Depends(require_permissions("party:read"))],
)
def get_enterprise_profile(
    party_id: int, svc: PartyEnterpriseService = Depends(_svc)
) -> dict:
    return ok(svc.get_profile(party_id))


@router.put("/parties/{party_id}/enterprise-profile")
def save_enterprise_profile(
    party_id: int,
    body: EnterpriseProfileSave,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.save_profile(party_id, body.model_dump(exclude_unset=True)),
        message="saved",
    )


@router.get(
    "/parties/{party_id}/enterprise-relationships",
    dependencies=[Depends(require_permissions("party:read"))],
)
def list_enterprise_relationships(
    party_id: int,
    include_ended: bool = False,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(svc.list_relationships(party_id, include_ended=include_ended))


@router.post("/parties/{party_id}/enterprise-relationships")
def create_enterprise_relationship(
    party_id: int,
    body: EnterpriseRelationshipCreate,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_relationship(party_id, body.model_dump(exclude_unset=True)),
        message="created",
    )


@router.post("/parties/{party_id}/enterprise-relationships/{relationship_id}/end")
def end_enterprise_relationship(
    party_id: int,
    relationship_id: int,
    body: VersionReason,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.end_relationship(
            party_id,
            relationship_id,
            expected_lock_version=body.expected_lock_version,
            reason=body.reason,
        ),
        message="ended",
    )


@router.get(
    "/parties/{party_id}/enterprise-credentials",
    dependencies=[Depends(require_permissions("party:credential_read"))],
)
def list_enterprise_credentials(
    party_id: int,
    include_archived: bool = False,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(svc.list_credentials(party_id, include_archived=include_archived))


@router.post(
    "/parties/{party_id}/enterprise-credentials",
    dependencies=[Depends(require_permissions("party:credential_manage"))],
)
def create_enterprise_credential(
    party_id: int,
    body: EnterpriseCredentialCreate,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_credential(party_id, body.model_dump(exclude_unset=True)),
        message="created",
    )


@router.post(
    "/parties/{party_id}/enterprise-credentials/{credential_id}/review",
    dependencies=[Depends(require_permissions("party:credential_manage"))],
)
def review_enterprise_credential(
    party_id: int,
    credential_id: int,
    body: EnterpriseCredentialReview,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.review_credential(
            party_id,
            credential_id,
            expected_lock_version=body.expected_lock_version,
            verification_status=body.verification_status,
            reason=body.reason,
        ),
        message="reviewed",
    )


@router.post(
    "/parties/{party_id}/enterprise-credentials/{credential_id}/transition",
    dependencies=[Depends(require_permissions("party:credential_manage"))],
)
def transition_enterprise_credential(
    party_id: int,
    credential_id: int,
    body: EnterpriseCredentialTransition,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.transition_credential(
            party_id,
            credential_id,
            expected_lock_version=body.expected_lock_version,
            status=body.status,
            reason=body.reason,
        ),
        message="transitioned",
    )


@router.get(
    "/parties/{party_id}/enterprise-tags",
    dependencies=[Depends(require_permissions("party:read"))],
)
def list_enterprise_tags(
    party_id: int,
    include_inactive: bool = False,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(svc.list_tags(party_id, include_inactive=include_inactive))


@router.post("/parties/{party_id}/enterprise-tags")
def create_enterprise_tag(
    party_id: int,
    body: EnterpriseTagCreate,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_tag(party_id, body.model_dump(exclude_unset=True)),
        message="created",
    )


@router.post("/parties/{party_id}/enterprise-tags/{tag_id}/deactivate")
def deactivate_enterprise_tag(
    party_id: int,
    tag_id: int,
    body: VersionReason,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.deactivate_tag(
            party_id,
            tag_id,
            expected_lock_version=body.expected_lock_version,
            reason=body.reason,
        ),
        message="deactivated",
    )


@router.get(
    "/parties/{party_id}/enterprise-risk-signals",
    dependencies=[Depends(require_permissions("party:risk_read"))],
)
def list_enterprise_risk_signals(
    party_id: int, svc: PartyEnterpriseService = Depends(_svc)
) -> dict:
    return ok(svc.list_risk_signals(party_id))


@router.post(
    "/parties/{party_id}/enterprise-risk-signals",
    dependencies=[Depends(require_permissions("party:risk_manage"))],
)
def create_enterprise_risk_signal(
    party_id: int,
    body: EnterpriseRiskSignalCreate,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_risk_signal(party_id, body.model_dump(exclude_unset=True)),
        message="created",
    )


@router.post(
    "/parties/{party_id}/enterprise-risk-signals/{signal_id}/resolve",
    dependencies=[Depends(require_permissions("party:risk_manage"))],
)
def resolve_enterprise_risk_signal(
    party_id: int,
    signal_id: int,
    body: EnterpriseRiskResolve,
    svc: PartyEnterpriseService = Depends(_svc),
) -> dict:
    return ok(
        svc.resolve_risk_signal(
            party_id,
            signal_id,
            resolution_type=body.resolution_type,
            reason=body.reason,
        ),
        message="resolved",
    )
