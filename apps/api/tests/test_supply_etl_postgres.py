"""PostgreSQL gate for the isolated synthetic supply migration drill."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg


def _module():
    path = Path(__file__).resolve().parents[3] / "tools" / "etl" / "run_supply_etl_drill.py"
    spec = importlib.util.spec_from_file_location("run_supply_etl_drill", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pg_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    return url


def test_supply_etl_reconciles_replays_recovers_and_rolls_back(tmp_path: Path) -> None:
    module = _module()
    report_path = tmp_path / "supply-etl.json"
    assert module.main(["--database-url", _pg_url(), "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "PASS"
    assert report["synthetic_only"] is True
    assert report["live_legacy_verified"] is False
    assert report["authoritative_legacy_schema_present"] is False
    assert report["authoritative_legacy_transactions_present"] is False
    assert report["real_legacy_readiness"].startswith("BLOCKED_")
    assert report["production_contacted"] is False
    assert all(stage["passed"] for stage in report["stages"].values())
    assert report["stages"]["interruption_recovery"]["partial_rows_after_rollback"] == 0
    checkpoint = report["stages"]["checkpoint_resume"]
    assert checkpoint["checkpoint"] == "warehouses"
    assert sum(checkpoint["committed_counts_before_resume"].values()) == 5
    assert checkpoint["resume_inserted"]["suppliers"] == 0
    assert checkpoint["resume_inserted"]["stock_movements"] == 2
    assert all(value == 0 for value in report["stages"]["idempotent_reapply"]["inserted"].values())
    reconciliation = report["stages"]["reconciliation"]
    assert reconciliation["target_counts"] == {
        "suppliers": 1,
        "supplier_scopes": 1,
        "materials": 2,
        "warehouses": 1,
        "procurement_orders": 1,
        "stock_movements": 2,
        "stock_balances": 1,
        "outsourcing_orders": 1,
        "quarantine": 4,
    }
    assert reconciliation["raw_sensitive_columns"] == 0
    assert reconciliation["raw_credential_values"] == 0
    assert reconciliation["orphan_stock_movements"] == 0
    assert reconciliation["ledger_balance_mismatches"] == 0
    assert reconciliation["negative_or_invalid_balances"] == 0
    assert reconciliation["fabricated_trusted_approvals"] == 0
    assert reconciliation["fabricated_integrated_settlements"] == 0
    assert reconciliation["on_hand_reconciled"] == "7.0000"
    assert reconciliation["quarantine_reasons"] == {
        "APPROVAL_EVIDENCE_MISSING": 1,
        "PARK_KEY_UNMAPPED": 1,
        "SETTLEMENT_EVIDENCE_MISSING": 1,
        "STOCK_REFERENCE_UNMAPPED": 1,
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
def test_supply_etl_refuses_unsafe_targets(url: str) -> None:
    with pytest.raises(ValueError):
        _module().safe_engine(url)
