"""Identity session + admin API tests."""

from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.database.models.audit import AuditLog
from app.infrastructure.database.models.identity import AuthSecurityEvent, Tenant
from app.infrastructure.database.models.identity import (
    PageAccessProof,
    VerificationCode,
)
from app.infrastructure.database.models.integration_outbox import IntegrationOutbox
from app.infrastructure.database.models.park_property import Park


def _login(client, username="admin", password="admin123", tenant_code="default"):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "tenant_code": tenant_code},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get("data") or body
    assert data.get("access_token")
    assert data.get("refresh_token")
    return data


def test_login_refresh_logout_password(client):
    data = _login(client)
    access = data["access_token"]
    refresh = data["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    refreshed = r.json().get("data") or r.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"] != refresh

    # old refresh revoked
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401

    r3 = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed["refresh_token"]},
    )
    assert r3.status_code == 200

    r4 = client.post(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {access}"},
        json={"old_password": "admin123", "new_password": "Secure#456789"},
    )
    assert r4.status_code == 200, r4.text

    # login with new password
    bad = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123", "tenant_code": "default"},
    )
    assert bad.status_code == 403
    ok = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Secure#456789", "tenant_code": "default"},
    )
    assert ok.status_code == 200


def test_user_role_menu_admin(client):
    data = _login(client)
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    r = client.get("/api/v1/system/users", headers=headers)
    assert r.status_code == 200, r.text
    users = (r.json().get("data") or r.json())
    assert any(u["username"] == "admin" for u in users)

    r = client.post(
        "/api/v1/system/users",
        headers=headers,
        json={
            "username": "ops1",
            "password": "Ops#73915826",
            "real_name": "运维一号",
            "role_ids": [],
            "park_ids": [],
        },
    )
    assert r.status_code == 200, r.text
    created = r.json().get("data") or r.json()
    assert created["username"] == "ops1"

    r = client.get("/api/v1/system/roles", headers=headers)
    assert r.status_code == 200
    roles = r.json().get("data") or r.json()
    assert any(x["code"] == "ADMIN" for x in roles)

    r = client.post(
        "/api/v1/system/roles",
        headers=headers,
        json={
            "code": "PARK_OPS",
            "name": "园区运维",
            "permission_codes": ["park:read", "unit:read"],
            "all_parks": False,
        },
    )
    assert r.status_code == 200, r.text

    r = client.get("/api/v1/system/menus", headers=headers)
    assert r.status_code == 200
    menus = r.json().get("data") or r.json()
    assert len(menus) >= 1

    r = client.get("/api/v1/auth/menus", headers=headers)
    assert r.status_code == 200
    mine = r.json().get("data") or r.json()
    assert len(mine) >= 1

    r = client.get("/api/v1/auth/codes", headers=headers)
    assert r.status_code == 200
    codes = r.json().get("data") or r.json()
    assert "*" in codes or "identity.user.read" in codes


def test_duplicate_identity_admin_codes_return_conflict(client):
    data = _login(client)
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    user_payload = {
        "username": "unique-user",
        "password": "Unique#12345",
        "real_name": "唯一用户",
    }
    assert (
        client.post(
            "/api/v1/system/users",
            headers=headers,
            json=user_payload,
        ).status_code
        == 200
    )
    duplicate_user = client.post(
        "/api/v1/system/users",
        headers=headers,
        json=user_payload,
    )
    assert duplicate_user.status_code == 409
    assert duplicate_user.json()["code"] == "USER_EXISTS"

    role_payload = {"code": "UNIQUE_ROLE", "name": "唯一角色"}
    assert (
        client.post(
            "/api/v1/system/roles",
            headers=headers,
            json=role_payload,
        ).status_code
        == 200
    )
    duplicate_role = client.post(
        "/api/v1/system/roles",
        headers=headers,
        json=role_payload,
    )
    assert duplicate_role.status_code == 409
    assert duplicate_role.json()["code"] == "ROLE_EXISTS"


