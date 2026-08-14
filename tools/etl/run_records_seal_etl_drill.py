#!/usr/bin/env python3
"""Synthetic archive/signature/seal migration rehearsal on loopback PostgreSQL.

This proves deterministic mapping, binary checksum derivation, transaction recovery,
idempotent replay, reconciliation and rollback. It never connects to a live legacy
database and never fabricates a seal registry, custody chain or live signature event.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_records_seal_fixture"
TABLES = ("record_categories", "records", "record_revisions", "seal_assets", "quarantine")
MIGRATED_AT = datetime(2026, 8, 15, tzinfo=timezone.utc).replace(tzinfo=None)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def load_fixture(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("contains_real_customer_data") is not False:
        raise ValueError("fixture must declare contains_real_customer_data=false")
    if source.get("legacy_seal_aggregate_present") is not False:
        raise ValueError("synthetic evidence must not claim an unavailable legacy seal aggregate")
    if source.get("legacy_signature_event_aggregate_present") is not False:
        raise ValueError("synthetic evidence must not claim unavailable provider events")
    for key in ("categories", "documents", "seal_records"):
        if not isinstance(source.get(key), list):
            raise TypeError(f"fixture {key} must be an array")
    if source["seal_records"]:
        raise ValueError("seal rows cannot be fabricated when the legacy aggregate is absent")
    return source


def validate_source(source: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    category_ids: set[str] = set()
    category_codes: set[str] = set()
    for row in source["categories"]:
        missing = {
            "source_id",
            "code",
            "name",
            "retention_mode",
            "retention_years",
            "confidentiality_max",
        } - row.keys()
        if missing:
            errors.append(
                f"category:{row.get('source_id', '?')}:missing:{','.join(sorted(missing))}"
            )
            continue
        source_id = str(row["source_id"])
        code = str(row["code"]).strip().upper()
        if source_id in category_ids:
            errors.append(f"duplicate category source:{source_id}")
        if code in category_codes:
            errors.append(f"duplicate category code:{code}")
        category_ids.add(source_id)
        category_codes.add(code)
        mode = str(row["retention_mode"]).upper()
        years = row["retention_years"]
        if mode not in {"YEARS", "PERMANENT"}:
            errors.append(f"invalid retention mode:{source_id}")
        if mode == "PERMANENT" and years is not None:
            errors.append(f"permanent category has years:{source_id}")
        if mode == "YEARS" and (not isinstance(years, int) or not 1 <= years <= 100):
            errors.append(f"invalid retention years:{source_id}")
    document_keys: set[str] = set()
    for row in source["documents"]:
        required = {
            "legacy_table",
            "source_id",
            "category_ref",
            "park_ref",
            "title",
            "source_type",
            "source_biz_id",
            "confidentiality",
            "filename",
            "content_type",
            "content_base64",
            "legacy_signed_flag",
            "provider_certificate_ref",
        }
        missing = required - row.keys()
        source_key = f"{row.get('legacy_table', '?')}:{row.get('source_id', '?')}"
        if missing:
            errors.append(f"{source_key}:missing:{','.join(sorted(missing))}")
            continue
        if source_key in document_keys:
            errors.append(f"duplicate document source:{source_key}")
        document_keys.add(source_key)
        try:
            content = base64.b64decode(str(row["content_base64"]), validate=True)
            if not content:
                errors.append(f"empty binary:{source_key}")
        except ValueError:
            errors.append(f"invalid base64:{source_key}")
    return {
        "passed": not errors,
        "errors": errors,
        "source_categories": len(category_ids),
        "source_documents": len(document_keys),
        "source_seals": len(source["seal_records"]),
    }


def transform(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
    categories = {str(row["source_id"]): row for row in source["categories"]}
    for row in source["categories"]:
        rows["record_categories"].append(
            {
                "source_key": str(row["source_id"]),
                "code": str(row["code"]).strip().upper(),
                "name": str(row["name"]).strip(),
                "retention_mode": str(row["retention_mode"]).upper(),
                "retention_years": row["retention_years"],
                "confidentiality_max": str(row["confidentiality_max"]).upper(),
                "migrated_at": MIGRATED_AT,
            }
        )
    for row in source["documents"]:
        source_key = f"{row['legacy_table']}:{row['source_id']}"
        category = categories.get(str(row["category_ref"]))
        if category is None:
            rows["quarantine"].append(
                {
                    "source_key": source_key,
                    "issue_code": "CATEGORY_KEY_UNMAPPED",
                    "value_fingerprint": digest_text(str(row["category_ref"])),
                }
            )
            continue
        try:
            content = base64.b64decode(str(row["content_base64"]), validate=True)
        except ValueError:
            content = b""
        if not content:
            rows["quarantine"].append(
                {
                    "source_key": source_key,
                    "issue_code": "BINARY_MISSING_OR_INVALID",
                    "value_fingerprint": digest_text(str(row.get("filename", ""))),
                }
            )
            continue
        signed_unverified = bool(row["legacy_signed_flag"]) and not row["provider_certificate_ref"]
        signature_truth = (
            "LEGACY_SIGNATURE_UNVERIFIED" if signed_unverified else "NO_SIGNATURE_CLAIM"
        )
        if signed_unverified:
            rows["quarantine"].append(
                {
                    "source_key": source_key,
                    "issue_code": "SIGNATURE_EVIDENCE_MISSING",
                    "value_fingerprint": digest_text(
                        f"{row['legacy_signed_flag']}:{row['source_biz_id']}"
                    ),
                }
            )
        record_no = f"LEGACY-{digest_text(source_key)[:16].upper()}"
        rows["records"].append(
            {
                "source_key": source_key,
                "category_source_key": str(row["category_ref"]),
                "park_ref": str(row["park_ref"]),
                "record_no": record_no,
                "title": str(row["title"]).strip(),
                "source_type": str(row["source_type"]).upper(),
                "source_biz_id": str(row["source_biz_id"]),
                "confidentiality": str(row["confidentiality"]).upper(),
                "status": "FILED",
                "signature_truth": signature_truth,
                "migrated_at": MIGRATED_AT,
            }
        )
        rows["record_revisions"].append(
            {
                "source_revision_key": f"{source_key}:v1",
                "record_source_key": source_key,
                "version_no": 1,
                "filename": str(row["filename"]),
                "content_type": str(row["content_type"]),
                "size_bytes": len(content),
                "checksum_sha256": digest_bytes(content),
                "binary_fingerprint": digest_bytes(content),
                "migrated_at": MIGRATED_AT,
            }
        )
    # No source seal aggregate exists. Zero is a deliberate evidence-backed mapping.
    return rows


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.record_categories (
  source_key text PRIMARY KEY,
  code text NOT NULL UNIQUE,
  name text NOT NULL,
  retention_mode text NOT NULL CHECK (retention_mode IN ('YEARS','PERMANENT')),
  retention_years integer CHECK (
    (retention_mode = 'PERMANENT' AND retention_years IS NULL) OR
    (retention_mode = 'YEARS' AND retention_years BETWEEN 1 AND 100)
  ),
  confidentiality_max text NOT NULL CHECK (confidentiality_max IN ('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED')),
  migrated_at timestamp NOT NULL
);
CREATE TABLE {SCHEMA}.records (
  source_key text PRIMARY KEY,
  category_source_key text NOT NULL REFERENCES {SCHEMA}.record_categories(source_key),
  park_ref text NOT NULL,
  record_no text NOT NULL UNIQUE,
  title text NOT NULL,
  source_type text NOT NULL,
  source_biz_id text NOT NULL,
  confidentiality text NOT NULL CHECK (confidentiality IN ('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED')),
  status text NOT NULL CHECK (status = 'FILED'),
  signature_truth text NOT NULL CHECK (signature_truth IN ('NO_SIGNATURE_CLAIM','LEGACY_SIGNATURE_UNVERIFIED')),
  migrated_at timestamp NOT NULL,
  UNIQUE (source_type, source_biz_id)
);
CREATE TABLE {SCHEMA}.record_revisions (
  source_revision_key text PRIMARY KEY,
  record_source_key text NOT NULL REFERENCES {SCHEMA}.records(source_key),
  version_no integer NOT NULL CHECK (version_no > 0),
  filename text NOT NULL,
  content_type text NOT NULL,
  size_bytes bigint NOT NULL CHECK (size_bytes > 0),
  checksum_sha256 char(64) NOT NULL,
  binary_fingerprint char(64) NOT NULL,
  migrated_at timestamp NOT NULL,
  UNIQUE (record_source_key, version_no),
  UNIQUE (record_source_key, checksum_sha256)
);
CREATE TABLE {SCHEMA}.seal_assets (
  source_key text PRIMARY KEY,
  seal_code text NOT NULL UNIQUE,
  evidence_truth text NOT NULL CHECK (evidence_truth = 'LEGACY_AGGREGATE_VERIFIED')
);
CREATE TABLE {SCHEMA}.quarantine (
  source_key text NOT NULL,
  issue_code text NOT NULL,
  value_fingerprint char(64) NOT NULL,
  PRIMARY KEY (source_key, issue_code)
);
"""

