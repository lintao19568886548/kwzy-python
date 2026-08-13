<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type Park = { id: number; name: string };
type SpaceNode = {
  id: number;
  park_id: number;
  parent_id: number | null;
  code: string;
  name: string;
  node_type: "AREA" | "BUILDING" | "FLOOR";
  sort_order: number;
  status: string;
  children: SpaceNode[];
};
type FlatSpace = SpaceNode & { depth: number };
type UnitRow = {
  id: number;
  park_id: number;
  building_id: number;
  code: string;
  name: string;
  logical_id: string;
  version_no: number;
  lock_version: number;
  usage_type: string;
  billing_unit: string;
  rentable_area: number;
  used_area: number;
  available_area: number;
  base_rent_price: number;
  status: string;
  space_code: string | null;
  space_name: string | null;
  valid_from: string | null;
  valid_to: string | null;
};
type RentSummary = {
  inventory_count: number;
  rentable_area: number;
  used_area: number;
  available_area: number;
  occupancy_rate: number;
  status_counts: Record<string, number>;
};
type MatrixGroup = {
  space_id: number;
  space_code: string;
  space_name: string;
  node_type: string;
  units: UnitRow[];
};
type LeaseSummary = {
  contract_id: number;
  contract_no: string;
  contract_status: string;
  party_name: string;
  occupied_area: number;
  start_date: string;
  end_date: string;
};
type WorkOrderSummary = {
  id: number;
  title: string;
  status: string;
  priority: string;
  due_at: string | null;
};
type Lineage = {
  operation_id: string;
  operation_type: string;
  source_unit_id: number;
  target_unit_id: number;
};
type UnitDetail = UnitRow & {
  history: UnitRow[];
  lineage: Lineage[];
  effective_leases: LeaseSummary[];
  work_orders: WorkOrderSummary[];
  can_split_merge: boolean;
  blocking_reason: string | null;
};
type DialogKind = "space" | "unit" | "edit-unit" | "version" | "split" | "merge";

const auth = useAuthStore();
const parks = ref<Park[]>([]);
const selectedParkId = ref<number | null>(null);
const spaces = ref<SpaceNode[]>([]);
const selectedSpaceId = ref<number | null>(null);
const units = ref<UnitRow[]>([]);
const matrix = ref<MatrixGroup[]>([]);
const summary = ref<RentSummary | null>(null);
const selectedUnit = ref<UnitDetail | null>(null);
const viewMode = ref<"matrix" | "list">("matrix");
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");
const dialog = ref<DialogKind | null>(null);

const filters = reactive({ status: "", usage_type: "", keyword: "" });
const spaceForm = reactive({
  id: null as number | null,
  parent_id: "",
  code: "",
  name: "",
  node_type: "BUILDING",
  sort_order: "0",
  status: "ACTIVE",
});
const unitForm = reactive({
  building_id: "",
  code: "",
  name: "",
  rentable_area: "",
  usage_type: "FACTORY",
  billing_unit: "SQM",
  base_rent_price: "0",
});
const editForm = reactive({ name: "", base_rent_price: "", status: "VACANT" });
const versionForm = reactive({ building_id: "", code: "", name: "", rentable_area: "" });
const splitForm = reactive({
  code1: "",
  name1: "",
  area1: "",
  code2: "",
  name2: "",
  area2: "",
});
const mergeForm = reactive({ second_unit_id: "", code: "", name: "" });

const canWrite = computed(() => auth.can("unit:write") || auth.can("*"));
const flatSpaces = computed<FlatSpace[]>(() => {
  const result: FlatSpace[] = [];
  const walk = (nodes: SpaceNode[], depth: number) => {
    for (const node of nodes) {
      result.push({ ...node, depth });
      walk(node.children || [], depth + 1);
    }
  };
  walk(spaces.value, 0);
  return result;
});
const selectedSpace = computed(() =>
  flatSpaces.value.find((node) => node.id === selectedSpaceId.value)
);
const rentableSpaces = computed(() =>
  flatSpaces.value.filter(
    (node) => node.status === "ACTIVE" && ["BUILDING", "FLOOR"].includes(node.node_type)
  )
);
const mergeCandidates = computed(() =>
  units.value.filter(
    (unit) =>
      selectedUnit.value &&
      unit.id !== selectedUnit.value.id &&
      unit.building_id === selectedUnit.value.building_id &&
      unit.status === "VACANT" &&
      unit.used_area === 0
  )
);

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "请求失败，请稍后重试";
}

function queryParams() {
  return {
    park_id: selectedParkId.value || undefined,
    space_id: selectedSpaceId.value || undefined,
    status: filters.status || undefined,
    usage_type: filters.usage_type || undefined,
    keyword: filters.keyword.trim() || undefined,
  };
}

async function loadParks() {
  const response = await http.get<Envelope<PageResult<Park>>>("/parks", {
    params: { page_size: 200 },
  });
  parks.value = response.data.data.items;
  if (!selectedParkId.value && parks.value.length) selectedParkId.value = parks.value[0].id;
}

async function loadSpaces() {
  if (!selectedParkId.value) {
    spaces.value = [];
    return;
  }
  const response = await http.get<Envelope<SpaceNode[]>>("/spaces/tree", {
    params: { park_id: selectedParkId.value },
  });
  spaces.value = response.data.data;
}