def test_refresh_replay_revokes_replacement_session(client, db_session):
    data = _login(client)
    first = data["refresh_token"]

    rotated_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first},
    )
    assert rotated_response.status_code == 200, rotated_response.text
    rotated = (rotated_response.json().get("data") or rotated_response.json())[
        "refresh_token"
    ]

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401
    assert replay.json()["code"] == "AUTH_REFRESH_REUSED"

    replacement = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated},
    )
    assert replacement.status_code == 401
    db_session.expire_all()
    reuse_events = list(
        db_session.scalars(
            select(AuthSecurityEvent).where(
                AuthSecurityEvent.event_type == "REFRESH_REUSE"
            )
        ).all()
    )
    assert len(reuse_events) == 1
    assert reuse_events[0].reason_code == "ROTATED_TOKEN_REUSED"


def test_login_rate_limit_uses_sanitized_shared_events(client, db_session):
    for _ in range(5):
        failed = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "definitely-wrong",
                "tenant_code": "default",
            },
        )
        assert failed.status_code == 403

    limited = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "admin123",
            "tenant_code": "default",
        },
    )
    assert limited.status_code == 429
    assert limited.json()["code"] == "AUTH_RATE_LIMITED"

    db_session.expire_all()
    events = list(db_session.scalars(select(AuthSecurityEvent)).all())
    assert sum(row.event_type == "LOGIN_FAILURE" for row in events) == 5
    assert sum(row.event_type == "LOGIN_RATE_LIMITED" for row in events) == 1
    evidence = " ".join(
        f"{row.subject_digest} {row.client_digest} {row.reason_code}" for row in events
    )
    assert "admin" not in evidence
    assert "definitely-wrong" not in evidence


def test_pc_refresh_cookie_rotates_and_logout_clears(client):
    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "admin123",
            "tenant_code": "default",
        },
    )
    assert login.status_code == 200, login.text
    set_cookie = login.headers.get("set-cookie", "")
    assert "kwzy_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie

    refreshed = client.post("/api/v1/auth/refresh", json={})
    assert refreshed.status_code == 200, refreshed.text
    assert "kwzy_refresh=" in refreshed.headers.get("set-cookie", "")

    logged_out = client.post("/api/v1/auth/logout", json={})
    assert logged_out.status_code == 200, logged_out.text
    assert "Max-Age=0" in logged_out.headers.get("set-cookie", "")
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 401


