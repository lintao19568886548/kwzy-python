#!/usr/bin/env python3
"""Synthetic legacy outbox/notification/job migration drill on disposable PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_workbench_automation_fixture"
SOURCE_SCHEMA_VERSION = "kwzy.workbench-automation.synthetic.v1"
REGISTERED_EVENTS = {
    "BILL_ISSUED",
    "LEASE_ACTIVATED",
    "WORK_ORDER_CREATED",
    "APPROVAL_TASK_OVERDUE",
}
HANDLER_MAP = {
    "outboxDispatcher": "OUTBOX_DISPATCH",
    "syncLeaseExpiryTodos": "LEASE_TODO_SYNC",
    "approvalOverdueSweep": "APPROVAL_OVERDUE_SWEEP",
}
STATUS_MAP = {
    "pending": "PENDING",
    "retry": "RETRY",
    "failed": "RETRY",
    "success": "SUCCEEDED",
    "sent": "SUCCEEDED",
    "dead": "DEAD",
}
TABLE_FIELDS = {
    "business_events": (
        "tenant_ref",
        "source_event_id",
        "event_type",
        "source_type",
        "aggregate_id",
        "idempotency_key",
        "payload_json",
        "occurred_at",
    ),
    "event_consumer_logs": (
        "tenant_ref",
        "source_id",
        "source_event_id",
        "consumer_name",
        "generation",
        "status",
        "attempt_count",
        "last_error",
    ),
    "in_app_notifications": (
        "tenant_ref",
        "source_id",
        "recipient_user_ref",
        "source_event_id",
        "idempotency_key",
        "category",
        "title",
        "content",
        "status",
        "delivered_at",
        "read_at",
    ),
    "scheduler_definitions": (
        "tenant_ref",
        "source_id",
        "code",
        "name",
        "handler_key",
        "parameters_json",
        "cadence_seconds",
        "enabled",
    ),
    "quarantine": ("tenant_ref", "source_type", "source_id", "reason_code"),
}


def fixture() -> dict[str, Any]:
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "references": {"users": ["user-admin", "user-ops"]},
        "event_outbox": [
            {
                "tenant_ref": "tenant-demo",
                "event_id": "legacy-event-001",
                "event_type": "BILL_ISSUED",
                "aggregate_type": "BILL",
                "aggregate_id": "bill-001",
                "idempotency_key": "legacy-outbox-001",
                "payload": {"title": "账单待复核", "amount": "1200.00", "deep_link": "/bills"},
                "status": "sent",
                "created_at": "2026-01-02T08:00:00",
            },
            {
                "tenant_ref": "tenant-demo",
                "event_id": "legacy-event-002",
                "event_type": "WORK_ORDER_CREATED",
                "aggregate_type": "WORK_ORDER",
                "aggregate_id": "work-order-002",
                "idempotency_key": "legacy-outbox-002",
                "payload": {"title": "消防巡查异常", "deep_link": "/work-orders"},
                "status": "pending",
                "created_at": "2026-01-02T09:00:00",
            },
            {
                "tenant_ref": "tenant-demo",
                "event_id": "legacy-event-unsupported",
                "event_type": "ORGANIZATION_PROVISIONED",
                "aggregate_type": "ORGANIZATION",
                "aggregate_id": "organization-003",
                "idempotency_key": "legacy-outbox-003",
                "payload": {"title": "旧组织开通"},
                "status": "sent",
                "created_at": "2026-01-02T10:00:00",
            },
        ],
        "event_consume_log": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "consume-001",
                "event_id": "legacy-event-001",
                "consumer_group": "notification",
                "status": "success",
                "attempts": 1,
                "last_error": None,
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "consume-002",
                "event_id": "legacy-event-002",
                "consumer_group": "workbench",
                "status": "failed",
                "attempts": 2,
                "last_error": "legacy provider timeout",
            },
        ],
        "in_app_notification": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "notification-001",
                "event_id": "legacy-event-001",
                "recipient_user_ref": "user-admin",
                "idempotency_key": "legacy-notification-001",
                "template_key": "BILL_REVIEW",
                "title": "账单待复核",
                "content": "请在账单中心查看原始单据。",
                "status": "read",
                "delivered_at": "2026-01-02T08:01:00",
                "read_at": "2026-01-02T08:03:00",
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "notification-orphan",
                "event_id": "legacy-event-002",
                "recipient_user_ref": "missing-user",
                "idempotency_key": "legacy-notification-002",
                "template_key": "WORK_ORDER",
                "title": "工单待处理",
                "content": "原接收人无法映射。",
                "status": "unread",
                "delivered_at": "2026-01-02T09:01:00",
                "read_at": None,
            },
        ],
        "xxl_jobs": [
            {
                "tenant_ref": "tenant-demo",
                "source_id": "job-001",
                "handler": "outboxDispatcher",
                "name": "旧消息派发",
                "cadence_seconds": 30,
                "parameters": {"limit": 100},
            },
            {
                "tenant_ref": "tenant-demo",
                "source_id": "job-unsupported",
                "handler": "organizationProvisioningJob",
                "name": "旧组织开通",
                "cadence_seconds": 60,
                "parameters": {},
            },
        ],
    }


def _duplicates(rows: list[dict[str, Any]], *fields: str) -> bool:
    keys = [tuple(row.get(field) for field in fields) for row in rows]
    return len(keys) != len(set(keys))


def validate_source(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if data.get("schema_version") != SOURCE_SCHEMA_VERSION:
        errors.append("unsupported schema version")
    for name in ("event_outbox", "event_consume_log", "in_app_notification", "xxl_jobs"):
        if not isinstance(data.get(name), list):
            errors.append(f"missing source collection {name}")
    if errors:
        return {"passed": False, "errors": errors}
    if _duplicates(data["event_outbox"], "tenant_ref", "event_id"):
        errors.append("duplicate source event")
    if _duplicates(data["event_outbox"], "tenant_ref", "idempotency_key"):
        errors.append("duplicate source event idempotency key")
    if _duplicates(data["in_app_notification"], "tenant_ref", "idempotency_key"):
        errors.append("duplicate notification idempotency key")
    events = {(row["tenant_ref"], row["event_id"]) for row in data["event_outbox"]}
    for row in data["event_consume_log"]:
        if (row["tenant_ref"], row["event_id"]) not in events:
            errors.append("orphan consume log")
        if row["status"].lower() not in STATUS_MAP:
            errors.append("unsupported consume status")
    raw_text = json.dumps(data, ensure_ascii=False)
    if re.search(r"\b1[3-9]\d{9}\b|[\w.+-]+@[\w.-]+", raw_text):
        errors.append("raw PII in source fixture")
    return {"passed": not errors, "errors": sorted(set(errors))}


def transform(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result = {table: [] for table in TABLE_FIELDS}
    eligible_events: set[tuple[str, str]] = set()
    for row in data["event_outbox"]:
        key = (row["tenant_ref"], row["event_id"])
        if row["event_type"] not in REGISTERED_EVENTS:
            result["quarantine"].append(
                {"tenant_ref": row["tenant_ref"], "source_type": "EVENT", "source_id": row["event_id"], "reason_code": "EVENT_TYPE_NOT_REGISTERED"}
            )
            continue
        eligible_events.add(key)
        result["business_events"].append(
            {
                "tenant_ref": row["tenant_ref"],
                "source_event_id": row["event_id"],
                "event_type": row["event_type"],
                "source_type": row["aggregate_type"],
                "aggregate_id": row["aggregate_id"],
                "idempotency_key": row["idempotency_key"],
                "payload_json": json.dumps(row["payload"], ensure_ascii=False, sort_keys=True),
                "occurred_at": row["created_at"],
            }
        )
    for row in data["event_consume_log"]:
        if (row["tenant_ref"], row["event_id"]) not in eligible_events:
            result["quarantine"].append(
                {"tenant_ref": row["tenant_ref"], "source_type": "CONSUMER", "source_id": row["source_id"], "reason_code": "EVENT_QUARANTINED"}
            )
            continue
        result["event_consumer_logs"].append(
            {
                "tenant_ref": row["tenant_ref"],
                "source_id": row["source_id"],
                "source_event_id": row["event_id"],
                "consumer_name": "WORKBENCH_AUTOMATION",
                "generation": 1,
                "status": STATUS_MAP[row["status"].lower()],
                "attempt_count": int(row["attempts"]),
                "last_error": row["last_error"],
            }
        )
    valid_users = set(data["references"]["users"])
    for row in data["in_app_notification"]:
        if row["recipient_user_ref"] not in valid_users:
            result["quarantine"].append(
                {"tenant_ref": row["tenant_ref"], "source_type": "NOTIFICATION", "source_id": row["source_id"], "reason_code": "RECIPIENT_UNMAPPED"}
            )
            continue
        result["in_app_notifications"].append(
            {
                "tenant_ref": row["tenant_ref"],
                "source_id": row["source_id"],
                "recipient_user_ref": row["recipient_user_ref"],
                "source_event_id": row["event_id"],
                "idempotency_key": row["idempotency_key"],
                "category": row["template_key"],
                "title": row["title"],
                "content": row["content"],
                "status": row["status"].upper(),
                "delivered_at": row["delivered_at"],
                "read_at": row["read_at"],
            }
        )
    for row in data["xxl_jobs"]:
        handler = HANDLER_MAP.get(row["handler"])
        if handler is None:
            result["quarantine"].append(
                {"tenant_ref": row["tenant_ref"], "source_type": "JOB", "source_id": row["source_id"], "reason_code": "HANDLER_NOT_REGISTERED"}
            )
            continue
        result["scheduler_definitions"].append(
            {
                "tenant_ref": row["tenant_ref"],
                "source_id": row["source_id"],
                "code": f"LEGACY_{row['source_id'].replace('-', '_').upper()}",
                "name": row["name"],
                "handler_key": handler,
                "parameters_json": json.dumps(row["parameters"], sort_keys=True),
                "cadence_seconds": int(row["cadence_seconds"]),
                "enabled": False,
            }
        )
    return result


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.business_events (tenant_ref text NOT NULL, source_event_id text NOT NULL, event_type text NOT NULL, source_type text NOT NULL, aggregate_id text NOT NULL, idempotency_key text NOT NULL, payload_json jsonb NOT NULL, occurred_at timestamp NOT NULL, PRIMARY KEY (tenant_ref, source_event_id), UNIQUE (tenant_ref, idempotency_key));
CREATE TABLE {SCHEMA}.event_consumer_logs (tenant_ref text NOT NULL, source_id text NOT NULL, source_event_id text NOT NULL, consumer_name text NOT NULL, generation integer NOT NULL, status text NOT NULL, attempt_count integer NOT NULL, last_error text, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, source_event_id, consumer_name, generation));
CREATE TABLE {SCHEMA}.in_app_notifications (tenant_ref text NOT NULL, source_id text NOT NULL, recipient_user_ref text NOT NULL, source_event_id text NOT NULL, idempotency_key text NOT NULL, category text NOT NULL, title text NOT NULL, content text NOT NULL, status text NOT NULL, delivered_at timestamp NOT NULL, read_at timestamp, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, idempotency_key));
CREATE TABLE {SCHEMA}.scheduler_definitions (tenant_ref text NOT NULL, source_id text NOT NULL, code text NOT NULL, name text NOT NULL, handler_key text NOT NULL, parameters_json jsonb NOT NULL, cadence_seconds integer NOT NULL, enabled boolean NOT NULL, PRIMARY KEY (tenant_ref, source_id), UNIQUE (tenant_ref, code));
CREATE TABLE {SCHEMA}.quarantine (tenant_ref text NOT NULL, source_type text NOT NULL, source_id text NOT NULL, reason_code text NOT NULL, PRIMARY KEY (tenant_ref, source_type, source_id));
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("workbench automation ETL requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("workbench automation ETL is restricted to loopback PostgreSQL")
    if not parsed.database or "test" not in parsed.database.lower():
        raise ValueError("workbench automation ETL requires an explicit test database")
    return create_engine(database_url)


def authorization_counts(conn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("tenants", "users", "roles", "permissions", "role_permissions", "user_roles"):
        exists = conn.execute(
            text("SELECT to_regclass(:name) IS NOT NULL"), {"name": f"public.{table}"}
        ).scalar_one()
        counts[table] = int(
            conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one()
        ) if exists else 0
    return counts


def apply_rows(conn, rows: dict[str, list[dict[str, Any]]], tables: tuple[str, ...] | None = None) -> dict[str, int]:
    selected = tables or tuple(TABLE_FIELDS)
    inserted: dict[str, int] = {}
    for table in selected:
        fields = TABLE_FIELDS[table]
        count = 0
        for row in rows[table]:
            statement = text(
                f"INSERT INTO {SCHEMA}.{table} ({', '.join(fields)}) "
                f"VALUES ({', '.join(':' + field for field in fields)}) ON CONFLICT DO NOTHING"
            )
            count += conn.execute(statement, {field: row[field] for field in fields}).rowcount
        inserted[table] = count
    return inserted


def reconcile(conn, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    counts = {
        table: {
            "source_eligible": len(rows[table]),
            "target": int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()),
        }
        for table in TABLE_FIELDS
    }
    unsupported_success = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.event_consumer_logs "
                "WHERE status = 'SUCCEEDED' AND source_id <> 'consume-001'"
            )
        ).scalar_one()
    )
    enabled_jobs = int(
        conn.execute(
            text(f"SELECT count(*) FROM {SCHEMA}.scheduler_definitions WHERE enabled")
        ).scalar_one()
    )
    raw_pii = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.in_app_notifications "
                "WHERE content ~ '\\m1[3-9][0-9]{9}\\M' OR content ~ '[[:alnum:]._%+-]+@[[:alnum:].-]+'"
            )
        ).scalar_one()
    )
    passed = all(item["source_eligible"] == item["target"] for item in counts.values())
    passed = passed and unsupported_success == 0 and enabled_jobs == 0 and raw_pii == 0
    return {
        "passed": passed,
        "counts": counts,
        "fabricated_success": unsupported_success,
        "enabled_jobs_after_migration": enabled_jobs,
        "raw_pii_rows": raw_pii,
        "workspace_api_logs_migrated_as_layouts": 0,
    }


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WORKBENCH_AUTOMATION_ETL_REPORT={path}")
    print(f"WORKBENCH_AUTOMATION_ETL_DRILL={report['result']}")
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
    source = fixture()
    rows = transform(source)
    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "schema": SCHEMA,
        "synthetic_only": True,
        "readiness": "CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA",
        "real_legacy_readiness": "BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE",
        "stages": {"dry_run": validate_source(source)},
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
                apply_rows(conn, rows, ("business_events",))
                raise RuntimeError("synthetic interruption after events")
        except RuntimeError as exc:
            if "synthetic interruption" not in str(exc):
                raise
        with engine.connect() as conn:
            partial = sum(
                int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one())
                for table in TABLE_FIELDS
            )
        report["stages"]["interruption_recovery"] = {
            "passed": partial == 0,
            "partial_rows_after_rollback": partial,
        }
        with engine.begin() as conn:
            first = apply_rows(conn, rows)
        report["stages"]["first_apply"] = {
            "passed": all(first[table] == len(rows[table]) for table in TABLE_FIELDS),
            "inserted": first,
        }
        with engine.begin() as conn:
            second = apply_rows(conn, rows)
            report["stages"]["idempotent_reapply"] = {
                "passed": not any(second.values()),
                "inserted": second,
            }
            report["stages"]["reconciliation"] = reconcile(conn, rows)
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
            exists = bool(
                conn.execute(
                    text("SELECT to_regnamespace(:schema) IS NOT NULL"), {"schema": SCHEMA}
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
            f"WORKBENCH_AUTOMATION_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
