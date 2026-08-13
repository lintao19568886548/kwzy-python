#!/usr/bin/env python3
"""Synthetic asset hierarchy/unit/lineage ETL drill in an isolated PG schema."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_asset_fixture"


def fixture() -> dict[str, list[dict[str, Any]]]:
    return {
        "nodes": [
            {"tenant_id": "tenant-demo", "park_id": "park-a", "source_id": "area-1", "parent_source_id": None, "code": "A-1", "name": "一期", "node_type": "AREA", "status": "ACTIVE"},
            {"tenant_id": "tenant-demo", "park_id": "park-a", "source_id": "building-1", "parent_source_id": "area-1", "code": "B-1", "name": "一号楼", "node_type": "BUILDING", "status": "ACTIVE"},
            {"tenant_id": "tenant-demo", "park_id": "park-a", "source_id": "floor-1", "parent_source_id": "building-1", "code": "F-1", "name": "一层", "node_type": "FLOOR", "status": "ACTIVE"},
            {"tenant_id": "tenant-demo", "park_id": "park-b", "source_id": "building-2", "parent_source_id": None, "code": "B-2", "name": "二号楼", "node_type": "BUILDING", "status": "ACTIVE"},
        ],
        "units": [
            {"tenant_id": "tenant-demo", "park_id": "park-a", "source_id": "unit-old", "space_source_id": "floor-1", "logical_id": "logical-old", "version_no": 1, "valid_from": "2024-01-01T00:00:00", "valid_to": "2026-01-01T00:00:00", "code": "101", "name": "101原单元", "rentable_area": "100.00", "used_area": "0.00", "status": "RETIRED"},
            {"tenant_id": "tenant-demo", "park_id": "park-a", "source_id": "unit-a", "space_source_id": "floor-1", "logical_id": "logical-a", "version_no": 1, "valid_from": "2026-01-01T00:00:00", "valid_to": None, "code": "101-A", "name": "101A", "rentable_area": "40.00", "used_area": "40.00", "status": "OCCUPIED"},
            {"tenant_id": "tenant-demo", "park_id": "park-a", "source_id": "unit-b", "space_source_id": "floor-1", "logical_id": "logical-b", "version_no": 1, "valid_from": "2026-01-01T00:00:00", "valid_to": None, "code": "101-B", "name": "101B", "rentable_area": "60.00", "used_area": "0.00", "status": "VACANT"},
            {"tenant_id": "tenant-demo", "park_id": "park-b", "source_id": "unit-c", "space_source_id": "building-2", "logical_id": "logical-c", "version_no": 1, "valid_from": "2025-01-01T00:00:00", "valid_to": None, "code": "201", "name": "201", "rentable_area": "80.00", "used_area": "0.00", "status": "VACANT"},
        ],
        "lineages": [
            {"tenant_id": "tenant-demo", "park_id": "park-a", "operation_id": "split-001", "operation_type": "SPLIT", "source_unit_id": "unit-old", "target_unit_id": "unit-a"},
            {"tenant_id": "tenant-demo", "park_id": "park-a", "operation_id": "split-001", "operation_type": "SPLIT", "source_unit_id": "unit-old", "target_unit_id": "unit-b"},
        ],
    }


def validate_source(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    nodes = {(row["tenant_id"], row["park_id"], row["source_id"]): row for row in data["nodes"]}
    units = {(row["tenant_id"], row["park_id"], row["source_id"]): row for row in data["units"]}

    if len(nodes) != len(data["nodes"]):
        errors.append("duplicate node source id")
    if len(units) != len(data["units"]):
        errors.append("duplicate unit source id")
    siblings = [
        (row["tenant_id"], row["park_id"], row["parent_source_id"], row["code"].upper())
        for row in data["nodes"]
    ]
    if len(siblings) != len(set(siblings)):
        errors.append("duplicate sibling code")

    valid_parent = {"AREA": {None}, "BUILDING": {None, "AREA"}, "FLOOR": {"BUILDING"}}
    for row in data["nodes"]:
        parent_id = row["parent_source_id"]
        parent = nodes.get((row["tenant_id"], row["park_id"], parent_id)) if parent_id else None
        parent_type = parent["node_type"] if parent else None
        if parent_id and parent is None:
            errors.append("orphan or cross-park node parent")
        if parent_type not in valid_parent.get(row["node_type"], set()):
            errors.append("invalid node parent type")
        seen = {row["source_id"]}
        cursor = parent_id
        while cursor:
            if cursor in seen:
                errors.append("node cycle")
                break
            seen.add(cursor)
            parent_row = nodes.get((row["tenant_id"], row["park_id"], cursor))
            cursor = parent_row["parent_source_id"] if parent_row else None

    current_codes: list[tuple[str, str, str, str]] = []
    for row in data["units"]:
        node = nodes.get((row["tenant_id"], row["park_id"], row["space_source_id"]))
        if node is None or node["node_type"] not in {"BUILDING", "FLOOR"}:
            errors.append("unit space invalid")
        rentable = Decimal(row["rentable_area"])
        used = Decimal(row["used_area"])
        if rentable < 0 or used < 0 or used > rentable:
            errors.append("unit area invalid")
        if row["valid_to"] is None:
            current_codes.append((row["tenant_id"], row["park_id"], row["space_source_id"], row["code"].upper()))
        if used > 0 and row["status"] != "OCCUPIED":
            errors.append("occupancy status mismatch")
    if len(current_codes) != len(set(current_codes)):
        errors.append("duplicate current unit code")

    edges: set[tuple[str, str, str]] = set()
    for row in data["lineages"]:
        source = units.get((row["tenant_id"], row["park_id"], row["source_unit_id"]))
        target = units.get((row["tenant_id"], row["park_id"], row["target_unit_id"]))
        if source is None or target is None:
            errors.append("orphan or cross-park lineage")
        elif source["valid_to"] is None or target["valid_to"] is not None:
            errors.append("lineage validity mismatch")
        edge = (row["operation_id"], row["source_unit_id"], row["target_unit_id"])
        if edge in edges:
            errors.append("duplicate lineage edge")
        edges.add(edge)
    return {"passed": not errors, "errors": sorted(set(errors))}


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.nodes (
  tenant_id text NOT NULL, park_id text NOT NULL, source_id text NOT NULL,
  parent_source_id text, code text NOT NULL, name text NOT NULL,
  node_type text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, park_id, source_id)
);
CREATE UNIQUE INDEX uk_asset_root_code ON {SCHEMA}.nodes (tenant_id, park_id, code)
  WHERE parent_source_id IS NULL;
CREATE UNIQUE INDEX uk_asset_child_code ON {SCHEMA}.nodes (tenant_id, park_id, parent_source_id, code)
  WHERE parent_source_id IS NOT NULL;
CREATE TABLE {SCHEMA}.units (
  tenant_id text NOT NULL, park_id text NOT NULL, source_id text NOT NULL,
  space_source_id text NOT NULL, logical_id text NOT NULL, version_no integer NOT NULL,
  valid_from timestamp NOT NULL, valid_to timestamp, code text NOT NULL, name text NOT NULL,
  rentable_area numeric(12,2) NOT NULL, used_area numeric(12,2) NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, park_id, source_id),
  UNIQUE (tenant_id, logical_id, version_no)
);
CREATE UNIQUE INDEX uk_asset_current_unit_code ON {SCHEMA}.units
  (tenant_id, park_id, space_source_id, code) WHERE valid_to IS NULL;
CREATE TABLE {SCHEMA}.lineages (
  tenant_id text NOT NULL, park_id text NOT NULL, operation_id text NOT NULL,
  operation_type text NOT NULL, source_unit_id text NOT NULL, target_unit_id text NOT NULL,
  PRIMARY KEY (tenant_id, operation_id, source_unit_id, target_unit_id)
);
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("asset ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("asset ETL drill is restricted to loopback PostgreSQL")
    if not parsed.database or "prod" in parsed.database.lower():
        raise ValueError("asset ETL drill refuses an empty or production-like database name")
    return create_engine(database_url)


def apply_rows(conn, data: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    fields = {
        "nodes": ("tenant_id", "park_id", "source_id", "parent_source_id", "code", "name", "node_type", "status"),
        "units": ("tenant_id", "park_id", "source_id", "space_source_id", "logical_id", "version_no", "valid_from", "valid_to", "code", "name", "rentable_area", "used_area", "status"),
        "lineages": ("tenant_id", "park_id", "operation_id", "operation_type", "source_unit_id", "target_unit_id"),
    }
    inserted: dict[str, int] = {}
    for table, columns in fields.items():
        count = 0
        for row in data[table]:
            result = conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.{table} ({', '.join(columns)}) "
                    f"VALUES ({', '.join(':' + column for column in columns)}) ON CONFLICT DO NOTHING"
                ),
                {column: row[column] for column in columns},
            )
            count += result.rowcount
        inserted[table] = count
    return inserted


def reconcile(conn, data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    counts = {
        table: {
            "source": len(rows),
            "target": conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one(),
        }
        for table, rows in data.items()
    }
    source_total = sum(Decimal(row["rentable_area"]) for row in data["units"])
    source_current_total = sum(Decimal(row["rentable_area"]) for row in data["units"] if row["valid_to"] is None)
    source_used = sum(Decimal(row["used_area"]) for row in data["units"] if row["valid_to"] is None)
    target_area = conn.execute(
        text(
            f"SELECT coalesce(sum(rentable_area),0), "
            "coalesce(sum(rentable_area) FILTER (WHERE valid_to IS NULL),0), "
            "coalesce(sum(used_area) FILTER (WHERE valid_to IS NULL),0) "
            f"FROM {SCHEMA}.units"
        )
    ).one()
    orphans = {
        "node_parent": conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.nodes n LEFT JOIN {SCHEMA}.nodes p ON p.tenant_id=n.tenant_id AND p.park_id=n.park_id AND p.source_id=n.parent_source_id WHERE n.parent_source_id IS NOT NULL AND p.source_id IS NULL")).scalar_one(),
        "unit_space": conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.units u LEFT JOIN {SCHEMA}.nodes n ON n.tenant_id=u.tenant_id AND n.park_id=u.park_id AND n.source_id=u.space_source_id WHERE n.source_id IS NULL")).scalar_one(),
        "lineage_source": conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.lineages l LEFT JOIN {SCHEMA}.units u ON u.tenant_id=l.tenant_id AND u.park_id=l.park_id AND u.source_id=l.source_unit_id WHERE u.source_id IS NULL")).scalar_one(),
        "lineage_target": conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.lineages l LEFT JOIN {SCHEMA}.units u ON u.tenant_id=l.tenant_id AND u.park_id=l.park_id AND u.source_id=l.target_unit_id WHERE u.source_id IS NULL")).scalar_one(),
    }
    duplicates = {
        "sibling_codes": conn.execute(text(f"SELECT count(*) FROM (SELECT tenant_id, park_id, parent_source_id, upper(code), count(*) FROM {SCHEMA}.nodes GROUP BY tenant_id, park_id, parent_source_id, upper(code) HAVING count(*) > 1) d")).scalar_one(),
        "current_unit_codes": conn.execute(text(f"SELECT count(*) FROM (SELECT tenant_id, park_id, space_source_id, upper(code), count(*) FROM {SCHEMA}.units WHERE valid_to IS NULL GROUP BY tenant_id, park_id, space_source_id, upper(code) HAVING count(*) > 1) d")).scalar_one(),
    }
    areas = {
        "all": {"source": str(source_total), "target": str(target_area[0])},
        "current_rentable": {"source": str(source_current_total), "target": str(target_area[1])},
        "current_used": {"source": str(source_used), "target": str(target_area[2])},
    }
    passed = (
        all(item["source"] == item["target"] for item in counts.values())
        and all(item["source"] == item["target"] for item in areas.values())
        and not any(orphans.values())
        and not any(duplicates.values())
    )
    return {"passed": passed, "counts": counts, "areas": areas, "orphans": orphans, "duplicates": duplicates}


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ASSET_ETL_REPORT={path}")
    print(f"ASSET_ETL_DRILL={report['result']}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("ETL_DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or ETL_DATABASE_URL is required")

    data = fixture()
    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "schema": SCHEMA,
        "synthetic_only": True,
        "real_legacy_readiness": "BLOCKED_PENDING_SCHEMA_AND_SAMPLE_EXPORT",
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
                "passed": all(first[name] == len(data[name]) for name in data),
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
            report["stages"]["rollback"] = {"passed": not exists, "schema_exists_after": exists}
    finally:
        engine.dispose()

    passed = all(stage.get("passed") for stage in report["stages"].values())
    return finish(args.out, report, 0 if passed else 1)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ASSET_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}", file=sys.stderr)
        raise