def test_page_access_code_is_hashed_rate_limited_and_one_time(
    client,
    db_session,
    monkeypatch,
):
    from app.modules.identity.application import page_access_service

    monkeypatch.setattr(page_access_service.secrets, "randbelow", lambda _: 234567)
    admin = _login(client)
    headers = {"Authorization": f"Bearer {admin['access_token']}"}
    user_id = admin["user"]["id"]
    phone_update = client.put(
        f"/api/v1/system/users/{user_id}",
        headers=headers,
        json={"phone": "13800138000"},
    )
    assert phone_update.status_code == 200, phone_update.text

    sent = client.post(
        "/api/v1/auth/page-access/send",
        headers=headers,
        json={"purpose": "contract.terminate"},
    )
    assert sent.status_code == 200, sent.text
    sent_data = sent.json().get("data") or sent.json()
    assert sent_data["provider"] == "fake"
    assert "code" not in sent_data
    assert "234567" not in sent.text

    rate_limited = client.post(
        "/api/v1/auth/page-access/send",
        headers=headers,
        json={"purpose": "contract.terminate"},
    )
    assert rate_limited.status_code == 429
    assert rate_limited.json()["code"] == "AUTH_CODE_RATE_LIMITED"

    wrong = client.post(
        "/api/v1/auth/page-access/verify",
        headers=headers,
        json={"purpose": "contract.terminate", "code": "000000"},
    )
    assert wrong.status_code == 400

    verified = client.post(
        "/api/v1/auth/page-access/verify",
        headers=headers,
        json={"purpose": "contract.terminate", "code": "234567"},
    )
    assert verified.status_code == 200, verified.text
    verified_data = verified.json().get("data") or verified.json()
    proof = verified_data["proof"]
    assert proof

    code_reuse = client.post(
        "/api/v1/auth/page-access/verify",
        headers=headers,
        json={"purpose": "contract.terminate", "code": "234567"},
    )
    assert code_reuse.status_code == 400

    wrong_purpose = client.post(
        "/api/v1/auth/page-access/consume",
        headers=headers,
        json={"purpose": "payment.reverse", "proof": proof},
    )
    assert wrong_purpose.status_code == 403

    consumed = client.post(
        "/api/v1/auth/page-access/consume",
        headers=headers,
        json={"purpose": "contract.terminate", "proof": proof},
    )
    assert consumed.status_code == 200, consumed.text
    assert (consumed.json().get("data") or consumed.json())["verified"] is True
    assert (
        client.post(
            "/api/v1/auth/page-access/consume",
            headers=headers,
            json={"purpose": "contract.terminate", "proof": proof},
        ).status_code
        == 403
    )

    db_session.expire_all()
    code_row = db_session.scalars(select(VerificationCode)).one()
    proof_row = db_session.scalars(select(PageAccessProof)).one()
    outbox = db_session.scalars(
        select(IntegrationOutbox).where(
            IntegrationOutbox.idempotency_key.like("page-access-%")
        )
    ).one()
    assert code_row.code_hash != "234567"
    assert proof_row.proof_hash != proof
    assert "234567" not in (outbox.payload_json or "")
    assert "13800138000" not in (outbox.payload_json or "")


def test_user_disable_and_role_change_revoke_existing_sessions(client):
    admin = _login(client)
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

    role_response = client.post(
        "/api/v1/system/roles",
        headers=admin_headers,
        json={
            "code": "SESSION_SCOPE",
            "name": "会话范围角色",
            "permission_codes": ["park:read"],
            "all_parks": False,
        },
    )
    assert role_response.status_code == 200, role_response.text
    role = role_response.json().get("data") or role_response.json()

    user_response = client.post(
        "/api/v1/system/users",
        headers=admin_headers,
        json={
            "username": "session-user",
            "password": "Session#12345",
            "real_name": "会话用户",
            "role_ids": [role["id"]],
            "park_ids": [],
            "all_parks": False,
        },
    )
    assert user_response.status_code == 200, user_response.text
    user = user_response.json().get("data") or user_response.json()
    session = _login(client, "session-user", "Session#12345")
    user_headers = {"Authorization": f"Bearer {session['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=user_headers).status_code == 200

    role_update = client.put(
        f"/api/v1/system/roles/{role['id']}",
        headers=admin_headers,
        json={"permission_codes": []},
    )
    assert role_update.status_code == 200, role_update.text
    assert client.get("/api/v1/auth/me", headers=user_headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": session["refresh_token"]},
        ).status_code
        == 401
    )

    relogin = _login(client, "session-user", "Session#12345")
    disable = client.delete(
        f"/api/v1/system/users/{user['id']}",
        headers=admin_headers,
    )
    assert disable.status_code == 200, disable.text
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {relogin['access_token']}"},
        ).status_code
        == 401
    )


def test_user_admin_and_password_change_reject_weak_or_reused_password(client):
    admin = _login(client)
    headers = {"Authorization": f"Bearer {admin['access_token']}"}

    weak_create = client.post(
        "/api/v1/system/users",
        headers=headers,
        json={"username": "weak-user", "password": "weakpass12"},
    )
    assert weak_create.status_code == 400
    assert weak_create.json()["code"] == "AUTH_WEAK_PASSWORD"

    weak_change = client.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"old_password": "admin123", "new_password": "lowercase123"},
    )
    assert weak_change.status_code == 400
    assert weak_change.json()["code"] == "AUTH_WEAK_PASSWORD"

    created = client.post(
        "/api/v1/system/users",
        headers=headers,
        json={"username": "reuse-user", "password": "Strong#12345"},
    )
    assert created.status_code == 200, created.text
    reused = client.put(
        f"/api/v1/system/users/{created.json()['data']['id']}",
        headers=headers,
        json={"password": "Strong#12345"},
    )
    assert reused.status_code == 400
    assert reused.json()["code"] == "AUTH_PASSWORD_REUSE"


