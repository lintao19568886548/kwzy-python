"""System org/dict/params admin API tests."""

from __future__ import annotations

from app.core.security import create_access_token


def _h() -> dict:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": ["*"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def test_org_dict_param_crud(client) -> None:
    h = _h()
    org = client.post(
        "/api/v1/system/org-units",
        headers=h,
        json={"code": "HQ", "name": "总部"},
    )
    assert org.status_code == 200, org.text
    assert org.json()["data"]["code"] == "HQ"

    listed = client.get("/api/v1/system/org-units", headers=h)
    assert listed.status_code == 200
    assert any(x["code"] == "HQ" for x in listed.json()["data"])

    dt = client.post(
        "/api/v1/system/dict-types",
        headers=h,
        json={"code": "intent_level", "name": "意向等级"},
    )
    assert dt.status_code == 200, dt.text
    item = client.post(
        "/api/v1/system/dict-types/intent_level/items",
        headers=h,
        json={"item_label": "高", "item_value": "HIGH"},
    )
    assert item.status_code == 200, item.text
    items = client.get("/api/v1/system/dict-types/intent_level/items", headers=h)
    assert items.status_code == 200
    assert items.json()["data"][0]["item_value"] == "HIGH"

    param = client.put(
        "/api/v1/system/params",
        headers=h,
        json={
            "param_key": "workbench.expiring_days",
            "param_value": "90",
            "value_type": "INT",
        },
    )
    assert param.status_code == 200, param.text
    secret = client.put(
        "/api/v1/system/params",
        headers=h,
        json={
            "param_key": "sms.api_token",
            "param_value": "super-secret",
            "is_secret": True,
        },
    )
    assert secret.status_code == 200
    assert secret.json()["data"]["param_value"] == "******"
