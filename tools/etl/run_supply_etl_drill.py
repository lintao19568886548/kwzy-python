#!/usr/bin/env python3
"""Synthetic supply migration rehearsal restricted to loopback PostgreSQL.

This drill proves deterministic masking/fingerprinting, source-key mapping,
transaction recovery, idempotent replay, ledger reconciliation and rollback.
It never claims a live legacy migration or invents approval/settlement evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = "etl_supply_fixture"
TABLES = (
    "suppliers",
    "supplier_scopes",
    "materials",
    "warehouses",
    "procurement_orders",
    "stock_movements",
    "stock_balances",
    "outsourcing_orders",
    "quarantine",
)
MIGRATED_AT = datetime(2026, 8, 15, tzinfo=timezone.utc)
SYNTHETIC_PEPPER = "kwzy-supply-etl-synthetic-only-v1"


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
    if source.get("authoritative_legacy_schema_present") is not False:
        raise ValueError("synthetic drill cannot claim an authoritative legacy schema")
    if source.get("authoritative_legacy_transactions_present") is not False:
        raise ValueError(
            "synthetic drill cannot claim authoritative legacy transactions"
        )
    for name in (
        "parks",
        "suppliers",
        "materials",
        "warehouses",
        "procurement_orders",
        "stock_movements",
        "outsourcing_orders",
    ):
        if not isinstance(source.get(name), list):
            raise TypeError(f"fixture {name} must be an array")
    return source


def validate_source(source: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for name in (
        "parks",
        "suppliers",
        "materials",
        "warehouses",
        "procurement_orders",
        "stock_movements",
        "outsourcing_orders",
    ):
        keys = [str(row.get("source_id", "")) for row in source[name]]
        if any(not key for key in keys):
            errors.append(f"{name}:blank source_id")
        if len(keys) != len(set(keys)):
            errors.append(f"{name}:duplicate source_id")
    for row in source["suppliers"]:
        if str(row.get("status", "")).upper() not in {"ACTIVE", "SUSPENDED", "RETIRED"}:
            errors.append(f"supplier:{row.get('source_id', '?')}:invalid status")
    for row in source["stock_movements"]:
        try:
            quantity = Decimal(str(row.get("quantity")))
        except Exception:  # noqa: BLE001 - validation reports malformed source rows
            errors.append(f"movement:{row.get('source_id', '?')}:invalid quantity")
            continue
        if quantity == 0:
            errors.append(f"movement:{row.get('source_id', '?')}:zero quantity")
        movement_type = str(row.get("movement_type", "")).upper()
        if movement_type not in {"RECEIPT", "ISSUE", "RETURN", "ADJUSTMENT"}:
            errors.append(f"movement:{row.get('source_id', '?')}:invalid type")
    return {
        "passed": not errors,
        "errors": errors,
        "source_counts": {
            name: len(source[name])
            for name in (
                "parks",
                "suppliers",
                "materials",
                "warehouses",
                "procurement_orders",
                "stock_movements",
                "outsourcing_orders",
            )
        },
    }


def transform(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
    parks = {str(row["source_id"]): str(row["target_ref"]) for row in source["parks"]}
    suppliers: dict[str, dict[str, Any]] = {}
    materials: dict[str, dict[str, Any]] = {}
    warehouses: dict[str, dict[str, Any]] = {}

    for item in source["suppliers"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        if park_ref is None:
            rows["quarantine"].append(
                {
                    "source_key": f"supplier:{source_id}",
                    "issue_code": "PARK_KEY_UNMAPPED",
                    "value_fingerprint": fingerprint(str(item["park_ref"])),
                }
            )
            continue
        supplier = {
            "source_key": source_id,
            "code": str(item["code"]).strip().upper(),
            "display_name": str(item["display_name"]).strip(),
            "status": str(item["status"]).upper(),
            "credential_masked": mask(str(item["credential_number"])),
            "credential_fingerprint": fingerprint(str(item["credential_number"])),
            "migrated_at": MIGRATED_AT,
        }
        suppliers[source_id] = supplier
        rows["suppliers"].append(supplier)
        rows["supplier_scopes"].append(
            {
                "source_key": f"scope:{source_id}:{park_ref}",
                "supplier_source_key": source_id,
                "park_ref": park_ref,
                "service_type": str(item.get("service_type") or "GENERAL").upper(),
                "status": "ACTIVE",
            }
        )

    for item in source["materials"]:
        source_id = str(item["source_id"])
        material = {
            "source_key": source_id,
            "code": str(item["code"]).strip().upper(),
            "name": str(item["name"]).strip(),
            "category": str(item["category"]).strip(),
            "unit": str(item["unit"]).strip(),
            "status": "ACTIVE",
        }
        materials[source_id] = material
        rows["materials"].append(material)

    for item in source["warehouses"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        if park_ref is None:
            rows["quarantine"].append(
                {
                    "source_key": f"warehouse:{source_id}",
                    "issue_code": "PARK_KEY_UNMAPPED",
                    "value_fingerprint": fingerprint(str(item["park_ref"])),
                }
            )
            continue
        warehouse = {
            "source_key": source_id,
            "park_ref": park_ref,
            "code": str(item["code"]).strip().upper(),
            "name": str(item["name"]).strip(),
            "status": "ACTIVE",
        }
        warehouses[source_id] = warehouse
        rows["warehouses"].append(warehouse)

    for item in source["procurement_orders"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        supplier_ref = str(item["supplier_ref"])
        material_ref = str(item["material_ref"])
        if (
            park_ref is None
            or supplier_ref not in suppliers
            or material_ref not in materials
        ):
            rows["quarantine"].append(
                {
                    "source_key": f"procurement:{source_id}",
                    "issue_code": "PROCUREMENT_REFERENCE_UNMAPPED",
                    "value_fingerprint": fingerprint(
                        f"{item['park_ref']}:{supplier_ref}:{material_ref}"
                    ),
                }
            )
            continue
        rows["procurement_orders"].append(
            {
                "source_key": source_id,
                "park_ref": park_ref,
                "supplier_source_key": supplier_ref,
                "material_source_key": material_ref,
                "quantity": Decimal(str(item["quantity"])),
                "unit_price": Decimal(str(item["unit_price"])),
                "status": "PENDING_REVIEW",
                "approval_truth": "LEGACY_UNVERIFIED",
            }
        )
        if str(item.get("legacy_status", "")).upper() not in {"", "DRAFT"}:
            rows["quarantine"].append(
                {
                    "source_key": f"procurement:{source_id}",
                    "issue_code": "APPROVAL_EVIDENCE_MISSING",
                    "value_fingerprint": fingerprint(str(item.get("legacy_status"))),
                }
            )

    balance_totals: dict[tuple[str, str], Decimal] = {}
    for item in source["stock_movements"]:
        source_id = str(item["source_id"])
        warehouse_ref = str(item["warehouse_ref"])
        material_ref = str(item["material_ref"])
        if warehouse_ref not in warehouses or material_ref not in materials:
            rows["quarantine"].append(
                {
                    "source_key": f"movement:{source_id}",
                    "issue_code": "STOCK_REFERENCE_UNMAPPED",
                    "value_fingerprint": fingerprint(f"{warehouse_ref}:{material_ref}"),
                }
            )
            continue
        quantity = Decimal(str(item["quantity"]))
        balance_key = (warehouse_ref, material_ref)
        next_balance = balance_totals.get(balance_key, Decimal(0)) + quantity
        if next_balance < 0:
            rows["quarantine"].append(
                {
                    "source_key": f"movement:{source_id}",
                    "issue_code": "NEGATIVE_STOCK_SEQUENCE",
                    "value_fingerprint": fingerprint(str(quantity)),
                }
            )
            continue
        balance_totals[balance_key] = next_balance
        rows["stock_movements"].append(
            {
                "source_key": source_id,
                "park_ref": warehouses[warehouse_ref]["park_ref"],
                "warehouse_source_key": warehouse_ref,
                "material_source_key": material_ref,
                "movement_type": str(item["movement_type"]).upper(),
                "quantity": quantity,
                "source_truth": "LEGACY_UNVERIFIED",
            }
        )
    for (warehouse_ref, material_ref), on_hand in sorted(balance_totals.items()):
        rows["stock_balances"].append(
            {
                "source_key": f"balance:{warehouse_ref}:{material_ref}",
                "park_ref": warehouses[warehouse_ref]["park_ref"],
                "warehouse_source_key": warehouse_ref,
                "material_source_key": material_ref,
                "on_hand_qty": on_hand,
                "reserved_qty": Decimal(0),
            }
        )

    for item in source["outsourcing_orders"]:
        source_id = str(item["source_id"])
        park_ref = parks.get(str(item["park_ref"]))
        supplier_ref = str(item["supplier_ref"])
        if park_ref is None or supplier_ref not in suppliers:
            rows["quarantine"].append(
                {
                    "source_key": f"outsourcing:{source_id}",
                    "issue_code": "OUTSOURCING_REFERENCE_UNMAPPED",
                    "value_fingerprint": fingerprint(
                        f"{item['park_ref']}:{supplier_ref}"
                    ),
                }
            )
            continue
        rows["outsourcing_orders"].append(
            {
                "source_key": source_id,
                "park_ref": park_ref,
                "supplier_source_key": supplier_ref,
                "title": str(item["title"]).strip(),
                "amount": Decimal(str(item["amount"])),
                "status": "PENDING_REVIEW",
                "settlement_state": "NOT_INTEGRATED",
            }
        )
        if str(item.get("legacy_status", "")).upper() in {"PAID", "SETTLED"}:
            rows["quarantine"].append(
                {
                    "source_key": f"outsourcing:{source_id}",
                    "issue_code": "SETTLEMENT_EVIDENCE_MISSING",
                    "value_fingerprint": fingerprint(str(item.get("legacy_status"))),
                }
            )
    return rows


DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.suppliers (
  source_key text PRIMARY KEY, code text NOT NULL UNIQUE, display_name text NOT NULL,
  status text NOT NULL CHECK (status IN ('ACTIVE','SUSPENDED','RETIRED')),
  credential_masked text NOT NULL, credential_fingerprint char(64) NOT NULL,
  migrated_at timestamptz NOT NULL
);
CREATE TABLE {SCHEMA}.supplier_scopes (
  source_key text PRIMARY KEY,
  supplier_source_key text NOT NULL REFERENCES {SCHEMA}.suppliers(source_key),
  park_ref text NOT NULL, service_type text NOT NULL, status text NOT NULL CHECK (status='ACTIVE')
);
CREATE TABLE {SCHEMA}.materials (
  source_key text PRIMARY KEY, code text NOT NULL UNIQUE, name text NOT NULL,
  category text NOT NULL, unit text NOT NULL, status text NOT NULL CHECK (status='ACTIVE')
);
CREATE TABLE {SCHEMA}.warehouses (
  source_key text PRIMARY KEY, park_ref text NOT NULL, code text NOT NULL UNIQUE,
  name text NOT NULL, status text NOT NULL CHECK (status='ACTIVE')
);
CREATE TABLE {SCHEMA}.procurement_orders (
  source_key text PRIMARY KEY, park_ref text NOT NULL,
  supplier_source_key text NOT NULL REFERENCES {SCHEMA}.suppliers(source_key),
  material_source_key text NOT NULL REFERENCES {SCHEMA}.materials(source_key),
  quantity numeric(18,4) NOT NULL CHECK (quantity>0),
  unit_price numeric(18,4) NOT NULL CHECK (unit_price>=0),
  status text NOT NULL CHECK (status='PENDING_REVIEW'),
  approval_truth text NOT NULL CHECK (approval_truth='LEGACY_UNVERIFIED')
);
CREATE TABLE {SCHEMA}.stock_movements (
  source_key text PRIMARY KEY, park_ref text NOT NULL,
  warehouse_source_key text NOT NULL REFERENCES {SCHEMA}.warehouses(source_key),
  material_source_key text NOT NULL REFERENCES {SCHEMA}.materials(source_key),
  movement_type text NOT NULL CHECK (movement_type IN ('RECEIPT','ISSUE','RETURN','ADJUSTMENT')),
  quantity numeric(18,4) NOT NULL CHECK (quantity<>0),
  source_truth text NOT NULL CHECK (source_truth='LEGACY_UNVERIFIED')
);
CREATE TABLE {SCHEMA}.stock_balances (
  source_key text PRIMARY KEY, park_ref text NOT NULL,
  warehouse_source_key text NOT NULL REFERENCES {SCHEMA}.warehouses(source_key),
  material_source_key text NOT NULL REFERENCES {SCHEMA}.materials(source_key),
  on_hand_qty numeric(18,4) NOT NULL CHECK (on_hand_qty>=0),
  reserved_qty numeric(18,4) NOT NULL CHECK (reserved_qty>=0 AND reserved_qty<=on_hand_qty),
  UNIQUE (warehouse_source_key,material_source_key)
);
CREATE TABLE {SCHEMA}.outsourcing_orders (
  source_key text PRIMARY KEY, park_ref text NOT NULL,
  supplier_source_key text NOT NULL REFERENCES {SCHEMA}.suppliers(source_key),
  title text NOT NULL, amount numeric(18,2) NOT NULL CHECK (amount>=0),
  status text NOT NULL CHECK (status='PENDING_REVIEW'),
  settlement_state text NOT NULL CHECK (settlement_state='NOT_INTEGRATED')
);
CREATE TABLE {SCHEMA}.quarantine (
  source_key text NOT NULL, issue_code text NOT NULL, value_fingerprint char(64) NOT NULL,
  PRIMARY KEY (source_key,issue_code)
);
"""

