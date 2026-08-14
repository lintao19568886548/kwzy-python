#!/usr/bin/env python3
"""Synthetic legacy repair-order ETL rehearsal on isolated loopback PostgreSQL.

This proves deterministic mapping, transactional restart, idempotent replay,
reconciliation, PII minimisation and rollback. It never reads a live legacy
database and therefore cannot be used as evidence of a production migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_work_order_fixture"
TABLES = ("work_orders", "work_order_events", "quarantine")
STATUS_MAP = {
    "待接单": "SUBMITTED",
    "处理中": "IN_PROGRESS",
    "待验收": "WAITING_ACCEPTANCE",
    "已完成": "COMPLETED",
    "已取消": "CANCELLED",
}
PRIORITY_MAP = {"紧急": "URGENT", "高": "HIGH", "普通": "MEDIUM", "低": "LOW"}
SOURCE_MAP = {
    "租户报修": "TENANT_PORTAL",
    "物业代报修": "PROPERTY_STAFF",
    "电话报修": "PHONE",
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def masked_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) < 7:
        return None
    return f"{digits[:3]}****{digits[-4:]}"


def parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def load_fixture(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("contains_real_customer_data") is not False:
        raise ValueError(
            "fixture must explicitly declare contains_real_customer_data=false"
        )
    if not isinstance(source.get("repair_order"), list):
        raise TypeError("fixture repair_order must be an array")
    return source


def validate_source(source: dict[str, Any]) -> dict[str, Any]:
    required = {
        "repair_order_id",
        "order_no",
        "park_ref",
        "tenant_ref",
        "repair_type",
        "description",
        "status",
        "priority",
        "create_time",
    }
    errors: list[str] = []
    identifiers: set[str] = set()
    order_numbers: set[str] = set()
    for row in source["repair_order"]:
        missing = sorted(required - row.keys())
        if missing:
            errors.append(
                f"{row.get('repair_order_id', '?')}:missing:{','.join(missing)}"
            )
            continue
        reference = str(row["repair_order_id"])
        order_no = str(row["order_no"])
        if reference in identifiers:
            errors.append(f"duplicate repair_order_id:{reference}")
        if order_no in order_numbers:
            errors.append(f"duplicate order_no:{order_no}")
        identifiers.add(reference)
        order_numbers.add(order_no)
        times = [
            parse_time(row.get("create_time")),
            parse_time(row.get("accept_time")),
            parse_time(row.get("finish_time")),
            parse_time(row.get("confirm_time")),
        ]
        ordered = [value for value in times if value is not None]
        if ordered != sorted(ordered):
            errors.append(f"timestamp order invalid:{reference}")
    return {"passed": not errors, "errors": errors, "source_rows": len(identifiers)}


def transform(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
    for source_row in source["repair_order"]:
        source_ref = str(source_row["repair_order_id"])
        status = STATUS_MAP.get(str(source_row["status"]))
        priority = PRIORITY_MAP.get(str(source_row["priority"]))
        if status is None or priority is None:
            reason = "UNKNOWN_STATUS" if status is None else "UNKNOWN_PRIORITY"
            rows["quarantine"].append(
                {
                    "source_ref": source_ref,
                    "field_name": "status" if status is None else "priority",
                    "value_fingerprint": digest(
                        str(
                            source_row["status"]
                            if status is None
                            else source_row["priority"]
                        )
                    ),
                    "reason_code": reason,
                }
            )
            continue
        created_at = parse_time(source_row["create_time"])
        accepted_at = parse_time(source_row.get("accept_time"))
        finished_at = parse_time(source_row.get("finish_time"))
        confirmed_at = parse_time(source_row.get("confirm_time"))
        evidence = list(source_row.get("images") or []) + list(
            source_row.get("process_images") or []
        )
        source_type = SOURCE_MAP.get(str(source_row.get("source") or ""), "OTHER")
        assignee_ref = source_row.get("assignee_ref")
        rows["work_orders"].append(
            {
                "source_ref": source_ref,
                "park_ref": str(source_row["park_ref"]),
                "party_ref": str(source_row["tenant_ref"]),
                "order_no": str(source_row["order_no"]),
                "source_type": source_type,
                "title": f"Legacy repair {source_ref}",
                "description_fingerprint": digest(str(source_row["description"])),
                "contact_name_fingerprint": digest(
                    str(source_row.get("tenant_name") or "")
                ),
                "contact_phone_masked": masked_phone(source_row.get("tenant_phone")),
                "category": str(source_row["repair_type"]).upper()[:64],
                "priority": priority,
                "status": status,
                "assignee_ref": str(assignee_ref) if assignee_ref else None,
                "created_at": created_at,
                "first_responded_at": accepted_at,
                "submitted_for_acceptance_at": finished_at
                if status == "WAITING_ACCEPTANCE"
                else None,
                "completed_at": confirmed_at if status == "COMPLETED" else None,
                "evidence_ref_count": len(evidence),
                "migration_confidence": "SYNTHETIC_MAPPING_ONLY",
            }
        )
        events: list[tuple[str, datetime]] = [("LEGACY_REQUEST_IMPORTED", created_at)]
        if accepted_at:
            events.append(("LEGACY_ACCEPTED_RECONSTRUCTED", accepted_at))
        if finished_at:
            events.append(("LEGACY_FINISHED_RECONSTRUCTED", finished_at))
        if confirmed_at:
            events.append(("LEGACY_CONFIRMED_RECONSTRUCTED", confirmed_at))
        for event_type, occurred_at in events:
            rows["work_order_events"].append(
                {
                    "source_event_ref": f"{source_ref}:{event_type}",
                    "source_ref": source_ref,
                    "event_type": event_type,
                    "actor_type": "SYSTEM",
                    "occurred_at": occurred_at,
                    "evidence_truth": "LEGACY_RECONSTRUCTED_NOT_PROVIDER_VERIFIED",
                }
            )
    return rows


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.work_orders (
  source_ref text PRIMARY KEY,
  park_ref text NOT NULL,
  party_ref text NOT NULL,
  order_no text NOT NULL UNIQUE,
  source_type text NOT NULL CHECK (source_type IN ('TENANT_PORTAL','PROPERTY_STAFF','PHONE','OTHER')),
  title text NOT NULL,
  description_fingerprint char(64) NOT NULL,
  contact_name_fingerprint char(64) NOT NULL,
  contact_phone_masked text,
  category text NOT NULL,
  priority text NOT NULL CHECK (priority IN ('LOW','MEDIUM','HIGH','URGENT')),
  status text NOT NULL CHECK (status IN ('SUBMITTED','IN_PROGRESS','WAITING_ACCEPTANCE','COMPLETED','CANCELLED')),
  assignee_ref text,
  created_at timestamp NOT NULL,
  first_responded_at timestamp,
  submitted_for_acceptance_at timestamp,
  completed_at timestamp,
  evidence_ref_count integer NOT NULL CHECK (evidence_ref_count >= 0),
  migration_confidence text NOT NULL
);
CREATE TABLE {SCHEMA}.work_order_events (
  source_event_ref text PRIMARY KEY,
  source_ref text NOT NULL REFERENCES {SCHEMA}.work_orders(source_ref),
  event_type text NOT NULL,
  actor_type text NOT NULL CHECK (actor_type = 'SYSTEM'),
  occurred_at timestamp NOT NULL,
  evidence_truth text NOT NULL
);
CREATE TABLE {SCHEMA}.quarantine (
  source_ref text NOT NULL,
  field_name text NOT NULL,
  value_fingerprint char(64) NOT NULL,
  reason_code text NOT NULL,
  PRIMARY KEY (source_ref, field_name)
);
"""

