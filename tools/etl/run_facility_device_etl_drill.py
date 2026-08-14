#!/usr/bin/env python3
"""Synthetic legacy facility-device ETL rehearsal on loopback PostgreSQL.

The drill proves deterministic mapping, transactional restart, idempotent replay,
reconciliation and rollback. It never reads a live legacy database and must not be
used as evidence that production facility data or a vendor IoT platform was migrated.
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

SCHEMA = "etl_facility_device_fixture"
TABLES = ("facility_devices", "facility_device_history", "quarantine")
TYPE_MAP = {
    "消防设备": "FIRE",
    "电梯": "ELEVATOR",
    "变压器": "TRANSFORMER",
    "配电设备": "ELECTRICAL",
    "空调": "HVAC",
    "给排水": "WATER",
    "安防": "SECURITY",
    "其他": "CUSTOM",
}
STATUS_MAP = {"正常": "ACTIVE", "维修中": "MAINTENANCE", "已停用": "RETIRED"}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_fixture(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("contains_real_customer_data") is not False:
        raise ValueError("fixture must declare contains_real_customer_data=false")
    if not isinstance(source.get("facility_records"), list):
        raise TypeError("fixture facility_records must be an array")
    return source


def validate_source(source: dict[str, Any]) -> dict[str, Any]:
    required = {
        "legacy_table",
        "source_id",
        "park_ref",
        "device_code",
        "name",
        "device_type",
        "location",
        "status",
    }
    errors: list[str] = []
    source_keys: set[str] = set()
    device_codes: set[str] = set()
    for row in source["facility_records"]:
        missing = sorted(required - row.keys())
        if missing:
            errors.append(f"{row.get('source_id', '?')}:missing:{','.join(missing)}")
            continue
        source_key = f"{row['legacy_table']}:{row['source_id']}"
        device_code = str(row["device_code"])
        if source_key in source_keys:
            errors.append(f"duplicate source key:{source_key}")
        if device_code in device_codes:
            errors.append(f"duplicate device code:{device_code}")
        source_keys.add(source_key)
        device_codes.add(device_code)
        check_time = row.get("last_check_time")
        if check_time:
            try:
                datetime.fromisoformat(str(check_time))
            except ValueError:
                errors.append(f"invalid last_check_time:{source_key}")
    return {"passed": not errors, "errors": errors, "source_rows": len(source_keys)}


def transform(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
    for source_row in source["facility_records"]:
        source_key = f"{source_row['legacy_table']}:{source_row['source_id']}"
        device_type = TYPE_MAP.get(str(source_row["device_type"]))
        status = STATUS_MAP.get(str(source_row["status"]))
        if device_type is None or status is None:
            field = "device_type" if device_type is None else "status"
            value = source_row[field]
            rows["quarantine"].append(
                {
                    "source_key": source_key,
                    "field_name": field,
                    "value_fingerprint": digest(str(value)),
                    "reason_code": "UNKNOWN_DEVICE_TYPE"
                    if device_type is None
                    else "UNKNOWN_STATUS",
                }
            )
            continue
        migrated_at = datetime(2026, 8, 15, tzinfo=timezone.utc).replace(tzinfo=None)
        device = {
            "source_key": source_key,
            "park_ref": str(source_row["park_ref"]),
            "device_code": str(source_row["device_code"]).strip().upper(),
            "name": str(source_row["name"]).strip(),
            "device_type": device_type,
            "location": str(source_row["location"]).strip(),
            "status": status,
            "criticality": "HIGH" if device_type in {"FIRE", "ELEVATOR", "TRANSFORMER"} else "MEDIUM",
            "manufacturer": source_row.get("manufacturer"),
            "model_no": source_row.get("model_no"),
            "last_check_time": datetime.fromisoformat(source_row["last_check_time"])
            if source_row.get("last_check_time")
            else None,
            "migration_confidence": "SYNTHETIC_MAPPING_ONLY",
            "migrated_at": migrated_at,
        }
        rows["facility_devices"].append(device)
        rows["facility_device_history"].append(
            {
                "source_event_key": f"{source_key}:IMPORTED",
                "source_key": source_key,
                "action": "MIGRATED",
                "status": status,
                "occurred_at": migrated_at,
                "evidence_truth": "LEGACY_ROW_RECONSTRUCTED_NOT_PROVIDER_VERIFIED",
            }
        )
    return rows


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.facility_devices (
  source_key text PRIMARY KEY,
  park_ref text NOT NULL,
  device_code text NOT NULL UNIQUE,
  name text NOT NULL,
  device_type text NOT NULL CHECK (device_type IN ('FIRE','ELEVATOR','TRANSFORMER','ELECTRICAL','HVAC','WATER','SECURITY','CUSTOM')),
  location text NOT NULL,
  status text NOT NULL CHECK (status IN ('ACTIVE','MAINTENANCE','RETIRED')),
  criticality text NOT NULL CHECK (criticality IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  manufacturer text,
  model_no text,
  last_check_time timestamp,
  migration_confidence text NOT NULL,
  migrated_at timestamp NOT NULL
);
CREATE TABLE {SCHEMA}.facility_device_history (
  source_event_key text PRIMARY KEY,
  source_key text NOT NULL REFERENCES {SCHEMA}.facility_devices(source_key),
  action text NOT NULL CHECK (action = 'MIGRATED'),
  status text NOT NULL,
  occurred_at timestamp NOT NULL,
  evidence_truth text NOT NULL
);
CREATE TABLE {SCHEMA}.quarantine (
  source_key text NOT NULL,
  field_name text NOT NULL,
  value_fingerprint char(64) NOT NULL,
  reason_code text NOT NULL,
  PRIMARY KEY (source_key, field_name)
);
"""

