"""Party Repository 专项测试（租户隔离与可见性）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.database.models.party import Party, PartyParkRelation, PartyRole
from app.infrastructure.database.base import utc_now
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.modules.park_property.application.park_service import ParkService
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _ctx(
    *,
    permissions: list[str] | None = None,
    mode: ParkScopeMode = ParkScopeMode.ALL,
    park_ids: list[int] | None = None,
    tenant_id: int = 1,
) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="repo-test",
        permissions=permissions or ["*"],
        park_scope_mode=mode,
        park_ids=park_ids or [],
    )


def test_repository_tenant_isolation(db_session: Session) -> None:
    """功能说明：跨租户查询不得返回其他租户 Party。"""
    repo_t1 = PartyRepository(db_session, _ctx(tenant_id=1))
    p = Party(
        tenant_id=1,
        party_type="ORGANIZATION",
        name="租户1公司",
        status="ACTIVE",
        risk_status="NORMAL",
    )
    repo_t1.add(p)
    db_session.commit()

    repo_t2 = PartyRepository(db_session, _ctx(tenant_id=2))
    assert repo_t2.get_by_id(p.id) is None
    assert repo_t2.get_raw_by_id(p.id) is None


def test_repository_park_scope_visibility(db_session: Session) -> None:
    """功能说明：LIST 范围仅见关联 ACTIVE 关系的 Party。"""
    admin = _ctx(mode=ParkScopeMode.ALL)
    park = ParkService(db_session, admin).create_park({"name": "可见园"})
    park_id = park["id"]

    repo = PartyRepository(db_session, admin)
    party = Party(
        tenant_id=1,
        party_type="ORGANIZATION",
        name="有园公司",
        status="ACTIVE",
        risk_status="NORMAL",
    )
    repo.add(party)
    role = PartyRole(
        tenant_id=1,
        party_id=party.id,
        role_code="LESSEE",
        status="ACTIVE",
        started_at=utc_now(),
    )
    db_session.add(role)
    db_session.flush()
    db_session.add(
        PartyParkRelation(
            tenant_id=1,
            party_id=party.id,
            park_id=park_id,
            party_role_id=role.id,
            status="ACTIVE",
            started_at=utc_now(),
        )
    )
    db_session.commit()

    scoped = PartyRepository(
        db_session,
        _ctx(
            permissions=["party:read"],
            mode=ParkScopeMode.LIST,
            park_ids=[park_id],
        ),
    )
    assert scoped.get_by_id(party.id) is not None

    other = PartyRepository(
        db_session,
        _ctx(
            permissions=["party:read"],
            mode=ParkScopeMode.LIST,
            park_ids=[park_id + 9999],
        ),
    )
    assert other.get_by_id(party.id) is None

    empty = PartyRepository(
        db_session,
        _ctx(permissions=["party:read"], mode=ParkScopeMode.NONE, park_ids=[]),
    )
    assert empty.get_by_id(party.id) is None
