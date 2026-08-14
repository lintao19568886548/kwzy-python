"""PostgreSQL gate for the synthetic organization-governance ETL drill."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg


def _module():
    path = (
        Path(__file__).resolve().parents[3]
        / "tools"
        / "etl"
        / "run_organization_governance_etl_drill.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_organization_governance_etl_drill", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pg_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    return url


def test_organization_governance_etl_reconciles_replays_and_rolls_back(
    tmp_path: Path,
) -> None:
    module = _module()
    report_path = tmp_path / "organization-governance-etl.json"
    assert module.main(["--database-url", _pg_url(), "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "PASS"
    assert report["source_schema_version"] == module.SOURCE_SCHEMA_VERSION
    assert report["readiness"] == "CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA"
    assert (
        report["real_legacy_readiness"]
        == "BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE"
    )
    assert all(stage["passed"] for stage in report["stages"].values())
    assert report["stages"]["idempotent_reapply"]["inserted"] == {
        table: 0 for table in module.FIELDS
    }
    assert report["stages"]["reconciliation"]["authorization_rows_emitted"] == 0
    assert report["stages"]["reconciliation"]["raw_pii_rows"] == 0
    engine = create_engine(_pg_url())
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT to_regnamespace(:schema) IS NOT NULL"),
                {"schema": module.SCHEMA},
            ).scalar_one()
        assert exists is False
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@db.example.com/kwzy_test",
        "postgresql+psycopg://u:p@127.0.0.1/kwzy_prod",
        "postgresql+psycopg://u:p@127.0.0.1/kwzy",
        "sqlite:///kwzy_test.db",
    ],
)
def test_organization_governance_etl_refuses_unsafe_targets(url: str) -> None:
    with pytest.raises(ValueError):
        _module().safe_engine(url)