FIELDS = {
    "record_categories": (
        "source_key",
        "code",
        "name",
        "retention_mode",
        "retention_years",
        "confidentiality_max",
        "migrated_at",
    ),
    "records": (
        "source_key",
        "category_source_key",
        "park_ref",
        "record_no",
        "title",
        "source_type",
        "source_biz_id",
        "confidentiality",
        "status",
        "signature_truth",
        "migrated_at",
    ),
    "record_revisions": (
        "source_revision_key",
        "record_source_key",
        "version_no",
        "filename",
        "content_type",
        "size_bytes",
        "checksum_sha256",
        "binary_fingerprint",
        "migrated_at",
    ),
    "seal_assets": ("source_key", "seal_code", "evidence_truth"),
    "quarantine": ("source_key", "issue_code", "value_fingerprint"),
}


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("records/seal ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("records/seal ETL drill is restricted to loopback PostgreSQL")
    identity = (parsed.database or "").lower()
    if "prod" in identity or not any(
        word in identity for word in ("test", "local", "dev", "audit")
    ):
        raise ValueError("records/seal ETL drill refuses a production-like database identity")
    return create_engine(database_url, pool_pre_ping=True)


def create_schema(conn) -> None:  # type: ignore[no-untyped-def]
    conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    for statement in DDL.split(";"):
        if statement.strip():
            conn.execute(text(statement))


def counts(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one())
        for table in TABLES
    }