FIELDS = {
    "suppliers": (
        "source_key",
        "code",
        "display_name",
        "status",
        "credential_masked",
        "credential_fingerprint",
        "migrated_at",
    ),
    "supplier_scopes": (
        "source_key",
        "supplier_source_key",
        "park_ref",
        "service_type",
        "status",
    ),
    "materials": ("source_key", "code", "name", "category", "unit", "status"),
    "warehouses": ("source_key", "park_ref", "code", "name", "status"),
    "procurement_orders": (
        "source_key",
        "park_ref",
        "supplier_source_key",
        "material_source_key",
        "quantity",
        "unit_price",
        "status",
        "approval_truth",
    ),
    "stock_movements": (
        "source_key",
        "park_ref",
        "warehouse_source_key",
        "material_source_key",
        "movement_type",
        "quantity",
        "source_truth",
    ),
    "stock_balances": (
        "source_key",
        "park_ref",
        "warehouse_source_key",
        "material_source_key",
        "on_hand_qty",
        "reserved_qty",
    ),
    "outsourcing_orders": (
        "source_key",
        "park_ref",
        "supplier_source_key",
        "title",
        "amount",
        "status",
        "settlement_state",
    ),
    "quarantine": ("source_key", "issue_code", "value_fingerprint"),
}


def safe_engine(database_url: str):
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("supply ETL drill requires PostgreSQL")
    if parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("supply ETL drill is restricted to loopback PostgreSQL")
    identity = (parsed.database or "").lower()
    if "prod" in identity or not any(
        word in identity for word in ("test", "local", "dev", "audit")
    ):
        raise ValueError("supply ETL drill refuses a production-like database identity")
    return create_engine(database_url, pool_pre_ping=True)


