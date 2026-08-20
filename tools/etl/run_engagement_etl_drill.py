#!/usr/bin/env python3
"""Synthetic engagement migration rehearsal restricted to loopback PostgreSQL.

The drill proves deterministic source keys, provenance, dry-run validation,
transactional interruption recovery, checkpoint/resume, idempotent replay,
reconciliation, run-scoped rollback and logical backup/delete/restore. It does
not read a live legacy database or authorize production contact/cutover.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_engagement_fixture"
RUN_ID = "engagement-synthetic-v1"
PRESERVE_RUN_ID = "unrelated-preserved-run"
TABLES = (
    "policies",
    "policy_versions",
    "service_catalogs",
    "service_cases",
    "activities",
    "activity_versions",
    "registrations",
    "announcements",
    "announcement_versions",
    "announcement_targets",
    "announcement_deliveries",
    "quarantine",
)
MIGRATED_AT = datetime(2026, 8, 20, tzinfo=timezone.utc)
SYNTHETIC_PEPPER = "kwzy-engagement-etl-synthetic-only-v1"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fingerprint(value: str) -> str:
    return digest(f"{SYNTHETIC_PEPPER}:{value.strip()}")


def source_key(kind: str, value: str) -> str:
    return f"engagement-v1:{kind}:{value.strip()}"


def canonical_hash(value: Any) -> str:
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


SOURCE_ARRAYS = (
    "parks",
    "parties",
    "policies",
    "services",
    "service_cases",
    "activities",
    "registrations",
    "announcements",
    "deliveries",
)


def load_fixture(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("contains_real_customer_data") is not False:
        raise ValueError("fixture must declare contains_real_customer_data=false")
    if source.get("authoritative_legacy_schema_present") is not False:
        raise ValueError("synthetic drill cannot claim an authoritative legacy schema")
    if source.get("authorized_legacy_exports_present") is not False:
        raise ValueError("synthetic drill cannot claim authorized legacy exports")
    for name in SOURCE_ARRAYS:
        if not isinstance(source.get(name), list):
            raise TypeError(f"fixture {name} must be an array")
    return source


def validate_source(source: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for name in SOURCE_ARRAYS:
        keys = [str(row.get("source_id", "")) for row in source[name]]
        if any(not key for key in keys):
            errors.append(f"{name}:blank source_id")
        if len(keys) != len(set(keys)):
            errors.append(f"{name}:duplicate source_id")
    for row in source["activities"]:
        if int(row.get("capacity") or 0) < 1:
            errors.append(f"activity:{row.get('source_id', '?')}:invalid capacity")
        values = [
            parse_time(row.get("registration_opens_at")),
            parse_time(row.get("registration_closes_at")),
            parse_time(row.get("starts_at")),
            parse_time(row.get("ends_at")),
        ]
        if not all(values) or values != sorted(values):
            errors.append(f"activity:{row.get('source_id', '?')}:invalid schedule")
    return {
        "passed": not errors,
        "errors": errors,
        "source_counts": {name: len(source[name]) for name in SOURCE_ARRAYS},
    }


def transform(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
    parks = {str(row["source_id"]): str(row["target_ref"]) for row in source["parks"]}
    parties = {str(row["source_id"]): str(row["target_ref"]) for row in source["parties"]}
    policy_keys: dict[str, str] = {}
    service_keys: dict[str, str] = {}
    activity_keys: dict[str, str] = {}
    announcement_keys: dict[str, str] = {}

    def quarantine(kind: str, source_id: str, issue_code: str, value: str) -> None:
        rows["quarantine"].append(
            {
                "source_key": source_key("quarantine", f"{kind}:{source_id}:{issue_code}"),
                "run_id": RUN_ID,
                "source_kind": kind,
                "source_identifier": source_id,
                "issue_code": issue_code,
                "value_fingerprint": fingerprint(value),
            }
        )

    for item in source["policies"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        if park_ref is None:
            quarantine("POLICY", source_id, "PARK_KEY_UNMAPPED", str(item["park_ref"]))
            continue
        if str(item["source_type"]).upper() == "GOVERNMENT_OFFICIAL":
            quarantine(
                "POLICY", source_id, "OFFICIAL_SOURCE_UNAUTHORIZED", str(item["source_identifier"])
            )
            continue
        effective_at = parse_time(item["effective_at"])
        expires_at = parse_time(item.get("expires_at"))
        if expires_at is not None and effective_at is not None and expires_at <= effective_at:
            quarantine("POLICY", source_id, "ACTIVE_WINDOW_INVALID", source_id)
            continue
        key = source_key("policy", source_id)
        version_key = source_key("policy-version", f"{source_id}:1")
        snapshot = {
            "title": str(item["title"]).strip(),
            "content_text": str(item["content_text"]).strip(),
            "source_publisher": str(item["source_publisher"]).strip(),
            "effective_at": item["effective_at"],
            "expires_at": item.get("expires_at"),
        }
        policy_keys[source_id] = key
        rows["policies"].append(
            {
                "source_key": key,
                "run_id": RUN_ID,
                "park_ref": park_ref,
                "status": "REVIEW_REQUIRED",
                "current_version": 1,
                "source_identifier": str(item["source_identifier"]),
            }
        )
        rows["policy_versions"].append(
            {
                "source_key": version_key,
                "run_id": RUN_ID,
                "policy_source_key": key,
                "version": 1,
                "title": snapshot["title"],
                "content_text": snapshot["content_text"],
                "source_publisher": snapshot["source_publisher"],
                "effective_at": effective_at,
                "expires_at": expires_at,
                "checksum": canonical_hash(snapshot),
                "approval_truth": "LEGACY_UNVERIFIED",
            }
        )

    for item in source["services"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        if park_ref is None:
            quarantine("SERVICE", source_id, "PARK_KEY_UNMAPPED", str(item["park_ref"]))
            continue
        provider_type = str(item["provider_type"]).upper()
        provider_state = str(item["provider_state"]).upper()
        if provider_type == "EXTERNAL" and provider_state != "NOT_CONNECTED":
            quarantine(
                "SERVICE",
                source_id,
                "EXTERNAL_PROVIDER_EVIDENCE_MISSING",
                f"{item['provider_name']}:{provider_state}",
            )
            continue
        key = source_key("service", source_id)
        snapshot = {
            "title": str(item["title"]).strip(),
            "provider_type": provider_type,
            "provider_name": str(item["provider_name"]).strip(),
            "provider_state": provider_state,
            "sla_hours": int(item["sla_hours"]),
        }
        service_keys[source_id] = key
        rows["service_catalogs"].append(
            {
                "source_key": key,
                "run_id": RUN_ID,
                "park_ref": park_ref,
                "title": snapshot["title"],
                "provider_type": provider_type,
                "provider_name": snapshot["provider_name"],
                "provider_state": provider_state,
                "sla_hours": snapshot["sla_hours"],
                "status": "REVIEW_REQUIRED",
                "checksum": canonical_hash(snapshot),
            }
        )

    for item in source["service_cases"]:
        source_id = str(item["source_id"])
        service_ref = service_keys.get(str(item["service_ref"]))
        party_ref = parties.get(str(item["party_ref"]))
        park_ref = parks.get(str(item["park_ref"]))
        if party_ref is None:
            quarantine("SERVICE_CASE", source_id, "PARTY_KEY_UNMAPPED", str(item["party_ref"]))
            continue
        if service_ref is None or park_ref is None:
            quarantine(
                "SERVICE_CASE",
                source_id,
                "CASE_REFERENCE_UNMAPPED",
                f"{item['service_ref']}:{item['park_ref']}",
            )
            continue
        rows["service_cases"].append(
            {
                "source_key": source_key("service-case", source_id),
                "run_id": RUN_ID,
                "service_source_key": service_ref,
                "park_ref": park_ref,
                "party_ref": party_ref,
                "subject": str(item["subject"]).strip(),
                "status": "REVIEW_REQUIRED",
                "source_status": str(item["source_status"]).upper(),
                "source_created_at": parse_time(item["created_at"]),
            }
        )

    for item in source["activities"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        if park_ref is None:
            quarantine("ACTIVITY", source_id, "PARK_KEY_UNMAPPED", str(item["park_ref"]))
            continue
        key = source_key("activity", source_id)
        version_key = source_key("activity-version", f"{source_id}:1")
        snapshot = {
            "title": str(item["title"]).strip(),
            "location": str(item["location"]).strip(),
            "capacity": int(item["capacity"]),
            "registration_opens_at": item["registration_opens_at"],
            "registration_closes_at": item["registration_closes_at"],
            "starts_at": item["starts_at"],
            "ends_at": item["ends_at"],
        }
        activity_keys[source_id] = key
        rows["activities"].append(
            {
                "source_key": key,
                "run_id": RUN_ID,
                "park_ref": park_ref,
                "status": "REVIEW_REQUIRED",
                "current_version": 1,
            }
        )
        rows["activity_versions"].append(
            {
                "source_key": version_key,
                "run_id": RUN_ID,
                "activity_source_key": key,
                "version": 1,
                "title": snapshot["title"],
                "location": snapshot["location"],
                "capacity": snapshot["capacity"],
                "confirmed_count": 0,
                "waitlist_count": 0,
                "registration_opens_at": parse_time(item["registration_opens_at"]),
                "registration_closes_at": parse_time(item["registration_closes_at"]),
                "starts_at": parse_time(item["starts_at"]),
                "ends_at": parse_time(item["ends_at"]),
                "checksum": canonical_hash(snapshot),
            }
        )

    activity_version_by_key = {row["activity_source_key"]: row for row in rows["activity_versions"]}
    for item in source["registrations"]:
        source_id = str(item["source_id"])
        activity_ref = activity_keys.get(str(item["activity_ref"]))
        party_ref = parties.get(str(item["party_ref"]))
        if activity_ref is None:
            quarantine(
                "REGISTRATION", source_id, "ACTIVITY_REFERENCE_UNMAPPED", str(item["activity_ref"])
            )
            continue
        if party_ref is None:
            quarantine("REGISTRATION", source_id, "PARTY_KEY_UNMAPPED", str(item["party_ref"]))
            continue
        status = str(item["source_status"]).upper()
        if status not in {"CONFIRMED", "WAITLISTED"}:
            quarantine("REGISTRATION", source_id, "REGISTRATION_STATUS_UNKNOWN", status)
            continue
        attendee_count = int(item["attendee_count"])
        version = activity_version_by_key[activity_ref]
        if status == "CONFIRMED" and int(version["confirmed_count"]) + attendee_count > int(
            version["capacity"]
        ):
            quarantine("REGISTRATION", source_id, "ACTIVITY_CAPACITY_EXCEEDED", str(attendee_count))
            continue
        if status == "CONFIRMED":
            version["confirmed_count"] = int(version["confirmed_count"]) + attendee_count
        else:
            version["waitlist_count"] = int(version["waitlist_count"]) + 1
        rows["registrations"].append(
            {
                "source_key": source_key("registration", source_id),
                "run_id": RUN_ID,
                "activity_source_key": activity_ref,
                "party_ref": party_ref,
                "status": status,
                "attendee_count": attendee_count,
                "source_truth": "SYNTHETIC_SOURCE_DECLARED",
            }
        )

    for item in source["announcements"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        audience_refs = [parties.get(str(value)) for value in item["audience_party_refs"]]
        if park_ref is None:
            quarantine("ANNOUNCEMENT", source_id, "PARK_KEY_UNMAPPED", str(item["park_ref"]))
            continue
        if any(value is None for value in audience_refs):
            quarantine(
                "ANNOUNCEMENT",
                source_id,
                "AUDIENCE_KEY_UNMAPPED",
                ":".join(str(value) for value in item["audience_party_refs"]),
            )
            continue
        key = source_key("announcement", source_id)
        snapshot = {
            "title": str(item["title"]).strip(),
            "content_text": str(item["content_text"]).strip(),
            "publish_at": item["publish_at"],
            "expires_at": item.get("expires_at"),
            "audience_party_refs": sorted(str(value) for value in audience_refs),
        }
        announcement_keys[source_id] = key
        rows["announcements"].append(
            {
                "source_key": key,
                "run_id": RUN_ID,
                "park_ref": park_ref,
                "status": "REVIEW_REQUIRED",
                "current_version": 1,
            }
        )
        rows["announcement_versions"].append(
            {
                "source_key": source_key("announcement-version", f"{source_id}:1"),
                "run_id": RUN_ID,
                "announcement_source_key": key,
                "version": 1,
                "title": snapshot["title"],
                "content_text": snapshot["content_text"],
                "publish_at": parse_time(item["publish_at"]),
                "expires_at": parse_time(item.get("expires_at")),
                "audience_snapshot": json.dumps(
                    snapshot["audience_party_refs"], ensure_ascii=False, sort_keys=True
                ),
                "target_count": len(audience_refs),
                "checksum": canonical_hash(snapshot),
            }
        )
        for party_ref in audience_refs:
            rows["announcement_targets"].append(
                {
                    "source_key": source_key("announcement-target", f"{source_id}:{party_ref}"),
                    "run_id": RUN_ID,
                    "announcement_source_key": key,
                    "party_ref": str(party_ref),
                    "snapshot_fingerprint": fingerprint(f"{source_id}:{party_ref}"),
                }
            )

    target_keys = {
        (row["announcement_source_key"], row["party_ref"]): row["source_key"]
        for row in rows["announcement_targets"]
    }
    for item in source["deliveries"]:
        source_id = str(item["source_id"])
        announcement_ref = announcement_keys.get(str(item["announcement_ref"]))
        party_ref = parties.get(str(item["party_ref"]))
        channel = str(item["channel"]).upper()
        if channel != "IN_APP":
            quarantine("DELIVERY", source_id, "EXTERNAL_CHANNEL_UNVERIFIED", channel)
            continue
        target_ref = target_keys.get((announcement_ref, party_ref))
        if announcement_ref is None or party_ref is None or target_ref is None:
            quarantine(
                "DELIVERY",
                source_id,
                "DELIVERY_TARGET_UNMAPPED",
                f"{item['announcement_ref']}:{item['party_ref']}",
            )
            continue
        status = str(item["source_status"]).upper()
        if status not in {"DELIVERED", "READ"}:
            quarantine("DELIVERY", source_id, "DELIVERY_STATUS_UNKNOWN", status)
            continue
        rows["announcement_deliveries"].append(
            {
                "source_key": source_key("announcement-delivery", source_id),
                "run_id": RUN_ID,
                "announcement_source_key": announcement_ref,
                "target_source_key": target_ref,
                "party_ref": party_ref,
                "channel": "IN_APP",
                "status": status,
                "delivered_at": parse_time(item.get("delivered_at")),
                "read_at": parse_time(item.get("read_at")),
                "external_contacted": False,
            }
        )
    return rows


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.migration_runs (
  run_id text PRIMARY KEY, fixture_sha256 char(64) NOT NULL, created_at timestamptz NOT NULL
);
CREATE TABLE {SCHEMA}.policies (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  park_ref text NOT NULL, status text NOT NULL CHECK(status='REVIEW_REQUIRED'), current_version integer NOT NULL,
  source_identifier text NOT NULL
);
CREATE TABLE {SCHEMA}.policy_versions (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  policy_source_key text NOT NULL REFERENCES {SCHEMA}.policies(source_key) ON DELETE CASCADE,
  version integer NOT NULL, title text NOT NULL, content_text text NOT NULL, source_publisher text NOT NULL,
  effective_at timestamptz NOT NULL, expires_at timestamptz, checksum char(64) NOT NULL,
  approval_truth text NOT NULL CHECK(approval_truth='LEGACY_UNVERIFIED'), UNIQUE(policy_source_key,version)
);
CREATE TABLE {SCHEMA}.service_catalogs (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  park_ref text NOT NULL, title text NOT NULL, provider_type text NOT NULL, provider_name text NOT NULL,
  provider_state text NOT NULL, sla_hours integer NOT NULL CHECK(sla_hours>0),
  status text NOT NULL CHECK(status='REVIEW_REQUIRED'), checksum char(64) NOT NULL
);
CREATE TABLE {SCHEMA}.service_cases (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  service_source_key text NOT NULL REFERENCES {SCHEMA}.service_catalogs(source_key), park_ref text NOT NULL,
  party_ref text NOT NULL, subject text NOT NULL, status text NOT NULL CHECK(status='REVIEW_REQUIRED'),
  source_status text NOT NULL, source_created_at timestamptz NOT NULL
);
CREATE TABLE {SCHEMA}.activities (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  park_ref text NOT NULL, status text NOT NULL CHECK(status='REVIEW_REQUIRED'), current_version integer NOT NULL
);
CREATE TABLE {SCHEMA}.activity_versions (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  activity_source_key text NOT NULL REFERENCES {SCHEMA}.activities(source_key) ON DELETE CASCADE,
  version integer NOT NULL, title text NOT NULL, location text NOT NULL, capacity integer NOT NULL CHECK(capacity>0),
  confirmed_count integer NOT NULL CHECK(confirmed_count>=0 AND confirmed_count<=capacity), waitlist_count integer NOT NULL CHECK(waitlist_count>=0),
  registration_opens_at timestamptz NOT NULL, registration_closes_at timestamptz NOT NULL,
  starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL, checksum char(64) NOT NULL,
  UNIQUE(activity_source_key,version)
);
CREATE TABLE {SCHEMA}.registrations (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  activity_source_key text NOT NULL REFERENCES {SCHEMA}.activities(source_key), party_ref text NOT NULL,
  status text NOT NULL CHECK(status IN ('CONFIRMED','WAITLISTED')), attendee_count integer NOT NULL CHECK(attendee_count>0),
  source_truth text NOT NULL CHECK(source_truth='SYNTHETIC_SOURCE_DECLARED'), UNIQUE(activity_source_key,party_ref)
);
CREATE TABLE {SCHEMA}.announcements (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  park_ref text NOT NULL, status text NOT NULL CHECK(status='REVIEW_REQUIRED'), current_version integer NOT NULL
);
CREATE TABLE {SCHEMA}.announcement_versions (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  announcement_source_key text NOT NULL REFERENCES {SCHEMA}.announcements(source_key) ON DELETE CASCADE,
  version integer NOT NULL, title text NOT NULL, content_text text NOT NULL, publish_at timestamptz NOT NULL,
  expires_at timestamptz, audience_snapshot text NOT NULL, target_count integer NOT NULL CHECK(target_count>=0),
  checksum char(64) NOT NULL, UNIQUE(announcement_source_key,version)
);
CREATE TABLE {SCHEMA}.announcement_targets (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  announcement_source_key text NOT NULL REFERENCES {SCHEMA}.announcements(source_key) ON DELETE CASCADE,
  party_ref text NOT NULL, snapshot_fingerprint char(64) NOT NULL, UNIQUE(announcement_source_key,party_ref)
);
CREATE TABLE {SCHEMA}.announcement_deliveries (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  announcement_source_key text NOT NULL REFERENCES {SCHEMA}.announcements(source_key) ON DELETE CASCADE,
  target_source_key text NOT NULL REFERENCES {SCHEMA}.announcement_targets(source_key) ON DELETE CASCADE,
  party_ref text NOT NULL, channel text NOT NULL CHECK(channel='IN_APP'),
  status text NOT NULL CHECK(status IN ('DELIVERED','READ')), delivered_at timestamptz,
  read_at timestamptz, external_contacted boolean NOT NULL CHECK(external_contacted=false),
  UNIQUE(announcement_source_key,party_ref,channel)
);
CREATE TABLE {SCHEMA}.quarantine (
  source_key text PRIMARY KEY, run_id text NOT NULL REFERENCES {SCHEMA}.migration_runs(run_id) ON DELETE CASCADE,
  source_kind text NOT NULL, source_identifier text NOT NULL, issue_code text NOT NULL,
  value_fingerprint char(64) NOT NULL, UNIQUE(run_id,source_kind,source_identifier,issue_code)
);
"""

