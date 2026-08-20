"""PostgreSQL gate for the isolated synthetic engagement migration drill."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg


def _module():
    path = Path(__file__).resolve().parents[3] / "tools" / "etl" / "run_engagement_etl_drill.py"
    spec = importlib.util.spec_from_file_location("run_engagement_etl_drill", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pg_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    return url


def test_engagement_etl_reconciles_resumes_replays_restores_and_rolls_back(
    tmp_path: Path,
) -> None:
    module = _module()
    report_path = tmp_path / "engagement-etl.json"
    assert module.main(["--database-url", _pg_url(), "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "PASS"
    assert report["synthetic_only"] is True
    assert report["live_legacy_verified"] is False
    assert report["authoritative_legacy_schema_present"] is False
    assert report["authorized_legacy_exports_present"] is False
    assert report["real_legacy_readiness"].startswith("BLOCKED_")
    assert report["production_contacted"] is False
    assert all(stage["passed"] for stage in report["stages"].values())
    assert report["stages"]["interruption_recovery"]["partial_rows_after_rollback"] == 0
    checkpoint = report["stages"]["checkpoint_resume"]
    assert checkpoint["checkpoint"] == "service_cases"
    assert sum(checkpoint["committed_counts_before_resume"].values()) == 4
    assert checkpoint["resume_inserted"]["policies"] == 0
    assert checkpoint["resume_inserted"]["registrations"] == 2
    assert all(value == 0 for value in report["stages"]["idempotent_reapply"]["inserted"].values())
    reconciliation = report["stages"]["reconciliation"]
    assert reconciliation["target_counts"] == {
        "policies": 1,
        "policy_versions": 1,
        "service_catalogs": 1,
        "service_cases": 1,
        "activities": 1,
        "activity_versions": 1,
        "registrations": 2,
        "announcements": 1,
        "announcement_versions": 1,
        "announcement_targets": 2,
        "announcement_deliveries": 2,
        "quarantine": 5,
    }
    for field in (
        "version_mismatches",
        "invalid_active_windows",
        "orphan_service_cases",
        "capacity_or_registration_mismatches",
        "orphan_registrations",
        "audience_target_mismatches",
        "delivery_or_read_mismatches",
        "false_external_deliveries",
        "fabricated_approved_or_published_state",
        "raw_sensitive_columns",
    ):
        assert reconciliation[field] == 0
    assert reconciliation["quarantine_reasons"] == {
        "ACTIVITY_REFERENCE_UNMAPPED": 1,
        "EXTERNAL_CHANNEL_UNVERIFIED": 1,
        "EXTERNAL_PROVIDER_EVIDENCE_MISSING": 1,
        "OFFICIAL_SOURCE_UNAUTHORIZED": 1,
        "PARTY_KEY_UNMAPPED": 1,
    }
    assert report["stages"]["run_scoped_rollback"] == {
        "passed": True,
        "target_rows_after_run_delete": 0,
        "unrelated_run_preserved": True,
    }
    restore = report["stages"]["backup_delete_restore"]
    assert restore["restored_manifest_matches"] is True
    assert restore["backup_manifest"]["counts"] == reconciliation["target_counts"]
    engine = create_engine(_pg_url())
    try:
        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT to_regnamespace(:schema) IS NOT NULL"),
                    {"schema": module.SCHEMA},
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
def test_engagement_etl_refuses_unsafe_targets(url: str) -> None:
    with pytest.raises(ValueError):
        _module().safe_engine(url)
