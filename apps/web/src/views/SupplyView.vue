<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import {
  fetchSupplyWorkspace,
  idempotencyHeaders,
  type Balance,
  type InventoryRequisition,
  type Material,
  type OutsourcingOrder,
  type Procurement,
  type PurchaseOrder,
  type StockMovement,
  type Stocktake,
  type Supplier,
  type SupplyOverview,
  type Warehouse,
} from "@/api/supply";
import { useAuthStore } from "@/stores/auth";

type Tab = "overview" | "suppliers" | "procurement" | "inventory" | "outsourcing";
type Drawer = "supplier" | "qualification" | "material" | "warehouse" | "procurement" | "inventory" | "outsourcing" | "approval" | "order" | "stocktake" | null;
type ApprovalKind = "procurement" | "inventory" | "outsourcing" | "stocktake";

const auth = useAuthStore();
const activeTab = ref<Tab>("overview");
const drawer = ref<Drawer>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const online = ref(navigator.onLine);
const overview = ref<SupplyOverview | null>(null);
const suppliers = ref<Supplier[]>([]);
const materials = ref<Material[]>([]);
const warehouses = ref<Warehouse[]>([]);
const balances = ref<Balance[]>([]);
const procurements = ref<Procurement[]>([]);
const orders = ref<PurchaseOrder[]>([]);
const inventory = ref<InventoryRequisition[]>([]);
const outsourcing = ref<OutsourcingOrder[]>([]);
const movements = ref<StockMovement[]>([]);
const stocktakes = ref<Stocktake[]>([]);

const canSupplier = computed(() => auth.can("*") || auth.can("supplier:manage"));
const canCredential = computed(() => auth.can("*") || auth.can("supplier:credential"));
const canProcurement = computed(() => auth.can("*") || auth.can("procurement:request"));
const canOrder = computed(() => auth.can("*") || auth.can("procurement:order"));
const canInventory = computed(() => auth.can("*") || auth.can("inventory:manage") || auth.can("inventory:issue"));
const canOutsourcing = computed(() => auth.can("*") || auth.can("outsourcing:manage"));
const canAccept = computed(() => auth.can("*") || auth.can("outsourcing:accept"));
const canApprovalWrite = computed(() => auth.can("*") || auth.can("approval:write"));
const canAdjust = computed(() => auth.can("*") || auth.can("inventory:adjust"));

const supplierDraft = ref({ party_id: "", code: "", display_name: "", park_id: "" });
const qualificationTarget = ref<Supplier | null>(null);
const qualificationDraft = ref({ qualification_type: "", credential_number: "", issuer: "", effective_on: "", expires_on: "", attachment_id: "" });
const materialDraft = ref({ code: "", name: "", category: "维修耗材", unit: "件", reorder_point: "0" });
const warehouseDraft = ref({ park_id: "", code: "", name: "" });
const procurementDraft = ref({ park_id: "", purpose: "", material_id: "", quantity: "", estimated_unit_price: "0" });
const inventoryDraft = ref({ park_id: "", purpose: "", warehouse_id: "", material_id: "", quantity: "" });
const outsourcingDraft = ref({ park_id: "", supplier_id: "", title: "", sla_due_at: "", amount: "0" });
const procurementEditing = ref<Procurement | null>(null);
const approvalTarget = ref<{ kind: ApprovalKind; id: number; lock_version: number } | null>(null);
const approvalDraft = ref({ definition_code: "", priority: "MEDIUM" });
const orderTarget = ref<Procurement | null>(null);
const orderDraft = ref({ supplier_id: "", unit_price: "0", required_qualification: "" });
const stocktakeDraft = ref({ warehouse_id: "", material_id: "", counted_qty: "0" });

function clearMessages() { error.value = ""; errorStatus.value = 0; success.value = ""; }
function requestError(value: unknown, fallback: string) { error.value = value instanceof Error ? value.message : fallback; errorStatus.value = value instanceof ApiRequestError ? value.status : 0; }
function materialName(id: number) { const row = materials.value.find((item) => item.id === id); return row ? `${row.code} · ${row.name}` : `物料 #${id}`; }
function warehouseName(id: number) { const row = warehouses.value.find((item) => item.id === id); return row ? `${row.code} · ${row.name}` : `仓库 #${id}`; }
function supplierName(id: number) { return suppliers.value.find((item) => item.id === id)?.display_name || `供应商 #${id}`; }
function statusClass(status: string) { return ["REJECTED", "CANCELLED", "SUSPENDED", "REWORK"].includes(status) ? "risk" : ["DRAFT", "PENDING_APPROVAL", "ACK_PENDING", "PARTIALLY_RECEIVED", "PARTIALLY_ISSUED", "WAITING_ACCEPTANCE"].includes(status) ? "pending" : "ok"; }

async function loadAll() {
  clearMessages(); loading.value = true;
  try {
    const data = await fetchSupplyWorkspace();
    overview.value = data.overview; suppliers.value = data.suppliers; materials.value = data.materials;
    warehouses.value = data.warehouses; balances.value = data.balances; procurements.value = data.procurements;
    orders.value = data.orders; inventory.value = data.inventory; outsourcing.value = data.outsourcing;
    movements.value = data.movements; stocktakes.value = data.stocktakes;
  } catch (value) { requestError(value, "供应链工作区加载失败"); }
  finally { loading.value = false; }
}

