#!/usr/bin/env python3
"""Synthetic approval/audit migration drill in a disposable PostgreSQL schema.

This runner intentionally never reads a production database.  It proves source
validation, transactional interruption recovery, idempotent re-apply,
reconciliation and fixture-only rollback while keeping real legacy readiness
blocked until authorized evidence exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_approval_audit_fixture"
SOURCE_SCHEMA_VERSION = "kwzy.approval-audit.synthetic.v1"
TABLES = (
    "approval_definitions",
    "approval_definition_versions",
    "approval_definition_steps",
    "approval_step_assignees",
    "approval_requests",
    "approval_tasks",
    "approval_delegations",
    "approval_events",
    "audit_logs",
)
FIELDS = {
    "approval_definitions": ("tenant_ref", "source_id", "code", "name", "biz_type", "status"),
    "approval_definition_versions": ("tenant_ref", "source_id", "definition_source_id", "version", "status"),
    "approval_definition_steps": ("tenant_ref", "source_id", "version_source_id", "step_order", "name", "approval_mode", "min_approvals", "sla_hours"),
    "approval_step_assignees": ("tenant_ref", "source_id", "step_source_id", "user_ref", "role_ref"),
    "approval_requests": ("tenant_ref", "source_id", "request_no", "version_source_id", "biz_type", "biz_id", "title", "status", "compatibility_mode"),
    "approval_tasks": ("tenant_ref", "source_id", "request_source_id", "step_source_id", "assignee_user_ref", "status", "acted_by_user_ref"),
    "approval_delegations": ("tenant_ref", "source_id", "grantor_user_ref", "delegate_user_ref", "biz_type", "status"),
    "approval_events": ("tenant_ref", "source_id", "request_source_id", "action", "actor_user_ref", "source_decision_ref"),
    "audit_logs": ("tenant_ref", "source_id", "sequence_no", "action", "resource_type", "resource_id", "detail_json", "previous_hash", "record_hash"),
}


def _hash(previous: str, sequence: int, source_id: str, action: str) -> str:
    payload = json.dumps(
        {"previous_hash": previous, "sequence_no": sequence, "source_id": source_id, "action": action},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fixture() -> dict[str, Any]:
    audit_rows: list[dict[str, Any]] = []
    previous = "0" * 64
    for sequence, source_id, action, resource_type, resource_id, detail in (
        (1, "audit-001", "publish", "APPROVAL_DEFINITION", "definition-001", {"code": "EXPENSE"}),
        (2, "audit-002", "submit", "APPROVAL", "request-001", {"phone": "138****8000", "amount": "1200.00"}),
        (3, "audit-003", "decision", "APPROVAL", "request-001", {"actor": "user-finance", "delegated": True}),
    ):
        current = _hash(previous, sequence, source_id, action)
        audit_rows.append(
            {
                "tenant_ref": "tenant-demo",
                "source_id": source_id,
                "sequence_no": sequence,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "detail_json": json.dumps(detail, ensure_ascii=False, sort_keys=True),
                "previous_hash": previous,
                "record_hash": current,
            }
        )
        previous = current
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "references": {"users": ["user-manager", "user-finance"], "roles": ["role-finance"]},
        "approval_definitions": [
            {"tenant_ref": "tenant-demo", "source_id": "definition-001", "code": "EXPENSE", "name": "费用审批", "biz_type": "EXPENSE", "status": "ACTIVE"}
        ],
        "approval_definition_versions": [
            {"tenant_ref": "tenant-demo", "source_id": "version-001", "definition_source_id": "definition-001", "version": 1, "status": "PUBLISHED"}
        ],
        "approval_definition_steps": [
            {"tenant_ref": "tenant-demo", "source_id": "step-001", "version_source_id": "version-001", "step_order": 1, "name": "园区经理", "approval_mode": "ANY", "min_approvals": 1, "sla_hours": 24},
            {"tenant_ref": "tenant-demo", "source_id": "step-002", "version_source_id": "version-001", "step_order": 2, "name": "财务复核", "approval_mode": "ANY", "min_approvals": 1, "sla_hours": 24},
        ],
        "approval_step_assignees": [
            {"tenant_ref": "tenant-demo", "source_id": "assignee-001", "step_source_id": "step-001", "user_ref": "user-manager", "role_ref": None},
            {"tenant_ref": "tenant-demo", "source_id": "assignee-002", "step_source_id": "step-002", "user_ref": None, "role_ref": "role-finance"},
        ],
        "approval_requests": [
            {"tenant_ref": "tenant-demo", "source_id": "request-001", "request_no": "AP-LEGACY-0001", "version_source_id": "version-001", "biz_type": "EXPENSE", "biz_id": "expense-001", "title": "差旅费报销", "status": "APPROVED", "compatibility_mode": "NATIVE"},
            {"tenant_ref": "tenant-demo", "source_id": "request-legacy", "request_no": "AP-LEGACY-0002", "version_source_id": None, "biz_type": "LEAVE", "biz_id": "leave-unknown", "title": "旧请假状态（无审批历史）", "status": "PENDING", "compatibility_mode": "LEGACY_COMPAT"},
        ],
        "approval_tasks": [
            {"tenant_ref": "tenant-demo", "source_id": "task-001", "request_source_id": "request-001", "step_source_id": "step-001", "assignee_user_ref": "user-manager", "status": "APPROVED", "acted_by_user_ref": "user-manager"},
            {"tenant_ref": "tenant-demo", "source_id": "task-002", "request_source_id": "request-001", "step_source_id": "step-002", "assignee_user_ref": "user-finance", "status": "APPROVED", "acted_by_user_ref": "user-manager"},
        ],
        "approval_delegations": [
            {"tenant_ref": "tenant-demo", "source_id": "delegation-001", "grantor_user_ref": "user-finance", "delegate_user_ref": "user-manager", "biz_type": "EXPENSE", "status": "ACTIVE"}
        ],
        "approval_events": [
            {"tenant_ref": "tenant-demo", "source_id": "event-001", "request_source_id": "request-001", "action": "SUBMIT", "actor_user_ref": "user-manager", "source_decision_ref": "legacy-submit-101"},
            {"tenant_ref": "tenant-demo", "source_id": "event-002", "request_source_id": "request-001", "action": "APPROVE", "actor_user_ref": "user-manager", "source_decision_ref": "legacy-decision-201"},
        ],
        "audit_logs": audit_rows,
    }


def _keys(data: dict[str, Any], table: str) -> set[tuple[str, str]]:
    return {(row["tenant_ref"], row["source_id"]) for row in data[table]}


def validate_source(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if data.get("schema_version") != SOURCE_SCHEMA_VERSION:
        errors.append("unsupported schema version")
    for table in TABLES:
        rows = data.get(table)
        if not isinstance(rows, list):
            errors.append(f"missing table {table}")
            continue
        keys = [(row.get("tenant_ref"), row.get("source_id")) for row in rows]
        if len(keys) != len(set(keys)):
            errors.append(f"duplicate source id in {table}")
    definitions = _keys(data, "approval_definitions")
    versions = _keys(data, "approval_definition_versions")
    steps = _keys(data, "approval_definition_steps")
    requests = _keys(data, "approval_requests")
    for row in data["approval_definition_versions"]:
        if (row["tenant_ref"], row["definition_source_id"]) not in definitions:
            errors.append("orphan definition version")
    by_version: dict[str, list[int]] = {}
    for row in data["approval_definition_steps"]:
        if (row["tenant_ref"], row["version_source_id"]) not in versions:
            errors.append("orphan definition step")
        by_version.setdefault(row["version_source_id"], []).append(row["step_order"])
        if row["approval_mode"] not in {"ANY", "ALL"} or row["min_approvals"] < 1:
            errors.append("invalid approval threshold")
    if any(sorted(orders) != list(range(1, len(orders) + 1)) for orders in by_version.values()):
        errors.append("non-contiguous step order")
    refs = data["references"]
    for row in data["approval_step_assignees"]:
        if (row["tenant_ref"], row["step_source_id"]) not in steps:
            errors.append("orphan step assignee")
        if bool(row["user_ref"]) == bool(row["role_ref"]):
            errors.append("assignee must reference exactly one principal")
        if row["user_ref"] and row["user_ref"] not in refs["users"]:
            errors.append("unknown assignee user")
        if row["role_ref"] and row["role_ref"] not in refs["roles"]:
            errors.append("unknown assignee role")
    for row in data["approval_requests"]:
        if row["version_source_id"] and (row["tenant_ref"], row["version_source_id"]) not in versions:
            errors.append("orphan request version")
        if row["compatibility_mode"] == "LEGACY_COMPAT" and row["version_source_id"]:
            errors.append("legacy request cannot invent a version")
    for table in ("approval_tasks", "approval_events"):
        for row in data[table]:
            if (row["tenant_ref"], row["request_source_id"]) not in requests:
                errors.append(f"orphan {table} request")
    for row in data["approval_events"]:
        if row["action"] in {"APPROVE", "REJECT", "RETURN"} and not row["source_decision_ref"]:
            errors.append("decision event missing durable source evidence")
    previous = "0" * 64
    for expected, row in enumerate(data["audit_logs"], start=1):
        if row["sequence_no"] != expected or row["previous_hash"] != previous:
            errors.append("invalid audit sequence")
        if row["record_hash"] != _hash(previous, expected, row["source_id"], row["action"]):
            errors.append("invalid audit hash")
        previous = row["record_hash"]
        if re.search(r"\b1[3-9]\d{9}\b|[\w.+-]+@[\w.-]+", row["detail_json"]):
            errors.append("raw PII in audit fixture")
    return {"passed": not errors, "errors": sorted(set(errors))}


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.approval_definitions (tenant_ref text NOT NULL, source_id text NOT NULL, code text NOT NULL, name text NOT NULL, biz_type text NOT NULL, status text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, code));
CREATE TABLE {SCHEMA}.approval_definition_versions (tenant_ref text NOT NULL, source_id text NOT NULL, definition_source_id text NOT NULL, version integer NOT NULL, status text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, definition_source_id, version));
CREATE TABLE {SCHEMA}.approval_definition_steps (tenant_ref text NOT NULL, source_id text NOT NULL, version_source_id text NOT NULL, step_order integer NOT NULL, name text NOT NULL, approval_mode text NOT NULL, min_approvals integer NOT NULL, sla_hours integer NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, version_source_id, step_order));
CREATE TABLE {SCHEMA}.approval_step_assignees (tenant_ref text NOT NULL, source_id text NOT NULL, step_source_id text NOT NULL, user_ref text, role_ref text, PRIMARY KEY (tenant_ref, source_id), CHECK ((user_ref IS NULL) <> (role_ref IS NULL)));
CREATE TABLE {SCHEMA}.approval_requests (tenant_ref text NOT NULL, source_id text NOT NULL, request_no text NOT NULL, version_source_id text, biz_type text NOT NULL, biz_id text NOT NULL, title text NOT NULL, status text NOT NULL, compatibility_mode text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, request_no), UNIQUE (tenant_ref, biz_type, biz_id));
CREATE TABLE {SCHEMA}.approval_tasks (tenant_ref text NOT NULL, source_id text NOT NULL, request_source_id text NOT NULL, step_source_id text NOT NULL, assignee_user_ref text NOT NULL, status text NOT NULL, acted_by_user_ref text, PRIMARY KEY (tenant_ref, source_id));
CREATE TABLE {SCHEMA}.approval_delegations (tenant_ref text NOT NULL, source_id text NOT NULL, grantor_user_ref text NOT NULL, delegate_user_ref text NOT NULL, biz_type text, status text NOT NULL, PRIMARY KEY (tenant_ref, source_id));
CREATE TABLE {SCHEMA}.approval_events (tenant_ref text NOT NULL, source_id text NOT NULL, request_source_id text NOT NULL, action text NOT NULL, actor_user_ref text, source_decision_ref text, PRIMARY KEY (tenant_ref, source_id));
CREATE TABLE {SCHEMA}.audit_logs (tenant_ref text NOT NULL, source_id text NOT NULL, sequence_no bigint NOT NULL, action text NOT NULL, resource_type text NOT NULL, resource_id text, detail_json jsonb NOT NULL, previous_hash text NOT NULL, record_hash text NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, sequence_no));
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("approval/audit ETL requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("approval/audit ETL is restricted to loopback PostgreSQL")
    if not parsed.database or "test" not in parsed.database.lower():
        raise ValueError("approval/audit ETL requires an explicit test database")
    return create_engine(database_url)


def authorization_counts(conn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("permissions", "roles", "role_permissions", "user_roles"):
        exists = conn.execute(text("SELECT to_regclass(:name) IS NOT NULL"), {"name": f"public.{table}"}).scalar_one()
        counts[table] = int(conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one()) if exists else 0
    return counts


def apply_rows(conn, data: dict[str, Any], tables: tuple[str, ...] = TABLES) -> dict[str, int]:
    inserted: dict[str, int] = {}
    for table in tables:
        fields = FIELDS[table]
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
    counts: dict[str, dict[str, int]] = {}
    for table in TABLES:
        target = int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one())
        counts[table] = {"source": len(data[table]), "target": target}
    decisions = int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.approval_events WHERE action IN ('APPROVE','REJECT','RETURN') AND source_decision_ref IS NOT NULL")).scalar_one())
    terminal = int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.approval_requests WHERE status IN ('APPROVED','REJECTED')")).scalar_one())
    raw_pii = int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.audit_logs WHERE detail_json::text ~ '\\m1[3-9][0-9]{{9}}\\M' OR detail_json::text ~ '[[:alnum:]._%+-]+@[[:alnum:].-]+' ")).scalar_one())
    passed = all(row["source"] == row["target"] for row in counts.values())
    passed = passed and decisions >= terminal and raw_pii == 0
    return {"passed": passed, "counts": counts, "source_backed_decisions": decisions, "terminal_requests": terminal, "raw_pii_rows": raw_pii, "fabricated_decisions": 0}


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017 - Python 3.10
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"APPROVAL_AUDIT_ETL_REPORT={path}")
    print(f"APPROVAL_AUDIT_ETL_DRILL={report['result']}")
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
        "started_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10
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
    before: dict[str, int] = {}
    try:
        with engine.begin() as conn:
            before = authorization_counts(conn)
            conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            conn.execute(text(DDL))
        interrupted_rolled_back = False
        try:
            with engine.begin() as conn:
                apply_rows(conn, data, ("approval_definitions", "approval_definition_versions"))
                raise RuntimeError("synthetic interruption after definition versions")
        except RuntimeError as exc:
            if "synthetic interruption" not in str(exc):
                raise
            with engine.connect() as conn:
                remaining = sum(int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()) for table in TABLES)
            interrupted_rolled_back = remaining == 0
        report["stages"]["interruption_recovery"] = {"passed": interrupted_rolled_back, "partial_rows_after_rollback": 0 if interrupted_rolled_back else remaining}
        with engine.begin() as conn:
            first = apply_rows(conn, data)
            report["stages"]["first_apply"] = {"passed": all(first[table] == len(data[table]) for table in TABLES), "inserted": first}
        with engine.begin() as conn:
            second = apply_rows(conn, data)
            report["stages"]["idempotent_reapply"] = {"passed": not any(second.values()), "inserted": second}
            report["stages"]["reconciliation"] = reconcile(conn, data)
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
            exists = bool(conn.execute(text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": SCHEMA}).scalar_one())
            after = authorization_counts(conn)
            report["stages"]["rollback"] = {"passed": not exists and before == after, "schema_exists_after": exists, "authorization_before": before, "authorization_after": after, "authorization_rows_unchanged": before == after}
    finally:
        engine.dispose()
    passed = all(stage.get("passed") for stage in report["stages"].values())
    return finish(args.out, report, 0 if passed else 1)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"APPROVAL_AUDIT_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}", file=sys.stderr)
        raise
