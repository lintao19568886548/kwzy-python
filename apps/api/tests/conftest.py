from __future__ import annotations

import base64
import hashlib
import os
from datetime import date, timedelta
from decimal import Decimal

# Force isolated sqlite DB for tests — never touch production/old MySQL
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
# Explicit local/test anonymous identity for fixtures that omit JWT.
os.environ["ALLOW_ANON_DEV"] = "true"
# Test fixture credential only — not a production password
os.environ["LOCAL_ADMIN_PASSWORD"] = "admin123"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"
os.environ["PII_FINGERPRINT_SECRET"] = "test-pii-fingerprint-secret-not-production-32chars"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.infrastructure.database.base import Base, utc_now
from app.infrastructure.database.models.investment import (
    LeadIntentApplication,
    LeadIntentUnit,
    LeadIntentVersion,
)
from app.infrastructure.database.models.park_property import Unit
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.identity.application.bootstrap import ensure_default_tenant

# Clear settings cache so env takes effect
get_settings.cache_clear()


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _fk(dbapi_connection, _):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    import app.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(bind=eng)
    yield eng
    # SQLite cannot topologically drop tables that contain a real circular-FK row
    # (receipt_transactions.payment_id <-> payments.source_receipt_id). Enforcement
    # stays enabled for the complete test; only schema teardown disables it.
    with eng.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db_session(engine) -> Session:
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    ensure_default_tenant(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine, db_session: Session):
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    application = create_app()
    application.dependency_overrides[get_db] = _override_db
    with TestClient(application) as c:
        yield c
    application.dependency_overrides.clear()


@pytest.fixture()
def approved_intent(db_session: Session):
    """Create an approved immutable intent for legacy lock-focused regression tests.

    End-to-end intent submission and approval is covered separately; this fixture keeps
    older inventory/conversion tests focused on their original assertions while still
    satisfying the new non-bypassable lock gate.
    """

    def run(*, lead_id: int, unit_ids: list[int]) -> dict[str, int]:
        from app.infrastructure.database.models.investment import Lead

        lead = db_session.get(Lead, int(lead_id))
        assert lead is not None
        units = [db_session.get(Unit, int(unit_id)) for unit_id in unit_ids]
        assert all(unit is not None for unit in units)
        application = LeadIntentApplication(
            tenant_id=int(lead.tenant_id),
            park_id=int(lead.park_id),
            lead_id=int(lead.id),
            status="APPROVED",
            current_version=1,
            lock_version=1,
            submitted_at=utc_now(),
            created_by=1,
            updated_by=1,
        )
        db_session.add(application)
        db_session.flush()
        version = LeadIntentVersion(
            tenant_id=int(lead.tenant_id),
            application_id=int(application.id),
            version=1,
            starts_on=date.today(),
            ends_on=date.today() + timedelta(days=365),
            valid_until=utc_now() + timedelta(days=30),
            proposed_unit_price=Decimal("1.00"),
            currency="CNY",
            checksum=f"test-approved-intent-{application.id}",
            created_by=1,
        )
        db_session.add(version)
        db_session.flush()
        for unit in units:
            assert unit is not None
            db_session.add(
                LeadIntentUnit(
                    tenant_id=int(lead.tenant_id),
                    intent_version_id=int(version.id),
                    unit_id=int(unit.id),
                    unit_version=int(unit.version_no),
                    requested_area=Decimal(str(unit.rentable_area)),
                )
            )
        approval = ApprovalRequest(
            tenant_id=int(lead.tenant_id),
            park_id=int(lead.park_id),
            biz_type="LEAD_INTENT",
            biz_id=str(application.id),
            title="测试批准意向",
            status="APPROVED",
            priority="HIGH",
            applicant_user_id=1,
            approver_user_id=1,
            submitted_at=utc_now(),
            completed_at=utc_now(),
            lock_version=1,
            compatibility_mode="NATIVE",
        )
        db_session.add(approval)
        db_session.flush()
        application.approval_request_id = int(approval.id)
        db_session.commit()
        return {"id": int(application.id), "version_id": int(version.id)}

    return run


