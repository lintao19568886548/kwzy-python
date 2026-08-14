#!/usr/bin/env python3
"""Synthetic workforce migration rehearsal restricted to loopback PostgreSQL.

The drill proves deterministic masking/fingerprinting, source-key mapping,
transaction recovery, idempotent replay, reconciliation and rollback. It does not
claim a live legacy migration, native approval evidence, payroll, performance or
qualification history when those authoritative aggregates are unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_workforce_fixture"
TABLES = (
    "employees",
    "shift_versions",
    "assignments",
    "punches",
    "summaries",
    "leaves",
    "performance_records",
    "qualifications",
    "quarantine",
)
MIGRATED_AT = datetime(2026, 8, 15, tzinfo=timezone.utc)
SYNTHETIC_PEPPER = "kwzy-workforce-etl-synthetic-only-v1"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fingerprint(value: str) -> str:
    return digest(f"{SYNTHETIC_PEPPER}:{value.strip()}")


def mask(value: str) -> str:
    stripped = value.strip()
    return f"***{stripped[-4:]}" if stripped else "***"


def load_fixture(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("contains_real_customer_data") is not False:
        raise ValueError("fixture must declare contains_real_customer_data=false")
    if source.get("legacy_performance_aggregate_present") is not False:
        raise ValueError("synthetic drill must not claim a performance aggregate")
    if source.get("legacy_qualification_aggregate_present") is not False:
        raise ValueError("synthetic drill must not claim a qualification aggregate")
    for name in (
        "parks",
        "employees",
        "attendance",
        "leaves",
        "performance_records",
        "qualification_records",
    ):
        if not isinstance(source.get(name), list):
            raise TypeError(f"fixture {name} must be an array")
    if source["performance_records"] or source["qualification_records"]:
        raise ValueError("unavailable workforce aggregates cannot be fabricated")
    return source


def validate_source(source: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    park_ids = [str(row.get("source_id", "")) for row in source["parks"]]
    employee_ids = [str(row.get("source_id", "")) for row in source["employees"]]
    if len(park_ids) != len(set(park_ids)):
        errors.append("duplicate park source_id")
    if len(employee_ids) != len(set(employee_ids)):
        errors.append("duplicate employee source_id")
    employee_required = {
        "source_id",
        "park_ref",
        "employee_no",
        "display_name",
        "mobile",
        "identity_number",
        "status",
        "start_date",
    }
    for row in source["employees"]:
        missing = employee_required - row.keys()
        if missing:
            errors.append(
                f"employee:{row.get('source_id', '?')}:missing:{','.join(sorted(missing))}"
            )
        if str(row.get("status", "")).upper() not in {"ACTIVE", "SUSPENDED", "LEFT"}:
            errors.append(f"employee:{row.get('source_id', '?')}:invalid status")
    punch_ids: set[str] = set()
    for row in source["attendance"]:
        key = str(row.get("source_id", ""))
        if key in punch_ids:
            errors.append(f"duplicate punch source:{key}")
        punch_ids.add(key)
        if str(row.get("punch_type", "")).upper() not in {"IN", "OUT"}:
            errors.append(f"punch:{key}:invalid type")
        if row.get("latitude") is None or row.get("longitude") is None:
            errors.append(f"punch:{key}:coordinate pair missing")
    return {
        "passed": not errors,
        "errors": errors,
        "source_counts": {
            "parks": len(source["parks"]),
            "employees": len(source["employees"]),
            "attendance": len(source["attendance"]),
            "leaves": len(source["leaves"]),
            "performance_records": len(source["performance_records"]),
            "qualification_records": len(source["qualification_records"]),
        },
    }


def transform(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
    parks = {str(row["source_id"]): str(row["target_ref"]) for row in source["parks"]}
    employees: dict[str, dict[str, Any]] = {}
    for item in source["employees"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        if park_ref is None:
            rows["quarantine"].append(
                {
                    "source_key": f"employee:{source_id}",
                    "issue_code": "PARK_KEY_UNMAPPED",
                    "value_fingerprint": fingerprint(str(item["park_ref"])),
                }
            )
            continue
        target = {
            "source_key": source_id,
            "park_ref": park_ref,
            "employee_no": str(item["employee_no"]).strip().upper(),
            "display_name": str(item["display_name"]).strip(),
            "department_name": item.get("department_name"),
            "position_name": item.get("position_name"),
            "mobile_masked": mask(str(item["mobile"])),
            "mobile_fingerprint": fingerprint(str(item["mobile"])),
            "identity_masked": mask(str(item["identity_number"])),
            "identity_fingerprint": fingerprint(str(item["identity_number"])),
            "status": str(item["status"]).upper(),
            "start_date": item["start_date"],
            "migrated_at": MIGRATED_AT,
        }
        employees[source_id] = target
        rows["employees"].append(target)

    if employees:
        rows["shift_versions"].append(
            {
                "source_key": "LEGACY_FIXED_DAY:v1",
                "code": "LEGACY_FIXED_DAY",
                "version_no": 1,
                "start_time": "09:00:00",
                "end_time": "18:00:00",
                "break_minutes": 60,
            }
        )
        for source_id in sorted(employees):
            rows["assignments"].append(
                {
                    "source_key": f"legacy-roster:{source_id}:2026-08-14",
                    "employee_source_key": source_id,
                    "shift_source_key": "LEGACY_FIXED_DAY:v1",
                    "work_date": "2026-08-14",
                }
            )

    punches_by_employee: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in source["attendance"]:
        employee_ref = str(item["employee_ref"])
        if employee_ref not in employees:
            rows["quarantine"].append(
                {
                    "source_key": f"punch:{item['source_id']}",
                    "issue_code": "EMPLOYEE_KEY_UNMAPPED",
                    "value_fingerprint": fingerprint(employee_ref),
                }
            )
            continue
        target = {
            "source_key": str(item["source_id"]),
            "employee_source_key": employee_ref,
            "punch_type": str(item["punch_type"]).upper(),
            "punched_at": str(item["punched_at"]),
            "source": "LEGACY_IMPORT",
            "location_fingerprint": fingerprint(str(item["legacy_location_name"])),
        }
        rows["punches"].append(target)
        punches_by_employee[employee_ref].append(target)

    for employee_ref in sorted(employees):
        punches = sorted(punches_by_employee[employee_ref], key=lambda item: item["punched_at"])
        has_in = any(item["punch_type"] == "IN" for item in punches)
        has_out = any(item["punch_type"] == "OUT" for item in punches)
        status = "NORMAL" if has_in and has_out else "ANOMALY"
        anomaly = None if status == "NORMAL" else ("MISSING_OUT" if has_in else "MISSING_IN")
        rows["summaries"].append(
            {
                "source_key": f"summary:{employee_ref}:2026-08-14",
                "employee_source_key": employee_ref,
                "work_date": "2026-08-14",
                "status": status,
                "anomaly_code": anomaly,
                "worked_minutes": 480 if status == "NORMAL" else 0,
            }
        )

    for item in source["leaves"]:
        employee_ref = str(item["employee_ref"])
        if employee_ref not in employees:
            rows["quarantine"].append(
                {
                    "source_key": f"leave:{item['source_id']}",
                    "issue_code": "EMPLOYEE_KEY_UNMAPPED",
                    "value_fingerprint": fingerprint(employee_ref),
                }
            )
            continue
        status = "PENDING_REVIEW"
        if str(item["legacy_status"]).upper() == "APPROVED":
            rows["quarantine"].append(
                {
                    "source_key": f"leave:{item['source_id']}",
                    "issue_code": "LEAVE_APPROVAL_EVIDENCE_MISSING",
                    "value_fingerprint": fingerprint(str(item["legacy_status"])),
                }
            )
        rows["leaves"].append(
            {
                "source_key": str(item["source_id"]),
                "employee_source_key": employee_ref,
                "leave_type": str(item["leave_type"]).upper(),
                "start_at": str(item["start_at"]),
                "end_at": str(item["end_at"]),
                "status": status,
                "approval_truth": "LEGACY_UNVERIFIED",
            }
        )
    return rows


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.employees (
  source_key text PRIMARY KEY, park_ref text NOT NULL, employee_no text NOT NULL UNIQUE,
  display_name text NOT NULL, department_name text, position_name text,
  mobile_masked text NOT NULL, mobile_fingerprint char(64) NOT NULL,
  identity_masked text NOT NULL, identity_fingerprint char(64) NOT NULL,
  status text NOT NULL CHECK (status IN ('ACTIVE','SUSPENDED','LEFT')),
  start_date date NOT NULL, migrated_at timestamptz NOT NULL
);
CREATE TABLE {SCHEMA}.shift_versions (
  source_key text PRIMARY KEY, code text NOT NULL, version_no integer NOT NULL,
  start_time time NOT NULL, end_time time NOT NULL, break_minutes integer NOT NULL,
  UNIQUE (code, version_no)
);
CREATE TABLE {SCHEMA}.assignments (
  source_key text PRIMARY KEY,
  employee_source_key text NOT NULL REFERENCES {SCHEMA}.employees(source_key),
  shift_source_key text NOT NULL REFERENCES {SCHEMA}.shift_versions(source_key),
  work_date date NOT NULL, UNIQUE (employee_source_key, work_date)
);
CREATE TABLE {SCHEMA}.punches (
  source_key text PRIMARY KEY,
  employee_source_key text NOT NULL REFERENCES {SCHEMA}.employees(source_key),
  punch_type text NOT NULL CHECK (punch_type IN ('IN','OUT')),
  punched_at timestamptz NOT NULL, source text NOT NULL CHECK (source = 'LEGACY_IMPORT'),
  location_fingerprint char(64) NOT NULL
);
CREATE TABLE {SCHEMA}.summaries (
  source_key text PRIMARY KEY,
  employee_source_key text NOT NULL REFERENCES {SCHEMA}.employees(source_key),
  work_date date NOT NULL, status text NOT NULL CHECK (status IN ('NORMAL','ANOMALY')),
  anomaly_code text, worked_minutes integer NOT NULL CHECK (worked_minutes >= 0),
  UNIQUE (employee_source_key, work_date)
);
CREATE TABLE {SCHEMA}.leaves (
  source_key text PRIMARY KEY,
  employee_source_key text NOT NULL REFERENCES {SCHEMA}.employees(source_key),
  leave_type text NOT NULL, start_at timestamptz NOT NULL, end_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status = 'PENDING_REVIEW'),
  approval_truth text NOT NULL CHECK (approval_truth = 'LEGACY_UNVERIFIED')
);
CREATE TABLE {SCHEMA}.performance_records (
  source_key text PRIMARY KEY, evidence_truth text NOT NULL CHECK (evidence_truth = 'LEGACY_AGGREGATE_VERIFIED')
);
CREATE TABLE {SCHEMA}.qualifications (
  source_key text PRIMARY KEY, evidence_truth text NOT NULL CHECK (evidence_truth = 'LEGACY_AGGREGATE_VERIFIED')
);
CREATE TABLE {SCHEMA}.quarantine (
  source_key text NOT NULL, issue_code text NOT NULL, value_fingerprint char(64) NOT NULL,
  PRIMARY KEY (source_key, issue_code)
);
"""

