#!/usr/bin/env python3
"""Synthetic legacy-contract ETL drill in one disposable loopback PG schema.

This is acceptance evidence for mapping mechanics only.  It never reads a
legacy database, stores raw quarantined PII, or authorizes a production cutover.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_contract_lifecycle_fixture"
CENT = Decimal("0.01")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fixture() -> dict[str, list[dict[str, Any]]]:
    """Traditional mixed rows, attachment/reminder facts and ambiguous data."""
    return {
        "rental_tenant": [
            {
                "source_contract_ref": "rt-001",
                "source_party_ref": "party-acme",
                "company_name": "Synthetic Acme Technology",
                "contact_phone": "13800000001",
                "park_ref": "park-a",
                "status": "LEASED",
                "contract_type": "NEW",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "deposit": "12000.00",
                "units": [
                    {"source_unit_ref": "A-101", "occupied_area": "80.00"},
                    {"source_unit_ref": "A-102", "occupied_area": "20.00"},
                ],
                "terms": [
                    {"source_term_ref": "term-001", "kind": "RENT", "amount": "5000.00"},
                    {"source_term_ref": "term-002", "kind": "PROPERTY", "amount": "800.00"},
                ],
            },
            {
                "source_contract_ref": "rt-002",
                "source_party_ref": "party-acme",
                "company_name": "Synthetic Acme Technology",
                "contact_phone": "13800000001",
                "park_ref": "park-b",
                "status": "EXPIRED",
                "contract_type": "RENEWAL_HISTORY",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "deposit": "6000.00",
                "units": [{"source_unit_ref": "B-201", "occupied_area": "55.50"}],
                "terms": [
                    {"source_term_ref": "term-003", "kind": "RENT", "amount": "3000.00"}
                ],
            },
            {
                "source_contract_ref": "rt-003",
                "source_party_ref": "party-beta",
                "company_name": "Synthetic Beta Services",
                "contact_phone": "13800000002",
                "park_ref": "park-a",
                "status": "LEASED",
                "contract_type": "NEW",
                "start_date": "2026-02-01",
                "end_date": "2027-01-31",
                "deposit": "9000.00",
                "units": [{"source_unit_ref": "A-301", "occupied_area": "66.00"}],
                "terms": [
                    {
                        "source_term_ref": "term-004",
                        "kind": "OTHER",
                        "raw_text": "Synthetic ambiguous increase and tax wording",
                    }
                ],
            },
        ],
        "tenant_images": [
            {"source_ref": "img-001", "contract_ref": "rt-001", "kind": "MAIN_CONTRACT"},
            {"source_ref": "img-002", "contract_ref": "rt-003", "kind": "SUPPLEMENT"},
        ],
        "contract_reminders": [
            {"source_ref": "rem-001", "contract_ref": "rt-001", "due_date": "2026-12-01"},
            {"source_ref": "rem-002", "contract_ref": "rt-003", "due_date": "2026-12-31"},
        ],
    }


def validate_source(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    rows = data["rental_tenant"]
    contract_refs = [row["source_contract_ref"] for row in rows]
    if len(contract_refs) != len(set(contract_refs)):
        errors.append("duplicate contract source reference")
    known = set(contract_refs)
    for table in ("tenant_images", "contract_reminders"):
        refs = [row["source_ref"] for row in data[table]]
        if len(refs) != len(set(refs)):
            errors.append(f"duplicate {table} source reference")
        if any(row["contract_ref"] not in known for row in data[table]):
            errors.append(f"orphan {table} contract reference")
    for row in rows:
        if date.fromisoformat(row["start_date"]) > date.fromisoformat(row["end_date"]):
            errors.append("contract date range invalid")
        if Decimal(row["deposit"]) < 0:
            errors.append("negative deposit")
        if not row["units"] or any(Decimal(unit["occupied_area"]) <= 0 for unit in row["units"]):
            errors.append("invalid occupied area")
    return {"passed": not errors, "errors": sorted(set(errors))}


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.parties (
  source_party_ref text PRIMARY KEY, display_name text NOT NULL, identity_fingerprint char(64) NOT NULL
);
CREATE TABLE {SCHEMA}.contracts (
  source_contract_ref text PRIMARY KEY, source_party_ref text NOT NULL REFERENCES {SCHEMA}.parties,
  park_ref text NOT NULL, status text NOT NULL, contract_type text NOT NULL,
  start_date date NOT NULL, end_date date NOT NULL, deposit numeric(18,2) NOT NULL
);
CREATE TABLE {SCHEMA}.versions (
  source_contract_ref text NOT NULL REFERENCES {SCHEMA}.contracts, version_no integer NOT NULL,
  snapshot_json jsonb NOT NULL, checksum char(64) NOT NULL,
  PRIMARY KEY (source_contract_ref, version_no), UNIQUE (checksum)
);
CREATE TABLE {SCHEMA}.contract_units (
  source_contract_ref text NOT NULL REFERENCES {SCHEMA}.contracts, source_unit_ref text NOT NULL,
  occupied_area numeric(18,2) NOT NULL, PRIMARY KEY (source_contract_ref, source_unit_ref)
);
CREATE TABLE {SCHEMA}.charges (
  source_contract_ref text NOT NULL REFERENCES {SCHEMA}.contracts, source_term_ref text NOT NULL,
  charge_code text NOT NULL, charge_type text NOT NULL, amount numeric(18,2) NOT NULL,
  PRIMARY KEY (source_contract_ref, source_term_ref), UNIQUE (source_contract_ref, charge_code)
);
CREATE TABLE {SCHEMA}.schedules (
  source_contract_ref text NOT NULL REFERENCES {SCHEMA}.contracts, deterministic_key char(64) NOT NULL,
  charge_code text NOT NULL, period_start date NOT NULL, gross_amount numeric(18,2) NOT NULL,
  PRIMARY KEY (source_contract_ref, deterministic_key)
);
CREATE TABLE {SCHEMA}.documents (
  source_ref text PRIMARY KEY, source_contract_ref text NOT NULL REFERENCES {SCHEMA}.contracts,
  document_type text NOT NULL, checksum char(64) NOT NULL
);
CREATE TABLE {SCHEMA}.reminders (
  source_ref text PRIMARY KEY, source_contract_ref text NOT NULL REFERENCES {SCHEMA}.contracts,
  due_date date NOT NULL
);
CREATE TABLE {SCHEMA}.quarantine (
  source_ref text NOT NULL, field_name text NOT NULL, value_fingerprint char(64) NOT NULL,
  reason_code text NOT NULL, PRIMARY KEY (source_ref, field_name)
);
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("contract ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("contract ETL drill is restricted to loopback PostgreSQL")
    database = (parsed.database or "").lower()
    if not database or "prod" in database or not any(token in database for token in ("test", "local", "dev")):
        raise ValueError("contract ETL drill refuses a production-like database identity")
    return create_engine(database_url, pool_pre_ping=True)


def transform(data: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {name: [] for name in (
        "parties", "contracts", "versions", "contract_units", "charges", "schedules",
        "documents", "reminders", "quarantine",
    )}
    seen_parties: set[str] = set()
    status_map = {"LEASED": "ACTIVE", "EXPIRED": "TERMINATED"}
    for source in data["rental_tenant"]:
        party_ref = source["source_party_ref"]
        if party_ref not in seen_parties:
            seen_parties.add(party_ref)
            out["parties"].append({
                "source_party_ref": party_ref,
                "display_name": source["company_name"],
                "identity_fingerprint": _hash(f"{source['company_name']}|{source['contact_phone']}"),
            })
        contract_ref = source["source_contract_ref"]
        out["contracts"].append({
            "source_contract_ref": contract_ref,
            "source_party_ref": party_ref,
            "park_ref": source["park_ref"],
            "status": status_map[source["status"]],
            "contract_type": source["contract_type"],
            "start_date": source["start_date"],
            "end_date": source["end_date"],
            "deposit": Decimal(source["deposit"]).quantize(CENT),
        })
        trusted_charges: list[dict[str, Any]] = []
        for index, term in enumerate(source["terms"], start=1):
            if term["kind"] not in {"RENT", "PROPERTY"}:
                out["quarantine"].append({
                    "source_ref": term["source_term_ref"],
                    "field_name": "raw_text",
                    "value_fingerprint": _hash(term.get("raw_text", "")),
                    "reason_code": "BLOCKED_PENDING_SCHEMA_OR_SAMPLE",
                })
                continue
            charge = {
                "source_contract_ref": contract_ref,
                "source_term_ref": term["source_term_ref"],
                "charge_code": f"{term['kind']}_{index}",
                "charge_type": term["kind"],
                "amount": Decimal(term["amount"]).quantize(CENT),
            }
            trusted_charges.append(charge)
            out["charges"].append(charge)
            key = _hash(f"{contract_ref}|1|{charge['charge_code']}|{source['start_date']}")
            out["schedules"].append({
                "source_contract_ref": contract_ref,
                "deterministic_key": key,
                "charge_code": charge["charge_code"],
                "period_start": source["start_date"],
                "gross_amount": charge["amount"],
            })
        for unit in source["units"]:
            out["contract_units"].append({
                "source_contract_ref": contract_ref,
                "source_unit_ref": unit["source_unit_ref"],
                "occupied_area": Decimal(unit["occupied_area"]).quantize(CENT),
            })
        snapshot = {
            "contract": {
                "source_contract_ref": contract_ref,
                "source_party_ref": party_ref,
                "park_ref": source["park_ref"],
                "status": status_map[source["status"]],
                "start_date": source["start_date"],
                "end_date": source["end_date"],
                "deposit": str(Decimal(source["deposit"]).quantize(CENT)),
            },
            "units": sorted(source["units"], key=lambda row: row["source_unit_ref"]),
            "charges": [
                {key: str(value) if isinstance(value, Decimal) else value for key, value in charge.items()}
                for charge in sorted(trusted_charges, key=lambda row: row["charge_code"])
            ],
            "review_required": any(term["kind"] == "OTHER" for term in source["terms"]),
        }
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        out["versions"].append({
            "source_contract_ref": contract_ref,
            "version_no": 1,
            "snapshot_json": canonical,
            "checksum": _hash(canonical),
        })
    for source in data["tenant_images"]:
        out["documents"].append({
            "source_ref": source["source_ref"],
            "source_contract_ref": source["contract_ref"],
            "document_type": source["kind"],
            "checksum": _hash(f"synthetic-document|{source['source_ref']}"),
        })
    for source in data["contract_reminders"]:
        out["reminders"].append({
            "source_ref": source["source_ref"],
            "source_contract_ref": source["contract_ref"],
            "due_date": source["due_date"],
        })
    return out


FIELDS = {
    "parties": ("source_party_ref", "display_name", "identity_fingerprint"),
    "contracts": ("source_contract_ref", "source_party_ref", "park_ref", "status", "contract_type", "start_date", "end_date", "deposit"),
    "versions": ("source_contract_ref", "version_no", "snapshot_json", "checksum"),
    "contract_units": ("source_contract_ref", "source_unit_ref", "occupied_area"),
    "charges": ("source_contract_ref", "source_term_ref", "charge_code", "charge_type", "amount"),
    "schedules": ("source_contract_ref", "deterministic_key", "charge_code", "period_start", "gross_amount"),
    "documents": ("source_ref", "source_contract_ref", "document_type", "checksum"),
    "reminders": ("source_ref", "source_contract_ref", "due_date"),
    "quarantine": ("source_ref", "field_name", "value_fingerprint", "reason_code"),
}


def apply_rows(conn, target: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    inserted: dict[str, int] = {}
    for table, fields in FIELDS.items():
        count = 0
        columns = ", ".join(fields)
        params = ", ".join(f":{field}" for field in fields)
        sql = text(f"INSERT INTO {SCHEMA}.{table} ({columns}) VALUES ({params}) ON CONFLICT DO NOTHING")
        for row in target[table]:
            count += conn.execute(sql, {field: row[field] for field in fields}).rowcount
        inserted[table] = count
    return inserted


def reconcile(conn, target: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    counts = {
        table: {
            "source": len(rows),
            "target": conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one(),
        }
        for table, rows in target.items()
    }
    source_status: dict[str, int] = {}
    source_type: dict[str, int] = {}
    source_park: dict[str, int] = {}
    for row in target["contracts"]:
        for bucket, key in ((source_status, "status"), (source_type, "contract_type"), (source_park, "park_ref")):
            bucket[row[key]] = bucket.get(row[key], 0) + 1
    def distribution(column: str) -> dict[str, int]:
        rows = conn.execute(text(f"SELECT {column}, count(*) FROM {SCHEMA}.contracts GROUP BY {column}"))
        return {str(key): int(value) for key, value in rows}
    target_area = conn.execute(text(f"SELECT coalesce(sum(occupied_area),0) FROM {SCHEMA}.contract_units")).scalar_one()
    target_deposit = conn.execute(text(f"SELECT coalesce(sum(deposit),0) FROM {SCHEMA}.contracts")).scalar_one()
    target_charge = conn.execute(text(f"SELECT coalesce(sum(amount),0) FROM {SCHEMA}.charges")).scalar_one()
    source_area = sum((row["occupied_area"] for row in target["contract_units"]), Decimal("0"))
    source_deposit = sum((row["deposit"] for row in target["contracts"]), Decimal("0"))
    source_charge = sum((row["amount"] for row in target["charges"]), Decimal("0"))
    duplicate_source_refs = conn.execute(text(
        f"SELECT count(*) FROM (SELECT source_contract_ref FROM {SCHEMA}.contracts GROUP BY source_contract_ref HAVING count(*)>1) x"
    )).scalar_one()
    orphan_queries = {
        "contracts_party": f"SELECT count(*) FROM {SCHEMA}.contracts c LEFT JOIN {SCHEMA}.parties p USING(source_party_ref) WHERE p.source_party_ref IS NULL",
        "versions_contract": f"SELECT count(*) FROM {SCHEMA}.versions v LEFT JOIN {SCHEMA}.contracts c USING(source_contract_ref) WHERE c.source_contract_ref IS NULL",
        "units_contract": f"SELECT count(*) FROM {SCHEMA}.contract_units u LEFT JOIN {SCHEMA}.contracts c USING(source_contract_ref) WHERE c.source_contract_ref IS NULL",
        "documents_contract": f"SELECT count(*) FROM {SCHEMA}.documents d LEFT JOIN {SCHEMA}.contracts c USING(source_contract_ref) WHERE c.source_contract_ref IS NULL",
        "reminders_contract": f"SELECT count(*) FROM {SCHEMA}.reminders r LEFT JOIN {SCHEMA}.contracts c USING(source_contract_ref) WHERE c.source_contract_ref IS NULL",
    }
    orphans = {name: conn.execute(text(sql)).scalar_one() for name, sql in orphan_queries.items()}
    raw_pii_columns = conn.execute(text(
        "SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema "
        "AND table_name='quarantine' AND column_name IN ('raw_value','raw_text','phone','contact_phone')"
    ), {"schema": SCHEMA}).scalar_one()
    version_checksums = conn.execute(text(
        f"SELECT source_contract_ref, checksum FROM {SCHEMA}.versions ORDER BY source_contract_ref"
    )).all()
    expected_checksums = sorted((row["source_contract_ref"], row["checksum"]) for row in target["versions"])
    distributions = {
        "status": {"source": source_status, "target": distribution("status")},
        "contract_type": {"source": source_type, "target": distribution("contract_type")},
        "park": {"source": source_park, "target": distribution("park_ref")},
    }
    totals = {
        "occupied_area": {"source": str(source_area), "target": str(target_area)},
        "deposit": {"source": str(source_deposit), "target": str(target_deposit)},
        "charges": {"source": str(source_charge), "target": str(target_charge)},
    }
    passed = (
        all(value["source"] == value["target"] for value in counts.values())
        and all(value["source"] == value["target"] for value in distributions.values())
        and all(Decimal(value["source"]) == Decimal(value["target"]) for value in totals.values())
        and duplicate_source_refs == 0 and not any(orphans.values()) and raw_pii_columns == 0
        and [(row[0], row[1]) for row in version_checksums] == expected_checksums
    )
    return {
        "passed": passed, "counts": counts, "distributions": distributions, "totals": totals,
        "duplicate_source_refs": duplicate_source_refs, "orphans": orphans,
        "quarantine": {"raw_pii_columns": raw_pii_columns, "fingerprints_only": raw_pii_columns == 0},
        "checksum_stable": [(row[0], row[1]) for row in version_checksums] == expected_checksums,
    }


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    report["readiness"] = (
        "CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA" if code == 0 else "SYNTHETIC_DRILL_FAILED"
    )
    report["real_legacy_readiness"] = "BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CONTRACT_ETL_REPORT={path}")
    print(f"CONTRACT_ETL_DRILL={report['result']}")
    print(f"CONTRACT_ETL_READINESS={report['readiness']}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("ETL_DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or ETL_DATABASE_URL is required")
    data = fixture()
    target = transform(data)
    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(), "schema": SCHEMA,
        "synthetic_only": True, "live_verified": False, "stages": {},
    }
    report["stages"]["dry_run"] = validate_source(data)
    if not report["stages"]["dry_run"]["passed"]:
        return finish(args.out, report, 1)
    engine = safe_engine(args.database_url)
    public_before = 0
    try:
        with engine.begin() as conn:
            public_before = conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar_one()
            conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            conn.execute(text(DDL))
        try:
            with engine.begin() as conn:
                apply_rows(conn, target)
                raise RuntimeError("synthetic interruption")
        except RuntimeError as exc:
            if str(exc) != "synthetic interruption":
                raise
        with engine.begin() as conn:
            empty_after_interrupt = all(
                conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one() == 0
                for table in FIELDS
            )
            report["stages"]["interruption_recovery"] = {"passed": empty_after_interrupt, "rolled_back": empty_after_interrupt}
            first = apply_rows(conn, target)
            report["stages"]["first_apply"] = {
                "passed": all(first[name] == len(target[name]) for name in target), "inserted": first,
            }
        with engine.begin() as conn:
            second = apply_rows(conn, target)
            report["stages"]["idempotent_reapply"] = {"passed": not any(second.values()), "inserted": second}
            report["stages"]["reconciliation"] = reconcile(conn, target)
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
            exists = conn.execute(text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": SCHEMA}).scalar_one()
            public_after = conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar_one()
            report["stages"]["rollback"] = {
                "passed": not exists and public_after == public_before,
                "schema_exists_after": exists, "public_tables_before": public_before, "public_tables_after": public_after,
            }
    finally:
        engine.dispose()
    passed = all(stage.get("passed") for stage in report["stages"].values())
    return finish(args.out, report, 0 if passed else 1)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CONTRACT_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}", file=sys.stderr)
        raise
