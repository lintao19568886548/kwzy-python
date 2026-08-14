"""PostgreSQL gate for the isolated synthetic workforce migration drill."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg


def _module():
    path = Path(__file__).resolve().parents[3] / "tools" / "etl" / "run_workforce_etl_drill.py"
    spec = importlib.util.spec_from_file_location("run_workforce_etl_drill", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pg_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    return url


def test_workforce_etl_reconciles_replays_recovers_and_rolls_back(tmp_path: Path) -> None:
    module = _module()
    report_path = tmp_path / "workforce-etl.json"
    assert module.main(["--database-url", _pg_url(), "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "PASS"
    assert report["synthetic_only"] is True
    assert report["live_legacy_verified"] is False
    assert report["legacy_performance_aggregate_present"] is False
    assert report["legacy_qualification_aggregate_present"] is False
    assert report["real_legacy_readiness"].startswith("BLOCKED_")
    assert report["production_contacted"] is False
    assert all(stage["passed"] for stage in report["stages"].values())
    assert report["stages"]["interruption_recovery"]["partial_rows_after_rollback"] == 0
    assert all(value == 0 for value in report["stages"]["idempotent_reapply"]["inserted"].values())
    reconciliation = report["stages"]["reconciliation"]
    assert reconciliation["target_counts"] == {
        "employees": 2,
        "shift_versions": 1,
        "assignments": 2,
        "punches": 3,
        "summaries": 2,
        "leaves": 1,
        "performance_records": 0,
        "qualifications": 0,
        "quarantine": 3,
    }
    assert reconciliation["raw_pii_or_exact_coordinate_columns"] == 0
    assert reconciliation["orphan_punches"] == 0
    assert reconciliation["fabricated_performance_records"] == 0
    assert reconciliation["fabricated_qualifications"] == 0
    assert reconciliation["payroll_results_generated"] == 0
    assert reconciliation["quarantine_reasons"] == {
        "EMPLOYEE_KEY_UNMAPPED": 1,
        "LEAVE_APPROVAL_EVIDENCE_MISSING": 1,
        "PARK_KEY_UNMAPPED": 1,
    }
    engine = create_engine(_pg_url())
    try:
        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": module.SCHEMA}
                ).scalar_one()
                is False
            )
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
def test_workforce_etl_refuses_unsafe_targets(url: str) -> None:
    with pytest.raises(ValueError):
        _module().safe_engine(url)
