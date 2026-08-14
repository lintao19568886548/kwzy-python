"""PostgreSQL 16 constraints and concurrency for records, signature and seal governance."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.records_seal import RecordRevision, SignatureEnvelope
from app.modules.attachments.application.attachment_service import AttachmentService
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.records_seal.application.service import RecordsSealService
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not value.startswith("postgresql") or "sqlite" in value.lower():
        pytest.fail("records-seal acceptance requires PostgreSQL")
    parsed = make_url(value)
    if parsed.host not in {"127.0.0.1", "localhost"}:
        pytest.fail("records-seal acceptance is restricted to loopback PostgreSQL")
    if (parsed.database or "").lower() != "kwzy_party_test":
        pytest.fail("records-seal acceptance requires the disposable kwzy_party_test DB")
    return value


def _factory():
    engine = create_engine(_url(), pool_pre_ping=True, pool_size=8, max_overflow=8)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int, user_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username="records-pg",
        permissions=["*"],
        park_ids=[],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed() -> dict[str, int]:
    _, Session = _factory()
    suffix = uuid4().hex[:10]
    with Session() as session:
        tenant = ensure_default_tenant(session)
        park = Park(tenant_id=tenant.id, name=f"档案PG园-{suffix}", status="ACTIVE")
        user = User(
            tenant_id=tenant.id,
            username=f"records_pg_{suffix}",
            password_hash="synthetic-not-a-login-secret",
            real_name="档案PG经办人",
            status="ACTIVE",
            all_parks=True,
        )
        foreign_tenant = Tenant(
            code=f"records-foreign-{suffix}",
            name=f"档案外租户-{suffix}",
            status="ACTIVE",
            db_strategy="SHARED",
        )
        session.add_all([park, user, foreign_tenant])
        session.commit()
        ctx = _ctx(int(tenant.id), int(user.id))
        service = RecordsSealService(session, ctx)
        category = service.create_category(
            {
                "code": f"PG_{suffix}",
                "name": "PG合同档案",
                "retention_mode": "YEARS",
                "retention_years": 10,
                "confidentiality_max": "RESTRICTED",
            }
        )
        record = service.create_record(
            {
                "park_id": int(park.id),
                "category_id": category["id"],
                "title": "PG并发档案",
                "confidentiality": "CONFIDENTIAL",
                "source_type": "PG_ACCEPTANCE",
                "source_id": suffix,
            }
        )
        attachment_service = AttachmentService(session, ctx)
        attachments = [
            attachment_service.upload(
                biz_type="PG_RECORD",
                biz_id=str(record["id"]),
                filename=f"pg-record-{index}.txt",
                content=f"pg-record-content-{suffix}-{index}".encode(),
                content_type="text/plain",
                park_id=int(park.id),
            )
            for index in (1, 2)
        ]
        return {
            "tenant_id": int(tenant.id),
            "park_id": int(park.id),
            "user_id": int(user.id),
            "foreign_tenant_id": int(foreign_tenant.id),
            "record_id": int(record["id"]),
            "attachment_1": int(attachments[0]["id"]),
            "attachment_2": int(attachments[1]["id"]),
        }


def test_pg_records_schema_indexes_types_and_truth_constraints() -> None:
    seed = _seed()
    engine, Session = _factory()
    inspector = inspect(engine)
    expected_tables = {
        "record_categories",
        "record_files",
        "record_revisions",
        "record_integrity_events",
        "record_holds",
        "record_access_requests",
        "record_dispositions",
        "record_disposition_confirmations",
        "seal_assets",
        "seal_custody_events",
        "seal_use_applications",
        "seal_use_receipts",
        "signature_providers",
        "signature_envelopes",
        "signature_participants",
        "signature_events",
    }
    assert expected_tables <= set(inspector.get_table_names())
    provider_live_type = next(
        column
        for column in inspector.get_columns("signature_providers")
        if column["name"] == "live_verified"
    )["type"]
    assert provider_live_type.__class__.__name__.upper() == "BOOLEAN"
    receipt_columns = {
        column["name"]: column for column in inspector.get_columns("seal_use_receipts")
    }
    assert receipt_columns["command_fingerprint"]["nullable"] is False
    assert {item["name"] for item in inspector.get_indexes("record_files")} >= {
        "ix_record_file_catalog",
        "ix_record_file_retention",
    }
    assert {item["name"] for item in inspector.get_indexes("seal_custody_events")} >= {
        "ix_seal_custody_timeline",
        "uk_seal_pending_transfer",
    }
    assert {item["name"] for item in inspector.get_check_constraints("signature_envelopes")} >= {
        "ck_signature_envelope_status",
        "ck_signature_envelope_truth",
    }
    assert {
        item["name"] for item in inspector.get_check_constraints("lease_contract_documents")
    } >= {"ck_lease_document_signed_truth"}

    with Session() as session:
        service = RecordsSealService(session, _ctx(seed["tenant_id"], seed["user_id"]))
        record = service.add_revision(
            seed["record_id"],
            {"expected_version": 1, "attachment_id": seed["attachment_1"]},
        )
        revision = record["revisions"][0]
        provider = service.create_signature_provider(
            {
                "code": f"PG_SANDBOX_{uuid4().hex[:8]}",
                "name": "PG签章沙箱",
                "adapter_kind": "LOCAL_SANDBOX",
            }
        )
        envelope = service.create_signature_envelope(
            {
                "provider_id": provider["id"],
                "record_id": record["id"],
                "revision_id": revision["id"],
                "source_type": "PG_RECORD",
                "source_id": uuid4().hex,
                "purpose": "数据库真实性约束",
                "participants": [{"role": "SIGNER", "display_name": "PG签署人"}],
            }
        )
        stored_envelope = session.get(SignatureEnvelope, envelope["id"])
        assert stored_envelope is not None
        with pytest.raises(IntegrityError), session.begin_nested():
            stored_envelope.status = "COMPLETED"
            stored_envelope.live_verified = False
            session.flush()

        invalid_revision = RecordRevision(
            tenant_id=seed["foreign_tenant_id"],
            park_id=seed["park_id"],
            record_id=seed["record_id"],
            attachment_id=seed["attachment_1"],
            version_no=99,
            filename="cross-tenant.txt",
            content_type="text/plain",
            size_bytes=1,
            checksum_sha256="0" * 64,
            status="ACTIVE",
        )
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(invalid_revision)
            session.flush()


def test_pg_record_revision_command_is_serialized_by_optimistic_version() -> None:
    seed = _seed()
    _, Session = _factory()
    barrier = threading.Barrier(2)

    def add(attachment_id: int) -> tuple[str, str | int]:
        with Session() as session:
            barrier.wait(timeout=15)
            try:
                result = RecordsSealService(
                    session, _ctx(seed["tenant_id"], seed["user_id"])
                ).add_revision(
                    seed["record_id"],
                    {"expected_version": 1, "attachment_id": attachment_id},
                )
                return "ok", int(result["revisions"][0]["id"])
            except AppError as exc:
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result(timeout=30)
            for future in [
                pool.submit(add, seed["attachment_1"]),
                pool.submit(add, seed["attachment_2"]),
            ]
        ]
    assert sum(kind == "ok" for kind, _ in outcomes) == 1, outcomes
    assert [value for kind, value in outcomes if kind == "error"] == ["VERSION_CONFLICT"]
    with Session() as session:
        assert (
            int(
                session.scalar(
                    select(func.count(RecordRevision.id)).where(
                        RecordRevision.tenant_id == seed["tenant_id"],
                        RecordRevision.record_id == seed["record_id"],
                    )
                )
                or 0
            )
            == 1
        )