async function loadInventory() {
  if (!selectedParkId.value) {
    summary.value = null;
    units.value = [];
    matrix.value = [];
    return;
  }
  const params = queryParams();
  const [summaryResponse, unitResponse, matrixResponse] = await Promise.all([
    http.get<Envelope<RentSummary>>("/rent-control/summary", { params }),
    http.get<Envelope<PageResult<UnitRow>>>("/rent-control/units", {
      params: { ...params, page_size: 200 },
    }),
    http.get<Envelope<MatrixGroup[]>>("/rent-control/matrix", { params }),
  ]);
  summary.value = summaryResponse.data.data;
  units.value = unitResponse.data.data.items;
  matrix.value = matrixResponse.data.data;
}

async function refreshWorkspace() {
  loading.value = true;
  error.value = "";
  try {
    await Promise.all([loadSpaces(), loadInventory()]);
  } catch (reason) {
    error.value = errorMessage(reason);
  } finally {
    loading.value = false;
  }
}

async function changePark() {
  selectedSpaceId.value = null;
  selectedUnit.value = null;
  await refreshWorkspace();
}

async function selectSpace(id: number | null) {
  selectedSpaceId.value = id;
  selectedUnit.value = null;
  await loadInventorySafely();
}

async function loadInventorySafely() {
  loading.value = true;
  error.value = "";
  try {
    await loadInventory();
  } catch (reason) {
    error.value = errorMessage(reason);
  } finally {
    loading.value = false;
  }
}

async function openDetail(unitId: number) {
  error.value = "";
  try {
    const response = await http.get<Envelope<UnitDetail>>(`/rent-control/units/${unitId}`);
    selectedUnit.value = response.data.data;
  } catch (reason) {
    error.value = errorMessage(reason);
  }
}

function openSpaceCreate() {
  const parent = selectedSpace.value;
  spaceForm.id = null;
  spaceForm.parent_id = parent ? String(parent.id) : "";
  spaceForm.code = "";
  spaceForm.name = "";
  spaceForm.node_type = parent?.node_type === "AREA" ? "BUILDING" : parent?.node_type === "BUILDING" ? "FLOOR" : "BUILDING";
  spaceForm.sort_order = "0";
  spaceForm.status = "ACTIVE";
  dialog.value = "space";
}

function openSpaceEdit() {
  const node = selectedSpace.value;
  if (!node) return;
  spaceForm.id = node.id;
  spaceForm.parent_id = node.parent_id ? String(node.parent_id) : "";
  spaceForm.code = node.code;
  spaceForm.name = node.name;
  spaceForm.node_type = node.node_type;
  spaceForm.sort_order = String(node.sort_order);
  spaceForm.status = node.status;
  dialog.value = "space";
}

async function saveSpace() {
  if (!selectedParkId.value) return;
  await mutate(async () => {
    const payload = {
      park_id: selectedParkId.value,
      parent_id: spaceForm.parent_id ? Number(spaceForm.parent_id) : null,
      code: spaceForm.code,
      name: spaceForm.name,
      node_type: spaceForm.node_type,
      sort_order: Number(spaceForm.sort_order || 0),
      status: spaceForm.status,
    };
    if (spaceForm.id) await http.patch(`/spaces/${spaceForm.id}`, payload);
    else await http.post("/spaces", payload);
  }, spaceForm.id ? "空间节点已更新" : "空间节点已创建");
}

async function deactivateSpace() {
  const node = selectedSpace.value;
  if (!node || !window.confirm(`确认停用空间“${node.name}”？`)) return;
  await mutate(() => http.delete(`/spaces/${node.id}`), "空间节点已停用");
  selectedSpaceId.value = null;
}

function openUnitCreate() {
  unitForm.building_id = selectedSpace.value && ["BUILDING", "FLOOR"].includes(selectedSpace.value.node_type)
    ? String(selectedSpace.value.id)
    : rentableSpaces.value.length ? String(rentableSpaces.value[0].id) : "";
  unitForm.code = "";
  unitForm.name = "";
  unitForm.rentable_area = "";
  unitForm.usage_type = "FACTORY";
  unitForm.billing_unit = "SQM";
  unitForm.base_rent_price = "0";
  dialog.value = "unit";
}

async function saveUnit() {
  if (!selectedParkId.value) return;
  await mutate(
    () =>
      http.post("/units", {
        park_id: selectedParkId.value,
        building_id: Number(unitForm.building_id),
        code: unitForm.code,
        name: unitForm.name,
        rentable_area: Number(unitForm.rentable_area),
        usage_type: unitForm.usage_type,
        billing_unit: unitForm.billing_unit,
        base_rent_price: Number(unitForm.base_rent_price || 0),
      }),
    "出租单元已创建"
  );
}

function openUnitEdit() {
  if (!selectedUnit.value) return;
  editForm.name = selectedUnit.value.name;
  editForm.base_rent_price = String(selectedUnit.value.base_rent_price);
  editForm.status = selectedUnit.value.status;
  dialog.value = "edit-unit";
}

async function saveUnitEdit() {
  const unit = selectedUnit.value;
  if (!unit) return;
  await mutate(
    () =>
      http.patch(`/units/${unit.id}`, {
        expected_lock_version: unit.lock_version,
        name: editForm.name,
        base_rent_price: Number(editForm.base_rent_price || 0),
        status: editForm.status,
      }),
    "单元信息已更新",
    unit.id
  );
}

