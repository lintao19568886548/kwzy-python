"""contract lifecycle v2

Revision ID: k7f35a0b2d19
Revises: j6e24f9a1c08
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k7f35a0b2d19"
down_revision: Union[str, None] = "j6e24f9a1c08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical_snapshot(value: dict[str, Any]) -> tuple[dict[str, Any], str]:
    normalized = _json_value(value)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return normalized, hashlib.sha256(encoded).hexdigest()


def _create_tables() -> None:
    op.create_table(
        "lease_change_orders",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("change_no", sa.String(64), nullable=False),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("base_version_no", sa.Integer(), nullable=False),
        sa.Column("applied_version_no", sa.Integer(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposal_json", sa.JSON(), nullable=False),
        sa.Column("proposal_checksum", sa.String(64), nullable=False),
        sa.Column("proposal_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("approval_id", FK_TYPE, nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["approval_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "change_no", name="uk_lease_change_no"),
    )
    op.create_index("ix_lease_change_contract_id", "lease_change_orders", ["contract_id"])
    op.create_index(
        "ix_lease_change_due",
        "lease_change_orders",
        ["tenant_id", "status", "effective_date"],
    )
    op.create_index(
        "uk_lease_change_inflight",
        "lease_change_orders",
        ["tenant_id", "contract_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('SUBMITTED', 'APPROVED')"),
        sqlite_where=sa.text("status IN ('SUBMITTED', 'APPROVED')"),
    )
    op.create_index(
        "uk_lease_change_idempotency",
        "lease_change_orders",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "lease_exit_settlements",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("change_order_id", FK_TYPE, nullable=True),
        sa.Column("settlement_no", sa.String(64), nullable=False),
        sa.Column("contract_version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("handover_date", sa.Date(), nullable=True),
        sa.Column("inspection_summary", sa.Text(), nullable=True),
        sa.Column("meter_readings_json", sa.JSON(), nullable=True),
        sa.Column("held_deposit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("outstanding_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "outstanding_source",
            sa.String(32),
            nullable=False,
            server_default="BILLING_SCOPED_READ",
        ),
        sa.Column("outstanding_as_of", sa.DateTime(), nullable=False),
        sa.Column("receivable_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("deduction_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "refund_adjustment_total", sa.Numeric(14, 2), nullable=False, server_default="0"
        ),
        sa.Column("net_due_from_party", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_due_to_party", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "financial_clearance_status",
            sa.String(32),
            nullable=False,
            server_default="UNCONFIRMED",
        ),
        sa.Column("clearance_evidence_attachment_id", FK_TYPE, nullable=True),
        sa.Column("clearance_reference", sa.String(128), nullable=True),
        sa.Column("clearance_reason", sa.Text(), nullable=True),
        sa.Column("clearance_by", FK_TYPE, nullable=True),
        sa.Column("clearance_at", sa.DateTime(), nullable=True),
        sa.Column("approval_id", FK_TYPE, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["change_order_id"], ["lease_change_orders.id"]),
        sa.ForeignKeyConstraint(["clearance_evidence_attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["clearance_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approval_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "settlement_no", name="uk_lease_exit_settlement_no"
        ),
        sa.UniqueConstraint("change_order_id", name="uk_lease_exit_change_order"),
    )
    op.create_index("ix_lease_exit_contract_id", "lease_exit_settlements", ["contract_id"])
    op.create_index(
        "ix_lease_exit_scope_status",
        "lease_exit_settlements",
        ["tenant_id", "park_id", "status"],
    )
    op.create_index(
        "uk_lease_exit_open",
        "lease_exit_settlements",
        ["tenant_id", "contract_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('DRAFT', 'SUBMITTED', 'APPROVED')"),
        sqlite_where=sa.text("status IN ('DRAFT', 'SUBMITTED', 'APPROVED')"),
    )
    op.create_index(
        "uk_lease_exit_idempotency",
        "lease_exit_settlements",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "lease_contract_versions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("base_version_no", sa.Integer(), nullable=True),
        sa.Column("change_order_id", FK_TYPE, nullable=True),
        sa.Column("exit_settlement_id", FK_TYPE, nullable=True),
        sa.Column("approval_id", FK_TYPE, nullable=True),
        sa.Column("effective_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["change_order_id"], ["lease_change_orders.id"]),
        sa.ForeignKeyConstraint(["exit_settlement_id"], ["lease_exit_settlements.id"]),
        sa.ForeignKeyConstraint(["approval_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "contract_id", "version_no", name="uk_lease_contract_version"
        ),
    )
    op.create_index("ix_lease_version_contract_id", "lease_contract_versions", ["contract_id"])
    op.create_index(
        "ix_lease_version_timeline",
        "lease_contract_versions",
        ["tenant_id", "contract_id", "version_no"],
    )

    op.create_table(
        "lease_charge_items",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("charge_code", sa.String(64), nullable=False),
        sa.Column("charge_type", sa.String(32), nullable=False),
        sa.Column("calculation_method", sa.String(32), nullable=False),
        sa.Column("billing_cycle", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("tax_rate", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("rules_json", sa.JSON(), nullable=True),
        sa.Column("source_term_id", FK_TYPE, nullable=True),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="CONFIRMED"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "contract_id", "charge_code", name="uk_lease_charge_code"
        ),
    )
    op.create_index("ix_lease_charge_contract_id", "lease_charge_items", ["contract_id"])
    op.create_index(
        "ix_lease_charge_contract",
        "lease_charge_items",
        ["tenant_id", "contract_id", "sort_order", "id"],
    )

    op.create_table(
        "lease_performance_schedules",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("charge_item_id", FK_TYPE, nullable=True),
        sa.Column("contract_version_no", sa.Integer(), nullable=False),
        sa.Column("charge_code", sa.String(64), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("area", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("rule_refs_json", sa.JSON(), nullable=True),
        sa.Column("deterministic_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PLANNED"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(
            ["charge_item_id"], ["lease_charge_items.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "deterministic_key", name="uk_lease_schedule_deterministic"
        ),
    )
    op.create_index("ix_lease_schedule_contract_id", "lease_performance_schedules", ["contract_id"])
    op.create_index(
        "ix_lease_schedule_contract_period",
        "lease_performance_schedules",
        ["tenant_id", "contract_id", "contract_version_no", "period_start"],
    )

    op.create_table(
        "lease_exit_items",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("settlement_id", FK_TYPE, nullable=False),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("evidence_attachment_id", FK_TYPE, nullable=True),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("source_ref", sa.String(128), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["settlement_id"], ["lease_exit_settlements.id"]),
        sa.ForeignKeyConstraint(["evidence_attachment_id"], ["attachments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lease_exit_item_settlement",
        "lease_exit_items",
        ["tenant_id", "settlement_id", "sort_order", "id"],
    )

    op.create_table(
        "lease_contract_documents",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("contract_version_no", sa.Integer(), nullable=True),
        sa.Column("change_order_id", FK_TYPE, nullable=True),
        sa.Column("exit_settlement_id", FK_TYPE, nullable=True),
        sa.Column("attachment_id", FK_TYPE, nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signature_provider", sa.String(32), nullable=True),
        sa.Column("signature_ref", sa.String(128), nullable=True),
        sa.Column("live_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["change_order_id"], ["lease_change_orders.id"]),
        sa.ForeignKeyConstraint(["exit_settlement_id"], ["lease_exit_settlements.id"]),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "contract_id",
            "document_type",
            "document_version",
            name="uk_lease_document_version",
        ),
    )
    op.create_index("ix_lease_document_contract_id", "lease_contract_documents", ["contract_id"])
    op.create_index(
        "ix_lease_document_contract",
        "lease_contract_documents",
        ["tenant_id", "contract_id", "status", "id"],
    )


def _backfill_existing_contracts() -> None:
    bind = op.get_bind()
    charge_table = sa.table(
        "lease_charge_items",
        sa.column("tenant_id", FK_TYPE),
        sa.column("contract_id", FK_TYPE),
        sa.column("charge_code", sa.String()),
        sa.column("charge_type", sa.String()),
        sa.column("calculation_method", sa.String()),
        sa.column("billing_cycle", sa.String()),
        sa.column("currency", sa.String()),
        sa.column("start_date", sa.Date()),
        sa.column("end_date", sa.Date()),
        sa.column("due_day", sa.Integer()),
        sa.column("amount", sa.Numeric()),
        sa.column("unit_price", sa.Numeric()),
        sa.column("tax_rate", sa.Numeric()),
        sa.column("rules_json", sa.JSON()),
        sa.column("source_term_id", FK_TYPE),
        sa.column("review_status", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    version_table = sa.table(
        "lease_contract_versions",
        sa.column("tenant_id", FK_TYPE),
        sa.column("park_id", FK_TYPE),
        sa.column("contract_id", FK_TYPE),
        sa.column("version_no", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("schema_version", sa.Integer()),
        sa.column("snapshot_json", sa.JSON()),
        sa.column("checksum", sa.String()),
        sa.column("reason", sa.String()),
        sa.column("base_version_no", sa.Integer()),
        sa.column("effective_at", sa.DateTime()),
        sa.column("created_by", FK_TYPE),
    )

    rows = bind.execute(
        sa.text(
            "SELECT id, tenant_id, park_id, party_id, contract_no, status, start_date, "
            "end_date, increase_date, increase_rate, deposit_amount, remark, created_by, "
            "created_at, updated_at FROM lease_contracts ORDER BY id"
        )
    ).mappings()
    versioned_statuses = {"ACTIVE", "EXPIRING", "RENEWED", "TERMINATED", "BREACHED"}
    for row in rows:
        contract_id = int(row["id"])
        units = list(
            bind.execute(
                sa.text(
                    "SELECT id, unit_id, occupied_area, unit_rent_price "
                    "FROM lease_contract_units WHERE tenant_id=:tenant_id "
                    "AND contract_id=:contract_id ORDER BY unit_id, id"
                ),
                {"tenant_id": row["tenant_id"], "contract_id": contract_id},
            ).mappings()
        )
        terms = list(
            bind.execute(
                sa.text(
                    "SELECT id, term_type, effective_date, end_date, rate, amount, "
                    "description, sort_order FROM lease_terms WHERE tenant_id=:tenant_id "
                    "AND contract_id=:contract_id ORDER BY sort_order, id"
                ),
                {"tenant_id": row["tenant_id"], "contract_id": contract_id},
            ).mappings()
        )
        rules: list[dict[str, Any]] = []
        review_required = False
        for term in terms:
            term_type = str(term["term_type"] or "").upper()
            if term_type == "INCREASE" and term["effective_date"] and term["rate"] is not None:
                rules.append(
                    {
                        "type": "INCREASE",
                        "effective_date": term["effective_date"],
                        "rate": term["rate"],
                        "source_term_id": term["id"],
                    }
                )
            elif term_type == "RENT_FREE" and term["effective_date"] and term["end_date"]:
                rules.append(
                    {
                        "type": "RENT_FREE",
                        "effective_date": term["effective_date"],
                        "end_date": term["end_date"],
                        "source_term_id": term["id"],
                    }
                )
            else:
                review_required = True
        if row["increase_date"] and row["increase_rate"] is not None:
            rules.append(
                {
                    "type": "INCREASE",
                    "effective_date": row["increase_date"],
                    "rate": row["increase_rate"],
                    "source": "lease_contracts",
                }
            )

        charges: list[dict[str, Any]] = []
        for index, unit in enumerate(units):
            unit_price = Decimal(str(unit["unit_rent_price"] or 0))
            if unit_price <= 0:
                continue
            charge = {
                "tenant_id": row["tenant_id"],
                "contract_id": contract_id,
                "charge_code": f"LEGACY_RENT_U{unit['unit_id']}",
                "charge_type": "RENT",
                "calculation_method": "PER_AREA",
                "billing_cycle": "MONTHLY",
                "currency": "CNY",
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "due_day": 1,
                "amount": None,
                "unit_price": unit_price,
                "tax_rate": Decimal("0"),
                "rules_json": _json_value(rules) or None,
                "source_term_id": None,
                "review_status": "REVIEW_REQUIRED" if review_required else "CONFIRMED",
                "sort_order": index,
            }
            bind.execute(sa.insert(charge_table).values(**charge))
            charges.append(
                {
                    key: value
                    for key, value in charge.items()
                    if key not in {"tenant_id", "contract_id", "source_term_id"}
                }
            )

        status = str(row["status"] or "DRAFT").upper()
        version_no = 1 if status in versioned_statuses else 0
        bind.execute(
            sa.text(
                "UPDATE lease_contracts SET contract_type='LEASE', currency='CNY', "
                "current_version_no=:version_no, lock_version=1, source_system='MANUAL' "
                "WHERE id=:id"
            ),
            {"id": contract_id, "version_no": version_no},
        )
        if version_no == 0:
            continue

        snapshot, checksum = _canonical_snapshot(
            {
                "schema_version": 1,
                "contract": {
                    "id": contract_id,
                    "park_id": row["park_id"],
                    "party_id": row["party_id"],
                    "contract_no": row["contract_no"],
                    "contract_type": "LEASE",
                    "currency": "CNY",
                    "status": status,
                    "start_date": row["start_date"],
                    "end_date": row["end_date"],
                    "deposit_amount": row["deposit_amount"],
                    "remark": row["remark"],
                },
                "units": [dict(unit) for unit in units],
                "charges": charges,
                "legacy_terms": [
                    {
                        **dict(term),
                        "mapping_status": (
                            "CONVERTED_RULE"
                            if str(term["term_type"] or "").upper() in {"INCREASE", "RENT_FREE"}
                            else "REVIEW_REQUIRED"
                        ),
                    }
                    for term in terms
                ],
                "schedules": [],
                "migration_source": "lease_v1_backfill",
            }
        )
        effective_at = datetime.combine(row["start_date"], time.min)
        bind.execute(
            sa.insert(version_table).values(
                tenant_id=row["tenant_id"],
                park_id=row["park_id"],
                contract_id=contract_id,
                version_no=1,
                status=status,
                schema_version=1,
                snapshot_json=snapshot,
                checksum=checksum,
                reason="V1_MIGRATION_BACKFILL",
                base_version_no=None,
                effective_at=effective_at,
                created_by=row["created_by"],
            )
        )


def upgrade() -> None:
    with op.batch_alter_table("lease_contracts") as batch:
        batch.add_column(sa.Column("contract_type", sa.String(32), nullable=True, server_default="LEASE"))
        batch.add_column(sa.Column("currency", sa.String(3), nullable=True, server_default="CNY"))
        batch.add_column(sa.Column("approval_status", sa.String(32), nullable=True))
        batch.add_column(sa.Column("signed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("effective_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("terminated_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("current_version_no", sa.Integer(), nullable=True, server_default="0"))
        batch.add_column(sa.Column("lock_version", sa.Integer(), nullable=True, server_default="1"))
        batch.add_column(sa.Column("source_system", sa.String(32), nullable=True, server_default="MANUAL"))
        batch.add_column(sa.Column("source_ref", sa.String(128), nullable=True))

    _create_tables()
    _backfill_existing_contracts()

    with op.batch_alter_table("lease_contracts") as batch:
        batch.alter_column("contract_type", nullable=False, server_default=None)
        batch.alter_column("currency", nullable=False, server_default=None)
        batch.alter_column("current_version_no", nullable=False, server_default=None)
        batch.alter_column("lock_version", nullable=False, server_default=None)
        batch.alter_column("source_system", nullable=False, server_default=None)
        batch.create_index(
            "ix_lease_contract_scope_status_end",
            ["tenant_id", "park_id", "status", "end_date"],
        )
        batch.create_index(
            "ix_lease_contract_scope_party",
            ["tenant_id", "party_id", "status"],
        )
    op.create_index(
        "uk_lease_contract_source_ref",
        "lease_contracts",
        ["tenant_id", "source_system", "source_ref"],
        unique=True,
        postgresql_where=sa.text("source_ref IS NOT NULL"),
        sqlite_where=sa.text("source_ref IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("lease_contract_documents")
    op.drop_table("lease_contract_versions")
    op.drop_table("lease_performance_schedules")
    op.drop_table("lease_charge_items")
    op.drop_table("lease_exit_items")
    op.drop_table("lease_exit_settlements")
    op.drop_table("lease_change_orders")

    op.drop_index("uk_lease_contract_source_ref", table_name="lease_contracts")
    with op.batch_alter_table("lease_contracts") as batch:
        batch.drop_index("ix_lease_contract_scope_party")
        batch.drop_index("ix_lease_contract_scope_status_end")
        batch.drop_column("source_ref")
        batch.drop_column("source_system")
        batch.drop_column("lock_version")
        batch.drop_column("current_version_no")
        batch.drop_column("terminated_at")
        batch.drop_column("effective_at")
        batch.drop_column("signed_at")
        batch.drop_column("approval_status")
        batch.drop_column("currency")
        batch.drop_column("contract_type")
