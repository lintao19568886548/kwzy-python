"""Step1 错误、请求关联、日志、软删除与审计合规测试。"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.audit import AuditLog
from app.main import create_app
from app.modules.park_property.application.park_service import ParkService
from app.modules.park_property.application.unit_service import UnitService
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _ctx(request_id: str = "audit-test") -> TenantContext:
    return TenantContext(
        tenant_id=1,
        user_id=1,
        username="admin",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
        request_id=request_id,
        client_ip="127.0.0.1",
    )


def test_request_id_is_preserved_or_generated(client) -> None:
    supplied = client.get("/health", headers={"X-Request-Id": "trace-123"})
    assert supplied.status_code == 200
    assert supplied.headers["X-Request-Id"] == "trace-123"

    generated = client.get("/health")
    assert generated.status_code == 200
    assert generated.headers["X-Request-Id"]


def test_validation_and_unhandled_errors_use_envelope(client) -> None:
    validation = client.post("/api/v1/parks", json={})
    assert validation.status_code == 422
    assert validation.json()["code"] == "VALIDATION_ERROR"
    assert validation.json()["data"]["errors"]

    app = create_app()

    def boom() -> None:
        raise RuntimeError("internal-secret-must-not-leak")

    app.add_api_route("/test-boom", boom, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as isolated_client:
        unknown = isolated_client.get(
            "/test-boom",
            headers={"X-Request-Id": "error-trace"},
        )
    assert unknown.status_code == 500
    assert unknown.headers["X-Request-Id"] == "error-trace"
    assert unknown.json() == {
        "code": "INTERNAL_ERROR",
        "message": "服务器内部错误",
        "data": None,
    }
    assert "internal-secret" not in unknown.text


def test_invalid_statuses_return_business_errors(client) -> None:
    bad_park = client.post(
        "/api/v1/parks",
        json={"name": "错误状态园区", "status": "BAD"},
    )
    assert bad_park.status_code == 400
    assert bad_park.json()["code"] == "VALIDATION_ERROR"

    park = client.post("/api/v1/parks", json={"name": "单元状态园区"}).json()["data"]
    bad_unit = client.post(
        "/api/v1/units",
        json={
            "park_id": park["id"],
            "code": "BAD-1",
            "name": "错误状态单元",
            "status": "BAD",
        },
    )
    assert bad_unit.status_code == 400
    assert bad_unit.json()["code"] == "UNIT_STATUS_INVALID"


def test_soft_deleted_park_is_not_visible(client) -> None:
    created = client.post("/api/v1/parks", json={"name": "待删除园区"})
    park_id = created.json()["data"]["id"]

    deleted = client.delete(f"/api/v1/parks/{park_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/parks/{park_id}").status_code == 404

    listed = client.get("/api/v1/parks").json()["data"]["items"]
    assert park_id not in {item["id"] for item in listed}


def test_park_unit_writes_are_audited_and_logged(
    db_session: Session,
    caplog,
) -> None:
    ctx = _ctx("audit-flow")
    park_service = ParkService(db_session, ctx)
    unit_service = UnitService(db_session, ctx)

    caplog.set_level(logging.INFO)
    park = park_service.create_park({"name": "审计园区"})
    park_service.update_park(park["id"], {"address": "审计地址"})
    unit = unit_service.create_unit(
        {
            "park_id": park["id"],
            "code": "AUDIT-U1",
            "name": "审计单元",
            "status": "VACANT",
        }
    )
    unit_service.change_status(unit["id"], "RESERVED")
    unit_service.delete_unit(unit["id"])
    park_service.delete_park(park["id"])

    audits = list(db_session.scalars(select(AuditLog).order_by(AuditLog.id)).all())
    assert [(item.resource_type, item.action) for item in audits] == [
        ("PARK", "create"),
        ("PARK", "update"),
        ("UNIT", "create"),
        ("UNIT", "change_status"),
        ("UNIT", "delete"),
        ("PARK", "delete"),
    ]
    assert all(item.tenant_id == 1 for item in audits)
    assert all(item.request_id == "audit-flow" for item in audits)
    assert all(item.user_id == 1 for item in audits)

    business_records = [
        record
        for record in caplog.records
        if getattr(record, "request_id", None) == "audit-flow"
    ]
    assert business_records
    assert any(
        getattr(record, "business_module", None) == "park"
        and getattr(record, "action", None) == "create"
        for record in business_records
    )


def test_failed_write_does_not_create_audit(db_session: Session) -> None:
    service = ParkService(db_session, _ctx("failed-audit"))
    before = int(db_session.scalar(select(func.count()).select_from(AuditLog)) or 0)

    with pytest.raises(AppError):
        service.create_park({"name": "失败园区", "status": "BAD"})

    after = int(db_session.scalar(select(func.count()).select_from(AuditLog)) or 0)
    assert after == before