function openVersion() {
  if (!selectedUnit.value) return;
  versionForm.building_id = String(selectedUnit.value.building_id);
  versionForm.code = selectedUnit.value.code;
  versionForm.name = selectedUnit.value.name;
  versionForm.rentable_area = String(selectedUnit.value.rentable_area);
  dialog.value = "version";
}

async function saveVersion() {
  const unit = selectedUnit.value;
  if (!unit) return;
  const response = await mutate(
    () =>
      http.post<Envelope<UnitRow>>(`/units/${unit.id}/versions`, {
        expected_lock_version: unit.lock_version,
        building_id: Number(versionForm.building_id),
        code: versionForm.code,
        name: versionForm.name,
        rentable_area: Number(versionForm.rentable_area),
      }),
    "结构新版本已生效"
  );
  if (response) await openDetail(response.data.data.id);
}

function openSplit() {
  if (!selectedUnit.value) return;
  const half = selectedUnit.value.rentable_area / 2;
  splitForm.code1 = `${selectedUnit.value.code}-A`;
  splitForm.name1 = `${selectedUnit.value.name}A`;
  splitForm.area1 = String(half);
  splitForm.code2 = `${selectedUnit.value.code}-B`;
  splitForm.name2 = `${selectedUnit.value.name}B`;
  splitForm.area2 = String(selectedUnit.value.rentable_area - half);
  dialog.value = "split";
}

async function saveSplit() {
  const unit = selectedUnit.value;
  if (!unit) return;
  await mutate(
    () =>
      http.post("/units/split", {
        unit_id: unit.id,
        expected_lock_version: unit.lock_version,
        targets: [
          { code: splitForm.code1, name: splitForm.name1, rentable_area: Number(splitForm.area1) },
          { code: splitForm.code2, name: splitForm.name2, rentable_area: Number(splitForm.area2) },
        ],
      }),
    "单元已原子拆分"
  );
  selectedUnit.value = null;
}

function openMerge() {
  if (!selectedUnit.value) return;
  mergeForm.second_unit_id = mergeCandidates.value.length ? String(mergeCandidates.value[0].id) : "";
  mergeForm.code = `${selectedUnit.value.code}-M`;
  mergeForm.name = `${selectedUnit.value.name}合并`;
  dialog.value = "merge";
}

async function saveMerge() {
  const unit = selectedUnit.value;
  const second = mergeCandidates.value.find((row) => row.id === Number(mergeForm.second_unit_id));
  if (!unit || !second) return;
  const response = await mutate(
    () =>
      http.post<Envelope<{ target: UnitRow }>>("/units/merge", {
        sources: [
          { unit_id: unit.id, expected_lock_version: unit.lock_version },
          { unit_id: second.id, expected_lock_version: second.lock_version },
        ],
        code: mergeForm.code,
        name: mergeForm.name,
      }),
    "单元已原子合并"
  );
  if (response) await openDetail(response.data.data.target.id);
}

async function mutate<T>(action: () => Promise<T>, message: string, detailId?: number): Promise<T | null> {
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const result = await action();
    dialog.value = null;
    success.value = message;
    await Promise.all([loadSpaces(), loadInventory()]);
    if (detailId) await openDetail(detailId);
    return result;
  } catch (reason) {
    error.value = errorMessage(reason);
    return null;
  } finally {
    saving.value = false;
  }
}

function formatArea(value: number) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value || 0);
}

