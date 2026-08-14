#!/usr/bin/env python3
"""Synthetic legacy receivables ETL drill in an isolated loopback PostgreSQL schema.

The drill proves repeatability, transaction recovery, amount reconciliation and
rollback mechanics. It never connects to a legacy database and does not claim a
production migration or external delivery confirmation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_receivables_fixture"
CENT = Decimal("0.01")
FIELDS: dict[str, tuple[str, ...]] = {
    "bills": (
        "source_bill_ref",
        "park_ref",
        "party_ref",
        "bill_no",
        "period_start",
        "period_end",
        "due_date",
        "status",
        "total_amount",
        "paid_amount",
    ),
    "bill_lines": (
        "source_bill_ref",
        "source_line_ref",
        "fee_code",
        "amount",
    ),
    "receipts": (
        "source_receipt_ref",
        "park_ref",
        "party_ref",
        "amount",
        "received_at",
        "source_provider",
        "source_ref",
        "payer_account_masked",
        "status",
    ),
    "payments": (
        "source_payment_ref",
        "source_receipt_ref",
        "park_ref",
        "party_ref",
        "amount",
        "paid_at",
        "status",
    ),
    "allocations": (
        "source_allocation_ref",
        "source_payment_ref",
        "source_bill_ref",
        "amount",
    ),
    "collection_cases": (
        "source_case_ref",
        "source_bill_ref",
        "level",
        "status",
        "amount_snapshot",
    ),
    "collection_records": (
        "source_record_ref",
        "source_case_ref",
        "action_type",
        "delivery_status",
        "occurred_at",
        "content_fingerprint",
    ),
    "quarantine": (
        "source_ref",
        "field_name",
        "value_fingerprint",
        "reason_code",
    ),
}


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fixture() -> dict[str, list[dict[str, Any]]]:
    """Mixed legacy facts including partial pay, unmatched receipt and SMS history."""
    return {
        "amount_bill": [
            {
                "id": "ab-001",
                "park_ref": "park-a",
                "party_ref": "party-acme",
                "bill_no": "OLD-202601-001",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "due_date": "2026-02-05",
                "total": "1000.00",
                "receipt_amount": "0.00",
                "fees": {"rent": "800.00", "management": "200.00"},
            },
            {
                "id": "ab-002",
                "park_ref": "park-a",
                "party_ref": "party-beta",
                "bill_no": "OLD-202601-002",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "due_date": "2026-02-05",
                "total": "500.00",
                "receipt_amount": "200.00",
                "fees": {"rent": "500.00"},
            },
        ],
        "receipt": [
            {
                "id": "rc-001",
                "park_ref": "park-a",
                "party_ref": "party-beta",
                "bill_ref": "ab-002",
                "amount": "200.00",
                "received_at": "2026-02-10T09:30:00",
                "confirmed": True,
                "bank_ref": "bank-20260210-001",
                "payer_account": "6222020000001234",
            },
            {
                "id": "rc-002",
                "park_ref": "park-a",
                "party_ref": None,
                "bill_ref": None,
                "amount": "88.00",
                "received_at": "2026-02-11T10:00:00",
                "confirmed": False,
                "bank_ref": "bank-20260211-unknown",
                "payer_account": "6217000000005678",
            },
        ],
        "dunning_sms": [
            {
                "id": "sms-001",
                "bill_ref": "ab-001",
                "occurred_at": "2026-03-01T08:00:00",
                "content": "synthetic overdue notice",
                "provider_delivery_evidence": None,
            }
        ],
        "finance": [
            {
                "id": "fin-ambiguous-001",
                "category": "manual-adjustment",
                "amount": "23.45",
                "source_link": None,
            }
        ],
    }


def validate_source(source: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    bills = {row["id"]: row for row in source["amount_bill"]}
    for row in bills.values():
        line_total = sum((_money(value) for value in row["fees"].values()), Decimal(0))
        if _money(row["total"]) != _money(line_total):
            errors.append(f"bill line mismatch:{row['id']}")
        if _money(row["receipt_amount"]) > _money(row["total"]):
            errors.append(f"bill over-receipt:{row['id']}")
        if date.fromisoformat(row["period_start"]) > date.fromisoformat(row["period_end"]):
            errors.append(f"bill period invalid:{row['id']}")
    for receipt in source["receipt"]:
        if receipt["bill_ref"] is not None and receipt["bill_ref"] not in bills:
            errors.append(f"orphan receipt:{receipt['id']}")
    return {"passed": not errors, "errors": errors}


def transform(source: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    rows = {name: [] for name in FIELDS}
    allocated_by_bill: dict[str, Decimal] = {}
    for receipt in source["receipt"]:
        masked = f"****{receipt['payer_account'][-4:]}"
        state = "CONFIRMED" if receipt["confirmed"] else "PENDING"
        rows["receipts"].append(
            {
                "source_receipt_ref": receipt["id"],
                "park_ref": receipt["park_ref"],
                "party_ref": receipt["party_ref"],
                "amount": _money(receipt["amount"]),
                "received_at": datetime.fromisoformat(receipt["received_at"]),
                "source_provider": "LEGACY_BANK_EXPORT",
                "source_ref": receipt["bank_ref"],
                "payer_account_masked": masked,
                "status": state,
            }
        )
        if not receipt["confirmed"]:
            continue
        payment_ref = f"payment:{receipt['id']}"
        rows["payments"].append(
            {
                "source_payment_ref": payment_ref,
                "source_receipt_ref": receipt["id"],
                "park_ref": receipt["park_ref"],
                "party_ref": receipt["party_ref"],
                "amount": _money(receipt["amount"]),
                "paid_at": datetime.fromisoformat(receipt["received_at"]),
                "status": "CONFIRMED",
            }
        )
        if receipt["bill_ref"]:
            allocation_ref = f"allocation:{receipt['id']}:{receipt['bill_ref']}"
            rows["allocations"].append(
                {
                    "source_allocation_ref": allocation_ref,
                    "source_payment_ref": payment_ref,
                    "source_bill_ref": receipt["bill_ref"],
                    "amount": _money(receipt["amount"]),
                }
            )
            allocated_by_bill[receipt["bill_ref"]] = allocated_by_bill.get(
                receipt["bill_ref"], Decimal(0)
            ) + _money(receipt["amount"])

    fee_map = {"rent": "RENT", "management": "MANAGEMENT", "water": "WATER", "ele": "ELECTRIC"}
    for bill in source["amount_bill"]:
        paid = _money(allocated_by_bill.get(bill["id"], Decimal(0)))
        total = _money(bill["total"])
        status = "PAID" if paid == total else "PARTIALLY_PAID" if paid else "ISSUED"
        rows["bills"].append(
            {
                "source_bill_ref": bill["id"],
                "park_ref": bill["park_ref"],
                "party_ref": bill["party_ref"],
                "bill_no": bill["bill_no"],
                "period_start": date.fromisoformat(bill["period_start"]),
                "period_end": date.fromisoformat(bill["period_end"]),
                "due_date": date.fromisoformat(bill["due_date"]),
                "status": status,
                "total_amount": total,
                "paid_amount": paid,
            }
        )
        for index, (name, value) in enumerate(sorted(bill["fees"].items()), start=1):
            if name not in fee_map:
                rows["quarantine"].append(
                    {
                        "source_ref": bill["id"],
                        "field_name": name,
                        "value_fingerprint": _hash(str(value)),
                        "reason_code": "UNKNOWN_FEE_CODE",
                    }
                )
                continue
            rows["bill_lines"].append(
                {
                    "source_bill_ref": bill["id"],
                    "source_line_ref": f"{bill['id']}:{index}",
                    "fee_code": fee_map[name],
                    "amount": _money(value),
                }
            )

    bill_by_ref = {row["source_bill_ref"]: row for row in rows["bills"]}
    for item in source["dunning_sms"]:
        bill = bill_by_ref[item["bill_ref"]]
        case_ref = f"case:{item['bill_ref']}"
        overdue_days = (date(2026, 3, 1) - bill["due_date"]).days
        level = (
            "L4"
            if overdue_days >= 61
            else "L3"
            if overdue_days >= 31
            else "L2"
            if overdue_days >= 8
            else "L1"
        )
        rows["collection_cases"].append(
            {
                "source_case_ref": case_ref,
                "source_bill_ref": item["bill_ref"],
                "level": level,
                "status": "OPEN",
                "amount_snapshot": _money(bill["total_amount"] - bill["paid_amount"]),
            }
        )
        rows["collection_records"].append(
            {
                "source_record_ref": item["id"],
                "source_case_ref": case_ref,
                "action_type": "SMS",
                "delivery_status": "LEGACY_UNVERIFIED",
                "occurred_at": datetime.fromisoformat(item["occurred_at"]),
                "content_fingerprint": _hash(item["content"]),
            }
        )
    for item in source["finance"]:
        rows["quarantine"].append(
            {
                "source_ref": item["id"],
                "field_name": "finance.amount",
                "value_fingerprint": _hash(str(item["amount"])),
                "reason_code": "FINANCE_SOURCE_LINK_MISSING",
            }
        )
    return rows


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.bills (
  source_bill_ref text PRIMARY KEY, park_ref text NOT NULL, party_ref text NOT NULL,
  bill_no text NOT NULL UNIQUE, period_start date NOT NULL, period_end date NOT NULL,
  due_date date NOT NULL, status text NOT NULL, total_amount numeric(14,2) NOT NULL CHECK(total_amount >= 0),
  paid_amount numeric(14,2) NOT NULL CHECK(paid_amount >= 0 AND paid_amount <= total_amount)
);
CREATE TABLE {SCHEMA}.bill_lines (
  source_bill_ref text NOT NULL REFERENCES {SCHEMA}.bills, source_line_ref text PRIMARY KEY,
  fee_code text NOT NULL, amount numeric(14,2) NOT NULL CHECK(amount >= 0)
);
CREATE TABLE {SCHEMA}.receipts (
  source_receipt_ref text PRIMARY KEY, park_ref text NOT NULL, party_ref text,
  amount numeric(14,2) NOT NULL CHECK(amount > 0), received_at timestamp NOT NULL,
  source_provider text NOT NULL, source_ref text NOT NULL UNIQUE,
  payer_account_masked text, status text NOT NULL
);
CREATE TABLE {SCHEMA}.payments (
  source_payment_ref text PRIMARY KEY, source_receipt_ref text NOT NULL UNIQUE REFERENCES {SCHEMA}.receipts,
  park_ref text NOT NULL, party_ref text NOT NULL, amount numeric(14,2) NOT NULL CHECK(amount > 0),
  paid_at timestamp NOT NULL, status text NOT NULL
);
CREATE TABLE {SCHEMA}.allocations (
  source_allocation_ref text PRIMARY KEY, source_payment_ref text NOT NULL REFERENCES {SCHEMA}.payments,
  source_bill_ref text NOT NULL REFERENCES {SCHEMA}.bills, amount numeric(14,2) NOT NULL CHECK(amount > 0)
);
CREATE TABLE {SCHEMA}.collection_cases (
  source_case_ref text PRIMARY KEY, source_bill_ref text NOT NULL UNIQUE REFERENCES {SCHEMA}.bills,
  level text NOT NULL CHECK(level IN ('L1','L2','L3','L4')), status text NOT NULL,
  amount_snapshot numeric(14,2) NOT NULL CHECK(amount_snapshot > 0)
);
CREATE TABLE {SCHEMA}.collection_records (
  source_record_ref text PRIMARY KEY, source_case_ref text NOT NULL REFERENCES {SCHEMA}.collection_cases,
  action_type text NOT NULL, delivery_status text NOT NULL, occurred_at timestamp NOT NULL,
  content_fingerprint char(64) NOT NULL
);
CREATE TABLE {SCHEMA}.quarantine (
  source_ref text NOT NULL, field_name text NOT NULL, value_fingerprint char(64) NOT NULL,
  reason_code text NOT NULL, PRIMARY KEY(source_ref, field_name)
);
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("receivables ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("receivables ETL drill is restricted to loopback PostgreSQL")
    database = (parsed.database or "").lower()
    if "prod" in database or not any(token in database for token in ("test", "local", "dev")):
        raise ValueError("receivables ETL drill refuses a production-like database identity")
    return create_engine(database_url, pool_pre_ping=True)


def _create_schema(conn) -> None:
    conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    for statement in DDL.split(";"):
        if statement.strip():
            conn.execute(text(statement))


def _counts(conn) -> dict[str, int]:
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one())
        for table in FIELDS
    }


def _apply(
    conn, rows: dict[str, list[dict[str, Any]]], *, interrupt: bool = False
) -> dict[str, int]:
    inserted = {table: 0 for table in FIELDS}
    for table, fields in FIELDS.items():
        columns = ",".join(fields)
        values = ",".join(f":{field}" for field in fields)
        for row in rows[table]:
            result = conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.{table} ({columns}) VALUES ({values}) ON CONFLICT DO NOTHING"
                ),
                {field: row[field] for field in fields},
            )
            inserted[table] += int(result.rowcount or 0)
        if interrupt and table == "bill_lines":
            raise RuntimeError("synthetic interruption after bill lines")
    return inserted


def _reconcile(conn, source: dict[str, list[dict[str, Any]]], rows) -> dict[str, Any]:
    expected = {table: len(values) for table, values in rows.items()}
    target = _counts(conn)
    source_bill_total = _money(
        sum((_money(row["total"]) for row in source["amount_bill"]), Decimal(0))
    )
    target_bill_total = _money(
        conn.execute(text(f"SELECT coalesce(sum(total_amount),0) FROM {SCHEMA}.bills")).scalar_one()
    )
    line_mismatches = int(
        conn.execute(
            text(f"""
      SELECT count(*) FROM {SCHEMA}.bills b
      WHERE b.total_amount <> (SELECT coalesce(sum(l.amount),0) FROM {SCHEMA}.bill_lines l WHERE l.source_bill_ref=b.source_bill_ref)
    """)
        ).scalar_one()
    )
    payment_overallocations = int(
        conn.execute(
            text(f"""
      SELECT count(*) FROM {SCHEMA}.payments p
      WHERE p.amount < (SELECT coalesce(sum(a.amount),0) FROM {SCHEMA}.allocations a WHERE a.source_payment_ref=p.source_payment_ref)
    """)
        ).scalar_one()
    )
    bill_allocation_mismatches = int(
        conn.execute(
            text(f"""
      SELECT count(*) FROM {SCHEMA}.bills b
      WHERE b.paid_amount <> (SELECT coalesce(sum(a.amount),0) FROM {SCHEMA}.allocations a WHERE a.source_bill_ref=b.source_bill_ref)
    """)
        ).scalar_one()
    )
    orphans = sum(
        int(conn.execute(text(query)).scalar_one())
        for query in (
            f"SELECT count(*) FROM {SCHEMA}.bill_lines l LEFT JOIN {SCHEMA}.bills b USING(source_bill_ref) WHERE b.source_bill_ref IS NULL",
            f"SELECT count(*) FROM {SCHEMA}.allocations a LEFT JOIN {SCHEMA}.payments p USING(source_payment_ref) WHERE p.source_payment_ref IS NULL",
            f"SELECT count(*) FROM {SCHEMA}.collection_records r LEFT JOIN {SCHEMA}.collection_cases c USING(source_case_ref) WHERE c.source_case_ref IS NULL",
        )
    )
    leaked_accounts = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.receipts WHERE payer_account_masked IS NOT NULL AND payer_account_masked !~ '^\\*{{4}}[0-9]{{4}}$'"
            )
        ).scalar_one()
    )
    false_deliveries = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.collection_records WHERE delivery_status IN ('SENT','DELIVERED')"
            )
        ).scalar_one()
    )
    quarantine_reasons = dict(
        conn.execute(
            text(f"SELECT reason_code,count(*) FROM {SCHEMA}.quarantine GROUP BY reason_code")
        ).all()
    )
    passed = (
        expected == target
        and source_bill_total == target_bill_total
        and line_mismatches == 0
        and payment_overallocations == 0
        and bill_allocation_mismatches == 0
        and orphans == 0
        and leaked_accounts == 0
        and false_deliveries == 0
        and quarantine_reasons == {"FINANCE_SOURCE_LINK_MISSING": 1}
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "source_bill_total": str(source_bill_total),
        "target_bill_total": str(target_bill_total),
        "line_mismatches": line_mismatches,
        "payment_overallocations": payment_overallocations,
        "bill_allocation_mismatches": bill_allocation_mismatches,
        "orphan_rows": orphans,
        "unmasked_account_rows": leaked_accounts,
        "false_external_deliveries": false_deliveries,
        "quarantine_reasons": quarantine_reasons,
    }


def _authorization_signature(conn) -> dict[str, int]:
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "out" / "receivables_etl_report.json")
    )
    args = parser.parse_args(argv)
    if not args.database_url:
        raise ValueError("--database-url or TEST_DATABASE_URL is required")
    source = fixture()
    validation = validate_source(source)
    if not validation["passed"]:
        raise ValueError(f"invalid synthetic source: {validation['errors']}")
    rows = transform(source)
    expected = {table: len(values) for table, values in rows.items()}
    engine = safe_engine(args.database_url)
    with engine.begin() as conn:
        authorization_before = _authorization_signature(conn)
        _create_schema(conn)
    interrupted = False
    try:
        with engine.begin() as conn:
            _apply(conn, rows, interrupt=True)
    except RuntimeError as exc:
        if str(exc) != "synthetic interruption after bill lines":
            raise
        interrupted = True
    with engine.begin() as conn:
        partial_rows = sum(_counts(conn).values())
        first = _apply(conn, rows)
    with engine.begin() as conn:
        second = _apply(conn, rows)
        reconciliation = _reconcile(conn, source, rows)
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
        schema_exists = bool(
            conn.execute(
                text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": SCHEMA}
            ).scalar_one()
        )
        authorization_after = _authorization_signature(conn)
    engine.dispose()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "schema": SCHEMA,
        "synthetic_only": True,
        "contains_real_customer_data": False,
        "live_legacy_verified": False,
        "readiness": "CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA",
        "real_legacy_readiness": "BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE",
        "fixture_sha256": _hash(json.dumps(source, ensure_ascii=False, sort_keys=True)),
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
                "passed": not schema_exists and authorization_before == authorization_after,
                "schema_exists_after": schema_exists,
                "authorization_rows_unchanged": authorization_before == authorization_after,
            },
        },
        "blockers": [
            "authorized legacy amount_bill/receipt/finance schema dump not supplied",
            "desensitized production-like finance snapshot and key maps not supplied",
            "bank/payment provider settlement files and contracts not supplied",
            "production freeze, backup, cutover and rollback are not authorized",
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
