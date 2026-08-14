"""Lease PostgreSQL 16 tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg


def _pg_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")


def _require_pg_url() -> str:
    url = _pg_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def test_pg_lease_tables_exist() -> None:
    url = _require_pg_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        for table in ("lease_contracts", "lease_contract_units", "lease_terms"):
            exists = conn.execute(
                text("SELECT to_regclass(:t)"),
                {"t": f"public.{table}"},
            ).scalar()
            # if migrations not applied yet, try information_schema
            if exists is None:
                n = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=:n"
                    ),
                    {"n": table},
                ).scalar()
                assert int(n or 0) == 1, f"missing {table}"
    engine.dispose()
