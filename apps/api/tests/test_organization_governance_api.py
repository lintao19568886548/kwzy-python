"""平台组织治理 API、隔离、字段策略与授权边界测试。"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select

from app.core.security import hash_password
from app.infrastructure.database.models.audit import AuditLog
from app.infrastructure.database.models.identity import (
    Role,
    Tenant,
    User,
    UserParkScope,
    UserRole,
)
from app.infrastructure.database.models.organization_governance import OrganizationGroup


def _login(client, username: str = "admin", password: str = "admin123") -> tuple[dict, dict]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "tenant_code": "default"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return data, {"Authorization": f"Bearer {data['access_token']}"}


def _post(client, path: str, headers: dict, body: dict) -> dict:
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _role(client, headers: dict, code: str, permissions: list[str], park_ids=None) -> dict:
    return _post(
        client,
        "/api/v1/system/roles",
        headers,
        {
            "code": code,
            "name": code,
            "permission_codes": permissions,
            "park_ids": park_ids or [],
            "all_parks": False,
        },
    )


def _user(client, headers: dict, username: str, role_ids: list[int], park_ids=None) -> dict:
    return _post(
        client,
        "/api/v1/system/users",
        headers,
        {
            "username": username,
            "password": "Strong#12345",
            "real_name": username,
            "phone": "13800138000",
            "role_ids": role_ids,
            "park_ids": park_ids or [],
            "all_parks": False,
        },
    )


def test_complete_hierarchy_position_history_and_audit_journey(client, db_session) -> None:
    login, headers = _login(client)
    park = _post(client, "/api/v1/parks", headers, {"name": "组织治理园"})
    group = _post(
        client,
        "/api/v1/system/organization-governance/groups",
        headers,
        {"code": "KW", "name": "瞰维集团"},
    )
    east = _post(
        client,
        "/api/v1/system/organization-governance/regions",
        headers,
        {"group_id": group["id"], "code": "EAST", "name": "华东区域"},
    )
    first = _post(
        client,
        "/api/v1/system/organization-governance/park-assignments",
        headers,
        {"region_id": east["id"], "park_id": park["id"], "reason": "首次归属"},
    )
    assert first["effective_to"] is None

    org = _post(
        client,
        "/api/v1/system/org-units",
        headers,
        {"code": "OPS", "name": "运营中心"},
    )
    position = _post(
        client,
        "/api/v1/system/organization-governance/positions",
        headers,
        {
            "code": "PARK_MANAGER",
            "name": "园区经理",
            "org_unit_id": org["id"],
            "responsibilities": "经营与现场协同",
        },
    )
    admin_id = int(login["user"]["id"])
    before_roles = int(
        db_session.scalar(select(func.count(UserRole.id)).where(UserRole.user_id == admin_id)) or 0
    )
    before_parks = int(
        db_session.scalar(
            select(func.count(UserParkScope.id)).where(UserParkScope.user_id == admin_id)
        )
        or 0
    )
    assignment = _post(
        client,
        "/api/v1/system/organization-governance/user-assignments",
        headers,
        {
            "user_id": admin_id,
            "position_id": position["id"],
            "park_id": park["id"],
            "is_primary": True,
        },
    )
    db_session.expire_all()
    assert (
        int(db_session.scalar(select(func.count(UserRole.id)).where(UserRole.user_id == admin_id)) or 0)
        == before_roles
    )
    assert (
        int(
            db_session.scalar(
                select(func.count(UserParkScope.id)).where(UserParkScope.user_id == admin_id)
            )
            or 0
        )
        == before_parks
    )

    second_position = _post(
        client,
        "/api/v1/system/organization-governance/positions",
        headers,
        {"code": "REGION_MANAGER", "name": "区域经理"},
    )
    duplicate_primary = client.post(
        "/api/v1/system/organization-governance/user-assignments",
        headers=headers,
        json={
            "user_id": admin_id,
            "position_id": second_position["id"],
            "is_primary": True,
        },
    )
    assert duplicate_primary.status_code == 409
    assert duplicate_primary.json()["code"] == "PRIMARY_POSITION_CONFLICT"

    active_disable = client.patch(
        f"/api/v1/system/organization-governance/positions/{position['id']}",
        headers=headers,
        json={"status": "DISABLED"},
    )
    assert active_disable.status_code == 409
    ended = _post(
        client,
        f"/api/v1/system/organization-governance/user-assignments/{assignment['id']}/end",
        headers,
        {},
    )
    assert ended["ends_at"] is not None
    assert (
        client.patch(
            f"/api/v1/system/organization-governance/positions/{position['id']}",
            headers=headers,
            json={"status": "DISABLED"},
        ).status_code
        == 200
    )

    blocked_region = client.patch(
        f"/api/v1/system/organization-governance/regions/{east['id']}",
        headers=headers,
        json={"status": "DISABLED"},
    )
    assert blocked_region.status_code == 409
    west = _post(
        client,
        "/api/v1/system/organization-governance/regions",
        headers,
        {"group_id": group["id"], "code": "WEST", "name": "华西区域"},
    )
    _post(
        client,
        "/api/v1/system/organization-governance/park-assignments",
        headers,
        {"region_id": west["id"], "park_id": park["id"], "reason": "经营调区"},
    )
    history = client.get(
        f"/api/v1/system/organization-governance/parks/{park['id']}/assignment-history",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    rows = history.json()["data"]
    assert len(rows) == 2
    assert rows[0]["effective_to"] is not None
    assert rows[1]["effective_to"] is None
    assert (
        client.patch(
            f"/api/v1/system/organization-governance/regions/{east['id']}",
            headers=headers,
            json={"status": "DISABLED"},
        ).status_code
        == 200
    )

    hierarchy = client.get(
        "/api/v1/system/organization-governance/hierarchy", headers=headers
    )
    assert hierarchy.status_code == 200, hierarchy.text
    assert hierarchy.json()["data"]["groups"][0]["regions"][1]["parks"][0]["id"] == park["id"]
    db_session.expire_all()
    audited = int(
        db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.resource_type.in_(
                    [
                        "ORGANIZATION_GROUP",
                        "ORGANIZATION_REGION",
                        "REGION_PARK_ASSIGNMENT",
                        "POSITION",
                        "USER_POSITION_ASSIGNMENT",
                    ]
                )
            )
        )
        or 0
    )
    assert audited >= 9


def test_field_policy_projection_precedence_allowlist_and_star_default(client, db_session) -> None:
    _, admin_headers = _login(client)
    suffix = uuid4().hex[:6].upper()
    visible_role = _role(client, admin_headers, f"VISIBLE_{suffix}", ["identity.user.read"])
    hidden_role = _role(client, admin_headers, f"HIDDEN_{suffix}", [])
    governed = _user(
        client,
        admin_headers,
        f"field-{suffix.lower()}",
        [visible_role["id"], hidden_role["id"]],
    )
    for role_id, mode in (
        (visible_role["id"], "VISIBLE"),
        (hidden_role["id"], "HIDDEN"),
    ):
        response = client.put(
            "/api/v1/system/organization-governance/field-policies",
            headers=admin_headers,
            json={
                "role_id": role_id,
                "resource_type": "USER",
                "field_name": "phone",
                "access_mode": mode,
                "mask_strategy": "PHONE",
                "status": "ACTIVE",
            },
        )
        assert response.status_code == 200, response.text

    _, governed_headers = _login(client, governed["username"], "Strong#12345")
    governed_list = client.get("/api/v1/system/users", headers=governed_headers)
    assert governed_list.status_code == 200, governed_list.text
    own = next(row for row in governed_list.json()["data"] if row["id"] == governed["id"])
    assert "phone" not in own

    invalid = client.put(
        "/api/v1/system/organization-governance/field-policies",
        headers=admin_headers,
        json={
            "role_id": visible_role["id"],
            "resource_type": "USER",
            "field_name": "password_hash",
            "access_mode": "VISIBLE",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "FIELD_POLICY_TARGET_INVALID"

    star_role = _role(client, admin_headers, f"STAR_{suffix}", ["*"])
    star_user = _user(client, admin_headers, f"star-{suffix.lower()}", [star_role["id"]])
    _, star_headers = _login(client, star_user["username"], "Strong#12345")
    star_list = client.get("/api/v1/system/users", headers=star_headers)
    assert star_list.status_code == 200, star_list.text
    star_own = next(row for row in star_list.json()["data"] if row["id"] == star_user["id"])
    assert star_own["phone"] == "138****8000"

    foreign_tenant = Tenant(code=f"foreign-{suffix.lower()}", name="外租户", status="ACTIVE")
    db_session.add(foreign_tenant)
    db_session.flush()
    foreign_role = Role(
        tenant_id=foreign_tenant.id,
        code="FOREIGN",
        name="外角色",
        status="ACTIVE",
        all_parks=False,
    )
    db_session.add(foreign_role)
    db_session.commit()
    foreign = client.put(
        "/api/v1/system/organization-governance/field-policies",
        headers=admin_headers,
        json={
            "role_id": foreign_role.id,
            "resource_type": "USER",
            "field_name": "phone",
            "access_mode": "VISIBLE",
        },
    )
    assert foreign.status_code == 404
    db_session.expire_all()
    policy_audits = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.resource_type == "FIELD_ACCESS_POLICY")
        ).all()
    )
    assert policy_audits
    assert all("13800138000" not in str(row.detail_json) for row in policy_audits)


def test_scope_tenant_isolation_and_fabricated_permission_are_denied(client, db_session) -> None:
    _, admin_headers = _login(client)
    park_a = _post(client, "/api/v1/parks", admin_headers, {"name": "范围园 A"})
    park_b = _post(client, "/api/v1/parks", admin_headers, {"name": "范围园 B"})
    group = _post(
        client,
        "/api/v1/system/organization-governance/groups",
        admin_headers,
        {"code": f"SCOPE_{uuid4().hex[:6]}", "name": "范围集团"},
    )
    region = _post(
        client,
        "/api/v1/system/organization-governance/regions",
        admin_headers,
        {"group_id": group["id"], "code": f"REG_{uuid4().hex[:6]}", "name": "范围区域"},
    )
    read_role = _role(
        client,
        admin_headers,
        f"GOV_READ_{uuid4().hex[:6]}",
        ["identity.org_governance.read"],
        [park_a["id"]],
    )
    read_user = _user(
        client,
        admin_headers,
        f"read-{uuid4().hex[:6]}",
        [read_role["id"]],
        [park_a["id"]],
    )
    _, read_headers = _login(client, read_user["username"], "Strong#12345")
    fabricated = client.post(
        "/api/v1/system/organization-governance/groups",
        headers={**read_headers, "X-Permissions": "identity.org_governance.write"},
        json={"code": "FORGED", "name": "伪造", "permission": "identity.org_governance.write"},
    )
    assert fabricated.status_code == 403

    scoped_role = _role(
        client,
        admin_headers,
        f"GOV_WRITE_{uuid4().hex[:6]}",
        ["identity.org_governance.read", "identity.org_governance.write"],
        [park_a["id"]],
    )
    scoped_user = _user(
        client,
        admin_headers,
        f"scope-{uuid4().hex[:6]}",
        [scoped_role["id"]],
        [park_a["id"]],
    )
    _, scoped_headers = _login(client, scoped_user["username"], "Strong#12345")
    denied = client.post(
        "/api/v1/system/organization-governance/park-assignments",
        headers=scoped_headers,
        json={"region_id": region["id"], "park_id": park_b["id"]},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "PARK_SCOPE_DENIED"

    foreign_tenant = Tenant(code=f"tenant-{uuid4().hex[:8]}", name="隔离租户", status="ACTIVE")
    db_session.add(foreign_tenant)
    db_session.flush()
    db_session.add(
        OrganizationGroup(
            tenant_id=foreign_tenant.id,
            code="FOREIGN_GROUP",
            name="外租户集团",
        )
    )
    db_session.add(
        User(
            tenant_id=foreign_tenant.id,
            username="foreign-user",
            password_hash=hash_password("Foreign#12345"),
            real_name="外租户用户",
            status="ACTIVE",
        )
    )
    db_session.commit()
    hierarchy = client.get(
        "/api/v1/system/organization-governance/hierarchy", headers=admin_headers
    )
    assert hierarchy.status_code == 200, hierarchy.text
    assert all(row["code"] != "FOREIGN_GROUP" for row in hierarchy.json()["data"]["groups"])