@pytest.fixture()
def governed_activate():
    """Prepare and attempt the full V2 approval/document activation chain."""

    def run(client, headers: dict[str, str], contract_id: int):
        contract = client.get(f"/api/v1/leases/{contract_id}", headers=headers).json()["data"]
        charges = client.put(
            f"/api/v1/leases/{contract_id}/charges",
            headers=headers,
            json={
                "expected_version": contract["lock_version"],
                "charges": [
                    {
                        "charge_code": "RENT",
                        "charge_type": "RENT",
                        "calculation_method": "FIXED",
                        "billing_cycle": "MONTHLY",
                        "start_date": contract["start_date"],
                        "end_date": contract["end_date"],
                        "amount": "1000",
                    }
                ],
            },
        )
        assert charges.status_code == 200, charges.text
        lock_version = charges.json()["data"]["lock_version"]
        submitted = client.post(
            f"/api/v1/leases/{contract_id}/lifecycle/submit",
            headers=headers,
            json={"expected_version": lock_version},
        )
        assert submitted.status_code == 200, submitted.text
        submitted_data = submitted.json()["data"]
        approved = client.post(
            f"/api/v1/leases/{contract_id}/lifecycle/approve",
            headers=headers,
            json={
                "approval_id": submitted_data["pending_approval"]["id"],
                "expected_version": submitted_data["contract"]["lock_version"],
                "override_reason": "测试夹具单管理员审批",
            },
        )
        assert approved.status_code == 200, approved.text
        approved_data = approved.json()["data"]
        content = f"synthetic governed contract {contract_id}".encode()
        uploaded = client.post(
            "/api/v1/attachments",
            headers=headers,
            json={
                "biz_type": "LEASE_CONTRACT",
                "biz_id": str(contract_id),
                "filename": f"contract-{contract_id}.txt",
                "content_type": "text/plain",
                "content_base64": base64.b64encode(content).decode("ascii"),
                "park_id": contract["park_id"],
            },
        )
        assert uploaded.status_code == 200, uploaded.text
        documented = client.post(
            f"/api/v1/leases/{contract_id}/documents",
            headers=headers,
            json={
                "expected_version": approved_data["contract"]["lock_version"],
                "attachment_id": uploaded.json()["data"]["id"],
                "document_type": "MAIN_CONTRACT",
                "checksum": hashlib.sha256(content).hexdigest(),
                "is_main": True,
            },
        )
        assert documented.status_code == 200, documented.text
        documented_data = documented.json()["data"]
        document_id = next(
            row["id"]
            for row in documented_data["documents"]
            if row["document_type"] == "MAIN_CONTRACT" and row["status"] == "DRAFT"
        )
        approved_document = client.post(
            f"/api/v1/leases/{contract_id}/documents/{document_id}/approve",
            headers=headers,
            json={"expected_version": documented_data["contract"]["lock_version"]},
        )
        assert approved_document.status_code == 200, approved_document.text
        ready = approved_document.json()["data"]
        return client.post(
            f"/api/v1/leases/{contract_id}/lifecycle/activate",
            headers=headers,
            json={"expected_version": ready["contract"]["lock_version"]},
        )

    return run


@pytest.fixture()
def governed_close_exit():
    """Close a zero-balance exit through approval and an approved handover document."""

    def run(client, headers: dict[str, str], contract_id: int):
        detail = client.get(f"/api/v1/leases/{contract_id}/lifecycle", headers=headers).json()[
            "data"
        ]
        created = client.post(
            f"/api/v1/leases/{contract_id}/exit-settlements",
            headers=headers,
            json={
                "expected_version": detail["contract"]["lock_version"],
                "handover_date": detail["contract"]["end_date"],
            },
        )
        assert created.status_code == 200, created.text
        created_data = created.json()["data"]
        settlement = created_data["exit_settlement"]
        submitted = client.post(
            f"/api/v1/lease-exit-settlements/{settlement['id']}/submit",
            headers=headers,
            json={
                "expected_version": settlement["lock_version"],
                "contract_expected_version": created_data["contract"]["lock_version"],
            },
        )
        assert submitted.status_code == 200, submitted.text
        submitted_data = submitted.json()["data"]
        approved = client.post(
            f"/api/v1/lease-exit-settlements/{settlement['id']}/approve",
            headers=headers,
            json={
                "expected_version": submitted_data["exit_settlement"]["lock_version"],
                "override_reason": "测试夹具单管理员审批",
            },
        )
        assert approved.status_code == 200, approved.text
        approved_data = approved.json()["data"]
        content = f"synthetic exit handover {settlement['id']}".encode()
        uploaded = client.post(
            "/api/v1/attachments",
            headers=headers,
            json={
                "biz_type": "LEASE_EXIT_SETTLEMENT",
                "biz_id": str(settlement["id"]),
                "filename": f"exit-{settlement['id']}.txt",
                "content_type": "text/plain",
                "content_base64": base64.b64encode(content).decode("ascii"),
                "park_id": approved_data["contract"]["park_id"],
            },
        )
        assert uploaded.status_code == 200, uploaded.text
        cleared = client.post(
            f"/api/v1/lease-exit-settlements/{settlement['id']}/clearance",
            headers=headers,
            json={
                "expected_version": approved_data["exit_settlement"]["lock_version"],
                "evidence_attachment_id": uploaded.json()["data"]["id"],
                "reference": f"SYNTHETIC-CLEARANCE-{settlement['id']}",
                "reason": "测试夹具记录外部清账事实；未执行资金操作",
            },
        )
        assert cleared.status_code == 200, cleared.text
        cleared_data = cleared.json()["data"]
        documented = client.post(
            f"/api/v1/leases/{contract_id}/documents",
            headers=headers,
            json={
                "expected_version": cleared_data["contract"]["lock_version"],
                "attachment_id": uploaded.json()["data"]["id"],
                "document_type": "EXIT_HANDOVER",
                "checksum": hashlib.sha256(content).hexdigest(),
                "exit_settlement_id": settlement["id"],
            },
        )
        assert documented.status_code == 200, documented.text
        documented_data = documented.json()["data"]
        document_id = next(
            row["id"]
            for row in documented_data["documents"]
            if row["document_type"] == "EXIT_HANDOVER"
            and int(row.get("exit_settlement_id") or 0) == int(settlement["id"])
            and row["status"] == "DRAFT"
        )
        approved_document = client.post(
            f"/api/v1/leases/{contract_id}/documents/{document_id}/approve",
            headers=headers,
            json={"expected_version": documented_data["contract"]["lock_version"]},
        )
        assert approved_document.status_code == 200, approved_document.text
        ready = approved_document.json()["data"]
        return client.post(
            f"/api/v1/lease-exit-settlements/{settlement['id']}/close",
            headers=headers,
            json={
                "expected_version": cleared_data["exit_settlement"]["lock_version"],
                "contract_expected_version": ready["contract"]["lock_version"],
                "idempotency_key": f"test-exit-close-{settlement['id']}",
            },
        )

    return run
