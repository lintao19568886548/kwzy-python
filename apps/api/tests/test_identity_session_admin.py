"""Identity session + admin API tests."""

from __future__ import annotations


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
        json={"old_password": "admin123", "new_password": "admin456"},
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
        json={"username": "admin", "password": "admin456", "tenant_code": "default"},
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
            "password": "ops12345",
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
