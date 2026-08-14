#!/usr/bin/env python3
"""Synthetic investment CRM ETL drill in an isolated loopback PostgreSQL schema.

The drill never reads a legacy database. It validates representative traditional
investment, CRM and radar-like fixtures, applies them twice, reconciles the
result, and drops the isolated schema as rollback proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_investment_crm_fixture"
STAGE_MAP = {
    "new": "NEW",
    "following": "CONTACTING",
    "contacting": "CONTACTING",
    "visiting": "VISITING",
    "quoting": "QUOTING",
    "negotiation": "NEGOTIATING",
    "won": "WON",
    "lost": "LOST",
    "cancelled": "CANCELLED",
    "merged": "MERGED",
}
ACTIVITY_TYPES = {"CALL", "NOTE", "VISIT", "QUOTE", "NEGOTIATION", "SYSTEM"}
FIELDS = {
    "leads": (
        "tenant_id",
        "park_id",
        "source_system",
        "source_id",
        "source_ref",
        "name",
        "normalized_phone",
        "stage",
        "pool_status",
        "owner_ref",
    ),
    "activities": (
        "tenant_id",
        "source_system",
        "source_id",
        "lead_source_system",
        "lead_source_id",
        "activity_type",
        "occurred_at",
    ),
    "assignments": (
        "tenant_id",
        "source_system",
        "source_id",
        "lead_source_system",
        "lead_source_id",
        "event_type",
        "from_owner_ref",
        "to_owner_ref",
    ),
    "merge_links": (
        "tenant_id",
        "source_system",
        "source_id",
        "source_lead_system",
        "source_lead_id",
        "target_lead_system",
        "target_lead_id",
        "reason_code",
    ),
    "assignment_rules": (
        "tenant_id",
        "source_system",
        "source_id",
        "park_id",
        "rule_code",
        "trigger_type",
        "status",
    ),
    "assignment_rule_versions": (
        "tenant_id",
        "source_system",
        "source_id",
        "rule_source_id",
        "version_no",
        "status",
        "checksum",
    ),
    "assignment_rule_members": (
        "tenant_id",
        "source_system",
        "source_id",
        "version_source_id",
        "member_ref",
        "capacity",
        "weight",
    ),
    "viewings": (
        "tenant_id",
        "source_system",
        "source_id",
        "lead_source_system",
        "lead_source_id",
        "scheduled_start",
        "scheduled_end",
        "status",
    ),
    "viewing_units": (
        "tenant_id",
        "source_system",
        "source_id",
        "viewing_source_id",
        "unit_ref",
    ),
    "intent_applications": (
        "tenant_id",
        "source_system",
        "source_id",
        "lead_source_system",
        "lead_source_id",
        "status",
    ),
    "intent_versions": (
        "tenant_id",
        "source_system",
        "source_id",
        "intent_source_id",
        "version_no",
        "snapshot_checksum",
        "status",
    ),
    "intent_units": (
        "tenant_id",
        "source_system",
        "source_id",
        "version_source_id",
        "unit_ref",
    ),
    "approval_links": (
        "tenant_id",
        "source_system",
        "source_id",
        "intent_source_id",
        "approval_source_ref",
        "status",
    ),
    "channels": (
        "tenant_id",
        "source_system",
        "source_id",
        "park_id",
        "channel_code",
        "secret_ref",
        "verification_status",
    ),
    "channel_inbox": (
        "tenant_id",
        "source_system",
        "source_id",
        "channel_source_id",
        "external_event_id",
        "payload_fingerprint",
        "lead_source_system",
        "lead_source_id",
        "status",
    ),
    "pii_quarantine": (
        "tenant_id",
        "source_system",
        "source_id",
        "field_name",
        "value_fingerprint",
        "reason_code",
    ),
    "migration_quarantine": (
        "tenant_id",
        "source_system",
        "source_id",
        "entity_type",
        "evidence_fingerprint",
        "reason_code",
    ),
}
SOURCE_TABLES = {
    **{name: name for name in FIELDS},
    "pii_quarantine": "pii_rejections",
    "migration_quarantine": "migration_rejections",
}


def fixture() -> dict[str, list[dict[str, Any]]]:
    """Return deterministic, non-personal synthetic source records."""
    return {
        "leads": [
            {
                "tenant_id": "tenant-demo",
                "park_id": "park-a",
                "source_system": "TRADITIONAL_INVESTMENT",
                "source_id": "investment-001",
                "source_ref": "legacy-investment-001",
                "name": "合成智造一号",
                "contact_phone": "+86 138-0000-0001",
                "status": "following",
                "pool_status": "PRIVATE",
                "owner_ref": "sales-a",
            },
            {
                "tenant_id": "tenant-demo",
                "park_id": "park-a",
                "source_system": "CRM",
                "source_id": "crm-001",
                "source_ref": "legacy-crm-001",
                "name": "合成公海客户",
                "contact_phone": "13900000002",
                "status": "new",
                "pool_status": "PUBLIC",
                "owner_ref": None,
            },
            {
                "tenant_id": "tenant-demo",
                "park_id": "park-b",
                "source_system": "RADAR_LIKE",
                "source_id": "radar-001",
                "source_ref": "radar-company-001",
                "name": "合成雷达机会",
                "contact_phone": "13700000003",
                "status": "negotiation",
                "pool_status": "PRIVATE",
                "owner_ref": "sales-b",
            },
            {
                "tenant_id": "tenant-demo",
                "park_id": "park-a",
                "source_system": "CRM",
                "source_id": "crm-merge-source",
                "source_ref": "legacy-crm-merge-source",
                "name": "合成重复机会",
                "contact_phone": "13600000004",
                "status": "merged",
                "pool_status": "PRIVATE",
                "owner_ref": "sales-a",
            },
            {
                "tenant_id": "tenant-demo",
                "park_id": "park-a",
                "source_system": "CRM",
                "source_id": "crm-merge-target",
                "source_ref": "legacy-crm-merge-target",
                "name": "合成保留机会",
                "contact_phone": "13500000005",
                "status": "quoting",
                "pool_status": "PRIVATE",
                "owner_ref": "sales-a",
            },
        ],
        "activities": [
            {"tenant_id": "tenant-demo", "source_system": "TRADITIONAL_INVESTMENT", "source_id": "activity-001", "lead_source_system": "TRADITIONAL_INVESTMENT", "lead_source_id": "investment-001", "activity_type": "CALL", "occurred_at": "2026-07-01T01:00:00Z"},
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "activity-002", "lead_source_system": "CRM", "lead_source_id": "crm-001", "activity_type": "NOTE", "occurred_at": "2026-07-02T02:00:00Z"},
            {"tenant_id": "tenant-demo", "source_system": "RADAR_LIKE", "source_id": "activity-003", "lead_source_system": "RADAR_LIKE", "lead_source_id": "radar-001", "activity_type": "NEGOTIATION", "occurred_at": "2026-07-03T03:00:00Z"},
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "activity-004", "lead_source_system": "CRM", "lead_source_id": "crm-merge-target", "activity_type": "QUOTE", "occurred_at": "2026-07-04T04:00:00Z"},
        ],
        "assignments": [
            {"tenant_id": "tenant-demo", "source_system": "TRADITIONAL_INVESTMENT", "source_id": "assignment-001", "lead_source_system": "TRADITIONAL_INVESTMENT", "lead_source_id": "investment-001", "event_type": "ASSIGN", "from_owner_ref": None, "to_owner_ref": "sales-a"},
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "assignment-002", "lead_source_system": "CRM", "lead_source_id": "crm-001", "event_type": "RELEASE", "from_owner_ref": "sales-a", "to_owner_ref": None},
            {"tenant_id": "tenant-demo", "source_system": "RADAR_LIKE", "source_id": "assignment-003", "lead_source_system": "RADAR_LIKE", "lead_source_id": "radar-001", "event_type": "ASSIGN", "from_owner_ref": None, "to_owner_ref": "sales-b"},
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "assignment-004", "lead_source_system": "CRM", "lead_source_id": "crm-merge-target", "event_type": "REASSIGN", "from_owner_ref": "sales-b", "to_owner_ref": "sales-a"},
        ],
        "merge_links": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "merge-001", "source_lead_system": "CRM", "source_lead_id": "crm-merge-source", "target_lead_system": "CRM", "target_lead_id": "crm-merge-target", "reason_code": "SAME_OPPORTUNITY"},
        ],
        "pii_rejections": [
            {"tenant_id": "tenant-demo", "source_system": "RADAR_LIKE", "source_id": "radar-reject-001", "field_name": "contact_phone", "raw_value": "unsupported-contact-token", "reason_code": "PII_FORMAT_UNSUPPORTED"},
        ],
        "assignment_rules": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "rule-001", "park_id": "park-a", "rule_code": "LEGACY_AUTO_ASSIGN_A", "trigger_type": "MANUAL_CREATE", "status": "ACTIVE"},
        ],
        "assignment_rule_versions": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "rule-version-001", "rule_source_id": "rule-001", "version_no": 1, "status": "PUBLISHED", "checksum": "sha256:rule-version-001"},
        ],
        "assignment_rule_members": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "rule-member-001", "version_source_id": "rule-version-001", "member_ref": "sales-a", "capacity": 20, "weight": 1},
        ],
        "viewings": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "viewing-001", "lead_source_system": "CRM", "lead_source_id": "crm-merge-target", "scheduled_start": "2026-07-05T01:00:00Z", "scheduled_end": "2026-07-05T02:00:00Z", "status": "COMPLETED"},
        ],
        "viewing_units": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "viewing-unit-001", "viewing_source_id": "viewing-001", "unit_ref": "legacy-unit-a-101"},
        ],
        "intent_applications": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "intent-001", "lead_source_system": "CRM", "lead_source_id": "crm-merge-target", "status": "APPROVED"},
        ],
        "intent_versions": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "intent-version-001", "intent_source_id": "intent-001", "version_no": 1, "snapshot_checksum": "sha256:intent-version-001", "status": "APPROVED"},
        ],
        "intent_units": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "intent-unit-001", "version_source_id": "intent-version-001", "unit_ref": "legacy-unit-a-101"},
        ],
        "approval_links": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "intent-approval-001", "intent_source_id": "intent-001", "approval_source_ref": "legacy-approval-001", "status": "APPROVED"},
        ],
        "channels": [
            {"tenant_id": "tenant-demo", "source_system": "RADAR_LIKE", "source_id": "channel-001", "park_id": "park-b", "channel_code": "RADAR_SYNTHETIC", "secret_ref": "KWZY_CHANNEL_RADAR_SYNTHETIC", "verification_status": "NOT_CONNECTED"},
        ],
        "channel_inbox": [
            {"tenant_id": "tenant-demo", "source_system": "RADAR_LIKE", "source_id": "inbox-001", "channel_source_id": "channel-001", "external_event_id": "synthetic-event-001", "payload_fingerprint": "sha256:synthetic-event-001", "lead_source_system": "RADAR_LIKE", "lead_source_id": "radar-001", "status": "PROCESSED"},
        ],
        "migration_rejections": [
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "reject-owner-001", "entity_type": "ASSIGNMENT", "raw_evidence": "ambiguous-owner-token", "reason_code": "AMBIGUOUS_OWNER"},
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "reject-viewing-001", "entity_type": "VIEWING", "raw_evidence": "missing-unit-token", "reason_code": "INVALID_UNIT_REFERENCE"},
            {"tenant_id": "tenant-demo", "source_system": "CRM", "source_id": "reject-approval-001", "entity_type": "INTENT", "raw_evidence": "inferred-approver-token", "reason_code": "INFERRED_APPROVER"},
            {"tenant_id": "tenant-demo", "source_system": "RADAR_LIKE", "source_id": "reject-channel-001", "entity_type": "CHANNEL_EVENT", "raw_evidence": "unknown-channel-token", "reason_code": "UNKNOWN_CHANNEL"},
        ],
    }


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]
    if not re.fullmatch(r"1\d{10}", digits):
        raise ValueError("unsupported synthetic phone format")
    return digits


def lead_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["tenant_id"], row["source_system"], row["source_id"]


def validate_source(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    leads = {lead_key(row): row for row in data["leads"]}
    if len(leads) != len(data["leads"]):
        errors.append("duplicate lead source key")
    refs = [(row["tenant_id"], row["source_system"], row["source_ref"]) for row in data["leads"]]
    if len(refs) != len(set(refs)):
        errors.append("duplicate lead source ref")

    for row in data["leads"]:
        if str(row["status"]).lower() not in STAGE_MAP:
            errors.append("unsupported lead status")
        if row["pool_status"] not in {"PUBLIC", "PRIVATE"}:
            errors.append("unsupported pool status")
        if (row["pool_status"] == "PUBLIC") != (row["owner_ref"] is None):
            errors.append("pool owner mismatch")
        try:
            normalize_phone(row["contact_phone"])
        except ValueError:
            errors.append("invalid accepted lead phone")

    def duplicate_source(table: str) -> None:
        keys = [(row["tenant_id"], row["source_system"], row["source_id"]) for row in data[table]]
        if len(keys) != len(set(keys)):
            errors.append(f"duplicate {table} source key")

    for table in data:
        duplicate_source(table)

    for row in data["activities"]:
        key = (row["tenant_id"], row["lead_source_system"], row["lead_source_id"])
        if key not in leads:
            errors.append("orphan activity lead")
        if row["activity_type"] not in ACTIVITY_TYPES:
            errors.append("unsupported activity type")
    for row in data["assignments"]:
        key = (row["tenant_id"], row["lead_source_system"], row["lead_source_id"])
        if key not in leads:
            errors.append("orphan assignment lead")
    for row in data["merge_links"]:
        source_key = (row["tenant_id"], row["source_lead_system"], row["source_lead_id"])
        target_key = (row["tenant_id"], row["target_lead_system"], row["target_lead_id"])
        source, target = leads.get(source_key), leads.get(target_key)
        if source is None or target is None:
            errors.append("orphan merge lead")
        elif source_key == target_key or source["park_id"] != target["park_id"]:
            errors.append("invalid merge scope")
        elif STAGE_MAP[str(source["status"]).lower()] != "MERGED":
            errors.append("merge source not terminal MERGED")
    for row in data["pii_rejections"]:
        if not row["raw_value"] or row["reason_code"] != "PII_FORMAT_UNSUPPORTED":
            errors.append("invalid PII quarantine disposition")

    rule_ids = {row["source_id"] for row in data["assignment_rules"]}
    version_ids = {row["source_id"] for row in data["assignment_rule_versions"]}
    viewing_ids = {row["source_id"] for row in data["viewings"]}
    intent_ids = {row["source_id"] for row in data["intent_applications"]}
    intent_version_ids = {row["source_id"] for row in data["intent_versions"]}
    channel_ids = {row["source_id"] for row in data["channels"]}
    for row in data["assignment_rule_versions"]:
        if row["rule_source_id"] not in rule_ids:
            errors.append("orphan assignment rule version")
    for row in data["assignment_rule_members"]:
        if row["version_source_id"] not in version_ids:
            errors.append("orphan assignment rule member")
    for row in data["viewings"]:
        if (row["tenant_id"], row["lead_source_system"], row["lead_source_id"]) not in leads:
            errors.append("orphan viewing lead")
    for row in data["viewing_units"]:
        if row["viewing_source_id"] not in viewing_ids:
            errors.append("orphan viewing unit")
    for row in data["intent_applications"]:
        if (row["tenant_id"], row["lead_source_system"], row["lead_source_id"]) not in leads:
            errors.append("orphan intent lead")
    for row in data["intent_versions"]:
        if row["intent_source_id"] not in intent_ids:
            errors.append("orphan intent version")
    for row in data["intent_units"]:
        if row["version_source_id"] not in intent_version_ids:
            errors.append("orphan intent unit")
    for row in data["approval_links"]:
        if row["intent_source_id"] not in intent_ids:
            errors.append("orphan intent approval")
    for row in data["channel_inbox"]:
        if row["channel_source_id"] not in channel_ids:
            errors.append("orphan channel inbox")
        if (row["tenant_id"], row["lead_source_system"], row["lead_source_id"]) not in leads:
            errors.append("orphan channel lead")
    if any("secret" in row for row in data["channels"]):
        errors.append("raw channel secret supplied")
    allowed_rejections = {
        "AMBIGUOUS_OWNER",
        "INFERRED_APPROVER",
        "INVALID_UNIT_REFERENCE",
        "UNKNOWN_CHANNEL",
    }
    for row in data["migration_rejections"]:
        if not row["raw_evidence"] or row["reason_code"] not in allowed_rejections:
            errors.append("invalid migration quarantine disposition")

    return {
        "passed": not errors,
        "errors": sorted(set(errors)),
        "source_groups": dict(sorted(Counter(row["source_system"] for row in data["leads"]).items())),
    }


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.leads (
  tenant_id text NOT NULL, park_id text NOT NULL, source_system text NOT NULL,
  source_id text NOT NULL, source_ref text NOT NULL, name text NOT NULL,
  normalized_phone text NOT NULL, stage text NOT NULL, pool_status text NOT NULL,
  owner_ref text, PRIMARY KEY (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, source_ref),
  CHECK ((pool_status = 'PUBLIC' AND owner_ref IS NULL) OR (pool_status = 'PRIVATE' AND owner_ref IS NOT NULL))
);
CREATE TABLE {SCHEMA}.activities (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  lead_source_system text NOT NULL, lead_source_id text NOT NULL,
  activity_type text NOT NULL, occurred_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, lead_source_system, lead_source_id)
    REFERENCES {SCHEMA}.leads (tenant_id, source_system, source_id)
);
CREATE TABLE {SCHEMA}.assignments (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  lead_source_system text NOT NULL, lead_source_id text NOT NULL,
  event_type text NOT NULL, from_owner_ref text, to_owner_ref text,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, lead_source_system, lead_source_id)
    REFERENCES {SCHEMA}.leads (tenant_id, source_system, source_id)
);
CREATE TABLE {SCHEMA}.merge_links (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  source_lead_system text NOT NULL, source_lead_id text NOT NULL,
  target_lead_system text NOT NULL, target_lead_id text NOT NULL, reason_code text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_lead_system, source_lead_id)
    REFERENCES {SCHEMA}.leads (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, target_lead_system, target_lead_id)
    REFERENCES {SCHEMA}.leads (tenant_id, source_system, source_id)
);
CREATE TABLE {SCHEMA}.pii_quarantine (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  field_name text NOT NULL, value_fingerprint text NOT NULL, reason_code text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id, field_name)
);
CREATE TABLE {SCHEMA}.assignment_rules (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  park_id text NOT NULL, rule_code text NOT NULL, trigger_type text NOT NULL,
  status text NOT NULL, PRIMARY KEY (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, park_id, rule_code)
);
CREATE TABLE {SCHEMA}.assignment_rule_versions (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  rule_source_id text NOT NULL, version_no integer NOT NULL, status text NOT NULL,
  checksum text NOT NULL, PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_system, rule_source_id)
    REFERENCES {SCHEMA}.assignment_rules (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, rule_source_id, version_no)
);
CREATE TABLE {SCHEMA}.assignment_rule_members (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  version_source_id text NOT NULL, member_ref text NOT NULL,
  capacity integer NOT NULL CHECK (capacity > 0),
  weight integer NOT NULL CHECK (weight > 0),
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_system, version_source_id)
    REFERENCES {SCHEMA}.assignment_rule_versions (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, version_source_id, member_ref)
);
CREATE TABLE {SCHEMA}.viewings (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  lead_source_system text NOT NULL, lead_source_id text NOT NULL,
  scheduled_start timestamptz NOT NULL, scheduled_end timestamptz NOT NULL,
  status text NOT NULL, PRIMARY KEY (tenant_id, source_system, source_id),
  CHECK (scheduled_end > scheduled_start),
  FOREIGN KEY (tenant_id, lead_source_system, lead_source_id)
    REFERENCES {SCHEMA}.leads (tenant_id, source_system, source_id)
);
CREATE TABLE {SCHEMA}.viewing_units (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  viewing_source_id text NOT NULL, unit_ref text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_system, viewing_source_id)
    REFERENCES {SCHEMA}.viewings (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, viewing_source_id, unit_ref)
);
CREATE TABLE {SCHEMA}.intent_applications (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  lead_source_system text NOT NULL, lead_source_id text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, lead_source_system, lead_source_id)
    REFERENCES {SCHEMA}.leads (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, lead_source_system, lead_source_id)
);
CREATE TABLE {SCHEMA}.intent_versions (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  intent_source_id text NOT NULL, version_no integer NOT NULL,
  snapshot_checksum text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_system, intent_source_id)
    REFERENCES {SCHEMA}.intent_applications (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, intent_source_id, version_no)
);
CREATE TABLE {SCHEMA}.intent_units (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  version_source_id text NOT NULL, unit_ref text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_system, version_source_id)
    REFERENCES {SCHEMA}.intent_versions (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, version_source_id, unit_ref)
);
CREATE TABLE {SCHEMA}.approval_links (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  intent_source_id text NOT NULL, approval_source_ref text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_system, intent_source_id)
    REFERENCES {SCHEMA}.intent_applications (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, approval_source_ref)
);
CREATE TABLE {SCHEMA}.channels (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  park_id text NOT NULL, channel_code text NOT NULL, secret_ref text NOT NULL,
  verification_status text NOT NULL, PRIMARY KEY (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, channel_code)
);
CREATE TABLE {SCHEMA}.channel_inbox (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  channel_source_id text NOT NULL, external_event_id text NOT NULL,
  payload_fingerprint text NOT NULL, lead_source_system text NOT NULL,
  lead_source_id text NOT NULL, status text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, source_system, channel_source_id)
    REFERENCES {SCHEMA}.channels (tenant_id, source_system, source_id),
  FOREIGN KEY (tenant_id, lead_source_system, lead_source_id)
    REFERENCES {SCHEMA}.leads (tenant_id, source_system, source_id),
  UNIQUE (tenant_id, source_system, channel_source_id, external_event_id)
);
CREATE TABLE {SCHEMA}.migration_quarantine (
  tenant_id text NOT NULL, source_system text NOT NULL, source_id text NOT NULL,
  entity_type text NOT NULL, evidence_fingerprint text NOT NULL, reason_code text NOT NULL,
  PRIMARY KEY (tenant_id, source_system, source_id)
);
"""


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("CRM ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("CRM ETL drill is restricted to loopback PostgreSQL")
    database_name = (parsed.database or "").lower()
    if not database_name or not any(marker in database_name for marker in ("test", "fixture", "dev")):
        raise ValueError("CRM ETL drill requires an explicitly non-production database name")
    return create_engine(database_url)


def apply_rows(
    conn,
    data: dict[str, list[dict[str, Any]]],
    *,
    only_tables: set[str] | None = None,
) -> dict[str, int]:
    inserted: dict[str, int] = {}
    for target_table, columns in FIELDS.items():
        if only_tables is not None and target_table not in only_tables:
            continue
        count = 0
        for source in data[SOURCE_TABLES[target_table]]:
            row = dict(source)
            if target_table == "leads":
                row["normalized_phone"] = normalize_phone(row.pop("contact_phone"))
                row["stage"] = STAGE_MAP[str(row.pop("status")).lower()]
            elif target_table == "pii_quarantine":
                raw = str(row.pop("raw_value"))
                row["value_fingerprint"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            elif target_table == "migration_quarantine":
                raw = str(row.pop("raw_evidence"))
                row["evidence_fingerprint"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            result = conn.execute(
                text(
                    f"INSERT INTO {SCHEMA}.{target_table} ({', '.join(columns)}) "
                    f"VALUES ({', '.join(':' + column for column in columns)}) ON CONFLICT DO NOTHING"
                ),
                {column: row[column] for column in columns},
            )
            count += result.rowcount
        inserted[target_table] = count
    return inserted


def grouped_source(rows: list[dict[str, Any]], field: str, transform=None) -> dict[str, int]:
    values = Counter(transform(row[field]) if transform else row[field] for row in rows)
    return dict(sorted((str(key) if key is not None else "PUBLIC_UNASSIGNED", value) for key, value in values.items()))


def grouped_target(conn, field: str) -> dict[str, int]:
    rows = conn.execute(
        text(f"SELECT coalesce({field}, 'PUBLIC_UNASSIGNED'), count(*) FROM {SCHEMA}.leads GROUP BY {field} ORDER BY 1")
    ).all()
    return {str(key): int(value) for key, value in rows}


def reconcile(conn, data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    expected_counts = {
        table: len(data[SOURCE_TABLES[table]])
        for table in FIELDS
    }
    counts = {
        table: {"source": source, "target": conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()}
        for table, source in expected_counts.items()
    }
    distributions = {
        "stage": {
            "source": grouped_source(data["leads"], "status", lambda value: STAGE_MAP[str(value).lower()]),
            "target": grouped_target(conn, "stage"),
        },
        "pool": {"source": grouped_source(data["leads"], "pool_status"), "target": grouped_target(conn, "pool_status")},
        "owner": {"source": grouped_source(data["leads"], "owner_ref"), "target": grouped_target(conn, "owner_ref")},
    }
    orphan_queries = {
        "activities": f"SELECT count(*) FROM {SCHEMA}.activities x LEFT JOIN {SCHEMA}.leads l ON l.tenant_id=x.tenant_id AND l.source_system=x.lead_source_system AND l.source_id=x.lead_source_id WHERE l.source_id IS NULL",
        "assignments": f"SELECT count(*) FROM {SCHEMA}.assignments x LEFT JOIN {SCHEMA}.leads l ON l.tenant_id=x.tenant_id AND l.source_system=x.lead_source_system AND l.source_id=x.lead_source_id WHERE l.source_id IS NULL",
        "merge_source": f"SELECT count(*) FROM {SCHEMA}.merge_links x LEFT JOIN {SCHEMA}.leads l ON l.tenant_id=x.tenant_id AND l.source_system=x.source_lead_system AND l.source_id=x.source_lead_id WHERE l.source_id IS NULL",
        "merge_target": f"SELECT count(*) FROM {SCHEMA}.merge_links x LEFT JOIN {SCHEMA}.leads l ON l.tenant_id=x.tenant_id AND l.source_system=x.target_lead_system AND l.source_id=x.target_lead_id WHERE l.source_id IS NULL",
        "assignment_rule_versions": f"SELECT count(*) FROM {SCHEMA}.assignment_rule_versions x LEFT JOIN {SCHEMA}.assignment_rules p ON p.tenant_id=x.tenant_id AND p.source_system=x.source_system AND p.source_id=x.rule_source_id WHERE p.source_id IS NULL",
        "assignment_rule_members": f"SELECT count(*) FROM {SCHEMA}.assignment_rule_members x LEFT JOIN {SCHEMA}.assignment_rule_versions p ON p.tenant_id=x.tenant_id AND p.source_system=x.source_system AND p.source_id=x.version_source_id WHERE p.source_id IS NULL",
        "viewings": f"SELECT count(*) FROM {SCHEMA}.viewings x LEFT JOIN {SCHEMA}.leads l ON l.tenant_id=x.tenant_id AND l.source_system=x.lead_source_system AND l.source_id=x.lead_source_id WHERE l.source_id IS NULL",
        "viewing_units": f"SELECT count(*) FROM {SCHEMA}.viewing_units x LEFT JOIN {SCHEMA}.viewings p ON p.tenant_id=x.tenant_id AND p.source_system=x.source_system AND p.source_id=x.viewing_source_id WHERE p.source_id IS NULL",
        "intent_applications": f"SELECT count(*) FROM {SCHEMA}.intent_applications x LEFT JOIN {SCHEMA}.leads l ON l.tenant_id=x.tenant_id AND l.source_system=x.lead_source_system AND l.source_id=x.lead_source_id WHERE l.source_id IS NULL",
        "intent_versions": f"SELECT count(*) FROM {SCHEMA}.intent_versions x LEFT JOIN {SCHEMA}.intent_applications p ON p.tenant_id=x.tenant_id AND p.source_system=x.source_system AND p.source_id=x.intent_source_id WHERE p.source_id IS NULL",
        "intent_units": f"SELECT count(*) FROM {SCHEMA}.intent_units x LEFT JOIN {SCHEMA}.intent_versions p ON p.tenant_id=x.tenant_id AND p.source_system=x.source_system AND p.source_id=x.version_source_id WHERE p.source_id IS NULL",
        "approval_links": f"SELECT count(*) FROM {SCHEMA}.approval_links x LEFT JOIN {SCHEMA}.intent_applications p ON p.tenant_id=x.tenant_id AND p.source_system=x.source_system AND p.source_id=x.intent_source_id WHERE p.source_id IS NULL",
        "channel_inbox_channel": f"SELECT count(*) FROM {SCHEMA}.channel_inbox x LEFT JOIN {SCHEMA}.channels p ON p.tenant_id=x.tenant_id AND p.source_system=x.source_system AND p.source_id=x.channel_source_id WHERE p.source_id IS NULL",
        "channel_inbox_lead": f"SELECT count(*) FROM {SCHEMA}.channel_inbox x LEFT JOIN {SCHEMA}.leads l ON l.tenant_id=x.tenant_id AND l.source_system=x.lead_source_system AND l.source_id=x.lead_source_id WHERE l.source_id IS NULL",
    }
    orphans = {name: conn.execute(text(query)).scalar_one() for name, query in orphan_queries.items()}
    duplicate_source_refs = conn.execute(
        text(
            f"SELECT count(*) FROM (SELECT tenant_id, source_system, source_ref, count(*) "
            f"FROM {SCHEMA}.leads GROUP BY tenant_id, source_system, source_ref HAVING count(*) > 1) d"
        )
    ).scalar_one()
    raw_value_column_present = conn.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema=:schema AND table_name='pii_quarantine' AND column_name='raw_value'"
        ),
        {"schema": SCHEMA},
    ).scalar_one()
    pii = {
        "source_rejected": len(data["pii_rejections"]),
        "target_quarantined": counts["pii_quarantine"]["target"],
        "raw_value_persisted": bool(raw_value_column_present),
    }
    sensitive_columns = conn.execute(
        text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema=:schema AND (column_name IN ('raw_value', 'raw_evidence', 'secret') "
            "OR column_name LIKE '%ciphertext%')"
        ),
        {"schema": SCHEMA},
    ).all()
    immutable_checksums = {
        "assignment_rule_versions": conn.execute(
            text(f"SELECT count(*) FROM {SCHEMA}.assignment_rule_versions WHERE checksum = ''")
        ).scalar_one(),
        "intent_versions": conn.execute(
            text(f"SELECT count(*) FROM {SCHEMA}.intent_versions WHERE snapshot_checksum = ''")
        ).scalar_one(),
        "channel_inbox": conn.execute(
            text(f"SELECT count(*) FROM {SCHEMA}.channel_inbox WHERE payload_fingerprint = ''")
        ).scalar_one(),
    }
    quarantine_reasons = dict(
        conn.execute(
            text(
                f"SELECT reason_code, count(*) FROM {SCHEMA}.migration_quarantine "
                "GROUP BY reason_code ORDER BY reason_code"
            )
        ).all()
    )
    required_quarantine_reasons = {
        "AMBIGUOUS_OWNER",
        "INFERRED_APPROVER",
        "INVALID_UNIT_REFERENCE",
        "UNKNOWN_CHANNEL",
    }
    passed = (
        all(item["source"] == item["target"] for item in counts.values())
        and all(item["source"] == item["target"] for item in distributions.values())
        and not any(orphans.values())
        and duplicate_source_refs == 0
        and pii["source_rejected"] == pii["target_quarantined"]
        and not pii["raw_value_persisted"]
        and not sensitive_columns
        and not any(immutable_checksums.values())
        and set(quarantine_reasons) == required_quarantine_reasons
    )
    return {
        "passed": passed,
        "counts": counts,
        "distributions": distributions,
        "orphans": orphans,
        "duplicate_source_refs": duplicate_source_refs,
        "pii": pii,
        "sensitive_columns": [list(row) for row in sensitive_columns],
        "immutable_checksum_failures": immutable_checksums,
        "quarantine_reasons": quarantine_reasons,
    }


def finish(path_value: str, report: dict[str, Any], code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    report["result"] = "PASS" if code == 0 else "FAIL"
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CRM_ETL_REPORT={path}")
    print(f"CRM_ETL_DRILL={report['result']}")
    print(f"KWZY_DATA_MIGRATION_READINESS={report['readiness']}")
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
        interrupted_tables = set(list(FIELDS)[:5])
        interrupted_inserted: dict[str, int] = {}
        try:
            with engine.begin() as conn:
                interrupted_inserted = apply_rows(conn, data, only_tables=interrupted_tables)
                raise RuntimeError("synthetic interruption after bounded batch")
        except RuntimeError as exc:
            if str(exc) != "synthetic interruption after bounded batch":
                raise
        with engine.connect() as conn:
            rolled_back_counts = {
                table: conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()
                for table in FIELDS
            }
        report["stages"]["interruption_recovery"] = {
            "passed": bool(interrupted_inserted)
            and not any(rolled_back_counts.values()),
            "attempted_inserted": interrupted_inserted,
            "counts_after_interruption": rolled_back_counts,
            "transaction_rolled_back": not any(rolled_back_counts.values()),
        }
        with engine.begin() as conn:
            first = apply_rows(conn, data)
            expected = {
                table: len(data[SOURCE_TABLES[table]])
                for table in FIELDS
            }
            report["stages"]["first_apply"] = {"passed": first == expected, "inserted": first}
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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CRM_ETL_DRILL=FAIL error={type(exc).__name__}: {exc}", file=sys.stderr)
        raise
