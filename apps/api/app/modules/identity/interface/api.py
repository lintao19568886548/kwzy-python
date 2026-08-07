"""Identity interface — login + me for step1."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.identity.application.auth_service import AuthService
from app.modules.identity.schemas import LoginRequest, LoginResponse, UserInfo
from app.shared.deps import TenantContext, get_tenant_context
from app.shared.response import ok

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    data = LoginResponse.model_validate(
        AuthService(db).login(
            username=body.username,
            password=body.password,
            tenant_code=body.tenant_code,
        )
    )
    return ok(data.model_dump())


@router.get("/me")
def me(ctx: TenantContext = Depends(get_tenant_context)) -> dict:
    info = UserInfo(
        id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        username=ctx.username,
        permissions=ctx.permissions,
        park_ids=ctx.park_ids,
    )
    return ok(info.model_dump())