FIELDS = {
    "policies": (
        "source_key",
        "run_id",
        "park_ref",
        "status",
        "current_version",
        "source_identifier",
    ),
    "policy_versions": (
        "source_key",
        "run_id",
        "policy_source_key",
        "version",
        "title",
        "content_text",
        "source_publisher",
        "effective_at",
        "expires_at",
        "checksum",
        "approval_truth",
    ),
    "service_catalogs": (
        "source_key",
        "run_id",
        "park_ref",
        "title",
        "provider_type",
        "provider_name",
        "provider_state",
        "sla_hours",
        "status",
        "checksum",
    ),
    "service_cases": (
        "source_key",
        "run_id",
        "service_source_key",
        "park_ref",
        "party_ref",
        "subject",
        "status",
        "source_status",
        "source_created_at",
    ),
    "activities": ("source_key", "run_id", "park_ref", "status", "current_version"),
    "activity_versions": (
        "source_key",
        "run_id",
        "activity_source_key",
        "version",
        "title",
        "location",
        "capacity",
        "confirmed_count",
        "waitlist_count",
        "registration_opens_at",
        "registration_closes_at",
        "starts_at",
        "ends_at",
        "checksum",
    ),
    "registrations": (
        "source_key",
        "run_id",
        "activity_source_key",
        "party_ref",
        "status",
        "attendee_count",
        "source_truth",
    ),
    "announcements": ("source_key", "run_id", "park_ref", "status", "current_version"),
    "announcement_versions": (
        "source_key",
        "run_id",
        "announcement_source_key",
        "version",
        "title",
        "content_text",
        "publish_at",
        "expires_at",
        "audience_snapshot",
        "target_count",
        "checksum",
    ),
    "announcement_targets": (
        "source_key",
        "run_id",
        "announcement_source_key",
        "party_ref",
        "snapshot_fingerprint",
    ),
    "announcement_deliveries": (
        "source_key",
        "run_id",
        "announcement_source_key",
        "target_source_key",
        "party_ref",
        "channel",
        "status",
        "delivered_at",
        "read_at",
        "external_contacted",
    ),
    "quarantine": (
        "source_key",
        "run_id",
        "source_kind",
        "source_identifier",
        "issue_code",
        "value_fingerprint",
    ),
}


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("engagement ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("engagement ETL drill is restricted to loopback PostgreSQL")
    identity = (parsed.database or "").lower()
    if "prod" in identity or not any(
        word in identity for word in ("test", "local", "dev", "audit")
    ):
        raise ValueError("engagement ETL drill refuses a production-like database identity")
    return create_engine(database_url, pool_pre_ping=True)


def create_schema(conn, fixture_hash: str) -> None:  # type: ignore[no-untyped-def]
    conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    for statement in DDL.split(";"):
        if statement.strip():
            conn.execute(text(statement))
    conn.execute(
        text(
            f"INSERT INTO {SCHEMA}.migration_runs(run_id,fixture_sha256,created_at) VALUES (:run_id,:fixture_hash,:created_at)"
        ),
        {"run_id": RUN_ID, "fixture_hash": fixture_hash, "created_at": MIGRATED_AT},
    )
    conn.execute(
        text(
            f"INSERT INTO {SCHEMA}.migration_runs(run_id,fixture_sha256,created_at) VALUES (:run_id,:fixture_hash,:created_at)"
        ),
        {"run_id": PRESERVE_RUN_ID, "fixture_hash": "0" * 64, "created_at": MIGRATED_AT},
    )


def counts(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one())
        for table in TABLES
    }