FIELDS = {
    "work_orders": (
        "source_ref",
        "park_ref",
        "party_ref",
        "order_no",
        "source_type",
        "title",
        "description_fingerprint",
        "contact_name_fingerprint",
        "contact_phone_masked",
        "category",
        "priority",
        "status",
        "assignee_ref",
        "created_at",
        "first_responded_at",
        "submitted_for_acceptance_at",
        "completed_at",
        "evidence_ref_count",
        "migration_confidence",
    ),
    "work_order_events": (
        "source_event_ref",
        "source_ref",
        "event_type",
        "actor_type",
        "occurred_at",
        "evidence_truth",
    ),
    "quarantine": ("source_ref", "field_name", "value_fingerprint", "reason_code"),
}


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("work-order ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("work-order ETL drill is restricted to loopback PostgreSQL")
    identity = (parsed.database or "").lower()
    if "prod" in identity or not any(
        word in identity for word in ("test", "local", "dev", "audit")
    ):
        raise ValueError(
            "work-order ETL drill refuses a production-like database identity"
        )
    return create_engine(database_url, pool_pre_ping=True)


def create_schema(conn) -> None:
    conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    for statement in DDL.split(";"):
        if statement.strip():
            conn.execute(text(statement))


def counts(conn) -> dict[str, int]:
    return {
        table: int(
            conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()
        )
        for table in TABLES
    }


def apply_rows(conn, rows: dict[str, list[dict[str, Any]]], *, interrupt: bool = False):
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
        if interrupt and table == "work_orders":
            raise RuntimeError("synthetic interruption after work orders")
    return inserted


def authorization_signature(conn) -> dict[str, int]:
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def reconcile(conn, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    expected = {table: len(values) for table, values in rows.items()}
    target = counts(conn)
    target_statuses = dict(
        conn.execute(
            text(f"SELECT status,count(*) FROM {SCHEMA}.work_orders GROUP BY status")
        ).all()
    )
    expected_statuses = dict(Counter(row["status"] for row in rows["work_orders"]))
    orphans = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.work_order_events e "
                f"LEFT JOIN {SCHEMA}.work_orders w USING(source_ref) WHERE w.source_ref IS NULL"
            )
        ).scalar_one()
    )
    bad_phone_masks = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.work_orders "
                "WHERE contact_phone_masked IS NOT NULL "
                "AND contact_phone_masked !~ '^[0-9]{3}\\*{4}[0-9]{4}$'"
            )
        ).scalar_one()
    )
    raw_pii_hits = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.work_orders "
                "WHERE title LIKE '%合成企业%' OR title ~ '[0-9]{11}'"
            )
        ).scalar_one()
    )
    timestamp_violations = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.work_orders WHERE "
                "(first_responded_at IS NOT NULL AND first_responded_at < created_at) OR "
                "(submitted_for_acceptance_at IS NOT NULL AND "
                " submitted_for_acceptance_at < coalesce(first_responded_at, created_at)) OR "
                "(completed_at IS NOT NULL AND completed_at < "
                " coalesce(submitted_for_acceptance_at, first_responded_at, created_at))"
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
        expected == target
        and expected_statuses == target_statuses
        and orphans == 0
        and bad_phone_masks == 0
        and raw_pii_hits == 0
        and timestamp_violations == 0
        and quarantine_reasons == {"UNKNOWN_STATUS": 1}
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "expected_status_counts": expected_statuses,
        "target_status_counts": target_statuses,
        "orphan_events": orphans,
        "bad_phone_masks": bad_phone_masks,
        "raw_pii_hits": raw_pii_hits,
        "timestamp_violations": timestamp_violations,
        "quarantine_reasons": quarantine_reasons,
        "fabricated_quotes": 0,
        "fabricated_ratings": 0,
        "fabricated_provider_deliveries": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL"),
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "work_order_v1.json",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "out" / "work_order_etl_report.json"),
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
        if str(exc) != "synthetic interruption after work orders":
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
        "readiness": "CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA",
        "real_legacy_readiness": "BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE",
        "fixture_sha256": digest(args.fixture.read_text(encoding="utf-8")),
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
            "authorized legacy repair_order schema dump and status dictionary not supplied",
            "desensitized production-like repair-order snapshot not supplied",
            "park/party/user/unit key maps not supplied",
            "legacy attachment object inventory and checksums not supplied",
            "production freeze, backup, cutover and rollback are not authorized",
        ],
    }
    report["result"] = (
        "PASS"
        if all(stage["passed"] for stage in report["stages"].values())
        else "FAIL"
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
