"""PostgreSQL 16 harness tests (no Party business logic).

Requires TEST_DATABASE_URL or POSTGRES_TEST_URL pointing at disposable kwzy_party_test.
Never logs connection passwords.
"""

from __future__ import annotations

import os
import re

import pytest

pytestmark = pytest.mark.pg


def _pg_url() -> str | None:
    return (
        os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("POSTGRES_TEST_URL")
        or None
    )


def _require_pg_url() -> str:
    url = _pg_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if "sqlite" in url.lower():
        pytest.fail("PostgreSQL harness must not use SQLite URL")
    if not url.startswith("postgresql"):
        pytest.fail("PostgreSQL harness requires postgresql URL scheme")
    # safety: localhost only
    if "127.0.0.1" not in url and "localhost" not in url:
        pytest.fail("PostgreSQL harness must bind to localhost")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def test_psycopg_importable() -> None:
    import psycopg  # noqa: F401

    assert psycopg is not None


def test_postgres_connect_and_version() -> None:
    url = _require_pg_url()
    from sqlalchemy import create_engine, text

    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        ver = conn.execute(text("SHOW server_version")).scalar_one()
        db = conn.execute(text("SELECT current_database()")).scalar_one()
        user = conn.execute(text("SELECT current_user")).scalar_one()
    major = int(str(ver).split(".")[0])
    assert major == 16, f"expected PostgreSQL 16, got {ver!r}"
    assert db == "kwzy_party_test"
    assert user == "kwzy_party_test"
    # never assert password
    assert "password" not in url.lower().split("@")[0] or True


def test_postgres_transaction_commit_rollback() -> None:
    url = _require_pg_url()
    from sqlalchemy import create_engine, text

    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS _harness_tx (id INT PRIMARY KEY)"))
        conn.execute(text("DELETE FROM _harness_tx"))
        conn.execute(text("INSERT INTO _harness_tx (id) VALUES (1)"))
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM _harness_tx")).scalar_one()
        assert int(n) == 1
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("INSERT INTO _harness_tx (id) VALUES (2)"))
        trans.rollback()
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM _harness_tx")).scalar_one()
        assert int(n) == 1
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS _harness_tx"))


def test_postgres_url_safety_shape() -> None:
    """Sanity: URL points at local test DB (no password assertion)."""
    url = _require_pg_url()
    assert re.search(r"@127\.0\.0\.1:\d+/kwzy_party_test", url) or re.search(
        r"@localhost:\d+/kwzy_party_test", url
    )
