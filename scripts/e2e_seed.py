#!/usr/bin/env python3
"""Seed E2E tenants, users, roles, parks for browser full-stack tests.

Requires DATABASE_URL pointing at the E2E PostgreSQL instance.
Never connects to production databases.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.identity import (
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.infrastructure.database.models.park_property import Building, Park, Unit
from app.modules.identity.application.bootstrap import ensure_default_tenant


def _ensure_role(
    db,
    *,
    tenant_id: int,
    code: str,
    name: str,
    perm_codes: list[str],
    all_parks: bool = True,
) -> Role:
    role = db.scalars(
        select(Role).where(Role.tenant_id == tenant_id, Role.code == code)
    ).first()
    if role is None:
        role = Role(
            tenant_id=tenant_id,
            code=code,
            name=name,
            status="ACTIVE",
            all_parks=all_parks,
        )
        db.add(role)
        db.flush()
    for pcode in perm_codes:
        perm = db.scalars(select(Permission).where(Permission.code == pcode)).first()
        if not perm:
            continue
        exists = db.scalars(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == perm.id,
            )
        ).first()
        if exists is None:
            db.add(
                RolePermission(
                    tenant_id=tenant_id, role_id=role.id, permission_id=perm.id
                )
            )
    return role


def _ensure_user(
    db,
    *,
    tenant_id: int,
    username: str,
    password: str,
    real_name: str,
    role: Role,
    all_parks: bool = False,
    reset_password: bool = False,
) -> User:
    user = db.scalars(
        select(User).where(User.tenant_id == tenant_id, User.username == username)
    ).first()
    if user is None:
        user = User(
            tenant_id=tenant_id,
            username=username,
            password_hash=hash_password(password),
            real_name=real_name,
            status="ACTIVE",
            all_parks=all_parks,
        )
        db.add(user)
        db.flush()
    elif reset_password:
        user.password_hash = hash_password(password)
        user.status = "ACTIVE"
        db.add(user)
    ur = db.scalars(
        select(UserRole).where(
            UserRole.user_id == user.id, UserRole.role_id == role.id
        )
    ).first()
    if ur is None:
        db.add(UserRole(tenant_id=tenant_id, user_id=user.id, role_id=role.id))
    return user


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    url = os.environ.get("DATABASE_URL") or settings.database_url
    if "prod" in (url or "").lower() and "test" not in (url or "").lower():
        print("REFUSE: DATABASE_URL looks like production", file=sys.stderr)
        return 2

    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        ensure_default_tenant(db)
        tenant = db.scalars(select(Tenant).where(Tenant.code == "default")).first()
        assert tenant is not None

        admin_role = db.scalars(
            select(Role).where(Role.tenant_id == tenant.id, Role.code == "ADMIN")
        ).first()
        assert admin_role is not None

        # Always reset admin password for deterministic E2E
        admin_pwd = (
            os.environ.get("LOCAL_ADMIN_PASSWORD")
            or settings.local_admin_password
            or "admin123"
        ).strip() or "admin123"
        _ensure_user(
            db,
            tenant_id=tenant.id,
            username="admin",
            password=admin_pwd,
            real_name="管理员",
            role=admin_role,
            reset_password=True,
        )

        limited_role = _ensure_role(
            db,
            tenant_id=tenant.id,
            code="E2E_LIMITED",
            name="E2E只读主体",
            perm_codes=["party:read"],
            all_parks=True,
        )
        _ensure_user(
            db,
            tenant_id=tenant.id,
            username="e2e_limited",
            password="limited123",
            real_name="受限用户",
            role=limited_role,
            reset_password=True,
        )

        # Second tenant for cross-tenant isolation tests
        t2 = db.scalars(select(Tenant).where(Tenant.code == "tenant_b")).first()
        if t2 is None:
            t2 = Tenant(
                code="tenant_b",
                name="租户B",
                status="ACTIVE",
                db_strategy="SHARED",
            )
            db.add(t2)
            db.flush()
        t2_admin_role = _ensure_role(
            db,
            tenant_id=t2.id,
            code="ADMIN",
            name="租户B管理员",
            perm_codes=["*"],
            all_parks=True,
        )
        _ensure_user(
            db,
            tenant_id=t2.id,
            username="admin_b",
            password="adminb123",
            real_name="租户B管理员",
            role=t2_admin_role,
            reset_password=True,
        )

        # Seed parks + units for main chain UI
        park = db.scalars(
            select(Park).where(Park.tenant_id == tenant.id, Park.name == "E2E默认园")
        ).first()
        if park is None:
            park = Park(
                tenant_id=tenant.id,
                name="E2E默认园",
                address="e2e-seed-road",
                status="ACTIVE",
            )
            db.add(park)
            db.flush()
        building = db.scalars(
            select(Building).where(
                Building.tenant_id == tenant.id, Building.park_id == park.id
            )
        ).first()
        if building is None:
            building = Building(
                tenant_id=tenant.id,
                park_id=park.id,
                name="E2E默认楼",
                building_type="FACTORY",
                address="e2e-seed-building",
            )
            db.add(building)
            db.flush()
        unit = db.scalars(
            select(Unit).where(Unit.tenant_id == tenant.id, Unit.code == "E2E-U1")
        ).first()
        if unit is None:
            unit = Unit(
                tenant_id=tenant.id,
                park_id=park.id,
                building_id=building.id,
                code="E2E-U1",
                name="E2E单元1",
                rentable_area=100,
                status="VACANT",
            )
            db.add(unit)

        park_b = db.scalars(
            select(Park).where(Park.tenant_id == t2.id, Park.name == "租户B园")
        ).first()
        if park_b is None:
            db.add(
                Park(
                    tenant_id=t2.id,
                    name="租户B园",
                    address="tenant-b",
                    status="ACTIVE",
                )
            )

        db.commit()
        print(
            "E2E_SEED=OK "
            f"tenant=default park_id={park.id} "
            "admin=admin e2e_limited=e2e_limited tenant_b=admin_b"
        )
        return 0
    except Exception as exc:
        db.rollback()
        print(f"E2E_SEED=FAIL {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
