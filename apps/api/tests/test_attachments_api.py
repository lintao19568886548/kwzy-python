"""Attachment API tests."""

from __future__ import annotations

import base64

from app.core.security import create_access_token
from app.infrastructure.database.models.park_property import Park


def _h(*, park_ids: list[int] | None = None, mode: str = "ALL") -> dict:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": mode,
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
    assert dl.headers["x-content-type-options"] == "nosniff"

    deleted = client.delete(f"/api/v1/attachments/{att['id']}", headers=h)
    assert deleted.status_code == 200
    listed2 = client.get(
        "/api/v1/attachments", headers=h, params={"biz_type": "PARTY", "biz_id": "1"}
    )
    assert all(x["id"] != att["id"] for x in listed2.json()["data"])


def test_attachment_rejects_invalid_base64(client) -> None:
    response = client.post(
        "/api/v1/attachments",
        headers=_h(),
        json={
            "biz_type": "PARTY",
            "biz_id": "1",
            "filename": "invalid.txt",
            "content_base64": "not-valid-%%%",
            "content_type": "text/plain",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "ATTACHMENT_INVALID_BASE64"


def test_attachment_enforces_park_scope_for_all_operations(client, db_session) -> None:
    park_a = Park(tenant_id=1, name="园区 A", address="A")
    park_b = Park(tenant_id=1, name="园区 B", address="B")
    db_session.add_all([park_a, park_b])
    db_session.commit()
    db_session.refresh(park_a)
    db_session.refresh(park_b)

    all_scope = _h()
    attachment_ids: dict[int, int] = {}
    for park in (park_a, park_b):
        response = client.post(
            "/api/v1/attachments",
            headers=all_scope,
            json={
                "biz_type": "PARTY",
                "biz_id": "scope-test",
                "filename": f"park-{park.id}.txt",
                "content_base64": base64.b64encode(f"park-{park.id}".encode()).decode(),
                "content_type": "text/plain",
                "park_id": park.id,
            },
        )
        assert response.status_code == 200, response.text
        attachment_ids[park.id] = response.json()["data"]["id"]

    limited = _h(park_ids=[park_a.id], mode="LIST")
    listed = client.get(
        "/api/v1/attachments",
        headers=limited,
        params={"biz_type": "PARTY", "biz_id": "scope-test"},
    )
    assert listed.status_code == 200
    assert [item["park_id"] for item in listed.json()["data"]] == [park_a.id]

    hidden_id = attachment_ids[park_b.id]
    assert client.get(
        f"/api/v1/attachments/{hidden_id}/content", headers=limited
    ).status_code == 404
    assert client.delete(
        f"/api/v1/attachments/{hidden_id}", headers=limited
    ).status_code == 404

    forbidden_upload = client.post(
        "/api/v1/attachments",
        headers=limited,
        json={
            "biz_type": "PARTY",
            "biz_id": "scope-test",
            "filename": "forbidden.txt",
            "content_base64": base64.b64encode(b"forbidden").decode(),
            "content_type": "text/plain",
            "park_id": park_b.id,
        },
    )
    assert forbidden_upload.status_code == 403
    assert forbidden_upload.json()["code"] == "PARK_SCOPE_DENIED"


def test_attachment_restricted_scope_cannot_use_tenant_wide_attachment(client) -> None:
    response = client.post(
        "/api/v1/attachments",
        headers=_h(park_ids=[999], mode="LIST"),
        json={
            "biz_type": "PARTY",
            "biz_id": "scope-test",
            "filename": "tenant-wide.txt",
            "content_base64": base64.b64encode(b"tenant-wide").decode(),
            "content_type": "text/plain",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PARK_SCOPE_DENIED"


def test_attachment_rejects_active_content_and_mismatched_magic(client) -> None:
    html = client.post(
        "/api/v1/attachments",
        headers=_h(),
        json={
            "biz_type": "PARTY",
            "biz_id": "1",
            "filename": "attack.html",
            "content_base64": base64.b64encode(b"<script>alert(1)</script>").decode(),
            "content_type": "text/html",
        },
    )
    assert html.status_code == 400
    assert html.json()["code"] == "ATTACHMENT_TYPE_NOT_ALLOWED"

    fake_png = client.post(
        "/api/v1/attachments",
        headers=_h(),
        json={
            "biz_type": "PARTY",
            "biz_id": "1",
            "filename": "fake.png",
            "content_base64": base64.b64encode(b"not really a png").decode(),
            "content_type": "image/png",
        },
    )
    assert fake_png.status_code == 400
    assert fake_png.json()["code"] == "ATTACHMENT_MAGIC_MISMATCH"