async function command(action: () => Promise<unknown>, message: string, confirmText?: string) {
  if (!online.value) { error.value = "当前离线，危险操作已阻止"; return; }
  if (confirmText && !window.confirm(confirmText)) return;
  clearMessages(); saving.value = true;
  try { await action(); drawer.value = null; await loadAll(); success.value = message; }
  catch (value) { requestError(value, `${message}失败`); }
  finally { saving.value = false; }
}

async function createSupplier() {
  let supplierId = 0;
  await command(async () => {
    const response = await http.post("/supply/suppliers", { party_id: Number(supplierDraft.value.party_id), code: supplierDraft.value.code, display_name: supplierDraft.value.display_name || null });
    supplierId = Number(response.data.data.id);
    await http.post(`/supply/suppliers/${supplierId}/scopes`, { park_id: Number(supplierDraft.value.park_id), service_type: "GENERAL" });
  }, "供应商与园区范围已建立");
}
function openQualification(row: Supplier) {
  qualificationTarget.value = row;
  qualificationDraft.value = { qualification_type: "", credential_number: "", issuer: "", effective_on: "", expires_on: "", attachment_id: "" };
  drawer.value = "qualification";
}
async function createQualification() {
  const target = qualificationTarget.value;
  if (!target) return;
  await command(() => http.post(`/supply/suppliers/${target.id}/qualifications`, {
    qualification_type: qualificationDraft.value.qualification_type,
    credential_number: qualificationDraft.value.credential_number,
    issuer: qualificationDraft.value.issuer,
    effective_on: qualificationDraft.value.effective_on,
    expires_on: qualificationDraft.value.expires_on || null,
    attachment_id: qualificationDraft.value.attachment_id ? Number(qualificationDraft.value.attachment_id) : null,
  }), "供应商资质已登记且证件号仅保留掩码与指纹");
}
async function changeSupplierStatus(row: Supplier, status: "ACTIVE" | "SUSPENDED") {
  const reason = window.prompt(status === "SUSPENDED" ? "请输入暂停原因" : "请输入恢复原因");
  if (!reason) return;
  await command(() => http.post(`/supply/suppliers/${row.id}/status`, { status, expected_version: row.lock_version, reason }), status === "SUSPENDED" ? "供应商已暂停" : "供应商已恢复");
}
async function createMaterial() { await command(() => http.post("/supply/materials", { ...materialDraft.value, reorder_point: Number(materialDraft.value.reorder_point) }), "物料已建立"); }
async function createWarehouse() { await command(() => http.post("/supply/warehouses", { ...warehouseDraft.value, park_id: Number(warehouseDraft.value.park_id) }), "仓库已建立"); }
function openProcurement(row?: Procurement) {
  procurementEditing.value = row || null;
  const line = row?.lines[0];
  procurementDraft.value = row ? { park_id: String(row.park_id), purpose: row.purpose, material_id: String(line?.material_id || ""), quantity: line?.quantity || "", estimated_unit_price: line?.estimated_unit_price || "0" } : { park_id: "", purpose: "", material_id: "", quantity: "", estimated_unit_price: "0" };
  drawer.value = "procurement";
}
async function saveProcurement() {
  const payload = { park_id: Number(procurementDraft.value.park_id), purpose: procurementDraft.value.purpose, lines: [{ material_id: Number(procurementDraft.value.material_id), quantity: Number(procurementDraft.value.quantity), estimated_unit_price: Number(procurementDraft.value.estimated_unit_price) }] };
  const editing = procurementEditing.value;
  await command(
    () => editing ? http.put(`/supply/procurement/requisitions/${editing.id}/draft`, { ...payload, expected_version: editing.lock_version }) : http.post("/supply/procurement/requisitions", payload, { headers: idempotencyHeaders("pc-procurement") }),
    editing ? "采购申请草稿已更新" : "采购申请草稿已建立",
  );
}
async function createInventory() { await command(() => http.post("/supply/inventory/requisitions", { park_id: Number(inventoryDraft.value.park_id), purpose: inventoryDraft.value.purpose, lines: [{ warehouse_id: Number(inventoryDraft.value.warehouse_id), material_id: Number(inventoryDraft.value.material_id), quantity: Number(inventoryDraft.value.quantity) }] }, { headers: idempotencyHeaders("pc-inventory") }), "领用申请草稿已建立"); }
async function createOutsourcing() { await command(() => http.post("/supply/outsourcing/orders", { park_id: Number(outsourcingDraft.value.park_id), supplier_id: Number(outsourcingDraft.value.supplier_id), title: outsourcingDraft.value.title, deliverables: [{ code: "REPORT", name: "完工报告", required: true }], sla_due_at: new Date(outsourcingDraft.value.sla_due_at).toISOString(), amount: Number(outsourcingDraft.value.amount) }, { headers: idempotencyHeaders("pc-outsourcing") }), "外包服务草稿已建立"); }