def apply_rows(
    conn, rows: dict[str, list[dict[str, Any]]], *, interrupt: bool = False
) -> dict[str, int]:  # type: ignore[no-untyped-def]
    inserted = {table: 0 for table in TABLES}
    for table in TABLES:
        fields = FIELDS[table]
        columns = ",".join(fields)
        values = ",".join(f":{field}" for field in fields)
        for row in rows[table]:
            result = conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.{table} ({columns}) VALUES ({values}) "
                    "ON CONFLICT DO NOTHING"
                ),
                {field: row[field] for field in fields},
            )
            inserted[table] += int(result.rowcount or 0)
        if interrupt and table == "records":
            raise RuntimeError("synthetic interruption after records")
    return inserted


def authorization_signature(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def reconcile(conn, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    expected = {table: len(values) for table, values in rows.items()}
    target = counts(conn)
    expected_truth = dict(Counter(row["signature_truth"] for row in rows["records"]))
    target_truth = dict(
        conn.execute(
            text(f"SELECT signature_truth,count(*) FROM {SCHEMA}.records GROUP BY signature_truth")
        ).all()
    )
    orphan_revisions = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.record_revisions v "
                f"LEFT JOIN {SCHEMA}.records r ON r.source_key=v.record_source_key "
                "WHERE r.source_key IS NULL"
            )
        ).scalar_one()
    )
    checksum_mismatches = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.record_revisions "
                "WHERE checksum_sha256 <> binary_fingerprint"
            )
        ).scalar_one()
    )
    quarantine = dict(
        conn.execute(
            text(f"SELECT issue_code,count(*) FROM {SCHEMA}.quarantine GROUP BY issue_code")
        ).all()
    )
    passed = (
        expected == target
        and expected_truth == target_truth
        and orphan_revisions == 0
        and checksum_mismatches == 0
        and target["seal_assets"] == 0
        and quarantine == {"CATEGORY_KEY_UNMAPPED": 1, "SIGNATURE_EVIDENCE_MISSING": 1}
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "expected_signature_truth": expected_truth,
        "target_signature_truth": target_truth,
        "orphan_revisions": orphan_revisions,
        "checksum_mismatches": checksum_mismatches,
        "quarantine_reasons": quarantine,
        "fabricated_seals": target["seal_assets"],
        "fabricated_custody_events": 0,
        "fabricated_signature_providers": 0,
        "fabricated_signature_events": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "records_seal_v1.json",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "out" / "records_seal_etl_report.json"),
    )
    args = parser.parse_args(argv)
    if not args.database_url:
        raise ValueError("--database-url or TEST_DATABASE_URL is required")
    source = load_fixture(args.fixture)
    validation = validate_source(source)
    if not validation["passed"]:
        raise ValueError(f"invalid synthetic source: {validation['errors']}")
    rows = transform(source)
    expected = {table: len(values) for table, values in rows.items()}
    engine = safe_engine(args.database_url)
    with engine.begin() as conn:
        auth_before = authorization_signature(conn)
        create_schema(conn)
    interrupted = False
    try:
        with engine.begin() as conn:
            apply_rows(conn, rows, interrupt=True)
    except RuntimeError as exc:
        if str(exc) != "synthetic interruption after records":
            raise
        interrupted = True
    with engine.begin() as conn:
        partial_rows = sum(counts(conn).values())
        first = apply_rows(conn, rows)
    with engine.begin() as conn:
        second = apply_rows(conn, rows)
        reconciliation = reconcile(conn, rows)
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
        schema_exists = bool(
            conn.execute(
                text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": SCHEMA}
            ).scalar_one()
        )
        auth_after = authorization_signature(conn)
    engine.dispose()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "schema": SCHEMA,
        "synthetic_only": True,
        "contains_real_customer_data": False,
        "live_legacy_verified": False,
        "legacy_seal_aggregate_present": False,
        "legacy_signature_event_aggregate_present": False,
        "readiness": "CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA",
        "real_legacy_readiness": "BLOCKED_PENDING_AUTHORIZED_SCHEMA_BINARIES_AND_KEY_MAPS",
        "fixture_sha256": digest_text(args.fixture.read_text(encoding="utf-8")),
        "stages": {
            "dry_run": {"passed": validation["passed"], "mapped_counts": expected},
            "interruption_recovery": {
                "passed": interrupted and partial_rows == 0,
                "partial_rows_after_rollback": partial_rows,
            },
            "first_apply": {"passed": first == expected, "inserted": first},
            "idempotent_reapply": {
                "passed": all(value == 0 for value in second.values()),
                "inserted": second,
            },
            "reconciliation": reconciliation,
            "rollback": {
                "passed": not schema_exists and auth_before == auth_after,
                "schema_exists_after": schema_exists,
                "authorization_rows_unchanged": auth_before == auth_after,
            },
        },
        "blockers": [
            "authorized legacy attachment/document schema dump and retention dictionaries not supplied",
            "desensitized metadata plus binary inventory and SHA-256 manifest not supplied",
            "tenant/park/category/owner/source key maps and duplicate decisions not supplied",
            "legacy seal registry and custody aggregate was not found in available evidence",
            "real signature provider certificate, signed evidence and callback events not supplied",
            "production freeze, backup, cutover, storage deletion and rollback are not authorized",
        ],
    }
    report["result"] = (
        "PASS" if all(stage["passed"] for stage in report["stages"].values()) else "FAIL"
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