FIELDS = {
    "employees": (
        "source_key",
        "park_ref",
        "employee_no",
        "display_name",
        "department_name",
        "position_name",
        "mobile_masked",
        "mobile_fingerprint",
        "identity_masked",
        "identity_fingerprint",
        "status",
        "start_date",
        "migrated_at",
    ),
    "shift_versions": (
        "source_key",
        "code",
        "version_no",
        "start_time",
        "end_time",
        "break_minutes",
    ),
    "assignments": ("source_key", "employee_source_key", "shift_source_key", "work_date"),
    "punches": (
        "source_key",
        "employee_source_key",
        "punch_type",
        "punched_at",
        "source",
        "location_fingerprint",
    ),
    "summaries": (
        "source_key",
        "employee_source_key",
        "work_date",
        "status",
        "anomaly_code",
        "worked_minutes",
    ),
    "leaves": (
        "source_key",
        "employee_source_key",
        "leave_type",
        "start_at",
        "end_at",
        "status",
        "approval_truth",
    ),
    "performance_records": ("source_key", "evidence_truth"),
    "qualifications": ("source_key", "evidence_truth"),
    "quarantine": ("source_key", "issue_code", "value_fingerprint"),
}


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("workforce ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("workforce ETL drill is restricted to loopback PostgreSQL")
    identity = (parsed.database or "").lower()
    if "prod" in identity or not any(
        word in identity for word in ("test", "local", "dev", "audit")
    ):
        raise ValueError("workforce ETL drill refuses a production-like database identity")
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
        result_rows = rows[table]
        for row in result_rows:
            result = conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.{table} ({','.join(fields)}) "
                    f"VALUES ({','.join(f':{field}' for field in fields)}) ON CONFLICT DO NOTHING"
                ),
                {field: row[field] for field in fields},
            )
            inserted[table] += int(result.rowcount or 0)
        if interrupt and table == "assignments":
            raise RuntimeError("synthetic interruption after assignments")
    return inserted