function openApproval(kind: ApprovalKind, row: { id: number; lock_version: number }) {
  approvalTarget.value = { kind, id: row.id, lock_version: row.lock_version };
  approvalDraft.value = { definition_code: "", priority: kind === "outsourcing" ? "HIGH" : "MEDIUM" };
  drawer.value = "approval";
}
async function submitApproval() {
  const target = approvalTarget.value;
  if (!target) return;
  const paths: Record<ApprovalKind, string> = {
    procurement: `/supply/procurement/requisitions/${target.id}/submit`,
    inventory: `/supply/inventory/requisitions/${target.id}/submit`,
    outsourcing: `/supply/outsourcing/orders/${target.id}/submit`,
    stocktake: `/supply/inventory/stocktakes/${target.id}/submit`,
  };
  await command(() => http.post(paths[target.kind], { expected_version: target.lock_version, definition_code: approvalDraft.value.definition_code, priority: approvalDraft.value.priority }, { headers: idempotencyHeaders(`pc-${target.kind}-submit`) }), "已提交原生审批");
}
async function syncApproval(kind: Exclude<ApprovalKind, "stocktake">, id: number) {
  const paths = { procurement: `/supply/procurement/requisitions/${id}/sync`, inventory: `/supply/inventory/requisitions/${id}/sync`, outsourcing: `/supply/outsourcing/orders/${id}/sync` };
  await command(() => http.post(paths[kind]), "审批状态已同步");
}
async function cancelProcurement(row: Procurement) {
  const reason = window.prompt("请输入取消原因");
  if (!reason) return;
  await command(() => http.post(`/supply/procurement/requisitions/${row.id}/cancel`, { expected_version: row.lock_version, reason }, { headers: idempotencyHeaders("pc-procurement-cancel") }), "采购申请已取消", "确认取消该采购申请并撤回待审审批？");
}
function openOrder(row: Procurement) {
  orderTarget.value = row;
  orderDraft.value = { supplier_id: "", unit_price: row.lines[0]?.estimated_unit_price || "0", required_qualification: "" };
  drawer.value = "order";
}
async function createOrder() {
  const target = orderTarget.value;
  if (!target) return;
  await command(() => http.post("/supply/procurement/orders", { requisition_id: target.id, supplier_id: Number(orderDraft.value.supplier_id), currency: "CNY", truth_mode: "LOCAL", required_qualification: orderDraft.value.required_qualification || null, lines: target.lines.map((line) => ({ requisition_line_id: line.id, unit_price: Number(orderDraft.value.unit_price) })) }, { headers: idempotencyHeaders("pc-order") }), "采购订单已建立");
}
async function createStocktake() { await command(() => http.post("/supply/inventory/stocktakes", { warehouse_id: Number(stocktakeDraft.value.warehouse_id), lines: [{ material_id: Number(stocktakeDraft.value.material_id), counted_qty: Number(stocktakeDraft.value.counted_qty) }] }, { headers: idempotencyHeaders("pc-stocktake") }), "盘点草稿已建立"); }
async function postStocktake(row: Stocktake) { await command(() => http.post(`/supply/inventory/stocktakes/${row.id}/post`, undefined, { headers: idempotencyHeaders("pc-stocktake-post") }), "盘点已过账", "确认按已批准差异更新库存并追加流水？"); }
async function reverseMovement(row: StockMovement) { const reason = window.prompt("请输入冲正原因"); if (!reason) return; await command(() => http.post(`/supply/inventory/movements/${row.id}/reverse`, { reason }, { headers: idempotencyHeaders("pc-movement-reverse") }), "库存流水已冲正", "确认追加反向流水？原流水不会删除。"); }

async function acknowledge(row: PurchaseOrder) { await command(() => http.post(`/supply/procurement/orders/${row.id}/acknowledge`, { expected_version: row.lock_version, accepted: true }), "采购订单已确认", "确认供应商已线下确认该本地订单？"); }
async function receiveRemaining(row: PurchaseOrder) {
  const warehouse = warehouses.value.find((item) => item.park_id === row.park_id && item.status === "ACTIVE");
  if (!warehouse) { error.value = "该园区没有可用仓库"; return; }
  const lines = row.lines.map((line) => ({ order_line_id: line.id, quantity: Number(line.ordered_qty) - Number(line.received_qty) })).filter((line) => line.quantity > 0);
  await command(() => http.post(`/supply/procurement/orders/${row.id}/receipts`, { warehouse_id: warehouse.id, lines }, { headers: idempotencyHeaders("pc-receipt") }), "剩余订单数量已入库", `确认将 ${lines.length} 个订单行的全部剩余数量收入 ${warehouse.name}？`);
}
async function issueRemaining(row: InventoryRequisition) {
  const lines = row.lines.map((line) => ({ line_id: line.id, quantity: Number(line.requested_qty) - Number(line.issued_qty) })).filter((line) => line.quantity > 0);
  await command(() => http.post(`/supply/inventory/requisitions/${row.id}/issue`, { lines }, { headers: idempotencyHeaders("pc-issue") }), "已发放剩余批准物料", "确认扣减库存并发放全部剩余批准物料？");
}
async function outsourcingEvent(row: OutsourcingOrder, event_type: "STARTED" | "COMPLETED") { await command(() => http.post(`/supply/outsourcing/orders/${row.id}/events`, { event_type, note: "PC 供应链工作区操作", evidence: event_type === "COMPLETED" ? [{ type: "REPORT", reference: `local-evidence://${row.id}/${Date.now()}` }] : null }, { headers: idempotencyHeaders(`pc-${event_type.toLowerCase()}`) }), event_type === "STARTED" ? "外包服务已开工" : "外包服务已提交验收", event_type === "COMPLETED" ? "确认交付证据已齐备并提交租户验收？" : undefined); }
async function acceptOutsourcing(row: OutsourcingOrder, accepted: boolean) { await command(() => http.post(`/supply/outsourcing/orders/${row.id}/acceptance`, { accepted, reason: accepted ? null : "验收不通过，请按要求返工", score: accepted ? 5 : null, comment: accepted ? "PC 工作区验收通过" : null }, { headers: idempotencyHeaders("pc-acceptance") }), accepted ? "外包服务已验收" : "外包服务已退回返工", accepted ? "确认验收通过？该操作会追加供应商评价。" : "确认退回返工？"); }

