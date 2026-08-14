#!/usr/bin/env python3
"""Synthetic organization-governance ETL drill in an isolated PostgreSQL schema."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_organization_governance_fixture"
SOURCE_SCHEMA_VERSION = "kwzy.organization-governance.synthetic.v1"
FIELDS = {
    "organization_groups": ("tenant_ref", "source_id", "code", "name", "status"),
    "organization_regions": (
        "tenant_ref",
        "source_id",
        "group_source_id",
        "code",
        "name",
        "status",
    ),
    "region_park_assignments": (
        "tenant_ref",
        "source_id",
        "region_source_id",
        "park_source_id",
        "effective_from",
        "effective_to",
    ),
    "positions": (
        "tenant_ref",
        "source_id",
        "org_unit_source_id",
        "code",
        "name",
        "status",
    ),
    "user_position_assignments": (
        "tenant_ref",
        "source_id",
        "user_source_id",
        "position_source_id",
        "park_source_id",
        "scope_key",
        "starts_at",
        "ends_at",
        "is_primary",
    ),
    "field_access_policies": (
        "tenant_ref",
        "source_id",
        "role_source_id",
        "resource_type",
        "field_name",
        "access_mode",
        "mask_strategy",
        "status",
    ),
}


def fixture() -> dict[str, Any]:
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "references": {
            "parks": ["park-a", "park-b"],
            "users": ["user-admin", "user-ops"],
            "roles": ["role-admin", "role-ops"],
            "org_units": ["dept-investment", "dept-property"],
        },
        "organization_groups": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "group-001",
                "code": "KW",
                "name": "瞰维集团",
                "status": "ACTIVE",
            }
        ],
        "organization_regions": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "region-east",
                "group_source_id": "group-001",
                "code": "EAST",
                "name": "东区",
                "status": "ACTIVE",
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "region-west",
                "group_source_id": "group-001",
                "code": "WEST",
                "name": "西区",
                "status": "ACTIVE",
            },
        ],
        "region_park_assignments": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "region-park-001",
                "region_source_id": "region-east",
                "park_source_id": "park-a",
                "effective_from": "2024-01-01T00:00:00",
                "effective_to": "2025-01-01T00:00:00",
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "region-park-002",
                "region_source_id": "region-west",
                "park_source_id": "park-a",
                "effective_from": "2025-01-01T00:00:00",
                "effective_to": None,
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "region-park-003",
                "region_source_id": "region-east",
                "park_source_id": "park-b",
                "effective_from": "2024-06-01T00:00:00",
                "effective_to": None,
            },
        ],
        "positions": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "position-investment",
                "org_unit_source_id": "dept-investment",
                "code": "INVESTMENT_MANAGER",
                "name": "招商主管",
                "status": "ACTIVE",
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "position-property",
                "org_unit_source_id": "dept-property",
                "code": "PROPERTY_ENGINEER",
                "name": "物业工程师",
                "status": "ACTIVE",
            },
        ],
        "user_position_assignments": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "assignment-001",
                "user_source_id": "user-admin",
                "position_source_id": "position-investment",
                "park_source_id": None,
                "scope_key": "TENANT",
                "starts_at": "2024-01-01T00:00:00",
                "ends_at": None,
                "is_primary": True,
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "assignment-002",
                "user_source_id": "user-ops",
                "position_source_id": "position-property",
                "park_source_id": "park-b",
                "scope_key": "PARK:park-b",
                "starts_at": "2024-06-01T00:00:00",
                "ends_at": None,
                "is_primary": True,
            },
        ],
        "field_access_policies": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "policy-001",
                "role_source_id": "role-admin",
                "resource_type": "USER",
                "field_name": "phone",
                "access_mode": "VISIBLE",
                "mask_strategy": "PHONE",
                "status": "ACTIVE",
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "policy-002",
                "role_source_id": "role-ops",
                "resource_type": "USER",
                "field_name": "phone",
                "access_mode": "MASKED",
                "mask_strategy": "PHONE",
                "status": "ACTIVE",
            },
        ],
    }


def _keys(data: dict[str, Any], table: str) -> set[tuple[str, str]]:
    return {(row["tenant_ref"], row["source_id"]) for row in data[table]}


def validate_source(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if data.get("schema_version") != SOURCE_SCHEMA_VERSION:
        errors.append("unsupported schema version")
    for table in FIELDS:
        rows = data.get(table)
        if not isinstance(rows, list):
            errors.append(f"missing table {table}")
            continue
        keys = [(row.get("tenant_ref"), row.get("source_id")) for row in rows]
        if len(keys) != len(set(keys)):
            errors.append(f"duplicate source id in {table}")

    groups = _keys(data, "organization_groups")
    regions = _keys(data, "organization_regions")
    positions = _keys(data, "positions")
    refs = data["references"]
    current_parks: set[tuple[str, str]] = set()
    current_primary: set[tuple[str, str]] = set()
    allowed_status = {"ACTIVE", "DISABLED"}
    for row in data["organization_groups"] + data["organization_regions"] + data["positions"]:
        if row["status"] not in allowed_status:
            errors.append("unsupported lifecycle status")
    for row in data["organization_regions"]:
        if (row["tenant_ref"], row["group_source_id"]) not in groups:
            errors.append("orphan region group")
    for row in data["region_park_assignments"]:
        if (row["tenant_ref"], row["region_source_id"]) not in regions:
            errors.append("orphan region park region")
        if row["park_source_id"] not in refs["parks"]:
            errors.append("orphan region park park")
        start = datetime.fromisoformat(row["effective_from"])
        end = datetime.fromisoformat(row["effective_to"]) if row["effective_to"] else None
        if end is not None and end < start:
            errors.append("invalid region park effective range")
        if end is None:
            key = (row["tenant_ref"], row["park_source_id"])
            if key in current_parks:
                errors.append("multiple current regions for park")
            current_parks.add(key)
    for row in data["positions"]:
        if row["org_unit_source_id"] not in refs["org_units"]:
            errors.append("orphan position org unit")
    for row in data["user_position_assignments"]:
        if row["user_source_id"] not in refs["users"]:
            errors.append("orphan assignment user")
        if (row["tenant_ref"], row["position_source_id"]) not in positions:
            errors.append("orphan assignment position")
        park = row["park_source_id"]
        expected_scope = f"PARK:{park}" if park else "TENANT"
        if park and park not in refs["parks"]:
            errors.append("orphan assignment park")
        if row["scope_key"] != expected_scope:
            errors.append("assignment scope key mismatch")
        if row["ends_at"] is None and row["is_primary"]:
            key = (row["tenant_ref"], row["user_source_id"])
            if key in current_primary:
                errors.append("multiple current primary positions")
            current_primary.add(key)
    for row in data["field_access_policies"]:
        if row["role_source_id"] not in refs["roles"]:
            errors.append("orphan field policy role")
        if (row["resource_type"], row["field_name"]) != ("USER", "phone"):
            errors.append("field policy target outside registry")
        if row["access_mode"] not in {"VISIBLE", "MASKED", "HIDDEN"}:
            errors.append("unsupported field access mode")
        if row["mask_strategy"] != "PHONE":
            errors.append("unsupported field mask strategy")
    return {"passed": not errors, "errors": sorted(set(errors))}


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.organization_groups (tenant_ref text NOT NULL, source_id text NOT NULL, code text NOT NULL, name text NOT NULL, status text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, code));
CREATE TABLE {SCHEMA}.organization_regions (tenant_ref text NOT NULL, source_id text NOT NULL, group_source_id text NOT NULL, code text NOT NULL, name text NOT NULL, status text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, code));
CREATE TABLE {SCHEMA}.region_park_assignments (tenant_ref text NOT NULL, source_id text NOT NULL, region_source_id text NOT NULL, park_source_id text NOT NULL, effective_from timestamp NOT NULL, effective_to timestamp, PRIMARY KEY (tenant_ref, source_id));
CREATE UNIQUE INDEX uk_etl_region_park_current ON {SCHEMA}.region_park_assignments (tenant_ref, park_source_id) WHERE effective_to IS NULL;
CREATE TABLE {SCHEMA}.positions (tenant_ref text NOT NULL, source_id text NOT NULL, org_unit_source_id text, code text NOT NULL, name text NOT NULL, status text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, code));
CREATE TABLE {SCHEMA}.user_position_assignments (tenant_ref text NOT NULL, source_id text NOT NULL, user_source_id text NOT NULL, position_source_id text NOT NULL, park_source_id text, scope_key text NOT NULL, starts_at timestamp NOT NULL, ends_at timestamp, is_primary boolean NOT NULL, PRIMARY KEY (tenant_ref, source_id));
CREATE UNIQUE INDEX uk_etl_current_primary ON {SCHEMA}.user_position_assignments (tenant_ref, user_source_id) WHERE ends_at IS NULL AND is_primary = true;
CREATE TABLE {SCHEMA}.field_access_policies (tenant_ref text NOT NULL, source_id text NOT NULL, role_source_id text NOT NULL, resource_type text NOT NULL, field_name text NOT NULL, access_mode text NOT NULL, mask_strategy text NOT NULL, status text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, role_source_id, resource_type, field_name));
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("organization governance ETL requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("organization governance ETL is restricted to loopback PostgreSQL")
    if not parsed.database or "test" not in parsed.database.lower():
        raise ValueError("organization governance ETL requires an explicit test database")
    return create_engine(database_url)


def apply_rows(conn, data: dict[str, Any]) -> dict[str, int]:
    inserted: dict[str, int] = {}
    for table, fields in FIELDS.items():
        count = 0
        for row in data[table]:
            result = conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.{table} ({', '.join(fields)}) "
                    f"VALUES ({', '.join(':' + field for field in fields)}) ON CONFLICT DO NOTHING"
                ),
                {field: row[field] for field in fields},
            )
            count += result.rowcount
        inserted[table] = count
    return inserted


def reconcile(conn, data: dict[str, Any]) -> dict[str, Any]:
    counts = {}
    for table in FIELDS:
        target = conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()
        counts[table] = {"source": len(data[table]), "target": int(target)}
    current_region_duplicates = conn.execute(
        text(f"SELECT count(*) FROM (SELECT tenant_ref, park_source_id FROM {SCHEMA}.region_park_assignments WHERE effective_to IS NULL GROUP BY tenant_ref, park_source_id HAVING count(*) > 1) x")
    ).scalar_one()
    current_primary_duplicates = conn.execute(
        text(f"SELECT count(*) FROM (SELECT tenant_ref, user_source_id FROM {SCHEMA}.user_position_assignments WHERE ends_at IS NULL AND is_primary = true GROUP BY tenant_ref, user_source_id HAVING count(*) > 1) x")
    ).scalar_one()
    passed = all(row["source"] == row["target"] for row in counts.values())
    passed = passed and current_region_duplicates == 0 and current_primary_duplicates == 0
    return {
        "passed": passed,
        "counts": counts,
        "current_region_duplicates": int(current_region_duplicates),
        "current_primary_duplicates": int(current_primary_duplicates),
        "authorization_rows_emitted": 0,
        "raw_pii_rows": 0,
    }


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ORGANIZATION_GOVERNANCE_ETL_REPORT={path}")
    print(f"ORGANIZATION_GOVERNANCE_ETL_DRILL={report['result']}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.getenv("ETL_DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or ETL_DATABASE_URL is required")
    data = fixture()
    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "schema": SCHEMA,
        "synthetic_only": True,
        "readiness": "CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA",
        "real_legacy_readiness": "BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE",
        "stages": {},
    }
    report["stages"]["dry_run"] = validate_source(data)
    if not report["stages"]["dry_run"]["passed"]:
        return finish(args.out, report, 1)
    engine = safe_engine(args.database_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            conn.execute(text(DDL))
            first = apply_rows(conn, data)
            report["stages"]["first_apply"] = {
                "passed": all(first[table] == len(data[table]) for table in FIELDS),
                "inserted": first,
            }
        with engine.begin() as conn:
            second = apply_rows(conn, data)
            report["stages"]["idempotent_reapply"] = {
                "passed": not any(second.values()),
                "inserted": second,
            }
            report["stages"]["reconciliation"] = reconcile(conn, data)
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
            exists = conn.execute(
                text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": SCHEMA}
            ).scalar_one()
            report["stages"]["rollback"] = {
                "passed": not exists,
                "schema_exists_after": bool(exists),
            }
    finally:
        engine.dispose()
    passed = all(stage.get("passed") for stage in report["stages"].values())
    return finish(args.out, report, 0 if passed else 1)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"ORGANIZATION_GOVERNANCE_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