function statusLabel(status: string) {
  return (
    {
      DRAFT: "草稿",
      VACANT: "空置",
      RESERVED: "预留",
      OCCUPIED: "已租",
      MAINTENANCE: "维修",
      RETIRED: "退役",
      ACTIVE: "启用",
      INACTIVE: "停用",
    } as Record<string, string>
  )[status] || status;
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadParks();
    await Promise.all([loadSpaces(), loadInventory()]);
  } catch (reason) {
    error.value = errorMessage(reason);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="rent-page" data-testid="rent-control-page" @keydown.esc="dialog = null">
    <header class="page-head">
      <div>
        <p class="eyebrow">ASSET &amp; RENT CONTROL</p>
        <h1 data-testid="rent-control-title">资产租控</h1>
        <p class="muted">从空间层级、库存面积到租约占用，一处校准真实经营状态。</p>
      </div>
      <div class="park-picker">
        <label for="rent-park">当前园区</label>
        <select
          id="rent-park"
          v-model="selectedParkId"
          class="input"
          data-testid="rent-park-select"
          @change="changePark"
        >
          <option v-for="park in parks" :key="park.id" :value="park.id">{{ park.name }}</option>
        </select>
      </div>
    </header>

    <p v-if="error" class="notice notice-error" role="alert" data-testid="rent-error">{{ error }}</p>
    <p v-if="success" class="notice notice-success" role="status" data-testid="rent-success">{{ success }}</p>

    <div v-if="summary" class="metric-strip" aria-label="租控汇总" data-testid="rent-summary">
      <article class="metric-card"><span>在管单元</span><strong>{{ summary.inventory_count }}</strong><small>个</small></article>
      <article class="metric-card"><span>计租面积</span><strong>{{ formatArea(summary.rentable_area) }}</strong><small>㎡</small></article>
      <article class="metric-card"><span>已用面积</span><strong>{{ formatArea(summary.used_area) }}</strong><small>㎡</small></article>
      <article class="metric-card"><span>可租面积</span><strong>{{ formatArea(summary.available_area) }}</strong><small>㎡</small></article>
      <article class="metric-card accent"><span>出租率</span><strong>{{ (summary.occupancy_rate * 100).toFixed(1) }}</strong><small>%</small></article>
    </div>

    <div class="workspace">
      <aside class="tree-panel card" aria-label="空间树">
        <div class="panel-head">
          <div><p class="panel-kicker">SPACE</p><h2>空间结构</h2></div>
          <button v-if="canWrite" class="square-btn" type="button" aria-label="新增空间" data-testid="space-create-open" @click="openSpaceCreate">＋</button>
        </div>
        <button
          class="tree-item tree-root"
          :class="{ active: selectedSpaceId === null }"
          type="button"
          data-testid="space-all"
          @click="selectSpace(null)"
        >
          <span class="node-mark park">园</span><span>全部空间</span>
        </button>
        <div v-if="flatSpaces.length" class="tree-list">
          <button
            v-for="node in flatSpaces"
            :key="node.id"
            class="tree-item"
            :class="{ active: selectedSpaceId === node.id, inactive: node.status !== 'ACTIVE' }"
            :style="{ paddingLeft: `${0.75 + node.depth * 1.15}rem` }"
            type="button"
            :data-testid="`space-node-${node.id}`"
            @click="selectSpace(node.id)"
          >
            <span class="node-mark">{{ node.node_type === "AREA" ? "区" : node.node_type === "BUILDING" ? "栋" : "层" }}</span>
            <span class="tree-name">{{ node.name }}</span><small>{{ node.code }}</small>
          </button>
        </div>
        <div v-else class="empty compact"><strong>尚无空间层级</strong><span>从区域或楼栋开始建立资产目录。</span></div>
        <div v-if="selectedSpace" class="tree-actions">
          <button v-if="canWrite" class="text-btn" type="button" data-testid="space-edit-open" @click="openSpaceEdit">编辑 / 移动</button>
          <button v-if="canWrite" class="text-btn danger-text" type="button" data-testid="space-deactivate" @click="deactivateSpace">停用</button>
        </div>
      </aside>

      <main class="inventory-panel card">
        <div class="inventory-toolbar">
          <div>
            <p class="panel-kicker">INVENTORY</p>
            <h2>{{ selectedSpace?.name || "全园租控盘面" }}</h2>
          </div>
          <div class="view-switch" role="group" aria-label="视图切换">
            <button type="button" :aria-pressed="viewMode === 'matrix'" data-testid="view-matrix" @click="viewMode = 'matrix'">矩阵</button>
            <button type="button" :aria-pressed="viewMode === 'list'" data-testid="view-list" @click="viewMode = 'list'">列表</button>
          </div>
        </div>

        <form class="filters" aria-label="租控筛选" @submit.prevent="loadInventorySafely">
          <label>状态
            <select v-model="filters.status" class="input" data-testid="rent-status-filter">
              <option value="">全部状态</option><option value="VACANT">空置</option><option value="RESERVED">预留</option><option value="OCCUPIED">已租</option><option value="MAINTENANCE">维修</option>
            </select>
          </label>
          <label>用途
            <select v-model="filters.usage_type" class="input" data-testid="rent-usage-filter">
              <option value="">全部用途</option><option value="FACTORY">厂房</option><option value="OFFICE">办公</option><option value="WAREHOUSE">仓储</option><option value="SHOP">商铺</option>
            </select>
          </label>
          <label class="keyword">搜索
            <input v-model="filters.keyword" class="input" data-testid="rent-keyword" placeholder="单元编码或名称" />
          </label>
          <button class="btn filter-btn" type="submit" data-testid="rent-filter-submit">筛选</button>
          <button v-if="canWrite" class="btn btn-dark" type="button" data-testid="unit-create-open" @click="openUnitCreate">新增单元</button>
        </form>

        <div v-if="loading" class="state" aria-live="polite" data-testid="rent-loading"><span class="spinner"></span>正在校准租控数据…</div>
        <div v-else-if="!units.length" class="empty" data-testid="rent-empty"><strong>当前筛选下没有单元</strong><span>调整筛选条件，或在有效楼栋/楼层下新增出租单元。</span></div>

        <div v-else-if="viewMode === 'matrix'" class="matrix" data-testid="rent-matrix">
          <section v-for="group in matrix" :key="group.space_id" class="matrix-group">
            <header><div><strong>{{ group.space_name }}</strong><span>{{ group.space_code }} · {{ group.node_type }}</span></div><small>{{ group.units.length }} 个单元</small></header>
            <div class="unit-grid">
              <button
                v-for="unit in group.units"
                :key="unit.id"
                class="unit-tile"
                :class="`status-${unit.status.toLowerCase()}`"
                type="button"
                :data-testid="`rent-unit-${unit.id}`"
                @click="openDetail(unit.id)"
              >
                <span class="status-dot"></span><strong>{{ unit.code }}</strong><span>{{ unit.name }}</span>
                <small>{{ formatArea(unit.available_area) }} / {{ formatArea(unit.rentable_area) }} ㎡可租</small>
              </button>
            </div>
          </section>
        </div>

        <div v-else-if="units.length" class="table-wrap" data-testid="rent-list">
          <table class="table">
            <thead><tr><th>单元</th><th>空间</th><th>用途</th><th>计租 / 已用</th><th>租金基价</th><th>状态</th><th></th></tr></thead>
            <tbody>
              <tr v-for="unit in units" :key="unit.id">
                <td><strong>{{ unit.code }}</strong><br /><small>{{ unit.name }}</small></td><td>{{ unit.space_name }}</td><td>{{ unit.usage_type }}</td>
                <td>{{ formatArea(unit.rentable_area) }} / {{ formatArea(unit.used_area) }} ㎡</td><td>¥ {{ unit.base_rent_price }}</td>
                <td><span class="status-pill" :class="`status-${unit.status.toLowerCase()}`">{{ statusLabel(unit.status) }}</span></td>
                <td><button class="text-btn" type="button" :data-testid="`rent-detail-${unit.id}`" @click="openDetail(unit.id)">详情</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>

      <aside v-if="selectedUnit" class="detail-drawer card" data-testid="rent-detail" aria-label="单元详情">
        <header class="drawer-head"><div><p class="panel-kicker">UNIT DETAIL</p><h2>{{ selectedUnit.code }}</h2><span>{{ selectedUnit.name }}</span></div><button class="square-btn" type="button" aria-label="关闭详情" @click="selectedUnit = null">×</button></header>
        <div class="detail-status"><span class="status-pill" :class="`status-${selectedUnit.status.toLowerCase()}`">{{ statusLabel(selectedUnit.status) }}</span><span>V{{ selectedUnit.version_no }} · 锁版本 {{ selectedUnit.lock_version }}</span></div>
        <dl class="fact-grid">
          <div><dt>计租面积</dt><dd>{{ formatArea(selectedUnit.rentable_area) }} ㎡</dd></div><div><dt>可租面积</dt><dd>{{ formatArea(selectedUnit.available_area) }} ㎡</dd></div>
          <div><dt>已用面积</dt><dd>{{ formatArea(selectedUnit.used_area) }} ㎡</dd></div><div><dt>用途</dt><dd>{{ selectedUnit.usage_type }}</dd></div>
        </dl>
        <p v-if="selectedUnit.blocking_reason" class="blocking">{{ selectedUnit.blocking_reason }}</p>
        <div v-if="canWrite" class="action-grid">
          <button class="btn-quiet" type="button" data-testid="unit-edit-open" @click="openUnitEdit">编辑</button>
          <button class="btn-quiet" type="button" data-testid="unit-version-open" @click="openVersion">结构变更</button>
          <button class="btn-quiet" type="button" data-testid="unit-split-open" :disabled="!selectedUnit.can_split_merge" @click="openSplit">拆分</button>
          <button class="btn-quiet" type="button" data-testid="unit-merge-open" :disabled="!selectedUnit.can_split_merge || !mergeCandidates.length" @click="openMerge">合并</button>
        </div>
        <section class="detail-section"><h3>生效租约 / 客户</h3><div v-if="!selectedUnit.effective_leases.length" class="mini-empty">暂无生效租约</div><article v-for="lease in selectedUnit.effective_leases" :key="lease.contract_id" class="relation-row"><strong>{{ lease.party_name }}</strong><span>{{ lease.contract_no }} · {{ lease.occupied_area }} ㎡</span><small>{{ lease.start_date }} — {{ lease.end_date }}</small></article></section>
        <section class="detail-section"><h3>版本历史</h3><article v-for="row in selectedUnit.history" :key="row.id" class="relation-row"><strong>V{{ row.version_no }} · {{ row.code }}</strong><span>{{ formatArea(row.rentable_area) }} ㎡</span><small>{{ row.valid_from?.slice(0, 10) || "—" }} → {{ row.valid_to?.slice(0, 10) || "当前" }}</small></article></section>
        <section class="detail-section"><h3>拆并血缘</h3><div v-if="!selectedUnit.lineage.length" class="mini-empty">暂无拆分或合并记录</div><article v-for="edge in selectedUnit.lineage" :key="`${edge.operation_id}-${edge.source_unit_id}-${edge.target_unit_id}`" class="relation-row"><strong>{{ edge.operation_type }}</strong><span>#{{ edge.source_unit_id }} → #{{ edge.target_unit_id }}</span></article></section>
        <section class="detail-section"><h3>关联工单</h3><div v-if="!selectedUnit.work_orders.length" class="mini-empty">暂无关联工单</div><article v-for="order in selectedUnit.work_orders" :key="order.id" class="relation-row"><strong>{{ order.title }}</strong><span>{{ order.priority }} · {{ order.status }}</span></article></section>
      </aside>
    </div>

    <div v-if="dialog" class="modal-backdrop" @mousedown.self="dialog = null">
      <section class="modal card" role="dialog" aria-modal="true" :aria-label="dialog">
        <header><h2>{{ dialog === "space" ? (spaceForm.id ? "编辑空间" : "新增空间") : dialog === "unit" ? "新增出租单元" : dialog === "edit-unit" ? "编辑单元" : dialog === "version" ? "结构变更" : dialog === "split" ? "拆分单元" : "合并单元" }}</h2><button class="square-btn" type="button" aria-label="关闭" @click="dialog = null">×</button></header>

        <form v-if="dialog === 'space'" class="modal-form" data-testid="space-form" @submit.prevent="saveSpace">
          <label>父空间<select v-model="spaceForm.parent_id" class="input" data-testid="space-parent"><option value="">根节点</option><option v-for="node in flatSpaces.filter((row) => row.id !== spaceForm.id)" :key="node.id" :value="String(node.id)">{{ "—".repeat(node.depth) }} {{ node.name }} ({{ node.node_type }})</option></select></label>
          <label>节点类型<select v-model="spaceForm.node_type" class="input" data-testid="space-type" required><option value="AREA">区域</option><option value="BUILDING">楼栋</option><option value="FLOOR">楼层</option></select></label>
          <label>空间编码<input v-model="spaceForm.code" class="input" data-testid="space-code" required maxlength="64" /></label>
          <label>空间名称<input v-model="spaceForm.name" class="input" data-testid="space-name" required maxlength="128" /></label>
          <label>排序<input v-model="spaceForm.sort_order" class="input" type="number" /></label>
          <label>状态<select v-model="spaceForm.status" class="input"><option value="ACTIVE">启用</option><option value="INACTIVE">停用</option></select></label>
          <button class="btn modal-submit" type="submit" data-testid="space-save" :disabled="saving">{{ saving ? "保存中…" : "保存空间" }}</button>
        </form>

        <form v-else-if="dialog === 'unit'" class="modal-form" data-testid="unit-form" @submit.prevent="saveUnit">
          <label class="wide">所属空间<select v-model="unitForm.building_id" class="input" data-testid="unit-space" required><option value="" disabled>请选择楼栋或楼层</option><option v-for="node in rentableSpaces" :key="node.id" :value="String(node.id)">{{ "—".repeat(node.depth) }} {{ node.name }}</option></select></label>
          <label>单元编码<input v-model="unitForm.code" class="input" data-testid="unit-code-v2" required /></label><label>单元名称<input v-model="unitForm.name" class="input" data-testid="unit-name-v2" required /></label>
          <label>计租面积（㎡）<input v-model="unitForm.rentable_area" class="input" data-testid="unit-area-v2" type="number" min="0" step="0.01" required /></label>
          <label>用途<select v-model="unitForm.usage_type" class="input"><option value="FACTORY">厂房</option><option value="OFFICE">办公</option><option value="WAREHOUSE">仓储</option><option value="SHOP">商铺</option></select></label>
          <label>计费单位<select v-model="unitForm.billing_unit" class="input"><option value="SQM">平方米</option><option value="UNIT">单元</option></select></label><label>租金基价<input v-model="unitForm.base_rent_price" class="input" type="number" min="0" step="0.01" /></label>
          <button class="btn modal-submit" type="submit" data-testid="unit-save-v2" :disabled="saving || !rentableSpaces.length">{{ saving ? "保存中…" : "创建单元" }}</button>
        </form>

        <form v-else-if="dialog === 'edit-unit'" class="modal-form" @submit.prevent="saveUnitEdit">
          <label>单元名称<input v-model="editForm.name" class="input" required /></label><label>租金基价<input v-model="editForm.base_rent_price" class="input" type="number" min="0" step="0.01" /></label>
          <label class="wide">运营状态<select v-model="editForm.status" class="input"><option value="VACANT">空置</option><option value="RESERVED">预留</option><option value="MAINTENANCE">维修</option><option value="RETIRED">退役</option></select><small>“已租”由生效租约自动投影，不能手工设置。</small></label>
          <button class="btn modal-submit" type="submit" data-testid="unit-edit-save" :disabled="saving">保存非结构字段</button>
        </form>

        <form v-else-if="dialog === 'version'" class="modal-form" @submit.prevent="saveVersion">
          <p class="form-note wide">面积、编码与空间归属属于结构字段。保存后旧记录保留为历史版本，现有引用不被改写。</p>
          <label class="wide">所属空间<select v-model="versionForm.building_id" class="input" required><option v-for="node in rentableSpaces" :key="node.id" :value="String(node.id)">{{ node.name }}</option></select></label>
          <label>单元编码<input v-model="versionForm.code" class="input" required /></label><label>单元名称<input v-model="versionForm.name" class="input" required /></label>
          <label>计租面积（㎡）<input v-model="versionForm.rentable_area" class="input" type="number" min="0.01" step="0.01" required /></label>
          <button class="btn modal-submit" type="submit" data-testid="unit-version-save" :disabled="saving">创建新版本</button>
        </form>

        <form v-else-if="dialog === 'split'" class="modal-form" @submit.prevent="saveSplit">
          <p class="form-note wide">两个目标面积之和必须严格等于 {{ selectedUnit?.rentable_area }} ㎡。</p>
          <fieldset><legend>目标 A</legend><input v-model="splitForm.code1" class="input" aria-label="目标 A 编码" required /><input v-model="splitForm.name1" class="input" aria-label="目标 A 名称" required /><input v-model="splitForm.area1" class="input" aria-label="目标 A 面积" type="number" min="0.01" step="0.01" required /></fieldset>
          <fieldset><legend>目标 B</legend><input v-model="splitForm.code2" class="input" aria-label="目标 B 编码" required /><input v-model="splitForm.name2" class="input" aria-label="目标 B 名称" required /><input v-model="splitForm.area2" class="input" aria-label="目标 B 面积" type="number" min="0.01" step="0.01" required /></fieldset>
          <button class="btn modal-submit" type="submit" data-testid="unit-split-save" :disabled="saving">确认原子拆分</button>
        </form>

        <form v-else class="modal-form" @submit.prevent="saveMerge">
          <p class="form-note wide">仅可合并同一空间内零占用的空置单元；来源会退役并建立血缘。</p>
          <label class="wide">第二个来源单元<select v-model="mergeForm.second_unit_id" class="input" data-testid="unit-merge-second" required><option v-for="unit in mergeCandidates" :key="unit.id" :value="String(unit.id)">{{ unit.code }} · {{ unit.name }} · {{ unit.rentable_area }}㎡</option></select></label>
          <label>新单元编码<input v-model="mergeForm.code" class="input" required /></label><label>新单元名称<input v-model="mergeForm.name" class="input" required /></label>
          <button class="btn modal-submit" type="submit" data-testid="unit-merge-save" :disabled="saving || !mergeCandidates.length">确认原子合并</button>
        </form>
      </section>
    </div>
  </section>
</template>

<style scoped>
.rent-page { max-width: 1680px; margin: 0 auto; }
.page-head { display: flex; justify-content: space-between; align-items: end; gap: 1rem; margin-bottom: 1rem; }
.page-head h1, .panel-head h2, .inventory-toolbar h2, .drawer-head h2 { margin: 0; }
.page-head h1 { font-size: clamp(1.7rem, 3vw, 2.5rem); letter-spacing: -.04em; }
.eyebrow, .panel-kicker { margin: 0 0 .25rem; color: var(--primary); font-size: .7rem; font-weight: 800; letter-spacing: .14em; }
.page-head .muted { margin: .2rem 0 0; }
.park-picker { width: min(320px, 100%); }
.park-picker label, .filters label, .modal-form label { display: grid; gap: .3rem; color: var(--muted); font-size: .78rem; font-weight: 700; }
.metric-strip { display: grid; grid-template-columns: repeat(5, minmax(130px, 1fr)); gap: .7rem; margin-bottom: .8rem; }
.metric-card { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: .8rem 1rem; box-shadow: var(--shadow); }
.metric-card span { display: block; color: var(--muted); font-size: .76rem; }
.metric-card strong { display: inline-block; margin-top: .2rem; font-size: 1.45rem; }
.metric-card small { margin-left: .25rem; color: var(--muted); }
.metric-card.accent { color: #fff; background: linear-gradient(135deg, #0d6a54, #103f4a); border-color: transparent; }
.metric-card.accent span, .metric-card.accent small { color: #d9f4ec; }
.workspace { display: grid; grid-template-columns: minmax(210px, 250px) minmax(540px, 1fr); gap: .8rem; align-items: start; }
.workspace:has(.detail-drawer) { grid-template-columns: minmax(200px, 230px) minmax(480px, 1fr) minmax(300px, 360px); }
.tree-panel, .inventory-panel, .detail-drawer { min-height: 620px; }
.tree-panel, .inventory-panel { padding: 1rem; }
.panel-head, .inventory-toolbar, .drawer-head, .matrix-group header, .modal header { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
.square-btn { width: 2.2rem; height: 2.2rem; border: 1px solid var(--border); background: #fff; border-radius: 9px; color: var(--primary); font-size: 1.25rem; cursor: pointer; }
.tree-list { display: grid; gap: .18rem; }
.tree-item { width: 100%; display: flex; align-items: center; gap: .45rem; border: 0; border-radius: 8px; background: transparent; padding: .55rem .65rem; text-align: left; color: var(--text); cursor: pointer; }
.tree-item:hover, .tree-item.active { background: var(--primary-soft); color: var(--primary); }
.tree-item.inactive { opacity: .55; }
.tree-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-item small { margin-left: auto; color: var(--muted); font-size: .65rem; }
.node-mark { display: grid; place-items: center; flex: 0 0 1.55rem; height: 1.55rem; border-radius: 6px; background: #edf1f4; color: #53606c; font-size: .68rem; font-weight: 800; }
.node-mark.park { color: #fff; background: var(--primary); }
.tree-actions { display: flex; gap: .8rem; margin-top: 1rem; padding-top: .8rem; border-top: 1px solid var(--border); }
.text-btn { border: 0; padding: .25rem; background: transparent; color: var(--primary); cursor: pointer; font: inherit; font-weight: 700; }
.danger-text { color: var(--danger); }
.filters { display: grid; grid-template-columns: 130px 130px minmax(150px, 1fr) auto auto; gap: .55rem; align-items: end; margin: 1rem 0; padding: .8rem; background: #f8fafb; border: 1px solid var(--border); border-radius: 11px; }
.filters .input { padding: .55rem .65rem; }
.filter-btn, .btn-dark { min-height: 2.55rem; }
.btn-dark { background: #18343b; }
.view-switch { display: flex; padding: .18rem; background: #edf1f3; border-radius: 9px; }
.view-switch button { border: 0; padding: .45rem .8rem; background: transparent; border-radius: 7px; color: var(--muted); cursor: pointer; }
.view-switch button[aria-pressed="true"] { color: var(--text); background: #fff; box-shadow: 0 2px 8px rgba(15, 23, 42, .08); }
.matrix { display: grid; gap: 1rem; }
.matrix-group { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.matrix-group header { padding: .7rem .85rem; background: #f8faf9; border-bottom: 1px solid var(--border); }
.matrix-group header span { margin-left: .45rem; color: var(--muted); font-size: .72rem; }
.unit-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: .55rem; padding: .75rem; }
.unit-tile { position: relative; display: grid; gap: .18rem; min-height: 102px; padding: .75rem; border: 1px solid var(--border); border-radius: 10px; background: #fff; text-align: left; color: var(--text); cursor: pointer; }
.unit-tile:hover { transform: translateY(-1px); box-shadow: var(--shadow); }
.unit-tile > span, .unit-tile small { color: var(--muted); font-size: .72rem; }
.status-dot { position: absolute; top: .7rem; right: .7rem; width: .48rem; height: .48rem; border-radius: 50%; background: #84919c; }
.status-vacant .status-dot, .status-pill.status-vacant { background: #e3f5ed; color: #087052; }
.status-occupied .status-dot, .status-pill.status-occupied { background: #e6effd; color: #2558a8; }
.status-reserved .status-dot, .status-pill.status-reserved { background: #fff3d6; color: #8a5a00; }
.status-maintenance .status-dot, .status-pill.status-maintenance { background: #fee8e5; color: #aa3024; }
.unit-tile.status-vacant .status-dot { background: #17a578; }.unit-tile.status-occupied .status-dot { background: #397ee7; }.unit-tile.status-reserved .status-dot { background: #d79212; }.unit-tile.status-maintenance .status-dot { background: #d84e41; }
.table-wrap { overflow-x: auto; }
.status-pill { display: inline-flex; border-radius: 999px; padding: .18rem .55rem; background: #edf1f3; color: #53606c; font-size: .72rem; font-weight: 800; }
.detail-drawer { position: sticky; top: 1rem; max-height: calc(100vh - 2rem); overflow-y: auto; padding: 1rem; }
.drawer-head > div > span { color: var(--muted); font-size: .85rem; }
.detail-status { display: flex; justify-content: space-between; align-items: center; margin: 1rem 0; color: var(--muted); font-size: .76rem; }
.fact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: 0; }
.fact-grid div { padding: .65rem; background: #f7f9fa; border-radius: 9px; }.fact-grid dt { color: var(--muted); font-size: .68rem; }.fact-grid dd { margin: .15rem 0 0; font-weight: 800; }
.blocking { padding: .65rem; border-radius: 8px; background: #fff5e6; color: #8b5700; font-size: .78rem; }
.action-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .45rem; margin: .9rem 0; }.btn-quiet { border: 1px solid var(--border); border-radius: 8px; padding: .5rem; background: #fff; color: var(--primary); cursor: pointer; }.btn-quiet:disabled { opacity: .4; cursor: not-allowed; }
.detail-section { padding-top: .9rem; margin-top: .9rem; border-top: 1px solid var(--border); }.detail-section h3 { margin: 0 0 .55rem; font-size: .86rem; }.relation-row { display: grid; gap: .08rem; margin-bottom: .35rem; padding: .55rem; background: #f8faf9; border-radius: 8px; font-size: .76rem; }.relation-row span, .relation-row small, .mini-empty { color: var(--muted); }.mini-empty { padding: .6rem 0; font-size: .76rem; }
.state, .empty { min-height: 240px; display: grid; place-content: center; justify-items: center; gap: .4rem; color: var(--muted); text-align: center; }.empty.compact { min-height: 160px; font-size: .8rem; }.empty strong { color: var(--text); }.spinner { width: 1.6rem; height: 1.6rem; border: 3px solid #dce8e4; border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; }
.notice { margin: 0 0 .7rem; padding: .65rem .8rem; border-radius: 9px; }.notice-error { color: var(--danger); background: #fff0ef; }.notice-success { color: #087052; background: #e8f7f1; }
.modal-backdrop { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 1rem; background: rgba(15, 30, 35, .5); backdrop-filter: blur(3px); }
.modal { width: min(620px, 100%); max-height: calc(100vh - 2rem); overflow-y: auto; padding: 1.1rem; }.modal header { padding-bottom: .8rem; border-bottom: 1px solid var(--border); }.modal header h2 { margin: 0; }
.modal-form { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; margin-top: .9rem; }.modal-form .wide, .modal-submit, .form-note { grid-column: 1 / -1; }.modal-submit { margin-top: .25rem; }.modal-form small { font-weight: 400; }.form-note { margin: 0; padding: .7rem; border-radius: 8px; background: #eef6f3; color: #35534b; font-size: .8rem; }.modal-form fieldset { display: grid; gap: .5rem; margin: 0; padding: .7rem; border: 1px solid var(--border); border-radius: 9px; }.modal-form legend { color: var(--muted); font-size: .75rem; font-weight: 800; }
button:focus-visible, input:focus-visible, select:focus-visible { outline: 3px solid rgba(15, 110, 86, .28); outline-offset: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1250px) { .workspace:has(.detail-drawer) { grid-template-columns: 210px 1fr; }.detail-drawer { position: fixed; z-index: 30; top: 1rem; right: 1rem; bottom: 1rem; width: min(380px, calc(100vw - 2rem)); max-height: none; }.metric-strip { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .page-head { align-items: stretch; flex-direction: column; }.park-picker { width: 100%; }.workspace, .workspace:has(.detail-drawer) { grid-template-columns: 1fr; }.tree-panel { min-height: auto; }.filters { grid-template-columns: 1fr 1fr; }.filters .keyword { grid-column: 1 / -1; }.metric-strip { grid-template-columns: repeat(2, 1fr); }.detail-drawer { top: .5rem; right: .5rem; bottom: .5rem; width: calc(100vw - 1rem); } }
@media (max-width: 560px) { .metric-strip, .modal-form, .filters { grid-template-columns: 1fr; }.filters .keyword, .modal-form .wide, .modal-submit, .form-note { grid-column: auto; }.unit-grid { grid-template-columns: 1fr 1fr; } }
</style>
