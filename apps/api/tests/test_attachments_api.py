"""Attachment API tests."""

from __future__ import annotations

import base64

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


def test_attachment_upload_list_download_delete(client) -> None:
    h = _h()
    content = b"hello-attachment"
    up = client.post(
        "/api/v1/attachments",
        headers=h,
        json={
            "biz_type": "PARTY",
            "biz_id": "1",
            "filename": "../evil/name.txt",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "content_type": "text/plain",
        },
    )
    assert up.status_code == 200, up.text
    att = up.json()["data"]
    assert att["filename"] == "name.txt"
    assert att["size_bytes"] == len(content)

    listed = client.get(
        "/api/v1/attachments", headers=h, params={"biz_type": "PARTY", "biz_id": "1"}
    )
    assert listed.status_code == 200
    assert any(x["id"] == att["id"] for x in listed.json()["data"])

    dl = client.get(f"/api/v1/attachments/{att['id']}/content", headers=h)
    assert dl.status_code == 200
    assert dl.content == content

    deleted = client.delete(f"/api/v1/attachments/{att['id']}", headers=h)
    assert deleted.status_code == 200
    listed2 = client.get(
        "/api/v1/attachments", headers=h, params={"biz_type": "PARTY", "biz_id": "1"}
    )
    assert all(x["id"] != att["id"] for x in listed2.json()["data"])