FIELDS = {
    "facility_devices": (
        "source_key",
        "park_ref",
        "device_code",
        "name",
        "device_type",
        "location",
        "status",
        "criticality",
        "manufacturer",
        "model_no",
        "last_check_time",
        "migration_confidence",
        "migrated_at",
    ),
    "facility_device_history": (
        "source_event_key",
        "source_key",
        "action",
        "status",
        "occurred_at",
        "evidence_truth",
    ),
    "quarantine": ("source_key", "field_name", "value_fingerprint", "reason_code"),
}


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("facility-device ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("facility-device ETL drill is restricted to loopback PostgreSQL")
    identity = (parsed.database or "").lower()
    if "prod" in identity or not any(
        word in identity for word in ("test", "local", "dev", "audit")
    ):
        raise ValueError("facility-device ETL drill refuses a production-like database identity")
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
        if interrupt and table == "facility_devices":
            raise RuntimeError("synthetic interruption after facility devices")
    return inserted


def authorization_signature(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def reconcile(conn, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    expected = {table: len(values) for table, values in rows.items()}
    target = counts(conn)
    expected_types = dict(Counter(row["device_type"] for row in rows["facility_devices"]))
    target_types = dict(
        conn.execute(
            text(f"SELECT device_type,count(*) FROM {SCHEMA}.facility_devices GROUP BY device_type")
        ).all()
    )
    orphans = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.facility_device_history h "
                f"LEFT JOIN {SCHEMA}.facility_devices d USING(source_key) WHERE d.source_key IS NULL"
            )
        ).scalar_one()
    )
    bad_codes = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.facility_devices "
                "WHERE device_code <> upper(device_code) OR length(trim(device_code)) = 0"
            )
        ).scalar_one()
    )
    quarantine = dict(
        conn.execute(
            text(f"SELECT reason_code,count(*) FROM {SCHEMA}.quarantine GROUP BY reason_code")
        ).all()
    )
    passed = (
        expected == target
        and expected_types == target_types
        and orphans == 0
        and bad_codes == 0
        and quarantine == {"UNKNOWN_DEVICE_TYPE": 1}
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "expected_device_types": expected_types,
        "target_device_types": target_types,
        "orphan_history": orphans,
        "bad_device_codes": bad_codes,
        "quarantine_reasons": quarantine,
        "fabricated_inspection_schedules": 0,
        "fabricated_iot_bindings": 0,
        "fabricated_iot_alarms": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "facility_device_v1.json",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "out" / "facility_device_etl_report.json"),
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
        if str(exc) != "synthetic interruption after facility devices":
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
            "authorized legacy firefighting/elevator/transformer/factory_maint schema dump not supplied",
            "desensitized production-like facility snapshot and dictionaries not supplied",
            "park/unit/device key maps and duplicate-resolution decisions not supplied",
            "real IoT provider credentials, protocol and event samples not supplied",
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
