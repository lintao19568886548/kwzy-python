import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

export type SupplyOverview = {
  active_suppliers: number;
  pending_procurement: number;
  low_stock_items: number;
  open_outsourcing: number;
  external_integrations: Record<string, string | boolean>;
  legacy_data_migration: { status: string; reason: string };
};
export type Supplier = { id: number; party_id: number; code: string; display_name: string; status: string; lock_version: number; scopes: Array<{ id: number; park_id: number; service_type: string; status: string }>; qualifications: Array<{ id: number; qualification_type: string; credential_masked: string; expires_on: string | null; status: string }>; evaluations: Array<{ id: number; score: number; evaluated_at: string }> };
export type Material = { id: number; code: string; name: string; category: string; unit: string; reorder_point: string; status: string };
export type Warehouse = { id: number; park_id: number; code: string; name: string; status: string };
export type Balance = { id: number; park_id: number; warehouse_id: number; material_id: number; on_hand_qty: string; reserved_qty: string; available_qty: string; lock_version: number };
export type ProcurementLine = { id: number; material_id: number; quantity: string; estimated_unit_price: string };
export type Procurement = { id: number; park_id: number; request_no: string; purpose: string; status: string; approval_id: number | null; approval_status: string | null; lock_version: number; lines: ProcurementLine[] };
export type OrderLine = { id: number; material_id: number; ordered_qty: string; received_qty: string; unit_price: string };
export type PurchaseOrder = { id: number; park_id: number; supplier_id: number; order_no: string; status: string; truth_mode: string; total_amount: string; lock_version: number; lines: OrderLine[] };
export type InventoryLine = { id: number; warehouse_id: number; material_id: number; requested_qty: string; reserved_qty: string; issued_qty: string; returned_qty: string };
export type InventoryRequisition = { id: number; park_id: number; request_no: string; purpose: string; status: string; approval_id: number | null; lock_version: number; lines: InventoryLine[] };
export type OutsourcingOrder = { id: number; park_id: number; supplier_id: number; order_no: string; title: string; sla_due_at: string; amount: string; status: string; settlement_state: string; lock_version: number; events: Array<{ id: number; event_type: string; occurred_at: string }> };
export type StockMovement = { id: number; park_id: number; balance_id: number; warehouse_id: number; material_id: number; movement_type: string; quantity: string; reference_type: string; reference_id: number; reverses_movement_id: number | null; occurred_at: string };
export type Stocktake = { id: number; park_id: number; warehouse_id: number; stocktake_no: string; status: string; approval_id: number | null; approval_status: string | null; lock_version: number; lines: Array<{ id: number; material_id: number; expected_qty: string; counted_qty: string; variance_qty: string; adjustment_movement_id: number | null }> };

export async function fetchSupplyWorkspace() {
  const responses = await Promise.all([
    http.get<Envelope<SupplyOverview>>("/supply/overview"),
    http.get<Envelope<PageResult<Supplier>>>("/supply/suppliers", { params: { page: 1, page_size: 200 } }),
    http.get<Envelope<Material[]>>("/supply/materials"),
    http.get<Envelope<Warehouse[]>>("/supply/warehouses"),
    http.get<Envelope<Balance[]>>("/supply/inventory/balances"),
    http.get<Envelope<Procurement[]>>("/supply/procurement/requisitions"),
    http.get<Envelope<PurchaseOrder[]>>("/supply/procurement/orders"),
    http.get<Envelope<InventoryRequisition[]>>("/supply/inventory/requisitions"),
    http.get<Envelope<OutsourcingOrder[]>>("/supply/outsourcing/orders"),
    http.get<Envelope<StockMovement[]>>("/supply/inventory/movements", { params: { limit: 200 } }),
    http.get<Envelope<Stocktake[]>>("/supply/inventory/stocktakes"),
  ]);
  return {
    overview: responses[0].data.data,
    suppliers: responses[1].data.data.items,
    materials: responses[2].data.data,
    warehouses: responses[3].data.data,
    balances: responses[4].data.data,
    procurements: responses[5].data.data,
    orders: responses[6].data.data,
    inventory: responses[7].data.data,
    outsourcing: responses[8].data.data,
    movements: responses[9].data.data,
    stocktakes: responses[10].data.data,
  };
}

export function idempotencyHeaders(prefix: string) {
  return { "Idempotency-Key": `${prefix}-${crypto.randomUUID()}` };
}