def authorization_signature(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def reconcile(conn, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    expected = {table: len(values) for table, values in rows.items()}
    target = counts(conn)
    raw_columns = int(
        conn.execute(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema "
                "AND column_name IN ('mobile','identity_number','latitude','longitude','trajectory')"
            ),
            {"schema": SCHEMA},
        ).scalar_one()
    )
    orphan_rows = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.punches p LEFT JOIN {SCHEMA}.employees e "
                "ON e.source_key=p.employee_source_key WHERE e.source_key IS NULL"
            )
        ).scalar_one()
    )
    quarantine_reasons = dict(
        conn.execute(
            text(f"SELECT issue_code,count(*) FROM {SCHEMA}.quarantine GROUP BY issue_code")
        ).all()
    )
    expected_quarantine = {
        "EMPLOYEE_KEY_UNMAPPED": 1,
        "LEAVE_APPROVAL_EVIDENCE_MISSING": 1,
        "PARK_KEY_UNMAPPED": 1,
    }
    passed = (
        expected == target
        and raw_columns == 0
        and orphan_rows == 0
        and target["performance_records"] == 0
        and target["qualifications"] == 0
        and quarantine_reasons == expected_quarantine
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "raw_pii_or_exact_coordinate_columns": raw_columns,
        "orphan_punches": orphan_rows,
        "quarantine_reasons": quarantine_reasons,
        "fabricated_performance_records": target["performance_records"],
        "fabricated_qualifications": target["qualifications"],
        "payroll_results_generated": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    parser.add_argument(
        "--fixture", type=Path, default=Path(__file__).parent / "fixtures" / "workforce_v1.json"
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "out" / "workforce_etl_report.json")
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
        if str(exc) != "synthetic interruption after assignments":
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
    stages = {
        "dry_run": {
            "passed": validation["passed"],
            "source_counts": validation["source_counts"],
            "mapped_counts": expected,
        },
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
    }
    result = "PASS" if all(stage["passed"] for stage in stages.values()) else "FAIL"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "schema": SCHEMA,
        "synthetic_only": True,
        "contains_real_customer_data": False,
        "live_legacy_verified": False,
        "legacy_performance_aggregate_present": False,
        "legacy_qualification_aggregate_present": False,
        "readiness": "CONDITIONAL_SYNTHETIC_READY_FOR_AUTHORIZED_STAGING_DATA",
        "real_legacy_readiness": "BLOCKED_PENDING_AUTHORIZED_SCHEMA_SNAPSHOT_DICTIONARIES_AND_KEYMAPS",
        "fixture_sha256": digest(args.fixture.read_text(encoding="utf-8")),
        "stages": stages,
        "blockers": [
            "authorized legacy HR schema dump and row-count watermarks not supplied",
            "desensitized employee/attendance/leave snapshot and park/user key maps not supplied",
            "native approval evidence for legacy approved leave not supplied",
            "no authoritative legacy performance or qualification aggregate supplied",
            "production cutover and irreversible data-change authorization not granted",
        ],
        "production_contacted": False,
        "production_authorized": False,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
