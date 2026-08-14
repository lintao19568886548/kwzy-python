"""PostgreSQL 16 concurrency gate for integration delivery idempotency."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models.integration_outbox import IntegrationOutbox
from app.modules.identity.application.bootstrap import ensure_default_tenant

pytestmark = pytest.mark.pg


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not value.startswith("postgresql") or not any(
        host in value for host in ("127.0.0.1", "localhost")
    ):
        pytest.fail("integration concurrency test requires localhost PostgreSQL")
    if "kwzy_party_test" not in value:
        pytest.fail("database name must include kwzy_party_test")
    return value


def test_pg_outbox_unique_constraint_and_concurrent_claim() -> None:
    engine = create_engine(_url(), pool_pre_ping=True, pool_size=4, max_overflow=2)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    marker = f"pg-idem-{uuid4().hex}"
    with Session() as session:
        tenant_id = int(ensure_default_tenant(session).id)
        session.commit()

    barrier = threading.Barrier(2)

    def insert() -> str:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                session.add(
                    IntegrationOutbox(
                        tenant_id=tenant_id,
                        channel="sms",
                        provider="pg-test",
                        idempotency_key=marker,
                        status="PENDING",
                        attempts=0,
                    )
                )
                session.commit()
                return "ok"
            except IntegrityError:
                session.rollback()
                return "conflict"

    try:
        with engine.connect() as connection:
            definition = connection.scalar(
                text(
                    "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
                    "AND indexname='uk_integration_outbox_tenant_channel_key'"
                )
            )
        assert definition and "UNIQUE" in str(definition)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: insert(), range(2)))
        assert sorted(outcomes) == ["conflict", "ok"]
        with Session() as session:
            count = session.scalar(
                select(func.count(IntegrationOutbox.id)).where(
                    IntegrationOutbox.tenant_id == tenant_id,
                    IntegrationOutbox.channel == "sms",
                    IntegrationOutbox.idempotency_key == marker,
                )
            )
            assert int(count or 0) == 1
    finally:
        engine.dispose()
