#!/usr/bin/env python3
"""Synthetic-only enterprise Party ETL rehearsal on disposable localhost PostgreSQL.

The drill never reads legacy/production systems. It proves validation, deterministic
mapping, bounded interruption rollback, idempotent reapply, reconciliation, raw
identifier reduction, quarantine isolation, and isolated-schema rollback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
SCHEMA = "etl_party_enterprise_fixture"
SOURCE_SCHEMA_VERSION = "kwzy.party-enterprise.synthetic.v1"
TARGET_TABLES = (
    "enterprise_profiles",
    "relationships",
    "credentials",
    "tags",
    "risk_signals",
    "quarantine",
)


def _database_url() -> str:
    value = (
        os.environ.get("ETL_DATABASE_URL")
        or os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("POSTGRES_TEST_URL")
        or ""
    )
    lowered = value.lower()
    if not value or not value.startswith("postgresql"):
        raise SystemExit("ETL_DATABASE_URL / TEST_DATABASE_URL must be PostgreSQL")
    if "127.0.0.1" not in lowered and "localhost" not in lowered:
        raise SystemExit("refusing non-localhost database URL")
    if not any(marker in lowered for marker in ("test", "fixture", "dev")):
        raise SystemExit("database name must visibly be test/fixture/dev")
    return value


def _fingerprint(value: str) -> tuple[str, str]:
    normalized = "".join(char for char in value.upper() if char.isalnum())
    if not 4 <= len(normalized) <= 64:
        raise ValueError("organization identifier length invalid")
    return hashlib.sha256(
        normalized.encode()
    ).hexdigest(), f"{'*' * 12}{normalized[-4:]}"


def _load_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    metadata = data.get("metadata") or {}
    if metadata.get("source_schema_version") != SOURCE_SCHEMA_VERSION:
        raise ValueError("unsupported source schema version")
    if metadata.get("synthetic_only") is not True:
        raise ValueError("fixture must be explicitly synthetic_only")
    if metadata.get("contains_real_customer_data") is not False:
        raise ValueError("fixture real-data declaration is unsafe")
    serialized = json.dumps(data, ensure_ascii=False).lower()
    for forbidden in ("id_card", "identity_number", "bank_account", "personal_phone"):
        if forbidden in serialized:
            raise ValueError(f"forbidden personal field in fixture: {forbidden}")
    return data


def _transform(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result = {name: [] for name in TARGET_TABLES}
    enterprise_ids: set[str] = set()
    for row in data.get("enterprises") or []:
        source_id = str(row.get("source_id") or "")
        name = str(row.get("company_name") or "").strip()
        if not source_id or not name:
            continue
        enterprise_ids.add(source_id)
        result["enterprise_profiles"].append(
            {
                "source_id": source_id,
                "tenant_ref": str(row["tenant_ref"]),
                "company_name": name,
                "credit_code": str(row.get("credit_code") or "") or None,
                "legal_representative": row.get("legal_representative"),
                "established_on": row.get("established_on"),
                "registered_capital": row.get("registered_capital"),
                "capital_currency": row.get("capital_currency"),
                "registration_status": str(row.get("registration_status") or "UNKNOWN"),
                "industry_code": row.get("industry_code"),
                "industry_name": row.get("industry_name"),
                "business_scope": row.get("business_scope"),
                "provider_status": "NOT_CONNECTED",
            }
        )
    for row in data.get("relationships") or []:
        source_ref = str(row.get("source_enterprise_ref") or "")
        target_ref = str(row.get("target_enterprise_ref") or "")
        if source_ref not in enterprise_ids or target_ref not in enterprise_ids:
            result["quarantine"].append(
                {
                    "tenant_ref": str(row.get("tenant_ref") or ""),
                    "source_type": "relationship",
                    "source_id": str(row.get("source_id") or ""),
                    "reason_code": "ORPHAN_ENTERPRISE_REFERENCE",
                    "value_fingerprint": hashlib.sha256(
                        f"{source_ref}|{target_ref}".encode()
                    ).hexdigest(),
                }
            )
            continue
        result["relationships"].append(
            {
                "source_id": str(row["source_id"]),
                "tenant_ref": str(row["tenant_ref"]),
                "source_enterprise_ref": source_ref,
                "target_enterprise_ref": target_ref,
                "relationship_type": str(row["relationship_type"]),
                "ownership_percent": row.get("ownership_percent"),
                "source_type": "MIGRATION",
            }
        )
    for row in data.get("credentials") or []:
        enterprise_ref = str(row.get("enterprise_ref") or "")
        if enterprise_ref not in enterprise_ids:
            continue
        fingerprint, masked = _fingerprint(
            str(row.get("organization_identifier") or "")
        )
        result["credentials"].append(
            {
                "source_id": str(row["source_id"]),
                "tenant_ref": str(row["tenant_ref"]),
                "enterprise_ref": enterprise_ref,
                "credential_type": str(row["credential_type"]),
                "identifier_fingerprint": fingerprint,
                "identifier_masked": masked,
                "attachment_ref": str(row["attachment_ref"]),
                "issuer": row.get("issuer"),
                "issued_on": row.get("issued_on"),
                "expires_on": row.get("expires_on"),
                "verification_status": "UNVERIFIED",
            }
        )
    for source_name, target_name in (
        ("tags", "tags"),
        ("risk_signals", "risk_signals"),
    ):
        for row in data.get(source_name) or []:
            enterprise_ref = str(row.get("enterprise_ref") or "")
            if enterprise_ref not in enterprise_ids:
                continue
            mapped = dict(row)
            mapped["source_type"] = "MIGRATION"
            result[target_name].append(mapped)
    for row in data.get("quarantine_cases") or []:
        result["quarantine"].append(dict(row))
    return result


def _create_schema(conn) -> None:
    conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    conn.execute(
        text(
            f"""