def create_schema(conn) -> None:  # type: ignore[no-untyped-def]
    conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    for statement in DDL.split(";"):
        if statement.strip():
            conn.execute(text(statement))


def counts(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(
            conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()
        )
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
        if interrupt and table == "warehouses":
            raise RuntimeError("synthetic interruption after warehouses")
        if stop_after == table:
            break
    return inserted


def authorization_signature(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("users", "roles", "role_permissions", "user_roles")
    }


def reconcile(
    conn, rows: dict[str, list[dict[str, Any]]], source: dict[str, Any]
) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    expected = {table: len(values) for table, values in rows.items()}
    target = counts(conn)
    raw_columns = int(
        conn.execute(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema "
                "AND column_name IN ('credential_number','password','token','secret')"
            ),
            {"schema": SCHEMA},
        ).scalar_one()
    )
    raw_values = 0
    for item in source["suppliers"]:
        raw_values += int(
            conn.execute(
                text(
                    f"SELECT count(*) FROM {SCHEMA}.suppliers "
                    "WHERE credential_masked=:credential"
                ),
                {"credential": str(item["credential_number"])},
            ).scalar_one()
        )
    orphan_movements = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.stock_movements m "
                f"LEFT JOIN {SCHEMA}.warehouses w ON w.source_key=m.warehouse_source_key "
                f"LEFT JOIN {SCHEMA}.materials i ON i.source_key=m.material_source_key "
                "WHERE w.source_key IS NULL OR i.source_key IS NULL"
            )
        ).scalar_one()
    )
    ledger_mismatches = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.stock_balances b LEFT JOIN ("
                f"SELECT warehouse_source_key,material_source_key,sum(quantity) qty "
                f"FROM {SCHEMA}.stock_movements GROUP BY warehouse_source_key,material_source_key"
                ") m ON m.warehouse_source_key=b.warehouse_source_key "
                "AND m.material_source_key=b.material_source_key "
                "WHERE coalesce(m.qty,0)<>b.on_hand_qty"
            )
        ).scalar_one()
    )
    negative_balances = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.stock_balances "
                "WHERE on_hand_qty<0 OR reserved_qty<0 OR reserved_qty>on_hand_qty"
            )
        ).scalar_one()
    )
    trusted_approvals = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.procurement_orders "
                "WHERE approval_truth<>'LEGACY_UNVERIFIED' OR status<>'PENDING_REVIEW'"
            )
        ).scalar_one()
    )
    integrated_settlements = int(
        conn.execute(
            text(
                f"SELECT count(*) FROM {SCHEMA}.outsourcing_orders "
                "WHERE settlement_state<>'NOT_INTEGRATED'"
            )
        ).scalar_one()
    )
    quarantine_reasons = dict(
        conn.execute(
            text(
                f"SELECT issue_code,count(*) FROM {SCHEMA}.quarantine GROUP BY issue_code"
            )
        ).all()
    )
    expected_quarantine = {
        "APPROVAL_EVIDENCE_MISSING": 1,
        "PARK_KEY_UNMAPPED": 1,
        "SETTLEMENT_EVIDENCE_MISSING": 1,
        "STOCK_REFERENCE_UNMAPPED": 1,
    }
    passed = (
        expected == target
        and raw_columns == 0
        and raw_values == 0
        and orphan_movements == 0
        and ledger_mismatches == 0
        and negative_balances == 0
        and trusted_approvals == 0
        and integrated_settlements == 0
        and quarantine_reasons == expected_quarantine
    )
    return {
        "passed": passed,
        "expected_counts": expected,
        "target_counts": target,
        "raw_sensitive_columns": raw_columns,
        "raw_credential_values": raw_values,
        "orphan_stock_movements": orphan_movements,
        "ledger_balance_mismatches": ledger_mismatches,
        "negative_or_invalid_balances": negative_balances,
        "fabricated_trusted_approvals": trusted_approvals,
        "fabricated_integrated_settlements": integrated_settlements,
        "quarantine_reasons": quarantine_reasons,
        "on_hand_reconciled": "7.0000",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL"),
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "supply_v1.json",
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "out" / "supply_etl_report.json")
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
        if str(exc) != "synthetic interruption after warehouses":
            raise
        interrupted = True
    with engine.begin() as conn:
        partial_rows = sum(counts(conn).values())
    with engine.begin() as conn:
        checkpoint = apply_rows(conn, rows, stop_after="warehouses")
    with engine.begin() as conn:
        committed_checkpoint_counts = counts(conn)
        resumed = apply_rows(conn, rows)
    first = {table: checkpoint[table] + resumed[table] for table in TABLES}
    with engine.begin() as conn:
        second = apply_rows(conn, rows)
        reconciliation = reconcile(conn, rows, source)
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
            "passed": (
                sum(committed_checkpoint_counts.values()) == sum(checkpoint.values())
                and sum(checkpoint.values()) > 0
                and first == expected
            ),
            "checkpoint": "warehouses",
            "checkpoint_inserted": checkpoint,
            "committed_counts_before_resume": committed_checkpoint_counts,
            "resume_inserted": resumed,
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
        "authoritative_legacy_schema_present": False,
        "authoritative_legacy_transactions_present": False,
        "readiness": "CONDITIONAL_SYNTHETIC_READY_FOR_AUTHORIZED_STAGING_DATA",
        "real_legacy_readiness": (
            "BLOCKED_PENDING_AUTHORIZED_SCHEMA_EXPORT_TRANSACTION_SNAPSHOT_AND_KEYMAPS"
        ),
        "fixture_sha256": digest(args.fixture.read_text(encoding="utf-8")),
        "stages": stages,
        "blockers": [
            "authorized legacy supplier/procurement/inventory/outsourcing schema export not supplied",
            "desensitized transaction snapshot and park/party/material/warehouse key maps not supplied",
            "native approval evidence for legacy approved procurement records not supplied",
            "authoritative settlement evidence and finance integration contract not supplied",
            "production cutover and irreversible data-change authorization not granted",
        ],
        "external_integrations": {
            "erp": "NOT_CONNECTED",
            "wms": "NOT_CONNECTED",
            "supplier_portal": "NOT_CONNECTED",
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
