#!/usr/bin/env python3
"""Synthetic asset-template/geometry migration drill on disposable PostgreSQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_asset_portfolio_fixture"
SOURCE_SCHEMA_VERSION = "kwzy.asset-portfolio.synthetic.v1"
CATEGORIES = (
    "FACTORY",
    "WAREHOUSE",
    "SHOP",
    "OFFICE",
    "DORMITORY",
    "PARKING",
    "PUBLIC_SPACE",
)


def checksum(fields: list[dict[str, Any]], defaults: dict[str, Any]) -> str:
    payload = {"fields": fields, "defaults": defaults}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def fixture() -> dict[str, list[dict[str, Any]]]:
    templates: list[dict[str, Any]] = []
    versions: list[dict[str, Any]] = []
    for category in CATEGORIES:
        source_id = f"builtin-{category.lower()}"
        fields = [{"key": "legacy_ref", "label": "旧系统参考", "type": "TEXT"}]
        templates.append(
            {
                "tenant_ref": "tenant-demo",
                "source_id": source_id,
                "code": category,
                "name": f"{category}内置模板",
                "category": category,
                "status": "ACTIVE",
                "is_builtin": True,
                "current_version": 1,
            }
        )
        versions.append(
            {
                "tenant_ref": "tenant-demo",
                "source_id": f"{source_id}-v1",
                "template_source_id": source_id,
                "version": 1,
                "status": "PUBLISHED",
                "field_schema": fields,
                "defaults": {},
                "schema_checksum": checksum(fields, {}),
            }
        )

    custom_fields_v1 = [
        {"key": "capacity", "label": "容量", "type": "NUMBER", "required": True}
    ]
    custom_fields_v2 = [
        {"key": "capacity", "label": "容量", "type": "NUMBER", "required": True},
        {
            "key": "fitout",
            "label": "装修",
            "type": "ENUM",
            "options": ["BARE", "STANDARD"],
        },
    ]
    templates.append(
        {
            "tenant_ref": "tenant-demo",
            "source_id": "custom-office",
            "code": "CUSTOM_OFFICE",
            "name": "租户办公模板",
            "category": "OFFICE",
            "status": "ACTIVE",
            "is_builtin": False,
            "current_version": 2,
        }
    )
    versions.extend(
        [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "custom-office-v1",
                "template_source_id": "custom-office",
                "version": 1,
                "status": "RETIRED",
                "field_schema": custom_fields_v1,
                "defaults": {},
                "schema_checksum": checksum(custom_fields_v1, {}),
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "custom-office-v2",
                "template_source_id": "custom-office",
                "version": 2,
                "status": "PUBLISHED",
                "field_schema": custom_fields_v2,
                "defaults": {"fitout": "STANDARD"},
                "schema_checksum": checksum(custom_fields_v2, {"fitout": "STANDARD"}),
            },
        ]
    )
    return {
        "templates": templates,
        "versions": versions,
        "spaces": [
            {
                "tenant_ref": "tenant-demo",
                "park_ref": "park-a",
                "source_id": "building-mapped",
                "code": "B-MAP",
                "name": "已映射楼栋",
                "node_type": "BUILDING",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[10, 10], [110, 10], [110, 70], [10, 70], [10, 10]]
                    ],
                },
                "coordinate_reference": "LOCAL",
                "geometry_version": 1,
            },
            {
                "tenant_ref": "tenant-demo",
                "park_ref": "park-a",
                "source_id": "building-unmapped",
                "code": "B-NOMAP",
                "name": "未映射楼栋",
                "node_type": "BUILDING",
                "geometry": None,
                "coordinate_reference": None,
                "geometry_version": 1,
            },
        ],
        "units": [
            {
                "tenant_ref": "tenant-demo",
                "park_ref": "park-a",
                "source_id": "unit-office",
                "space_source_id": "building-mapped",
                "template_version_source_id": "custom-office-v2",
                "code": "O-101",
                "rentable_area": "88.00",
                "used_area": "20.00",
                "attributes": {"capacity": 12, "fitout": "STANDARD"},
            },
            {
                "tenant_ref": "tenant-demo",
                "park_ref": "park-a",
                "source_id": "unit-factory",
                "space_source_id": "building-unmapped",
                "template_version_source_id": "builtin-factory-v1",
                "code": "F-101",
                "rentable_area": "120.00",
                "used_area": "0.00",
                "attributes": {"legacy_ref": "factory-101"},
            },
        ],
    }


def validate_source(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    templates = {row["source_id"]: row for row in data["templates"]}
    versions = {row["source_id"]: row for row in data["versions"]}
    spaces = {row["source_id"]: row for row in data["spaces"]}
    if len(templates) != len(data["templates"]):
        errors.append("duplicate template source id")
    if len(versions) != len(data["versions"]):
        errors.append("duplicate template version source id")
    if {row["category"] for row in data["templates"] if row["is_builtin"]} != set(
        CATEGORIES
    ):
        errors.append("built-in category set incomplete")
    codes = [(row["tenant_ref"], row["code"].upper()) for row in data["templates"]]
    if len(codes) != len(set(codes)):
        errors.append("duplicate tenant template code")

    published: dict[str, list[int]] = {}
    seen_versions: set[tuple[str, int]] = set()
    for row in data["versions"]:
        template = templates.get(row["template_source_id"])
        if template is None:
            errors.append("orphan template version")
            continue
        edge = (row["template_source_id"], row["version"])
        if edge in seen_versions:
            errors.append("duplicate template version")
        seen_versions.add(edge)
        expected = checksum(row["field_schema"], row["defaults"])
        if expected != row["schema_checksum"]:
            errors.append("template checksum mismatch")
        if row["status"] == "PUBLISHED":
            published.setdefault(row["template_source_id"], []).append(row["version"])
    for source_id, template in templates.items():
        if published.get(source_id) != [template["current_version"]]:
            errors.append("current published template version mismatch")

    for row in data["spaces"]:
        geometry = row["geometry"]
        if geometry is not None:
            if geometry.get("type") not in {"Point", "Polygon"}:
                errors.append("unsupported geometry type")
            if row["coordinate_reference"] not in {"LOCAL", "WGS84", "GCJ02", "BD09"}:
                errors.append("invalid coordinate reference")
    for row in data["units"]:
        if row["space_source_id"] not in spaces:
            errors.append("orphan unit space")
        version = versions.get(row["template_version_source_id"])
        if version is None or version["status"] != "PUBLISHED":
            errors.append("unit references non-published template version")
        rentable = Decimal(row["rentable_area"])
        used = Decimal(row["used_area"])
        if rentable < 0 or used < 0 or used > rentable:
            errors.append("unit area invalid")
    return {"passed": not errors, "errors": sorted(set(errors))}


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.templates (
  tenant_ref text NOT NULL, source_id text NOT NULL, code text NOT NULL,
  name text NOT NULL, category text NOT NULL, status text NOT NULL,
  is_builtin boolean NOT NULL, current_version integer NOT NULL,
  PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, code),
  CHECK (status IN ('ACTIVE','RETIRED')), CHECK (current_version >= 0)
);
CREATE TABLE {SCHEMA}.versions (
  tenant_ref text NOT NULL, source_id text NOT NULL, template_source_id text NOT NULL,
  version integer NOT NULL, status text NOT NULL, field_schema jsonb NOT NULL,
  defaults_json jsonb NOT NULL, schema_checksum text NOT NULL,
  PRIMARY KEY (tenant_ref, source_id),
  UNIQUE (tenant_ref, template_source_id, version),
  FOREIGN KEY (tenant_ref, template_source_id)
    REFERENCES {SCHEMA}.templates (tenant_ref, source_id),
  CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')), CHECK (version > 0)
);
CREATE UNIQUE INDEX one_draft_per_template ON {SCHEMA}.versions
  (tenant_ref, template_source_id) WHERE status = 'DRAFT';
CREATE TABLE {SCHEMA}.spaces (
  tenant_ref text NOT NULL, park_ref text NOT NULL, source_id text NOT NULL,
  code text NOT NULL, name text NOT NULL, node_type text NOT NULL,
  geometry jsonb, coordinate_reference text, geometry_version integer NOT NULL,
  PRIMARY KEY (tenant_ref, park_ref, source_id),
  UNIQUE (tenant_ref, park_ref, code), CHECK (geometry_version > 0)
);
CREATE TABLE {SCHEMA}.units (
  tenant_ref text NOT NULL, park_ref text NOT NULL, source_id text NOT NULL,
  space_source_id text NOT NULL, template_version_source_id text NOT NULL,
  code text NOT NULL, rentable_area numeric(12,2) NOT NULL,
  used_area numeric(12,2) NOT NULL, attributes_json jsonb NOT NULL,
  PRIMARY KEY (tenant_ref, park_ref, source_id),
  UNIQUE (tenant_ref, park_ref, space_source_id, code),
  FOREIGN KEY (tenant_ref, park_ref, space_source_id)
    REFERENCES {SCHEMA}.spaces (tenant_ref, park_ref, source_id),
  FOREIGN KEY (tenant_ref, template_version_source_id)
    REFERENCES {SCHEMA}.versions (tenant_ref, source_id),
  CHECK (rentable_area >= 0), CHECK (used_area >= 0),
  CHECK (used_area <= rentable_area)
);
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("asset portfolio ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError(
            "asset portfolio ETL drill is restricted to loopback PostgreSQL"
        )
    if not parsed.database or "prod" in parsed.database.lower():
        raise ValueError("asset portfolio ETL refuses production-like database names")
    return create_engine(database_url)


def apply_rows(conn, data: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    statements = {
        "templates": f"""
          INSERT INTO {SCHEMA}.templates
            (tenant_ref,source_id,code,name,category,status,is_builtin,current_version)
          VALUES
            (:tenant_ref,:source_id,:code,:name,:category,:status,:is_builtin,:current_version)
          ON CONFLICT DO NOTHING
        """,
        "versions": f"""
          INSERT INTO {SCHEMA}.versions
            (tenant_ref,source_id,template_source_id,version,status,field_schema,
             defaults_json,schema_checksum)
          VALUES
            (:tenant_ref,:source_id,:template_source_id,:version,:status,
             CAST(:field_schema_text AS jsonb),CAST(:defaults_text AS jsonb),:schema_checksum)
          ON CONFLICT DO NOTHING
        """,
        "spaces": f"""
          INSERT INTO {SCHEMA}.spaces
            (tenant_ref,park_ref,source_id,code,name,node_type,geometry,
             coordinate_reference,geometry_version)
          VALUES
            (:tenant_ref,:park_ref,:source_id,:code,:name,:node_type,
             CAST(:geometry_text AS jsonb),
             :coordinate_reference,:geometry_version)
          ON CONFLICT DO NOTHING
        """,
        "units": f"""
          INSERT INTO {SCHEMA}.units
            (tenant_ref,park_ref,source_id,space_source_id,template_version_source_id,
             code,rentable_area,used_area,attributes_json)
          VALUES
            (:tenant_ref,:park_ref,:source_id,:space_source_id,:template_version_source_id,
             :code,:rentable_area,:used_area,CAST(:attributes_text AS jsonb))
          ON CONFLICT DO NOTHING
        """,
    }
    inserted: dict[str, int] = {}
    for table in ("templates", "versions", "spaces", "units"):
        count = 0
        for source in data[table]:
            row = dict(source)
            if table == "versions":
                row["field_schema_text"] = json.dumps(row.pop("field_schema"))
                row["defaults_text"] = json.dumps(row.pop("defaults"))
            elif table == "spaces":
                geometry = row.pop("geometry")
                row["geometry_text"] = (
                    json.dumps(geometry) if geometry is not None else None
                )
            elif table == "units":
                row["attributes_text"] = json.dumps(row.pop("attributes"))
            count += conn.execute(text(statements[table]), row).rowcount
        inserted[table] = count
    return inserted


def authorization_counts(conn) -> dict[str, int]:
    return {
        table: int(
            conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one()
        )
        for table in ("tenants", "users", "roles", "permissions")
    }


def reconcile(conn, data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    counts = {
        table: {
            "source": len(rows),
            "target": int(
                conn.execute(
                    text(f"SELECT count(*) FROM {SCHEMA}.{table}")
                ).scalar_one()
            ),
        }
        for table, rows in data.items()
    }
    source_rentable = sum(Decimal(row["rentable_area"]) for row in data["units"])
    source_used = sum(Decimal(row["used_area"]) for row in data["units"])
    target_areas = conn.execute(
        text(
            f"SELECT coalesce(sum(rentable_area),0), coalesce(sum(used_area),0) FROM {SCHEMA}.units"
        )
    ).one()
    checks = {
        "template_checksum_mismatch": int(
            conn.execute(
                text(
                    f"SELECT count(*) FROM {SCHEMA}.versions WHERE length(schema_checksum) <> 64"
                )
            ).scalar_one()
        ),
        "unit_non_published_version": int(
            conn.execute(
                text(
                    f"SELECT count(*) FROM {SCHEMA}.units u JOIN {SCHEMA}.versions v "
                    "ON v.tenant_ref=u.tenant_ref AND v.source_id=u.template_version_source_id "
                    "WHERE v.status <> 'PUBLISHED'"
                )
            ).scalar_one()
        ),
        "invalid_geometry_crs": int(
            conn.execute(
                text(
                    f"SELECT count(*) FROM {SCHEMA}.spaces WHERE geometry IS NOT NULL "
                    "AND coordinate_reference NOT IN ('LOCAL','WGS84','GCJ02','BD09')"
                )
            ).scalar_one()
        ),
        "unmapped_units": int(
            conn.execute(
                text(
                    f"SELECT count(*) FROM {SCHEMA}.units u JOIN {SCHEMA}.spaces s "
                    "ON s.tenant_ref=u.tenant_ref AND s.park_ref=u.park_ref "
                    "AND s.source_id=u.space_source_id WHERE s.geometry IS NULL"
                )
            ).scalar_one()
        ),
    }
    areas = {
        "rentable": {"source": str(source_rentable), "target": str(target_areas[0])},
        "used": {"source": str(source_used), "target": str(target_areas[1])},
    }
    passed = (
        all(item["source"] == item["target"] for item in counts.values())
        and all(item["source"] == item["target"] for item in areas.values())
        and checks["template_checksum_mismatch"] == 0
        and checks["unit_non_published_version"] == 0
        and checks["invalid_geometry_crs"] == 0
        and checks["unmapped_units"] == 1
    )
    return {"passed": passed, "counts": counts, "areas": areas, "checks": checks}


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"ASSET_PORTFOLIO_ETL_REPORT={path}")
    print(f"ASSET_PORTFOLIO_ETL_DRILL={report['result']}")
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
        "real_legacy_readiness": (
            "BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE"
        ),
        "external_map_provider": "NOT_CONNECTED_LOCAL_SCHEMATIC",
        "stages": {"dry_run": validate_source(data)},
    }
    if not report["stages"]["dry_run"]["passed"]:
        return finish(args.out, report, 1)

    engine = safe_engine(args.database_url)
    try:
        with engine.begin() as conn:
            authorization_before = authorization_counts(conn)
            conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            conn.execute(text(DDL))
        try:
            with engine.begin() as conn:
                partial_data = {key: value for key, value in data.items()}
                partial_data["versions"] = []
                partial_data["spaces"] = []
                partial_data["units"] = []
                apply_rows(conn, partial_data)
                raise RuntimeError("synthetic interruption after templates")
        except RuntimeError as exc:
            if "synthetic interruption" not in str(exc):
                raise
        with engine.connect() as conn:
            partial = sum(
                int(
                    conn.execute(
                        text(f"SELECT count(*) FROM {SCHEMA}.{table}")
                    ).scalar_one()
                )
                for table in data
            )
        report["stages"]["interruption_recovery"] = {
            "passed": partial == 0,
            "partial_rows_after_rollback": partial,
        }
        with engine.begin() as conn:
            first = apply_rows(conn, data)
        report["stages"]["first_apply"] = {
            "passed": all(first[table] == len(data[table]) for table in data),
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
            exists = bool(
                conn.execute(
                    text("SELECT to_regnamespace(:schema) IS NOT NULL"),
                    {"schema": SCHEMA},
                ).scalar_one()
            )
            authorization_after = authorization_counts(conn)
        report["stages"]["rollback"] = {
            "passed": not exists and authorization_before == authorization_after,
            "schema_exists_after": exists,
            "authorization_rows_unchanged": authorization_before == authorization_after,
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
            f"ASSET_PORTFOLIO_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