function onlineUpdate() { online.value = navigator.onLine; }
onMounted(() => { window.addEventListener("online", onlineUpdate); window.addEventListener("offline", onlineUpdate); void loadAll(); });
onBeforeUnmount(() => { window.removeEventListener("online", onlineUpdate); window.removeEventListener("offline", onlineUpdate); });
</script>

<template>
  <section class="supply-page" data-testid="supply-page">
    <header class="page-head"><div><p class="eyebrow">SUPPLY CONTROL TOWER</p><h1 data-testid="supply-title">供应、采购、库存与外包</h1><p>审批、收货、领用、盘点和外包验收共用同一园区范围与不可变证据链。</p></div><button class="btn secondary" data-testid="supply-refresh" type="button" :disabled="loading" @click="loadAll">刷新真实数据</button></header>
    <div v-if="!online" class="notice warning" data-testid="supply-offline"><b>当前离线</b><span>提交、收货、发料和验收已阻止，网络恢复后请重试。</span><button type="button" @click="loadAll">重试</button></div>
    <div v-if="error" class="notice danger" data-testid="supply-error"><b>{{ errorStatus === 403 ? '权限不足' : errorStatus === 409 ? '并发或状态冲突' : '操作失败' }}</b><span>{{ error }}</span><button type="button" @click="loadAll">刷新</button></div>
    <div v-if="success" class="notice success" data-testid="supply-success">{{ success }}</div>

    <section class="metric-grid" aria-label="供应链指标"><article class="card metric"><span>有效供应商</span><strong>{{ overview?.active_suppliers ?? '—' }}</strong><small>真实企业主体与园区范围</small></article><article class="card metric risk"><span>待批采购</span><strong>{{ overview?.pending_procurement ?? '—' }}</strong><small>原生审批真值</small></article><article class="card metric risk"><span>低库存项</span><strong>{{ overview?.low_stock_items ?? '—' }}</strong><small>余额与补货线实时比较</small></article><article class="card metric"><span>进行中外包</span><strong>{{ overview?.open_outsourcing ?? '—' }}</strong><small>完成不等于已验收</small></article></section>
    <section class="truth-bar"><span><b>ERP/WMS/供应商门户</b> 未连接</span><span><b>旧数据迁移</b> {{ overview?.legacy_data_migration.status || 'BLOCKED' }}</span><span>本地受控订单、库存和验收是真值；未配置外部适配器时不会显示“已同步/已付款”。</span></section>

    <nav class="card tabs" aria-label="供应链工作区"><button v-for="tab in ([['overview','总览'],['suppliers','供应商'],['procurement','采购'],['inventory','库存'],['outsourcing','外包']] as const)" :key="tab[0]" type="button" :class="{ active: activeTab === tab[0] }" :data-testid="`supply-tab-${tab[0]}`" @click="activeTab = tab[0]">{{ tab[1] }}</button></nav>
    <div v-if="loading" class="card state" data-testid="supply-loading"><span class="spinner" /><p>正在读取 PostgreSQL 供应链真值…</p></div>

    <template v-else-if="activeTab === 'overview'"><section class="overview-grid"><article class="card panel"><div class="section-head"><div><p class="eyebrow">LOW STOCK</p><h2>补货风险</h2></div></div><div class="compact-list"><p v-for="row in balances.filter((item) => Number(item.available_qty) <= Number(materials.find((m) => m.id === item.material_id)?.reorder_point || 0))" :key="row.id"><b>{{ materialName(row.material_id) }}</b><span>{{ warehouseName(row.warehouse_id) }}</span><span class="status risk">可用 {{ row.available_qty }}</span></p><p v-if="balances.length === 0" class="empty">尚无库存余额</p></div></article><article class="card panel"><div class="section-head"><div><p class="eyebrow">PENDING ACTION</p><h2>待处理链路</h2></div></div><div class="compact-list"><p><b>采购审批</b><span>待批准申请</span><span>{{ procurements.filter((r) => r.status === 'PENDING_APPROVAL').length }}</span></p><p><b>收货</b><span>未完成订单</span><span>{{ orders.filter((r) => !['RECEIVED','CANCELLED','REJECTED'].includes(r.status)).length }}</span></p><p><b>外包验收</b><span>等待验收</span><span>{{ outsourcing.filter((r) => r.status === 'WAITING_ACCEPTANCE').length }}</span></p></div></article></section></template>

    <template v-else-if="activeTab === 'suppliers'"><section class="card panel"><div class="section-head"><div><p class="eyebrow">PARTY + PARK SCOPE</p><h2>受控供应商</h2></div><button v-if="canSupplier" class="btn" data-testid="supply-add-supplier" type="button" @click="drawer = 'supplier'">新增供应商</button></div><div class="card-grid"><article v-for="row in suppliers" :key="row.id" class="item-card"><header><b>{{ row.code }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header><h3>{{ row.display_name }}</h3><p>企业主体 #{{ row.party_id }} · 园区范围 {{ row.scopes.length }}</p><p v-for="qualification in row.qualifications" :key="qualification.id">{{ qualification.qualification_type }} · {{ qualification.credential_masked }} · {{ qualification.status }}</p><footer><span>有效资质 {{ row.qualifications.filter((q) => q.status === 'ACTIVE').length }} · 评价 {{ row.evaluations.length }}</span><span class="inline-actions"><button v-if="canCredential && row.status !== 'RETIRED'" class="link-btn" type="button" @click="openQualification(row)">登记资质</button><button v-if="canSupplier && row.status === 'ACTIVE'" class="link-btn risk-action" type="button" @click="changeSupplierStatus(row, 'SUSPENDED')">暂停</button><button v-if="canSupplier && row.status === 'SUSPENDED'" class="link-btn" type="button" @click="changeSupplierStatus(row, 'ACTIVE')">恢复</button></span></footer></article><p v-if="suppliers.length === 0" class="empty">当前范围没有供应商</p></div></section></template>

    <template v-else-if="activeTab === 'procurement'">
      <section class="card panel">
        <div class="section-head"><div><p class="eyebrow">NATIVE APPROVAL</p><h2>采购申请</h2></div><button v-if="canProcurement" class="btn" type="button" @click="openProcurement()">新建申请</button></div>
        <div class="table-wrap"><table class="table"><thead><tr><th>单号</th><th>用途</th><th>物料</th><th>审批</th><th>状态</th><th>操作</th></tr></thead><tbody>
          <tr v-for="row in procurements" :key="row.id"><td data-label="单号"><b>{{ row.request_no }}</b></td><td data-label="用途">{{ row.purpose }}</td><td data-label="物料">{{ row.lines.map((line) => materialName(line.material_id)).join('；') }}</td><td data-label="审批">{{ row.approval_status || '尚未提交' }}</td><td data-label="状态"><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></td><td data-label="操作"><div class="inline-actions"><button v-if="canProcurement && row.status === 'DRAFT'" class="link-btn" type="button" @click="openProcurement(row)">编辑</button><button v-if="canProcurement && canApprovalWrite && row.status === 'DRAFT'" class="link-btn" type="button" @click="openApproval('procurement', row)">提交审批</button><button v-if="canProcurement && row.status === 'PENDING_APPROVAL'" class="link-btn" type="button" @click="syncApproval('procurement', row.id)">同步审批</button><button v-if="canProcurement && ['DRAFT','PENDING_APPROVAL'].includes(row.status)" class="link-btn risk-action" type="button" @click="cancelProcurement(row)">取消</button><button v-if="canOrder && row.status === 'APPROVED'" class="link-btn" type="button" @click="openOrder(row)">建立订单</button></div></td></tr>
          <tr v-if="procurements.length === 0"><td class="empty" colspan="6">尚无采购申请</td></tr>
        </tbody></table></div>
      </section>
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">RECEIPT DRIVES STOCK</p><h2>采购订单与收货</h2></div></div><div class="card-grid"><article v-for="row in orders" :key="row.id" class="item-card"><header><b>{{ row.order_no }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header><h3>{{ supplierName(row.supplier_id) }}</h3><p>金额 ¥{{ row.total_amount }} · {{ row.truth_mode === 'LOCAL' ? '本地真值' : '等待外部确认' }}</p><footer><button v-if="canOrder && ['ISSUED','ACK_PENDING'].includes(row.status)" class="link-btn" type="button" @click="acknowledge(row)">确认订单</button><button v-if="canInventory && ['ISSUED','ACKNOWLEDGED','PARTIALLY_RECEIVED'].includes(row.status) && row.truth_mode === 'LOCAL'" class="link-btn risk-action" type="button" @click="receiveRemaining(row)">收货剩余</button></footer></article><p v-if="orders.length === 0" class="empty">尚无采购订单</p></div></section>
    </template>

    <template v-else-if="activeTab === 'inventory'">
      <section class="action-row"><button v-if="canInventory" class="btn" type="button" @click="drawer = 'material'">新增物料</button><button v-if="canInventory" class="btn secondary" type="button" @click="drawer = 'warehouse'">新增仓库</button><button v-if="canInventory" class="btn secondary" type="button" @click="drawer = 'inventory'">领用申请</button><button v-if="canAdjust" class="btn secondary" type="button" @click="drawer = 'stocktake'">新建盘点</button></section>
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">APPEND-ONLY LEDGER</p><h2>库存余额</h2></div></div><div class="table-wrap"><table class="table" data-testid="supply-balance-table"><thead><tr><th>物料</th><th>仓库</th><th>在库</th><th>预留</th><th>可用</th></tr></thead><tbody><tr v-for="row in balances" :key="row.id"><td data-label="物料">{{ materialName(row.material_id) }}</td><td data-label="仓库">{{ warehouseName(row.warehouse_id) }}</td><td data-label="在库">{{ row.on_hand_qty }}</td><td data-label="预留">{{ row.reserved_qty }}</td><td data-label="可用"><b>{{ row.available_qty }}</b></td></tr><tr v-if="balances.length === 0"><td class="empty" colspan="5">尚无入库流水，余额不会用假数据填充</td></tr></tbody></table></div></section>
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">RESERVE BEFORE ISSUE</p><h2>领用与发料</h2></div></div><div class="card-grid"><article v-for="row in inventory" :key="row.id" class="item-card"><header><b>{{ row.request_no }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header><h3>{{ row.purpose }}</h3><p>{{ row.lines.length }} 项 · 审批后预留 · 发料后扣减</p><footer><button v-if="canInventory && canApprovalWrite && row.status === 'DRAFT'" class="link-btn" type="button" @click="openApproval('inventory', row)">提交审批</button><button v-if="canInventory && row.status === 'PENDING_APPROVAL'" class="link-btn" type="button" @click="syncApproval('inventory', row.id)">同步审批</button><button v-if="canInventory && ['APPROVED','PARTIALLY_ISSUED'].includes(row.status)" class="link-btn risk-action" type="button" @click="issueRemaining(row)">发放剩余</button></footer></article><p v-if="inventory.length === 0" class="empty">尚无领用申请</p></div></section>
      <section class="overview-grid"><article class="card panel"><div class="section-head"><div><p class="eyebrow">STOCKTAKE</p><h2>盘点与差异</h2></div></div><div class="compact-list"><p v-for="row in stocktakes" :key="row.id"><b>{{ row.stocktake_no }}</b><span>{{ warehouseName(row.warehouse_id) }} · {{ row.status }}</span><span class="inline-actions"><button v-if="canAdjust && canApprovalWrite && row.status === 'DRAFT'" class="link-btn" type="button" @click="openApproval('stocktake', row)">提交</button><button v-if="canAdjust && ['APPROVED','PENDING_APPROVAL'].includes(row.status)" class="link-btn risk-action" type="button" @click="postStocktake(row)">批准后过账</button></span></p><p v-if="stocktakes.length === 0" class="empty">尚无盘点记录</p></div></article><article class="card panel"><div class="section-head"><div><p class="eyebrow">LEDGER HISTORY</p><h2>最近库存流水</h2></div></div><div class="compact-list"><p v-for="row in movements.slice(0, 12)" :key="row.id"><b>{{ row.movement_type }} {{ row.quantity }}</b><span>{{ materialName(row.material_id) }}</span><button v-if="canAdjust && row.movement_type === 'ADJUSTMENT' && !row.reverses_movement_id" class="link-btn risk-action" type="button" @click="reverseMovement(row)">冲正</button></p><p v-if="movements.length === 0" class="empty">尚无库存流水</p></div></article></section>
    </template>

    <template v-else><section class="card panel"><div class="section-head"><div><p class="eyebrow">DELIVERY ≠ ACCEPTANCE</p><h2>外包服务订单</h2></div><button v-if="canOutsourcing" class="btn" type="button" @click="drawer = 'outsourcing'">新建外包</button></div><div class="card-grid"><article v-for="row in outsourcing" :key="row.id" class="item-card"><header><b>{{ row.order_no }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header><h3>{{ row.title }}</h3><p>{{ supplierName(row.supplier_id) }} · SLA {{ row.sla_due_at.slice(0, 16).replace('T', ' ') }}</p><p>结算：{{ row.settlement_state }}（不伪报付款）</p><footer><button v-if="canOutsourcing && canApprovalWrite && row.status === 'DRAFT'" class="link-btn" type="button" @click="openApproval('outsourcing', row)">提交审批</button><button v-if="canOutsourcing && row.status === 'PENDING_APPROVAL'" class="link-btn" type="button" @click="syncApproval('outsourcing', row.id)">同步审批</button><button v-if="canOutsourcing && ['APPROVED','REWORK'].includes(row.status)" class="link-btn" type="button" @click="outsourcingEvent(row, 'STARTED')">开始履约</button><button v-if="canOutsourcing && row.status === 'IN_PROGRESS'" class="link-btn" type="button" @click="outsourcingEvent(row, 'COMPLETED')">提交验收</button><button v-if="canAccept && row.status === 'WAITING_ACCEPTANCE'" class="link-btn" type="button" @click="acceptOutsourcing(row, true)">验收通过</button><button v-if="canAccept && row.status === 'WAITING_ACCEPTANCE'" class="link-btn risk-action" type="button" @click="acceptOutsourcing(row, false)">退回返工</button></footer></article><p v-if="outsourcing.length === 0" class="empty">尚无外包服务订单</p></div></section></template>

    <aside v-if="drawer" class="drawer-backdrop" data-testid="supply-drawer" @click.self="drawer = null"><section class="drawer card">
      <header><div><p class="eyebrow">GOVERNED COMMAND</p><h2>供应链操作</h2></div><button class="close" type="button" aria-label="关闭" @click="drawer = null">×</button></header>
      <form v-if="drawer === 'supplier'" class="form" @submit.prevent="createSupplier"><label>企业主体 ID<input v-model="supplierDraft.party_id" required type="number" min="1" /></label><label>供应商编码<input v-model="supplierDraft.code" required pattern="[A-Za-z][A-Za-z0-9_-]+" /></label><label>显示名称<input v-model="supplierDraft.display_name" required /></label><label>园区 ID<input v-model="supplierDraft.park_id" required type="number" min="1" /></label><button class="btn" :disabled="saving" type="submit">建立主体关联和园区范围</button></form>
      <form v-else-if="drawer === 'qualification'" class="form" @submit.prevent="createQualification"><p class="form-hint">原始证件号只用于服务端指纹计算；响应、审计和页面仅显示掩码。</p><label>资质类型<input v-model="qualificationDraft.qualification_type" required maxlength="32" /></label><label>证件号<input v-model="qualificationDraft.credential_number" required autocomplete="off" maxlength="128" /></label><label>签发机构<input v-model="qualificationDraft.issuer" required maxlength="128" /></label><label>生效日期<input v-model="qualificationDraft.effective_on" required type="date" /></label><label>到期日期<input v-model="qualificationDraft.expires_on" type="date" /></label><label>证据附件 ID（可空）<input v-model="qualificationDraft.attachment_id" type="number" min="1" /></label><button class="btn" :disabled="saving" type="submit">登记受控资质</button></form>
      <form v-else-if="drawer === 'material'" class="form" @submit.prevent="createMaterial"><label>物料编码<input v-model="materialDraft.code" required /></label><label>名称<input v-model="materialDraft.name" required /></label><label>分类<input v-model="materialDraft.category" required /></label><label>单位<input v-model="materialDraft.unit" required /></label><label>补货线<input v-model="materialDraft.reorder_point" type="number" min="0" step="0.0001" /></label><button class="btn" :disabled="saving" type="submit">建立物料</button></form>
      <form v-else-if="drawer === 'warehouse'" class="form" @submit.prevent="createWarehouse"><label>园区 ID<input v-model="warehouseDraft.park_id" required type="number" min="1" /></label><label>仓库编码<input v-model="warehouseDraft.code" required /></label><label>仓库名称<input v-model="warehouseDraft.name" required /></label><button class="btn" :disabled="saving" type="submit">建立园区仓库</button></form>
      <form v-else-if="drawer === 'procurement'" class="form" @submit.prevent="saveProcurement"><label>园区 ID<input v-model="procurementDraft.park_id" required type="number" min="1" /></label><label>用途<input v-model="procurementDraft.purpose" required /></label><label>物料<select v-model="procurementDraft.material_id" required><option value="" disabled>请选择</option><option v-for="row in materials" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.name }}</option></select></label><label>数量<input v-model="procurementDraft.quantity" required type="number" min="0.0001" step="0.0001" /></label><label>估算单价<input v-model="procurementDraft.estimated_unit_price" type="number" min="0" step="0.01" /></label><button class="btn" :disabled="saving" type="submit">{{ procurementEditing ? '更新采购草稿' : '保存采购草稿' }}</button></form>
      <form v-else-if="drawer === 'inventory'" class="form" @submit.prevent="createInventory"><label>园区 ID<input v-model="inventoryDraft.park_id" required type="number" min="1" /></label><label>用途<input v-model="inventoryDraft.purpose" required /></label><label>仓库<select v-model="inventoryDraft.warehouse_id" required><option value="" disabled>请选择</option><option v-for="row in warehouses" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.name }}</option></select></label><label>物料<select v-model="inventoryDraft.material_id" required><option value="" disabled>请选择</option><option v-for="row in materials" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.name }}</option></select></label><label>数量<input v-model="inventoryDraft.quantity" required type="number" min="0.0001" step="0.0001" /></label><button class="btn" :disabled="saving" type="submit">保存领用草稿</button></form>
      <form v-else-if="drawer === 'outsourcing'" class="form" @submit.prevent="createOutsourcing"><label>园区 ID<input v-model="outsourcingDraft.park_id" required type="number" min="1" /></label><label>供应商<select v-model="outsourcingDraft.supplier_id" required><option value="" disabled>请选择</option><option v-for="row in suppliers.filter((item) => item.status === 'ACTIVE')" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.display_name }}</option></select></label><label>服务标题<input v-model="outsourcingDraft.title" required /></label><label>SLA 截止<input v-model="outsourcingDraft.sla_due_at" required type="datetime-local" /></label><label>金额<input v-model="outsourcingDraft.amount" required type="number" min="0" step="0.01" /></label><button class="btn" :disabled="saving" type="submit">保存外包草稿</button></form>
      <form v-else-if="drawer === 'approval'" class="form" @submit.prevent="submitApproval"><p class="form-hint">定义须先在审批中心发布；提交后业务状态仅从原生审批聚合同步。</p><label>审批定义编码<input v-model="approvalDraft.definition_code" required maxlength="64" /></label><label>优先级<select v-model="approvalDraft.priority"><option value="LOW">LOW</option><option value="MEDIUM">MEDIUM</option><option value="HIGH">HIGH</option><option value="URGENT">URGENT</option></select></label><button class="btn" :disabled="saving" type="submit">提交原生审批</button></form>
      <form v-else-if="drawer === 'order'" class="form" @submit.prevent="createOrder"><label>供应商<select v-model="orderDraft.supplier_id" required><option value="" disabled>请选择</option><option v-for="row in suppliers.filter((item) => item.status === 'ACTIVE')" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.display_name }}</option></select></label><label>统一单价<input v-model="orderDraft.unit_price" required type="number" min="0" step="0.0001" /></label><label>所需资质（可空）<input v-model="orderDraft.required_qualification" maxlength="32" /></label><button class="btn" :disabled="saving" type="submit">建立本地采购订单</button></form>
      <form v-else class="form" @submit.prevent="createStocktake"><label>仓库<select v-model="stocktakeDraft.warehouse_id" required><option value="" disabled>请选择</option><option v-for="row in warehouses" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.name }}</option></select></label><label>物料<select v-model="stocktakeDraft.material_id" required><option value="" disabled>请选择</option><option v-for="row in materials" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.name }}</option></select></label><label>实盘数量<input v-model="stocktakeDraft.counted_qty" required type="number" min="0" step="0.0001" /></label><button class="btn" :disabled="saving" type="submit">保存盘点草稿</button></form>
    </section></aside>
  </section>
