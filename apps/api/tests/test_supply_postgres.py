"""PostgreSQL 16 schema and concurrent stock-truth acceptance for supply."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party, PartyRole
from app.infrastructure.database.models.supply import (
    GoodsReceipt,
    PurchaseOrderLine,
    StockBalance,
)
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.supply.application.service import SupplyService
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    parsed = make_url(value)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.host not in {"127.0.0.1", "localhost"}
        or (parsed.database or "").lower() != "kwzy_party_test"
    ):
        pytest.fail("supply acceptance requires disposable loopback PostgreSQL kwzy_party_test")
    return value


def _factory():
    engine = create_engine(_url(), pool_pre_ping=True, pool_size=6, max_overflow=6)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int, user_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username="supply-pg",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed_receivable_order() -> dict[str, int]:
    _, Session = _factory()
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        tenant = ensure_default_tenant(session)
        park = Park(tenant_id=tenant.id, name=f"供应PG园-{suffix}", status="ACTIVE")
        user = User(
            tenant_id=tenant.id,
            username=f"supply_pg_{suffix.lower()}",
            password_hash="synthetic-not-login",
            real_name="供应PG验收员",
            status="ACTIVE",
            all_parks=True,
        )
        party = Party(
            tenant_id=tenant.id,
            party_type="ORGANIZATION",
            name=f"供应PG主体-{suffix}",
            credit_code=f"91310000{suffix}",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        session.add_all([park, user, party])
        session.flush()
        session.add(
            PartyRole(
                tenant_id=tenant.id,
                party_id=party.id,
                role_code="SUPPLIER",
                status="ACTIVE",
            )
        )
        session.commit()

        service = SupplyService(session, _ctx(int(tenant.id), int(user.id)))
        supplier = service.create_supplier(
            {"party_id": int(party.id), "code": f"SUP_{suffix}", "display_name": "PG供应商"}
        )
        service.add_supplier_scope(
            supplier["id"], {"park_id": int(park.id), "service_type": "PROCUREMENT"}
        )
        material = service.create_material(
            {
                "code": f"MAT_{suffix}",
                "name": "PG并发收货物料",
                "category": "验收",
                "unit": "件",
                "reorder_point": "0",
            }
        )
        warehouse = service.create_warehouse(
            {"park_id": int(park.id), "code": f"WH_{suffix}", "name": "PG主仓"}
        )
        requisition = service.create_requisition(
            {
                "park_id": int(park.id),
                "purpose": "PG并发收货",
                "lines": [
                    {
                        "material_id": material["id"],
                        "quantity": "10",
                        "estimated_unit_price": "8.50",
                    }
                ],
            },
            key=f"pg-proc-{suffix}",
        )
        row = service.repo.requisition(requisition["id"], for_update=True)
        assert row is not None
        row.status = "APPROVED"
        service.repo.save(row)
        session.commit()
        order = service.create_order(
            {
                "requisition_id": requisition["id"],
                "supplier_id": supplier["id"],
                "truth_mode": "LOCAL",
                "currency": "CNY",
                "lines": [
                    {"requisition_line_id": requisition["lines"][0]["id"], "unit_price": "8.00"}
                ],
            },
            key=f"pg-order-{suffix}",
        )
        acknowledged = service.acknowledge_order(
            order["id"], {"expected_version": order["lock_version"], "accepted": True}
        )
        return {
            "tenant_id": int(tenant.id),
            "user_id": int(user.id),
            "park_id": int(park.id),
            "warehouse_id": warehouse["id"],
            "material_id": material["id"],
            "order_id": acknowledged["id"],
            "order_line_id": acknowledged["lines"][0]["id"],
        }


def test_pg_supply_schema_constraints_indexes_and_append_only_ledger() -> None:
    engine, _ = _factory()
    inspector = inspect(engine)
    expected = {
        "supply_suppliers",
        "supply_supplier_park_scopes",
        "supply_supplier_qualifications",
        "supply_supplier_evaluations",
        "supply_materials",
        "supply_warehouses",
        "supply_stock_balances",
        "supply_stock_movements",
        "supply_procurement_requisitions",
        "supply_procurement_requisition_lines",
        "supply_purchase_orders",
        "supply_purchase_order_lines",
        "supply_goods_receipts",
        "supply_goods_receipt_lines",
        "supply_inventory_requisitions",
        "supply_inventory_requisition_lines",
        "supply_stocktakes",
        "supply_stocktake_lines",
        "supply_outsourcing_orders",
        "supply_outsourcing_events",
    }
    assert expected <= set(inspector.get_table_names())
    assert {item["name"] for item in inspector.get_unique_constraints("supply_stock_balances")} >= {
        "uk_supply_stock_balance",
        "uk_supply_stock_balance_tenant_id",
    }
    assert {item["name"] for item in inspector.get_check_constraints("supply_stock_balances")} >= {
        "ck_supply_stock_on_hand_nonnegative",
        "ck_supply_stock_reserved_valid",
        "ck_supply_stock_balance_lock",
    }
    movement_columns = {item["name"] for item in inspector.get_columns("supply_stock_movements")}
    assert {"quantity", "reference_type", "reference_id", "idempotency_key", "payload_hash"} <= (
        movement_columns
    )
    assert {item["name"] for item in inspector.get_indexes("supply_stock_movements")} >= {
        "ix_supply_stock_movement_timeline"
    }
    engine.dispose()


def test_pg_concurrent_full_receipt_has_one_winner_and_one_stock_truth() -> None:
    seed = _seed_receivable_order()
    engine, Session = _factory()
    barrier = threading.Barrier(2)

    def receive(marker: str) -> tuple[str, str | int]:
        with Session() as session:
            barrier.wait(timeout=15)
            try:
                result = SupplyService(
                    session, _ctx(seed["tenant_id"], seed["user_id"])
                ).receive_order(
                    seed["order_id"],
                    {
                        "warehouse_id": seed["warehouse_id"],
                        "lines": [{"order_line_id": seed["order_line_id"], "quantity": "10"}],
                    },
                    key=f"pg-receipt-{marker}-{uuid4().hex}",
                )
                return "ok", result["id"]
            except AppError as exc:
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(receive, ["a", "b"]))
    assert sum(1 for state, _ in results if state == "ok") == 1
    assert (
        sum(
            1
            for state, code in results
            if state == "error"
            and code in {"PURCHASE_ORDER_STATE_INVALID", "OVER_RECEIPT", "GOODS_RECEIPT_CONFLICT"}
        )
        == 1
    )

    with Session() as session:
        receipts = session.scalars(
            select(GoodsReceipt).where(
                GoodsReceipt.tenant_id == seed["tenant_id"],
                GoodsReceipt.order_id == seed["order_id"],
            )
        ).all()
        order_line = session.get(PurchaseOrderLine, seed["order_line_id"])
        balance = session.scalar(
            select(StockBalance).where(
                StockBalance.tenant_id == seed["tenant_id"],
                StockBalance.park_id == seed["park_id"],
                StockBalance.warehouse_id == seed["warehouse_id"],
                StockBalance.material_id == seed["material_id"],
            )
        )
        assert len(receipts) == 1
        assert order_line is not None and Decimal(order_line.received_qty) == Decimal(10)
        assert balance is not None
        assert Decimal(balance.on_hand_qty) == Decimal(10)
        assert Decimal(balance.reserved_qty) == Decimal(0)
    engine.dispose()