def apply_rows(
    conn,
    rows: dict[str, list[dict[str, Any]]],
    *,
    interrupt: bool = False,
    stop_after: str | None = None,
) -> dict[str, int]:  # type: ignore[no-untyped-def]
    inserted = {table: 0 for table in TABLES}
    for table in TABLES:
        fields = FIELDS[table]
        for row in rows[table]:
            result = conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.{table} ({','.join(fields)}) "
                    f"VALUES ({','.join(f':{field}' for field in fields)}) ON CONFLICT DO NOTHING"
                ),
                {field: row[field] for field in fields},
            )
            inserted[table] += int(result.rowcount or 0)
        if interrupt and table == "service_cases":
            raise RuntimeError("synthetic interruption after service cases")
        if stop_after == table:
            break
    return inserted


def authorization_signature(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def reconcile(conn, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    expected = {table: len(values) for table, values in rows.items()}
    target = counts(conn)
    version_mismatches = int(
        conn.execute(
            text(
                f"SELECT (SELECT count(*) FROM {SCHEMA}.policies)-(SELECT count(*) FROM {SCHEMA}.policy_versions) "
                f"+ (SELECT count(*) FROM {SCHEMA}.activities)-(SELECT count(*) FROM {SCHEMA}.activity_versions) "
                f"+ (SELECT count(*) FROM {SCHEMA}.announcements)-(SELECT count(*) FROM {SCHEMA}.announcement_versions)"
            )
        ).scalar_one()
    )
    invalid_windows = int(
        conn.execute(
            text(
                f"SELECT (SELECT count(*) FROM {SCHEMA}.policy_versions WHERE expires_at IS NOT NULL AND expires_at<=effective_at) "
                f"+ (SELECT count(*) FROM {SCHEMA}.activity_versions WHERE NOT (registration_opens_at<=registration_closes_at AND registration_closes_at<=starts_at AND starts_at<=ends_at)) "
                f"+ (SELECT count(*) FROM {SCHEMA}.announcement_versions WHERE expires_at IS NOT NULL AND expires_at<=publish_at)"
            )
        ).scalar_one()
    )
    orphan_cases = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.service_cases c LEFT JOIN {SCHEMA}.service_catalogs s ON s.source_key=c.service_source_key WHERE s.source_key IS NULL"
            )
        ).scalar_one()
    )
    capacity_mismatches = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.activity_versions v LEFT JOIN ("
                f"SELECT activity_source_key,coalesce(sum(attendee_count) FILTER (WHERE status='CONFIRMED'),0) confirmed,count(*) FILTER (WHERE status='WAITLISTED') waitlisted "
                f"FROM {SCHEMA}.registrations GROUP BY activity_source_key) r ON r.activity_source_key=v.activity_source_key "
                "WHERE coalesce(r.confirmed,0)<>v.confirmed_count OR coalesce(r.waitlisted,0)<>v.waitlist_count OR v.confirmed_count>v.capacity"
            )
        ).scalar_one()
    )
    orphan_registrations = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.registrations r LEFT JOIN {SCHEMA}.activities a ON a.source_key=r.activity_source_key WHERE a.source_key IS NULL"
            )
        ).scalar_one()
    )
    audience_mismatches = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.announcement_versions v LEFT JOIN (SELECT announcement_source_key,count(*) total FROM {SCHEMA}.announcement_targets GROUP BY announcement_source_key) t ON t.announcement_source_key=v.announcement_source_key WHERE coalesce(t.total,0)<>v.target_count"
            )
        ).scalar_one()
    )
    delivery_mismatches = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.announcement_deliveries d LEFT JOIN {SCHEMA}.announcement_targets t ON t.source_key=d.target_source_key "
                "WHERE t.source_key IS NULL OR d.party_ref<>t.party_ref OR (d.status='READ' AND d.read_at IS NULL) OR (d.status='DELIVERED' AND d.read_at IS NOT NULL)"
            )
        ).scalar_one()
    )
    false_external_deliveries = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.announcement_deliveries WHERE channel<>'IN_APP' OR external_contacted"
            )
        ).scalar_one()
    )
    fabricated_approved_state = int(
        conn.execute(
            text(
                f"SELECT (SELECT count(*) FROM {SCHEMA}.policies WHERE status<>'REVIEW_REQUIRED') "
                f"+ (SELECT count(*) FROM {SCHEMA}.service_catalogs WHERE status<>'REVIEW_REQUIRED') "
                f"+ (SELECT count(*) FROM {SCHEMA}.activities WHERE status<>'REVIEW_REQUIRED') "
                f"+ (SELECT count(*) FROM {SCHEMA}.announcements WHERE status<>'REVIEW_REQUIRED')"
            )
        ).scalar_one()
    )
    raw_sensitive_columns = int(
        conn.execute(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema "
                "AND column_name IN ('phone','mobile','email','password','token','secret','contact_name')"
            ),
            {"schema": SCHEMA},
        ).scalar_one()
    )
    quarantine_reasons = dict(
        conn.execute(
            text(f"SELECT issue_code,count(*) FROM {SCHEMA}.quarantine GROUP BY issue_code")
        ).all()
    )
    expected_quarantine = {
        "ACTIVITY_REFERENCE_UNMAPPED": 1,
        "EXTERNAL_CHANNEL_UNVERIFIED": 1,
        "EXTERNAL_PROVIDER_EVIDENCE_MISSING": 1,
        "OFFICIAL_SOURCE_UNAUTHORIZED": 1,
        "PARTY_KEY_UNMAPPED": 1,
    }
    passed = (
        expected == target
        and version_mismatches == 0
        and invalid_windows == 0
        and orphan_cases == 0
        and capacity_mismatches == 0
        and orphan_registrations == 0
        and audience_mismatches == 0
        and delivery_mismatches == 0
        and false_external_deliveries == 0
        and fabricated_approved_state == 0
        and raw_sensitive_columns == 0
        and quarantine_reasons == expected_quarantine
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "version_mismatches": version_mismatches,
        "invalid_active_windows": invalid_windows,
        "orphan_service_cases": orphan_cases,
        "capacity_or_registration_mismatches": capacity_mismatches,
        "orphan_registrations": orphan_registrations,
        "audience_target_mismatches": audience_mismatches,
        "delivery_or_read_mismatches": delivery_mismatches,
        "false_external_deliveries": false_external_deliveries,
        "fabricated_approved_or_published_state": fabricated_approved_state,
        "raw_sensitive_columns": raw_sensitive_columns,
        "quarantine_reasons": quarantine_reasons,
    }


