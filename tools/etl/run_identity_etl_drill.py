#!/usr/bin/env python3
"""Synthetic Identity ETL acceptance drill against an isolated local PG schema.

The drill proves validation, first apply, idempotent re-apply, reconciliation and
rollback without reading legacy or production data.
"""

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

SCHEMA = "etl_identity_fixture"


def fixture() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": [
            {
                "source_id": "u-001",
                "tenant_id": "tenant-demo",
                "username": "admin",
                "password_hash": "$2b$12$syntheticRecognizableHashOnly",
                "status": "ACTIVE",
            },
            {
                "source_id": "u-002",
                "tenant_id": "tenant-demo",
                "username": "operator",
                "password_hash": "legacy-unknown-format",
                "status": "ACTIVE",
            },
        ],
        "roles": [
            {"source_id": "r-001", "tenant_id": "tenant-demo", "code": "ADMIN", "status": "ACTIVE"},
            {"source_id": "r-002", "tenant_id": "tenant-demo", "code": "OPERATOR", "status": "ACTIVE"},
        ],
        "menus": [
            {
                "source_id": "m-001",
                "tenant_id": "tenant-demo",
                "parent_source_id": None,
                "name": "System",
                "path": "/system",
                "status": "ACTIVE",
            },
            {
                "source_id": "m-002",
                "tenant_id": "tenant-demo",
                "parent_source_id": "m-001",
                "name": "Users",
                "path": "/system/users",
                "status": "ACTIVE",
            },
        ],
        "user_roles": [
            {"tenant_id": "tenant-demo", "user_source_id": "u-001", "role_source_id": "r-001"},
            {"tenant_id": "tenant-demo", "user_source_id": "u-002", "role_source_id": "r-002"},
        ],
        "role_menus": [
            {"tenant_id": "tenant-demo", "role_source_id": "r-001", "menu_source_id": "m-001"},
            {"tenant_id": "tenant-demo", "role_source_id": "r-001", "menu_source_id": "m-002"},
            {"tenant_id": "tenant-demo", "role_source_id": "r-002", "menu_source_id": "m-002"},
        ],
        "role_parks": [
            {"tenant_id": "tenant-demo", "role_source_id": "r-001", "park_source_id": "park-a"},
            {"tenant_id": "tenant-demo", "role_source_id": "r-002", "park_source_id": "park-b"},
        ],
    }