def test_menu_lifecycle_scope_validation_and_identity_audit(client, db_session):
    admin = _login(client)
    headers = {"Authorization": f"Bearer {admin['access_token']}"}

    parent_response = client.post(
        "/api/v1/system/menus",
        headers=headers,
        json={"name": "父菜单", "path": "/parent", "menu_type": "DIR"},
    )
    assert parent_response.status_code == 200, parent_response.text
    parent = parent_response.json().get("data") or parent_response.json()
    child_response = client.post(
        "/api/v1/system/menus",
        headers=headers,
        json={
            "name": "子菜单",
            "path": "/parent/child",
            "parent_id": parent["id"],
            "menu_type": "MENU",
            "permission_code": "park:read",
        },
    )
    assert child_response.status_code == 200, child_response.text
    child = child_response.json().get("data") or child_response.json()

    cycle = client.put(
        f"/api/v1/system/menus/{parent['id']}",
        headers=headers,
        json={"parent_id": child["id"]},
    )
    assert cycle.status_code == 400
    assert cycle.json()["code"] == "MENU_PARENT_CYCLE"

    rename = client.put(
        f"/api/v1/system/menus/{child['id']}",
        headers=headers,
        json={"name": "子菜单已更新"},
    )
    assert rename.status_code == 200, rename.text
    assert (rename.json().get("data") or rename.json())["name"] == "子菜单已更新"

    deactivated = client.delete(
        f"/api/v1/system/menus/{parent['id']}",
        headers=headers,
    )
    assert deactivated.status_code == 200, deactivated.text
    menus_response = client.get("/api/v1/system/menus", headers=headers)
    menus = menus_response.json().get("data") or menus_response.json()
    by_id = {menu["id"]: menu for menu in menus}
    assert by_id[parent["id"]]["status"] == "DISABLED"
    assert by_id[child["id"]]["status"] == "DISABLED"

    valid_role = client.post(
        "/api/v1/system/roles",
        headers=headers,
        json={
            "code": "AUDITED_ROLE",
            "name": "审计角色",
            "permission_codes": ["park:read"],
            "park_ids": [],
            "all_parks": False,
        },
    )
    assert valid_role.status_code == 200, valid_role.text

    foreign_tenant = Tenant(code="foreign-scope", name="外部租户", status="ACTIVE")
    db_session.add(foreign_tenant)
    db_session.flush()
    foreign_park = Park(
        tenant_id=foreign_tenant.id,
        name="外租户园区",
        address="",
        area=0,
        status="ACTIVE",
    )
    db_session.add(foreign_park)
    db_session.commit()
    invalid_scope = client.post(
        "/api/v1/system/roles",
        headers=headers,
        json={
            "code": "BAD_FOREIGN_SCOPE",
            "name": "非法跨租户范围",
            "permission_codes": [],
            "park_ids": [foreign_park.id],
            "all_parks": False,
        },
    )
    assert invalid_scope.status_code == 400
    assert invalid_scope.json()["code"] == "PARK_SCOPE_INVALID"

    db_session.expire_all()
    audits = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.resource_type.in_(
                    ["IDENTITY_USER", "IDENTITY_ROLE", "IDENTITY_MENU"]
                )
            )
        ).all()
    )
    assert any(row.resource_type == "IDENTITY_MENU" for row in audits)
    assert any(row.resource_type == "IDENTITY_ROLE" for row in audits)
    serialized = " ".join(str(row.detail_json) for row in audits)
    assert "admin123" not in serialized
    assert "refresh_token" not in serialized