def backup_manifest(conn) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    table_hashes: dict[str, str] = {}
    for table in TABLES:
        keys = [
            str(value)
            for value in conn.execute(
                text(f"SELECT source_key FROM {SCHEMA}.{table} ORDER BY source_key")
            ).scalars()
        ]
        table_hashes[table] = canonical_hash(keys)
    return {"counts": counts(conn), "source_key_hashes": table_hashes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    parser.add_argument(
        "--fixture", type=Path, default=Path(__file__).parent / "fixtures" / "engagement_v1.json"
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "out" / "engagement_etl_report.json")
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
    fixture_hash = digest(args.fixture.read_text(encoding="utf-8"))
    engine = safe_engine(args.database_url)
    with engine.begin() as conn:
        auth_before = authorization_signature(conn)
        create_schema(conn, fixture_hash)
    interrupted = False
    try:
        with engine.begin() as conn:
            apply_rows(conn, rows, interrupt=True)
    except RuntimeError as exc:
        if str(exc) != "synthetic interruption after service cases":
            raise
        interrupted = True
    with engine.begin() as conn:
        partial_rows = sum(counts(conn).values())
    with engine.begin() as conn:
        checkpoint = apply_rows(conn, rows, stop_after="service_cases")
    with engine.begin() as conn:
        checkpoint_counts = counts(conn)
        resumed = apply_rows(conn, rows)
    first = {table: checkpoint[table] + resumed[table] for table in TABLES}
    with engine.begin() as conn:
        second = apply_rows(conn, rows)
        reconciliation = reconcile(conn, rows)
        backup = backup_manifest(conn)
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {SCHEMA}.migration_runs WHERE run_id=:run_id"), {"run_id": RUN_ID}
        )
        rows_after_delete = sum(counts(conn).values())
        preserve_run_exists = bool(
            conn.execute(
                text(f"SELECT count(*)=1 FROM {SCHEMA}.migration_runs WHERE run_id=:run_id"),
                {"run_id": PRESERVE_RUN_ID},
            ).scalar_one()
        )
        conn.execute(
            text(
                f"INSERT INTO {SCHEMA}.migration_runs(run_id,fixture_sha256,created_at) VALUES (:run_id,:fixture_hash,:created_at)"
            ),
            {"run_id": RUN_ID, "fixture_hash": fixture_hash, "created_at": MIGRATED_AT},
        )
        restored = apply_rows(conn, rows)
        restored_reconciliation = reconcile(conn, rows)
        restored_backup = backup_manifest(conn)
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
        "checkpoint_resume": {
            "passed": sum(checkpoint_counts.values()) == sum(checkpoint.values())
            and sum(checkpoint.values()) > 0
            and first == expected,
            "checkpoint": "service_cases",
            "checkpoint_inserted": checkpoint,
            "committed_counts_before_resume": checkpoint_counts,
            "resume_inserted": resumed,
        },
        "first_apply": {"passed": first == expected, "inserted": first},
        "idempotent_reapply": {
            "passed": all(value == 0 for value in second.values()),
            "inserted": second,
        },
        "reconciliation": reconciliation,
        "run_scoped_rollback": {
            "passed": rows_after_delete == 0 and preserve_run_exists,
            "target_rows_after_run_delete": rows_after_delete,
            "unrelated_run_preserved": preserve_run_exists,
        },
        "backup_delete_restore": {
            "passed": restored == expected
            and restored_reconciliation["passed"]
            and restored_backup == backup,
            "backup_manifest": backup,
            "restored_inserted": restored,
            "restored_manifest_matches": restored_backup == backup,
        },
        "schema_rollback": {
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
        "run_id": RUN_ID,
        "synthetic_only": True,
        "contains_real_customer_data": False,
        "live_legacy_verified": False,
        "authoritative_legacy_schema_present": False,
        "authorized_legacy_exports_present": False,
        "real_legacy_readiness": "BLOCKED_PENDING_AUTHORIZED_NOTICE_EXPORTS_KEYMAPS_AND_SIGNED_RECONCILIATION",
        "fixture_sha256": fixture_hash,
        "stages": stages,
        "blockers": [
            "authorized standalone notice/policy/service/activity schema exports and row-count watermarks not supplied",
            "desensitized snapshots plus park/Party/user/attachment key maps not supplied",
            "native approval evidence and authoritative source provenance for legacy published records not supplied",
            "external government feed, service provider and notification delivery contracts/evidence not supplied",
            "production freeze, backup, cutover, deletion and rollback authorization not granted",
        ],
        "external_integrations": {
            "government_policy_feed": "NOT_CONNECTED",
            "external_service_provider": "NOT_CONNECTED",
            "external_notification": "NOT_CONNECTED",
        },
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