</template>

<style scoped>
.supply-page{display:grid;gap:1rem;min-width:0;overflow-x:hidden}.page-head,.section-head,.drawer header{display:flex;align-items:center;justify-content:space-between;gap:1rem}.page-head h1{margin:.15rem 0;font-size:clamp(1.65rem,3vw,2.4rem);letter-spacing:-.04em}.page-head p:last-child{color:var(--muted)}.eyebrow{margin:0;color:#087b9c;font-size:.68rem;font-weight:900;letter-spacing:.14em}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8rem}.metric{padding:1rem;border-top:3px solid #1389aa}.metric.risk{border-top-color:#df6845}.metric span,.metric small{display:block;color:var(--muted)}.metric strong{display:block;margin:.2rem 0;color:#113d50;font-size:1.85rem}.truth-bar{display:grid;grid-template-columns:auto auto minmax(0,1fr);gap:1rem;padding:.8rem 1rem;border-left:4px solid #df6845;border-radius:10px;background:#fff2ed;color:#72331f;font-size:.76rem}.tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.35rem;padding:.45rem}.tabs button{border:0;border-radius:9px;padding:.65rem;background:transparent;color:var(--muted);cursor:pointer}.tabs button.active{background:#e6f4f7;color:#096e8c;font-weight:800}.panel{padding:1rem}.section-head h2,.drawer h2{margin:.15rem 0;font-size:1.08rem}.overview-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem;margin-top:.8rem}.item-card{padding:.85rem;border:1px solid var(--border);border-radius:12px;background:#fbfcfd}.item-card header,.item-card footer{display:flex;align-items:center;justify-content:space-between;gap:.5rem;flex-wrap:wrap}.item-card h3{margin:.6rem 0 .1rem}.item-card p,.item-card footer{color:var(--muted);font-size:.74rem}.table-wrap{max-width:100%;overflow-x:auto}.table td{vertical-align:middle}.compact-list p{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto;gap:.7rem;padding:.65rem;margin:0;border-bottom:1px solid var(--border)}.status{display:inline-flex;width:max-content;padding:.18rem .5rem;border-radius:99px;font-size:.68rem;font-weight:800}.status.ok{background:#e2f4ed;color:#0e6e53}.status.pending{background:#fff1d0;color:#805600}.status.risk{background:#ffe9e2;color:#ae3b21}.notice{display:flex;align-items:center;gap:.7rem;padding:.7rem .9rem;border-radius:10px;font-size:.8rem}.notice button{margin-left:auto;border:0;background:transparent;color:inherit;font-weight:800}.notice.success{background:#e5f5ef;color:#0e6e53}.notice.warning{background:#fff2d5;color:#805b09}.notice.danger{background:#ffe9e2;color:#a33720}.secondary{border:1px solid #91b7c4;background:#fff;color:#0b718f}.state,.empty{min-height:120px;display:grid;place-content:center;justify-items:center;color:var(--muted);text-align:center}.spinner{width:1.6rem;height:1.6rem;border:3px solid #dce8e4;border-top-color:#0b7899;border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.action-row,.inline-actions{display:flex;gap:.6rem;flex-wrap:wrap}.link-btn{border:0;background:transparent;color:#087b9c;font-weight:800;cursor:pointer}.risk-action{color:#c74b2d}.drawer-backdrop{position:fixed;inset:0;z-index:30;display:flex;justify-content:flex-end;background:rgba(6,25,34,.38)}.drawer{width:min(440px,100%);height:100%;padding:1.2rem;border-radius:18px 0 0 18px;overflow:auto}.close{border:0;background:transparent;font-size:1.8rem;color:var(--muted);cursor:pointer}.form{display:grid;gap:.8rem;margin-top:1rem}.form-hint{padding:.65rem;border-radius:9px;background:#eaf5f7;color:#245d70;font-size:.75rem}.form label{display:grid;gap:.35rem;color:var(--muted);font-size:.78rem}.form input,.form select{width:100%;padding:.65rem .7rem;border:1px solid var(--border);border-radius:9px;background:#fff;color:var(--text)}
@media(max-width:1080px){.metric-grid,.card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.truth-bar{grid-template-columns:1fr 1fr}.truth-bar span:last-child{grid-column:1/-1}}
@media(max-width:640px){.page-head,.section-head{align-items:flex-start}.metric-grid,.card-grid,.overview-grid,.truth-bar{grid-template-columns:1fr}.truth-bar span:last-child{grid-column:auto}.tabs button{padding:.55rem .2rem;font-size:.7rem}.panel{padding:.8rem}.table-wrap{overflow:visible}.table,.table tbody{display:block;width:100%;min-width:0}.table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.table tr{display:grid;gap:.45rem;padding:.75rem 0;border-bottom:1px solid var(--border)}.table td{display:grid;grid-template-columns:minmax(6rem,40%) minmax(0,1fr);gap:.5rem;padding:0;border:0;overflow-wrap:anywhere}.table td::before{content:attr(data-label);color:var(--muted);font-size:.72rem;font-weight:700}.table td.empty{grid-template-columns:1fr}.table td.empty::before{content:none}.compact-list p{grid-template-columns:1fr}.notice{align-items:flex-start;flex-wrap:wrap}.notice button{margin-left:0}.drawer{border-radius:0}}
</style>