CREATE TABLE {SCHEMA}.enterprise_profiles (
  source_id text PRIMARY KEY, tenant_ref text NOT NULL, company_name text NOT NULL,
  credit_code text, legal_representative text, established_on date,
  registered_capital numeric(18,2), capital_currency varchar(3),
  registration_status text NOT NULL, industry_code text, industry_name text,
  business_scope text, provider_status text NOT NULL CHECK (provider_status='NOT_CONNECTED')
);
CREATE TABLE {SCHEMA}.relationships (
  source_id text PRIMARY KEY, tenant_ref text NOT NULL,
  source_enterprise_ref text NOT NULL REFERENCES {SCHEMA}.enterprise_profiles(source_id),
  target_enterprise_ref text NOT NULL REFERENCES {SCHEMA}.enterprise_profiles(source_id),
  relationship_type text NOT NULL, ownership_percent numeric(5,2), source_type text NOT NULL
);
CREATE TABLE {SCHEMA}.credentials (
  source_id text PRIMARY KEY, tenant_ref text NOT NULL,
  enterprise_ref text NOT NULL REFERENCES {SCHEMA}.enterprise_profiles(source_id),
  credential_type text NOT NULL, identifier_fingerprint char(64), identifier_masked text,
  attachment_ref text NOT NULL, issuer text, issued_on date, expires_on date,
  verification_status text NOT NULL
);
CREATE TABLE {SCHEMA}.tags (
  source_id text PRIMARY KEY, tenant_ref text NOT NULL,
  enterprise_ref text NOT NULL REFERENCES {SCHEMA}.enterprise_profiles(source_id),
  name text NOT NULL, tag_type text NOT NULL, confidence numeric(5,4), source_type text NOT NULL
);
CREATE TABLE {SCHEMA}.risk_signals (
  source_id text PRIMARY KEY, tenant_ref text NOT NULL,
  enterprise_ref text NOT NULL REFERENCES {SCHEMA}.enterprise_profiles(source_id),
  category text NOT NULL, severity text NOT NULL, summary text NOT NULL,
  occurred_at timestamptz NOT NULL, source_type text NOT NULL
);
CREATE TABLE {SCHEMA}.quarantine (
  tenant_ref text NOT NULL, source_type text NOT NULL, source_id text NOT NULL,
  reason_code text NOT NULL, value_fingerprint text NOT NULL,
  PRIMARY KEY (source_type, source_id)
);
CREATE TABLE {SCHEMA}.checkpoint (
  target_table text NOT NULL, source_id text NOT NULL,
  PRIMARY KEY (target_table, source_id)
);
"""
        )
    )


def _apply(
    conn, rows: dict[str, list[dict[str, Any]]], *, interrupt: bool = False
) -> dict[str, int]:
    inserted = {table: 0 for table in TARGET_TABLES}
    for table in TARGET_TABLES:
        for row in rows[table]:
            source_id = str(row["source_id"])
            done = conn.execute(
                text(
                    f"SELECT 1 FROM {SCHEMA}.checkpoint "
                    "WHERE target_table=:target_table AND source_id=:source_id"
                ),
                {"target_table": table, "source_id": source_id},
            ).first()
            if done:
                continue
            columns = list(row)
            statement = (
                f"INSERT INTO {SCHEMA}.{table} ({','.join(columns)}) VALUES "
                f"({','.join(':' + column for column in columns)}) ON CONFLICT DO NOTHING"
            )
            result = conn.execute(text(statement), row)
            inserted[table] += int(result.rowcount or 0)
            conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.checkpoint(target_table,source_id) "
                    "VALUES (:target_table,:source_id) ON CONFLICT DO NOTHING"
                ),
                {"target_table": table, "source_id": source_id},
            )
        if interrupt and table == "enterprise_profiles":
            raise RuntimeError("synthetic interruption after enterprise profiles")
    return inserted


def _counts(conn) -> dict[str, int]:
    return {
        table: int(
            conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()
        )
        for table in TARGET_TABLES
    }


def _reconcile(conn, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target = _counts(conn)
    expected = {table: len(rows[table]) for table in TARGET_TABLES}
    orphan_relationships = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.relationships r "
                f"LEFT JOIN {SCHEMA}.enterprise_profiles s ON s.source_id=r.source_enterprise_ref "
                f"LEFT JOIN {SCHEMA}.enterprise_profiles t ON t.source_id=r.target_enterprise_ref "
                "WHERE s.source_id IS NULL OR t.source_id IS NULL"
            )
        ).scalar_one()
    )
    bad_fingerprints = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.credentials "
                "WHERE identifier_fingerprint IS NOT NULL AND length(identifier_fingerprint)<>64"
            )
        ).scalar_one()
    )
    raw_identifier_columns = int(
        conn.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema=:schema AND column_name IN "
                "('organization_identifier','raw_identifier','id_card','identity_number')"
            ),
            {"schema": SCHEMA},
        ).scalar_one()
    )
    provider_errors = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.enterprise_profiles "
                "WHERE provider_status<>'NOT_CONNECTED'"
            )
        ).scalar_one()
    )
    quarantine_reasons = dict(
        conn.execute(
            text(
                f"SELECT reason_code,count(*) FROM {SCHEMA}.quarantine GROUP BY reason_code"
            )
        ).all()
    )
    passed = (
        target == expected
        and orphan_relationships == 0
        and bad_fingerprints == 0
        and raw_identifier_columns == 0
        and provider_errors == 0
        and set(quarantine_reasons)
        == {"ORPHAN_ENTERPRISE_REFERENCE", "PERSONAL_IDENTITY_FORBIDDEN"}
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "orphan_relationships": orphan_relationships,
        "bad_identifier_fingerprints": bad_fingerprints,
        "raw_identifier_columns": raw_identifier_columns,
        "provider_status_errors": provider_errors,
        "quarantine_reasons": quarantine_reasons,
    }


def _authorization_signature(conn) -> dict[str, int]:
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture", default=str(ROOT / "fixtures" / "party_enterprise_v1.json")
    )
    parser.add_argument(
        "--report", default=str(ROOT / "out" / "party_enterprise_etl_report.json")
    )
    args = parser.parse_args()
    fixture_path = Path(args.fixture)
    fixture = _load_fixture(fixture_path)
    rows = _transform(fixture)
    dry_counts = {table: len(rows[table]) for table in TARGET_TABLES}
    engine = create_engine(_database_url(), pool_pre_ping=True)
    with engine.begin() as conn:
        authorization_before = _authorization_signature(conn)
        _create_schema(conn)

    interrupted = False
    try:
        with engine.begin() as conn:
            _apply(conn, rows, interrupt=True)
    except RuntimeError as exc:
        if str(exc) != "synthetic interruption after enterprise profiles":
            raise
        interrupted = True
    with engine.begin() as conn:
        partial_after_rollback = sum(_counts(conn).values())
        first_apply = _apply(conn, rows)
    with engine.begin() as conn:
        second_apply = _apply(conn, rows)
        reconciliation = _reconcile(conn, rows)
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
        schema_exists = bool(
            conn.execute(
                text(
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name=:schema"
                ),
                {"schema": SCHEMA},
            ).first()
        )
        authorization_after = _authorization_signature(conn)
    engine.dispose()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "schema": SCHEMA,
        "synthetic_only": True,
        "live_legacy_verified": False,
        "stages": {
            "dry_run": {"passed": True, "mapped_counts": dry_counts},
            "interruption_recovery": {
                "passed": interrupted and partial_after_rollback == 0,
                "partial_rows_after_rollback": partial_after_rollback,
            },
            "first_apply": {
                "passed": first_apply == dry_counts,
                "inserted": first_apply,
            },
            "idempotent_reapply": {
                "passed": all(value == 0 for value in second_apply.values()),
                "inserted": second_apply,
            },
            "reconciliation": reconciliation,
            "rollback": {
                "passed": not schema_exists
                and authorization_before == authorization_after,
                "schema_exists_after": schema_exists,
                "authorization_rows_unchanged": authorization_before
                == authorization_after,
            },
        },
        "blockers": [
            "real legacy schema/dictionary and authorized desensitized snapshot not supplied",
            "external enterprise-registry credentials and contract not supplied",
            "production migration/cutover not authorized",
        ],
    }
    report["passed"] = all(stage["passed"] for stage in report["stages"].values())
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