def validate_source(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    users = {(row["tenant_id"], row["source_id"]) for row in data["users"]}
    roles = {(row["tenant_id"], row["source_id"]) for row in data["roles"]}
    menus = {(row["tenant_id"], row["source_id"]) for row in data["menus"]}

    def duplicates(rows: list[dict[str, Any]], fields: tuple[str, ...], label: str) -> None:
        values = [tuple(row[field] for field in fields) for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"duplicate {label}")

    duplicates(data["users"], ("tenant_id", "source_id"), "user source id")
    duplicates(data["users"], ("tenant_id", "username"), "username")
    duplicates(data["roles"], ("tenant_id", "source_id"), "role source id")
    duplicates(data["roles"], ("tenant_id", "code"), "role code")
    duplicates(data["menus"], ("tenant_id", "source_id"), "menu source id")

    for row in data["user_roles"]:
        if (row["tenant_id"], row["user_source_id"]) not in users:
            errors.append("orphan user_roles.user")
        if (row["tenant_id"], row["role_source_id"]) not in roles:
            errors.append("orphan user_roles.role")
    for row in data["role_menus"]:
        if (row["tenant_id"], row["role_source_id"]) not in roles:
            errors.append("orphan role_menus.role")
        if (row["tenant_id"], row["menu_source_id"]) not in menus:
            errors.append("orphan role_menus.menu")
    for row in data["role_parks"]:
        if (row["tenant_id"], row["role_source_id"]) not in roles:
            errors.append("orphan role_parks.role")

    parents = {
        (row["tenant_id"], row["source_id"]): row["parent_source_id"]
        for row in data["menus"]
    }
    for key, parent in parents.items():
        seen = {key[1]}
        while parent is not None:
            if (key[0], parent) not in menus:
                errors.append("orphan menu parent")
                break
            if parent in seen:
                errors.append("menu parent cycle")
                break
            seen.add(parent)
            parent = parents[(key[0], parent)]

    allowed_status = {"ACTIVE", "DISABLED"}
    if any(row["status"] not in allowed_status for table in ("users", "roles", "menus") for row in data[table]):
        errors.append("unsupported status")
    return {"passed": not errors, "errors": sorted(set(errors))}


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.users (
  tenant_id text NOT NULL, source_id text NOT NULL, username text NOT NULL,
  password_value text NOT NULL, password_disposition text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, source_id), UNIQUE (tenant_id, username)
);
CREATE TABLE {SCHEMA}.roles (
  tenant_id text NOT NULL, source_id text NOT NULL, code text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, source_id), UNIQUE (tenant_id, code)
);
CREATE TABLE {SCHEMA}.menus (
  tenant_id text NOT NULL, source_id text NOT NULL, parent_source_id text,
  name text NOT NULL, path text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, source_id)
);
CREATE TABLE {SCHEMA}.user_roles (
  tenant_id text NOT NULL, user_source_id text NOT NULL, role_source_id text NOT NULL,
  PRIMARY KEY (tenant_id, user_source_id, role_source_id)
);
CREATE TABLE {SCHEMA}.role_menus (
  tenant_id text NOT NULL, role_source_id text NOT NULL, menu_source_id text NOT NULL,
  PRIMARY KEY (tenant_id, role_source_id, menu_source_id)
);
CREATE TABLE {SCHEMA}.role_parks (
  tenant_id text NOT NULL, role_source_id text NOT NULL, park_source_id text NOT NULL,
  PRIMARY KEY (tenant_id, role_source_id, park_source_id)
);
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("identity ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("identity ETL drill is restricted to loopback PostgreSQL")
    if not parsed.database or "prod" in parsed.database.lower():
        raise ValueError("identity ETL drill refuses an empty or production-like database name")
    return create_engine(database_url)


def password_transform(value: str) -> tuple[str, str]:
    if value.startswith(("$2a$", "$2b$", "$2y$", "$argon2")):
        return value, "PRESERVED_RECOGNIZED_HASH"
    return "RESET_REQUIRED", "CONTROLLED_RESET_REQUIRED"


def apply_rows(conn, data: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    inserted: dict[str, int] = {}
    table_fields = {
        "users": ("tenant_id", "source_id", "username", "password_value", "password_disposition", "status"),
        "roles": ("tenant_id", "source_id", "code", "status"),
        "menus": ("tenant_id", "source_id", "parent_source_id", "name", "path", "status"),
        "user_roles": ("tenant_id", "user_source_id", "role_source_id"),
        "role_menus": ("tenant_id", "role_source_id", "menu_source_id"),
        "role_parks": ("tenant_id", "role_source_id", "park_source_id"),
    }
    for table, fields in table_fields.items():
        count = 0
        for source in data[table]:
            row = dict(source)
            if table == "users":
                row["password_value"], row["password_disposition"] = password_transform(row.pop("password_hash"))
            columns = ", ".join(fields)
            params = ", ".join(f":{field}" for field in fields)
            result = conn.execute(
                text(f"INSERT INTO {SCHEMA}.{table} ({columns}) VALUES ({params}) ON CONFLICT DO NOTHING"),
                {field: row[field] for field in fields},
            )
            count += result.rowcount
        inserted[table] = count
    return inserted


def reconcile(conn, data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    for table, rows in data.items():
        target = conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()
        counts[table] = {"source": len(rows), "target": target}
    orphan_queries = {
        "user_roles_user": f"SELECT count(*) FROM {SCHEMA}.user_roles x LEFT JOIN {SCHEMA}.users u ON u.tenant_id=x.tenant_id AND u.source_id=x.user_source_id WHERE u.source_id IS NULL",
        "user_roles_role": f"SELECT count(*) FROM {SCHEMA}.user_roles x LEFT JOIN {SCHEMA}.roles r ON r.tenant_id=x.tenant_id AND r.source_id=x.role_source_id WHERE r.source_id IS NULL",
        "role_menus_role": f"SELECT count(*) FROM {SCHEMA}.role_menus x LEFT JOIN {SCHEMA}.roles r ON r.tenant_id=x.tenant_id AND r.source_id=x.role_source_id WHERE r.source_id IS NULL",
        "role_menus_menu": f"SELECT count(*) FROM {SCHEMA}.role_menus x LEFT JOIN {SCHEMA}.menus m ON m.tenant_id=x.tenant_id AND m.source_id=x.menu_source_id WHERE m.source_id IS NULL",
    }
    orphans = {name: conn.execute(text(sql)).scalar_one() for name, sql in orphan_queries.items()}
    insecure_passwords = conn.execute(
        text(
            f"SELECT count(*) FROM {SCHEMA}.users WHERE password_disposition NOT IN "
            "('PRESERVED_RECOGNIZED_HASH', 'CONTROLLED_RESET_REQUIRED') "
            "OR password_value LIKE 'legacy-%'"
        )
    ).scalar_one()
    passed = all(item["source"] == item["target"] for item in counts.values()) and not any(orphans.values()) and insecure_passwords == 0
    return {"passed": passed, "counts": counts, "orphans": orphans, "insecure_password_rows": insecure_passwords}


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
        "stages": {},
    }
    source_check = validate_source(data)
    report["stages"]["dry_run"] = source_check
    if not source_check["passed"]:
        return finish(args.out, report, 1)

    engine = safe_engine(args.database_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            conn.execute(text(DDL))
            first = apply_rows(conn, data)
            report["stages"]["first_apply"] = {"passed": all(first[name] == len(data[name]) for name in data), "inserted": first}
        with engine.begin() as conn:
            second = apply_rows(conn, data)
            report["stages"]["idempotent_reapply"] = {"passed": not any(second.values()), "inserted": second}
            report["stages"]["reconciliation"] = reconcile(conn, data)
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
            exists = conn.execute(text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": SCHEMA}).scalar_one()
            report["stages"]["rollback"] = {"passed": not exists, "schema_exists_after": exists}
    finally:
        engine.dispose()

    passed = all(stage.get("passed") for stage in report["stages"].values())
    return finish(args.out, report, 0 if passed else 1)


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"IDENTITY_ETL_REPORT={path}")
    print(f"IDENTITY_ETL_DRILL={report['result']}")
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"IDENTITY_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}", file=sys.stderr)
        raise
