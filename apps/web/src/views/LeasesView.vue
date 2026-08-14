<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";
import { useAuthStore } from "@/stores/auth";
import { displaySnapshotValue, snapshotDiff } from "@/utils/snapshotDiff";

type Option = {
  id: number;
  label: string;
  park_id?: number;
  status?: string;
  eligible?: boolean;
  rentable_area?: string;
  used_area?: string;
  available_area?: string;
};
type LeaseRow = {
  id: number;
  park_id: number;
  party_id: number;
  contract_no: string;
  contract_type: string;
  currency: string;
  status: string;
  approval_status: string | null;
  start_date: string;
  end_date: string;
  deposit_amount: string;
  current_version_no: number;
  lock_version: number;
};
type Lifecycle = {
  contract: LeaseRow;
  current_snapshot: Record<string, unknown>;
  units: Array<{ id: number; unit_id: number; occupied_area: string; unit_rent_price: string }>;
  charges: Array<Record<string, unknown>>;
  schedules: Array<Record<string, unknown>>;
  versions: Array<Record<string, unknown>>;
  documents: Array<Record<string, unknown>>;
  changes: Array<Record<string, unknown>>;
  exit_settlement: Record<string, unknown> | null;
  approval_timeline: Array<Record<string, unknown>>;
};
type Summary = {
  as_of: string;
  metrics: Record<string, number | string>;
};
type SchedulePreview = {
  contract_id: number;
  lock_version: number;
  current_version_no: number;
  row_count: number;
  checksum: string;
  rows: Array<Record<string, unknown>>;
  billing_effect: "NONE";
};
type CreatedLease = LeaseRow & { schedule_preview: SchedulePreview };
type UnitLine = { unit_id: string; occupied_area: string; unit_rent_price: string };
type ChargeLine = {
  charge_code: string;
  charge_type: string;
  calculation_method: string;
  billing_cycle: string;
  start_date: string;
  end_date: string;
  due_day: number;
  amount: string;
  unit_price: string;
  tax_rate: string;
};

const auth = useAuthStore();
const items = ref<LeaseRow[]>([]);
const summary = ref<Summary | null>(null);
const parks = ref<Option[]>([]);
const parties = ref<Option[]>([]);
const units = ref<Option[]>([]);
const selected = ref<Lifecycle | null>(null);
const preview = ref<Record<string, unknown> | null>(null);
const loading = ref(false);
const detailLoading = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");
const createOpen = ref(false);
const drawerOpen = ref(false);
const activeTab = ref<"facts" | "schedule" | "versions" | "governance" | "changes" | "exit">("facts");
const documentFile = ref<File | null>(null);
const exitEvidenceFile = ref<File | null>(null);
let loadTicket = 0;
let detailTicket = 0;
let actionTicket = 0;

const filters = reactive({
  park_id: "",
  party_id: "",
  status: "",
  contract_type: "",
  approval_status: "",
  change_status: "",
  exit_status: "",
  keyword: "",
  end_from: "",
  end_to: "",
});
const form = reactive({
  park_id: "",
  party_id: "",
  start_date: "",
  end_date: "",
  deposit_amount: "0",
  units: [{ unit_id: "", occupied_area: "", unit_rent_price: "" }] as UnitLine[],
  charges: [
    {
      charge_code: "RENT",
      charge_type: "RENT",
      calculation_method: "FIXED",
      billing_cycle: "MONTHLY",
      start_date: "",
      end_date: "",
      due_day: 5,
      amount: "",
      unit_price: "",
      tax_rate: "0",
    },
  ] as ChargeLine[],
});
const changeForm = reactive({
  change_type: "RENEWAL",
  effective_date: "",
  reason: "",
  proposal: "",
});
const exitForm = reactive({
  handover_date: "",
  inspection_summary: "",
  meter_readings: "[]",
  items: "[]",
  clearance_reference: "",
  clearance_reason: "",
});

const canWrite = computed(() => auth.can("lease:write") || auth.can("*"));
const canApprove = computed(() => auth.can(["approval:decide", "lease:approve"]) || auth.can("*"));
const canDocument = computed(() => auth.can("lease:document") || auth.can("*"));
const canActivate = computed(() => auth.can("lease:activate") || auth.can("*"));
const canChange = computed(() => auth.can("lease:change") || auth.can("*"));
const canSettle = computed(() => auth.can("lease:settle") || auth.can("*"));
const parsedChangeProposal = computed<Record<string, unknown> | null>(() => {
  try {
    const value = JSON.parse(changeForm.proposal) as unknown;
    return value !== null && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
});
const draftChangeDiff = computed(() =>
  selected.value && parsedChangeProposal.value
    ? snapshotDiff(selected.value.current_snapshot, parsedChangeProposal.value)
    : [],
);
const availableUnits = computed(() =>
  units.value.filter((unit) => !form.park_id || String(unit.park_id) === form.park_id)
);
const selectedParty = computed(() => parties.value.find((row) => String(row.id) === form.party_id));
const pendingInitialApproval = computed(() =>
  [...(selected.value?.approval_timeline || [])]
    .reverse()
    .find((row) => row.biz_type === "LEASE_CONTRACT_VERSION" && row.status === "PENDING")
);
const canCloseSelectedExit = computed(() => {
  const exit = selected.value?.exit_settlement;
  if (!exit || exit.status !== "APPROVED" || exit.financial_clearance_status !== "CONFIRMED") {
    return false;
  }
  return selected.value!.documents.some(
    (document) =>
      Number(document.exit_settlement_id || 0) === Number(exit.id) &&
      ["APPROVED", "SIGNED"].includes(String(document.status))
  );
});

const statusLabel: Record<string, string> = {
  DRAFT: "草稿",
  PENDING_APPROVAL: "待审批",
  PENDING_ACTIVE: "待生效",
  ACTIVE: "履约中",
  EXPIRING: "即将到期",
  EXIT_PENDING: "退租中",
  TERMINATED: "已终止",
  BREACHED: "违约终止",
  CANCELLED: "已取消",
};

function labelStatus(value: unknown) {
  return statusLabel[String(value)] || String(value || "—");
}

function displayError(cause: unknown) {
  if (cause instanceof ApiRequestError) {
    if (cause.status === 409) return `数据已变化（${cause.code}），已保留当前输入，请刷新后重试。`;
    if (cause.status === 503) return `外部能力暂不可用（${cause.code}），业务数据未提交。`;
    if (cause.status === 403) return `当前账号没有执行此操作的权限（${cause.code}）。`;
    return `${cause.message}（${cause.code}）`;
  }
  return cause instanceof Error ? cause.message : "操作失败";
}

function listParams() {
  return {
    page: 1,
    page_size: 100,
    park_id: filters.park_id || undefined,
    party_id: filters.party_id || undefined,
    status: filters.status || undefined,
    contract_type: filters.contract_type || undefined,
    approval_status: filters.approval_status || undefined,
    change_status: filters.change_status || undefined,
    exit_status: filters.exit_status || undefined,
    keyword: filters.keyword || undefined,
    end_from: filters.end_from || undefined,
    end_to: filters.end_to || undefined,
  };
}

function existingChangeDiff(change: Record<string, unknown>) {
  return snapshotDiff(selected.value?.current_snapshot || {}, change.proposal || {});
}

async function load() {
  const ticket = ++loadTicket;
  loading.value = true;
  error.value = "";
  try {
    const [listResponse, summaryResponse, selectorResponse] = await Promise.all([
      http.get<Envelope<PageResult<LeaseRow>>>("/leases", { params: listParams() }),
      http.get<Envelope<Summary>>("/leases/summary", {
        params: { park_id: filters.park_id || undefined },
      }),
      http.get<Envelope<{ parks: Option[]; parties: Option[]; units: Option[] }>>(
        "/leases/selectors",
        { params: { park_id: filters.park_id || undefined } }
      ),
    ]);
    if (ticket !== loadTicket) return;
    items.value = listResponse.data.data.items;
    summary.value = summaryResponse.data.data;
    parks.value = selectorResponse.data.data.parks;
    parties.value = selectorResponse.data.data.parties;
    units.value = selectorResponse.data.data.units;
  } catch (cause) {
    if (ticket === loadTicket) error.value = displayError(cause);
  } finally {
    if (ticket === loadTicket) loading.value = false;
  }
}

async function openDetail(id: number, tab = activeTab.value) {
  const ticket = ++detailTicket;
  drawerOpen.value = true;
  detailLoading.value = true;
  activeTab.value = tab;
  try {
    const { data } = await http.get<Envelope<Lifecycle>>(`/leases/${id}/lifecycle`);
    if (ticket !== detailTicket) return;
    selected.value = data.data;
    changeForm.proposal = JSON.stringify(data.data.current_snapshot, null, 2);
  } catch (cause) {
    if (ticket === detailTicket) error.value = displayError(cause);
  } finally {
    if (ticket === detailTicket) detailLoading.value = false;
  }
}

async function refreshAll(id?: number, tab?: typeof activeTab.value) {
  await load();
  if (id) await openDetail(id, tab);
}

async function runAction(message: string, action: () => Promise<number | void>, tab?: typeof activeTab.value) {
  if (saving.value) {
    error.value = "上一项操作仍在处理，请稍候重试。";
    return;
  }
  const ticket = ++actionTicket;
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const id = await action();
    if (ticket !== actionTicket) return;
    success.value = message;
    await refreshAll(id || selected.value?.contract.id, tab);
  } catch (cause) {
    if (ticket === actionTicket) error.value = displayError(cause);
  } finally {
    if (ticket === actionTicket) saving.value = false;
  }
}

function openCreate() {
  createOpen.value = true;
  form.park_id = filters.park_id;
  form.party_id = "";
  form.start_date = "";
  form.end_date = "";
  form.deposit_amount = "0";
  form.units.splice(0, form.units.length, { unit_id: "", occupied_area: "", unit_rent_price: "" });
  form.charges.splice(0, form.charges.length, {
    charge_code: "RENT",
    charge_type: "RENT",
    calculation_method: "FIXED",
    billing_cycle: "MONTHLY",
    start_date: "",
    end_date: "",
    due_day: 5,
    amount: "",
    unit_price: "",
    tax_rate: "0",
  });
}

function addUnit() {
  form.units.push({ unit_id: "", occupied_area: "", unit_rent_price: "" });
}

function addCharge() {
  form.charges.push({
    charge_code: `CHARGE_${form.charges.length + 1}`,
    charge_type: "SERVICE_FEE",
    calculation_method: "FIXED",
    billing_cycle: "MONTHLY",
    start_date: form.start_date,
    end_date: form.end_date,
    due_day: 5,
    amount: "",
    unit_price: "",
    tax_rate: "0",
  });
}

function normalizeCharges() {
  return form.charges.map((row) => ({
    ...row,
    amount: row.calculation_method === "FIXED" ? row.amount : undefined,
    unit_price: row.calculation_method === "PER_AREA" ? row.unit_price : undefined,
  }));
}

async function createDraft() {
  await runAction("合同草稿已保存，并完成履约计划预览。", async () => {
    if (!selectedParty.value?.eligible) throw new Error("请选择状态正常且未列入黑名单的主体");
    const created = await http.post<Envelope<CreatedLease>>("/leases", {
      park_id: Number(form.park_id),
      party_id: Number(form.party_id),
      start_date: form.start_date,
      end_date: form.end_date,
      deposit_amount: form.deposit_amount,
      units: form.units.map((row) => ({
        unit_id: Number(row.unit_id),
        occupied_area: row.occupied_area,
        unit_rent_price: row.unit_rent_price || "0",
      })),
      charges: normalizeCharges(),
    });
    const id = created.data.data.id;
    preview.value = created.data.data.schedule_preview;
    createOpen.value = false;
    return id;
  }, "schedule");
}

async function submitInitial() {
  if (!selected.value) return;
  await runAction("合同已提交审批。", async () => {
    await http.post(`/leases/${selected.value!.contract.id}/lifecycle/submit`, {
      expected_version: selected.value!.contract.lock_version,
    });
    return selected.value!.contract.id;
  }, "governance");
}

async function decideInitial(approve: boolean) {
  if (!selected.value || !pendingInitialApproval.value) return;
  const overrideReason = approve ? window.prompt("如申请人与审批人为同一人，请填写越权审批原因") || undefined : undefined;
  await runAction(approve ? "合同审批已通过。" : "合同审批已驳回。", async () => {
    await http.post(
      `/leases/${selected.value!.contract.id}/lifecycle/${approve ? "approve" : "reject"}`,
      {
        approval_id: Number(pendingInitialApproval.value!.approval_id),
        expected_version: selected.value!.contract.lock_version,
        override_reason: overrideReason,
      }
    );
    return selected.value!.contract.id;
  }, "governance");
}

async function withdrawInitial() {
  if (!selected.value || !pendingInitialApproval.value) return;
  await runAction("审批申请已撤回，草稿内容保留。", async () => {
    await http.post(`/leases/${selected.value!.contract.id}/lifecycle/withdraw`, {
      approval_id: Number(pendingInitialApproval.value!.approval_id),
      expected_version: selected.value!.contract.lock_version,
      remark: "PC 工作台撤回",
    });
    return selected.value!.contract.id;
  }, "governance");
}

async function filePayload(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  bytes.forEach((value) => (binary += String.fromCharCode(value)));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const checksum = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
  return { content_base64: btoa(binary), checksum };
}

async function addMainDocument() {
  if (!selected.value || !documentFile.value) return;
  await runAction("主合同文档已追加为新版本。", async () => {
    const file = documentFile.value!;
    const payload = await filePayload(file);
    const uploaded = await http.post<Envelope<{ id: number }>>("/attachments", {
      biz_type: "LEASE_CONTRACT",
      biz_id: String(selected.value!.contract.id),
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      content_base64: payload.content_base64,
      park_id: selected.value!.contract.park_id,
    });
    await http.post(`/leases/${selected.value!.contract.id}/documents`, {
      expected_version: selected.value!.contract.lock_version,
      attachment_id: uploaded.data.data.id,
      document_type: "MAIN_CONTRACT",
      checksum: payload.checksum,
      is_main: true,
    });
    documentFile.value = null;
    return selected.value!.contract.id;
  }, "governance");
}

async function documentAction(documentId: number, action: "approve" | "sign") {
  if (!selected.value) return;
  await runAction(action === "approve" ? "文档已批准。" : "文档签署事实已登记。", async () => {
    await http.post(`/leases/${selected.value!.contract.id}/documents/${documentId}/${action}`, {
      expected_version: selected.value!.contract.lock_version,
    });
    return selected.value!.contract.id;
  }, "governance");
}

async function activateContract(id?: number) {
  const target = id ? items.value.find((row) => row.id === id) : selected.value?.contract;
  if (!target) return;
  await runAction("合同已激活：版本与履约计划已固化，未生成账单。", async () => {
    await http.post(`/leases/${target.id}/lifecycle/activate`, {
      expected_version: target.lock_version,
    });
    return target.id;
  });
}

async function createChange() {
  if (!selected.value) return;
  await runAction("变更草稿已创建。", async () => {
    await http.post(`/leases/${selected.value!.contract.id}/changes`, {
      expected_version: selected.value!.contract.lock_version,
      change_type: changeForm.change_type,
      effective_date: changeForm.effective_date,
      reason: changeForm.reason,
      proposed_snapshot: JSON.parse(changeForm.proposal),
    });
    return selected.value!.contract.id;
  }, "changes");
}

async function changeAction(change: Record<string, unknown>, action: string) {
  if (!selected.value) return;
  await runAction(`变更已${action === "apply" ? "应用" : action === "approve" ? "批准" : action === "submit" ? "提交" : action === "withdraw" ? "撤回" : "取消"}。`, async () => {
    const body: Record<string, unknown> = { expected_version: selected.value!.contract.lock_version };
    if (action === "apply") {
      body.idempotency_key = `pc-change-${change.id}-${Date.now()}`;
      body.as_of = String(change.effective_date);
    }
    if (action === "approve") body.override_reason = window.prompt("同人审批时请输入越权原因") || undefined;
    await http.post(`/lease-changes/${change.id}/${action}`, body);
    return selected.value!.contract.id;
  }, "changes");
}

async function createExit() {
  if (!selected.value) return;
  await runAction("退租交接草稿已创建；占用仍保留。", async () => {
    await http.post(`/leases/${selected.value!.contract.id}/exit-settlements`, {
      expected_version: selected.value!.contract.lock_version,
      handover_date: exitForm.handover_date,
      inspection_summary: exitForm.inspection_summary,
    });
    return selected.value!.contract.id;
  }, "exit");
}

async function editExit() {
  if (!selected.value?.exit_settlement) return;
  const exit = selected.value.exit_settlement;
  await runAction("退租读表与结算项已重新计算。", async () => {
    await http.put(`/lease-exit-settlements/${exit.id}`, {
      expected_version: Number(exit.lock_version),
      inspection_summary: exitForm.inspection_summary,
      meter_readings: JSON.parse(exitForm.meter_readings),
      items: JSON.parse(exitForm.items),
    });
    return selected.value!.contract.id;
  }, "exit");
}

async function exitAction(action: "submit" | "approve" | "reject" | "withdraw" | "close") {
  if (!selected.value?.exit_settlement) return;
  const exit = selected.value.exit_settlement;
  await runAction(action === "close" ? "退租已关闭并释放占用；未执行资金操作。" : `退租流程已${action}。`, async () => {
    const body: Record<string, unknown> = { expected_version: Number(exit.lock_version) };
    if (["submit", "withdraw", "close"].includes(action)) {
      body.contract_expected_version = selected.value!.contract.lock_version;
    }
    if (action === "approve") body.override_reason = window.prompt("同人审批时请输入越权原因") || undefined;
    if (action === "close") body.idempotency_key = `pc-exit-${exit.id}-${Date.now()}`;
    await http.post(`/lease-exit-settlements/${exit.id}/${action}`, body);
    return selected.value!.contract.id;
  }, "exit");
}

async function confirmClearance() {
  if (!selected.value?.exit_settlement || !exitEvidenceFile.value) return;
  const exit = selected.value.exit_settlement;
  await runAction("外部清账证据已确认；系统未执行收退款。", async () => {
    const file = exitEvidenceFile.value!;
    const payload = await filePayload(file);
    const uploaded = await http.post<Envelope<{ id: number }>>("/attachments", {
      biz_type: "LEASE_EXIT_SETTLEMENT",
      biz_id: String(exit.id),
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      content_base64: payload.content_base64,
      park_id: selected.value!.contract.park_id,
    });
    const documented = await http.post<Envelope<Lifecycle>>(
      `/leases/${selected.value!.contract.id}/documents`,
      {
        expected_version: selected.value!.contract.lock_version,
        attachment_id: uploaded.data.data.id,
        document_type: "EXIT_HANDOVER",
        checksum: payload.checksum,
        is_main: false,
        exit_settlement_id: Number(exit.id),
      }
    );
    const exitDocument = [...documented.data.data.documents]
      .reverse()
      .find(
        (document) =>
          Number(document.exit_settlement_id || 0) === Number(exit.id) &&
          document.document_type === "EXIT_HANDOVER" &&
          document.status === "DRAFT"
      );
    if (!exitDocument) throw new Error("退租交接文档创建失败");
    await http.post(
      `/leases/${selected.value!.contract.id}/documents/${exitDocument.id}/approve`,
      { expected_version: documented.data.data.contract.lock_version }
    );
    await http.post(`/lease-exit-settlements/${exit.id}/clearance`, {
      expected_version: Number(exit.lock_version),
      evidence_attachment_id: uploaded.data.data.id,
      reference: exitForm.clearance_reference,
      reason: exitForm.clearance_reason,
    });
    exitEvidenceFile.value = null;
    return selected.value!.contract.id;
  }, "exit");
}

onMounted(load);
</script>

<template>
  <section class="lease-workspace" aria-labelledby="leases-title">
    <header class="hero">
      <div>
        <p class="eyebrow">CONTRACT LIFECYCLE · V2</p>
        <h2 id="leases-title" data-testid="leases-title">合同履约与退租工作台</h2>
        <p class="muted">从草稿、审批、文档、履约版本到变更与退租，所有资金动作保持在账务域之外。</p>
      </div>
      <button v-if="canWrite" class="btn" type="button" @click="openCreate">新建合同草稿</button>
    </header>

    <div class="metrics" aria-label="合同关键指标">
      <article class="metric-card"><span>当前合同</span><strong>{{ summary?.metrics.current_contracts ?? 0 }}</strong><small>在租 / 到期 / 退租中</small></article>
      <article class="metric-card"><span>90 天内到期</span><strong>{{ summary?.metrics.expiring_within_90_days ?? 0 }}</strong><small>以 {{ summary?.as_of || "—" }} 为准</small></article>
      <article class="metric-card"><span>待审批 / 待生效</span><strong>{{ summary?.metrics.pending_approval ?? 0 }}</strong><small>治理队列</small></article>
      <article class="metric-card"><span>到期变更</span><strong>{{ summary?.metrics.due_changes ?? 0 }}</strong><small>需人工或受控任务应用</small></article>
      <article class="metric-card warning"><span>未清账结算</span><strong>{{ summary?.metrics.unresolved_clearance ?? 0 }}</strong><small>¥ {{ summary?.metrics.unresolved_clearance_amount ?? "0" }} · 外部证据</small></article>
    </div>

    <section class="card filters" aria-label="合同筛选">
      <label>园区<select v-model="filters.park_id" class="input" @change="load"><option value="">全部可见园区</option><option v-for="park in parks" :key="park.id" :value="String(park.id)">{{ park.label }}</option></select></label>
      <label>承租主体<select v-model="filters.party_id" class="input" @change="load"><option value="">全部可见主体</option><option v-for="party in parties" :key="party.id" :value="String(party.id)">{{ party.label }}</option></select></label>
      <label>状态<select v-model="filters.status" class="input" @change="load"><option value="">全部状态</option><option v-for="value in Object.keys(statusLabel)" :key="value" :value="value">{{ labelStatus(value) }}</option></select></label>
      <label>合同类型<select v-model="filters.contract_type" class="input" @change="load"><option value="">全部类型</option><option value="NEW">新签</option><option value="RENEWAL">续租</option><option value="TRANSFER">转签</option></select></label>
      <label>审批状态<select v-model="filters.approval_status" class="input" @change="load"><option value="">全部审批</option><option value="PENDING">待审批</option><option value="APPROVED">已批准</option><option value="REJECTED">已驳回</option><option value="WITHDRAWN">已撤回</option></select></label>
      <label>变更状态<select v-model="filters.change_status" class="input" @change="load"><option value="">全部变更</option><option value="DRAFT">草稿</option><option value="SUBMITTED">已提交</option><option value="APPROVED">待生效</option><option value="APPLIED">已应用</option></select></label>
      <label>退租状态<select v-model="filters.exit_status" class="input" @change="load"><option value="">全部退租</option><option value="DRAFT">草稿</option><option value="SUBMITTED">已提交</option><option value="APPROVED">已批准</option><option value="CLOSED">已关闭</option></select></label>
      <label>到期不早于<input v-model="filters.end_from" class="input" type="date" @change="load" /></label>
      <label>到期不晚于<input v-model="filters.end_to" class="input" type="date" @change="load" /></label>
      <label class="search">合同号 / 备注<input v-model.trim="filters.keyword" class="input" placeholder="输入关键字" @keyup.enter="load" /></label>
      <button class="btn btn-ghost" type="button" @click="load">查询</button>
    </section>

    <p v-if="error" class="notice error" data-testid="lease-error" role="alert">{{ error }}</p>
    <p v-if="success" class="notice success" data-testid="lease-success" role="status">{{ success }}</p>

    <section class="card table-card">
      <div class="section-title"><div><h3>合同台账</h3><p class="muted">{{ items.length }} 条可见记录</p></div><span v-if="loading" class="spinner">刷新中…</span></div>
      <div class="table-scroll">
        <table class="table" data-testid="lease-table">
          <thead><tr><th>合同 / 主体</th><th>园区</th><th>状态</th><th>租期</th><th>版本</th><th>押金（事实）</th><th class="right">操作</th></tr></thead>
          <tbody>
            <tr v-for="row in items" :key="row.id" :data-testid="`lease-row-${row.id}`">
              <td><button class="link-button" type="button" @click="openDetail(row.id)"><strong>{{ row.contract_no }}</strong><small>主体 #{{ row.party_id }}</small></button></td>
              <td>#{{ row.park_id }}</td>
              <td><span class="status" :data-status="row.status">{{ labelStatus(row.status) }}</span><small v-if="row.approval_status">{{ row.approval_status }}</small></td>
              <td>{{ row.start_date }}<br /><span class="muted">至 {{ row.end_date }}</span></td>
              <td>V{{ row.current_version_no }} <small>锁 {{ row.lock_version }}</small></td>
              <td>¥ {{ row.deposit_amount }}</td>
              <td class="right"><button class="btn btn-ghost compact" type="button" @click="openDetail(row.id)">查看</button><button v-if="row.status === 'PENDING_ACTIVE' && canActivate" class="btn compact" type="button" data-testid="lease-activate-btn" :disabled="saving" @click="activateContract(row.id)">激活</button></td>
            </tr>
            <tr v-if="!items.length && !loading"><td colspan="7" class="empty">暂无符合条件的合同</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="createOpen" class="overlay" @click.self="createOpen = false">
      <section class="dialog create-dialog" role="dialog" aria-modal="true" aria-labelledby="create-title">
        <header class="dialog-head"><div><p class="eyebrow">DRAFT BUILDER</p><h3 id="create-title">新建合同草稿</h3></div><button class="icon-button" type="button" aria-label="关闭" @click="createOpen = false">×</button></header>
        <form @submit.prevent="createDraft">
          <div class="form-grid">
            <label>园区<select v-model="form.park_id" class="input" data-testid="lease-park-id" required><option value="" disabled>请选择园区</option><option v-for="park in parks" :key="park.id" :value="String(park.id)">{{ park.label }}</option></select></label>
            <label>承租主体<select v-model="form.party_id" class="input" data-testid="lease-party-id" required><option value="" disabled>请选择主体</option><option v-for="party in parties" :key="party.id" :value="String(party.id)" :disabled="party.eligible === false">{{ party.label }}{{ party.eligible === false ? "（不可签约）" : "" }}</option></select></label>
            <label>开始日期<input v-model="form.start_date" class="input" data-testid="lease-start" type="date" required @change="form.charges.forEach((row) => (row.start_date = form.start_date))" /></label>
            <label>结束日期<input v-model="form.end_date" class="input" data-testid="lease-end" type="date" required @change="form.charges.forEach((row) => (row.end_date = form.end_date))" /></label>
            <label>押金事实金额<input v-model="form.deposit_amount" class="input" data-testid="lease-deposit" type="number" min="0" step="0.01" required /></label>
          </div>
          <div class="builder-section"><div class="builder-title"><h4>租赁单元</h4><button class="text-button" type="button" @click="addUnit">＋ 添加单元</button></div><div v-for="(line, index) in form.units" :key="index" class="line-grid"><label>单元<select v-model="line.unit_id" class="input" :data-testid="index === 0 ? 'lease-unit-id' : undefined" required><option value="" disabled>选择可见单元</option><option v-for="unit in availableUnits" :key="unit.id" :value="String(unit.id)">{{ unit.label }} · 可用 {{ unit.available_area }}㎡</option></select></label><label>占用面积<input v-model="line.occupied_area" class="input" :data-testid="index === 0 ? 'lease-area' : undefined" type="number" min="0.01" step="0.01" required /></label><label>参考单价<input v-model="line.unit_rent_price" class="input" type="number" min="0" step="0.0001" /></label><button v-if="form.units.length > 1" class="icon-button remove" type="button" aria-label="移除单元" @click="form.units.splice(index, 1)">×</button></div></div>
          <div class="builder-section"><div class="builder-title"><h4>结构化收费项</h4><button class="text-button" type="button" @click="addCharge">＋ 添加收费项</button></div><div v-for="(charge, index) in form.charges" :key="index" class="charge-grid"><input v-model="charge.charge_code" class="input" aria-label="收费项编码" placeholder="编码" required /><select v-model="charge.charge_type" class="input" aria-label="收费类型"><option>RENT</option><option>PROPERTY_FEE</option><option>SERVICE_FEE</option><option>UTILITIES</option><option>DEPOSIT</option></select><select v-model="charge.calculation_method" class="input" aria-label="计费方法"><option value="FIXED">固定金额</option><option value="PER_AREA">面积 × 单价</option></select><select v-model="charge.billing_cycle" class="input" aria-label="计费周期"><option value="MONTHLY">月</option><option value="QUARTERLY">季</option><option value="SEMI_ANNUAL">半年</option><option value="ANNUAL">年</option><option value="ONE_TIME">一次性</option></select><input v-if="charge.calculation_method === 'FIXED'" v-model="charge.amount" class="input" type="number" min="0" step="0.01" aria-label="固定金额" placeholder="金额" required /><input v-else v-model="charge.unit_price" class="input" type="number" min="0" step="0.0001" aria-label="计费单价" placeholder="单价" required /><button v-if="form.charges.length > 1" class="icon-button remove" type="button" aria-label="移除收费项" @click="form.charges.splice(index, 1)">×</button></div></div>
          <footer class="dialog-actions"><span class="muted">保存后仅生成履约计划预览，不生成账单。</span><button class="btn btn-ghost" type="button" @click="createOpen = false">取消</button><button class="btn" data-testid="lease-create-btn" type="submit" :disabled="saving">保存并预览</button></footer>
        </form>
      </section>
    </div>

    <div v-if="drawerOpen" class="overlay drawer-overlay" @click.self="drawerOpen = false">
      <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="detail-title">
        <header class="dialog-head"><div><p class="eyebrow">IMMUTABLE FACTS & GOVERNANCE</p><h3 id="detail-title">{{ selected?.contract.contract_no || "合同详情" }}</h3><p v-if="selected" class="muted">{{ labelStatus(selected.contract.status) }} · V{{ selected.contract.current_version_no }} · 锁版本 {{ selected.contract.lock_version }}</p></div><button class="icon-button" type="button" aria-label="关闭详情" @click="drawerOpen = false">×</button></header>
        <nav class="tabs" aria-label="合同详情页签"><button v-for="tab in (['facts','schedule','versions','governance','changes','exit'] as const)" :key="tab" type="button" :class="{ active: activeTab === tab }" @click="activeTab = tab">{{ { facts:'当前事实', schedule:'履约计划', versions:'版本', governance:'审批文档', changes:'合同变更', exit:'退租结算' }[tab] }}</button></nav>
        <div v-if="detailLoading" class="drawer-body empty">加载详情…</div>
        <div v-else-if="selected" class="drawer-body">
          <section v-if="activeTab === 'facts'" class="detail-grid"><article class="fact-card"><span>合同状态</span><strong>{{ labelStatus(selected.contract.status) }}</strong><small>{{ selected.contract.start_date }} — {{ selected.contract.end_date }}</small></article><article class="fact-card"><span>主体 / 园区</span><strong>#{{ selected.contract.party_id }} / #{{ selected.contract.park_id }}</strong><button class="text-button" type="button" @click="activeTab = 'governance'">查看治理链</button></article><article class="fact-card"><span>押金事实</span><strong>¥ {{ selected.contract.deposit_amount }}</strong><small>不代表已收或可退</small></article><article class="fact-card"><span>计费口径</span><strong>{{ selected.charges.length }} 项 / {{ selected.schedules.length }} 期</strong><small>Bill 由账务域另行生成</small></article><section class="wide-block"><h4>占用单元</h4><div class="mini-table"><div v-for="unit in selected.units" :key="unit.id"><strong>#{{ unit.unit_id }}</strong><span>{{ unit.occupied_area }}㎡</span><span>参考单价 {{ unit.unit_rent_price }}</span></div></div></section><section class="wide-block"><h4>当前收费项</h4><div class="mini-table"><div v-for="charge in selected.charges" :key="String(charge.id)"><strong>{{ charge.charge_code }}</strong><span>{{ charge.billing_cycle }}</span><span>{{ charge.amount || charge.unit_price }}</span></div></div></section></section>

          <section v-if="activeTab === 'schedule'"><div class="section-title"><div><h4>确定性履约计划</h4><p class="muted">仅为履约事实，不是账单。</p></div><span>{{ selected.schedules.length }} 行</span></div><div class="table-scroll"><table class="table compact-table"><thead><tr><th>版本</th><th>收费项</th><th>期间</th><th>到期日</th><th>未税</th><th>税额</th><th>含税</th></tr></thead><tbody><tr v-for="row in selected.schedules" :key="String(row.deterministic_key)"><td>V{{ row.contract_version_no }}</td><td>{{ row.charge_code }}</td><td>{{ row.period_start }} — {{ row.period_end }}</td><td>{{ row.due_date }}</td><td>{{ row.net_amount }}</td><td>{{ row.tax_amount }}</td><td>{{ row.gross_amount }}</td></tr></tbody></table></div></section>

          <section v-if="activeTab === 'versions'"><article v-for="version in [...selected.versions].reverse()" :key="String(version.version_no)" class="timeline-card"><div class="timeline-dot"></div><div><strong>版本 V{{ version.version_no }} · {{ version.reason }}</strong><p>{{ version.effective_at || "未标记生效时间" }}</p><code>{{ version.checksum }}</code></div></article><div v-if="selected.versions.length > 1" class="diff-box"><h4>最新版本快照</h4><pre>{{ JSON.stringify(selected.current_snapshot, null, 2) }}</pre></div></section>

          <section v-if="activeTab === 'governance'" class="stack"><div class="action-bar"><button v-if="selected.contract.status === 'DRAFT' && canWrite" class="btn" type="button" :disabled="saving" @click="submitInitial">提交审批</button><button v-if="selected.contract.status === 'PENDING_APPROVAL' && canApprove" class="btn" type="button" :disabled="saving" @click="decideInitial(true)">批准</button><button v-if="selected.contract.status === 'PENDING_APPROVAL' && canApprove" class="btn danger-btn" type="button" :disabled="saving" @click="decideInitial(false)">驳回</button><button v-if="selected.contract.status === 'PENDING_APPROVAL' && canWrite" class="btn btn-ghost" type="button" :disabled="saving" @click="withdrawInitial">撤回</button><button v-if="selected.contract.status === 'PENDING_ACTIVE' && canActivate" class="btn" type="button" data-testid="lease-activate-btn" :disabled="saving" @click="activateContract()">激活合同</button></div><div v-if="canDocument" class="upload-line"><label>追加主合同文档<input type="file" @change="documentFile = ($event.target as HTMLInputElement).files?.[0] || null" /></label><button class="btn btn-ghost" type="button" :disabled="saving || !documentFile" @click="addMainDocument">上传并追加</button></div><section class="wide-block"><h4>文档版本</h4><div v-for="doc in selected.documents" :key="String(doc.id)" class="document-row"><div><strong>{{ doc.document_type }} · V{{ doc.document_version }}</strong><small>{{ doc.status }} · {{ String(doc.checksum).slice(0, 12) }}…</small></div><div class="row-actions"><button v-if="doc.status === 'DRAFT' && canDocument" class="text-button" type="button" :disabled="saving" @click="documentAction(Number(doc.id), 'approve')">批准版本</button><button v-if="doc.status === 'APPROVED' && canDocument" class="text-button" type="button" :disabled="saving" @click="documentAction(Number(doc.id), 'sign')">签署</button></div></div></section><section class="wide-block"><h4>审批事件</h4><article v-for="approval in selected.approval_timeline" :key="String(approval.approval_id)" class="approval-card"><div><strong>{{ approval.title }}</strong><span class="status">{{ approval.status }}</span></div><p>{{ approval.biz_type }} · {{ approval.biz_id }}</p><ul><li v-for="event in (approval.events as Array<Record<string, unknown>>)" :key="String(event.id)">{{ event.action }} · 用户 #{{ event.actor_user_id || '—' }} · {{ event.created_at }}</li></ul></article></section></section>

          <section v-if="activeTab === 'changes'" class="stack">
            <form v-if="['ACTIVE','EXPIRING'].includes(selected.contract.status) && canChange" class="change-form" @submit.prevent="createChange">
              <label>变更类型<select v-model="changeForm.change_type" class="input"><option>RENEWAL</option><option>EXPANSION</option><option>REDUCTION</option><option>UNIT_TRANSFER</option><option>PRICE_ADJUSTMENT</option><option>PARTY_TRANSFER</option><option>EARLY_TERMINATION</option></select></label>
              <label>生效日<input v-model="changeForm.effective_date" class="input" type="date" required /></label>
              <label class="wide">变更原因<input v-model="changeForm.reason" class="input" required maxlength="2000" /></label>
              <label class="wide">完整未来快照<textarea v-model="changeForm.proposal" class="input code-input" rows="10" required></textarea></label>
              <section class="wide diff-preview" data-testid="draft-change-diff" aria-live="polite">
                <div class="builder-title"><h4>当前事实 → 未来快照</h4><span>{{ draftChangeDiff.length }} 项变化</span></div>
                <p v-if="!parsedChangeProposal" class="diff-note">未来快照必须是有效的 JSON 对象。</p>
                <p v-else-if="draftChangeDiff.length === 0" class="muted">未检测到字段变化，不能据此形成有效变更。</p>
                <div v-else class="table-scroll">
                  <table class="table diff-table">
                    <thead><tr><th>字段路径</th><th>变更前</th><th>变更后</th></tr></thead>
                    <tbody><tr v-for="row in draftChangeDiff" :key="row.path"><td><code>{{ row.path }}</code></td><td>{{ displaySnapshotValue(row.before) }}</td><td>{{ displaySnapshotValue(row.after) }}</td></tr></tbody>
                  </table>
                </div>
              </section>
              <div class="wide diff-note">提交前请核对逐字段差异；生效时会再次校验基准版本、单元容量和日期。</div>
              <button class="btn" type="submit" :disabled="saving || !parsedChangeProposal || draftChangeDiff.length === 0">创建变更草稿</button>
            </form>
            <article v-for="change in selected.changes" :key="String(change.id)" class="change-card">
              <header><div><strong>{{ change.change_no }} · {{ change.change_type }}</strong><p>{{ change.reason }}</p></div><span class="status">{{ change.status }}</span></header>
              <p>基于 V{{ change.base_version_no }} · 生效 {{ change.effective_date }} · 提案 {{ String(change.proposal_checksum).slice(0, 12) }}…</p>
              <div class="row-actions"><button v-if="change.status === 'DRAFT' && canChange" class="btn compact" type="button" :disabled="saving" @click="changeAction(change, 'submit')">提交</button><button v-if="change.status === 'DRAFT' && canChange" class="btn btn-ghost compact" type="button" :disabled="saving" @click="changeAction(change, 'cancel')">取消</button><button v-if="change.status === 'SUBMITTED' && canApprove" class="btn compact" type="button" :disabled="saving" @click="changeAction(change, 'approve')">批准</button><button v-if="change.status === 'SUBMITTED' && canChange" class="btn btn-ghost compact" type="button" :disabled="saving" @click="changeAction(change, 'withdraw')">撤回</button><button v-if="change.status === 'APPROVED' && canChange" class="btn compact" type="button" :disabled="saving" @click="changeAction(change, 'apply')">应用到期变更</button></div>
              <details open><summary>逐字段差异（{{ existingChangeDiff(change).length }}）</summary><div class="table-scroll"><table class="table diff-table"><thead><tr><th>字段路径</th><th>当前事实</th><th>提案值</th></tr></thead><tbody><tr v-for="row in existingChangeDiff(change)" :key="row.path"><td><code>{{ row.path }}</code></td><td>{{ displaySnapshotValue(row.before) }}</td><td>{{ displaySnapshotValue(row.after) }}</td></tr></tbody></table></div></details>
              <details><summary>查看完整未来快照</summary><pre>{{ JSON.stringify(change.proposal, null, 2) }}</pre></details>
            </article>
          </section>

          <section v-if="activeTab === 'exit'" class="stack"><div class="financial-warning">退租结算只保存账务余额快照、结算计算与外部清账证据；不会执行收款、退款或冲销。</div><form v-if="!selected.exit_settlement && ['ACTIVE','EXPIRING'].includes(selected.contract.status) && canSettle" class="form-grid" @submit.prevent="createExit"><label>计划交接日<input v-model="exitForm.handover_date" class="input" type="date" required /></label><label>验房说明<input v-model="exitForm.inspection_summary" class="input" /></label><button class="btn" type="submit">创建退租草稿</button></form><template v-if="selected.exit_settlement"><section class="settlement-total"><article><span>押金事实</span><strong>¥ {{ selected.exit_settlement.held_deposit_amount }}</strong></article><article><span>应收与扣减</span><strong>¥ {{ selected.exit_settlement.receivable_total }} / {{ selected.exit_settlement.deduction_total }}</strong></article><article><span>应收主体</span><strong>¥ {{ selected.exit_settlement.net_due_from_party }}</strong></article><article><span>应退主体</span><strong>¥ {{ selected.exit_settlement.net_due_to_party }}</strong></article></section><p>状态：<span class="status">{{ selected.exit_settlement.status }}</span> · 清账：{{ selected.exit_settlement.financial_clearance_status }}</p><form v-if="selected.exit_settlement.status === 'DRAFT' && canSettle" class="stack" @submit.prevent="editExit"><label>验房说明<input v-model="exitForm.inspection_summary" class="input" /></label><label>读表 JSON<textarea v-model="exitForm.meter_readings" class="input code-input" rows="5"></textarea></label><label>结算项 JSON<textarea v-model="exitForm.items" class="input code-input" rows="6"></textarea></label><button class="btn" type="submit">保存并重新计算</button></form><div class="action-bar"><button v-if="selected.exit_settlement.status === 'DRAFT' && canSettle" class="btn" type="button" @click="exitAction('submit')">提交退租审批</button><button v-if="selected.exit_settlement.status === 'SUBMITTED' && canApprove" class="btn" type="button" @click="exitAction('approve')">批准退租</button><button v-if="selected.exit_settlement.status === 'SUBMITTED' && canApprove" class="btn danger-btn" type="button" @click="exitAction('reject')">驳回</button><button v-if="selected.exit_settlement.status === 'SUBMITTED' && canSettle" class="btn btn-ghost" type="button" @click="exitAction('withdraw')">撤回</button></div><form v-if="selected.exit_settlement.status === 'APPROVED' && selected.exit_settlement.financial_clearance_status !== 'CONFIRMED' && canSettle" class="clearance-form" @submit.prevent="confirmClearance"><label>外部清账凭证<input type="file" required @change="exitEvidenceFile = ($event.target as HTMLInputElement).files?.[0] || null" /></label><label>外部引用<input v-model="exitForm.clearance_reference" class="input" required /></label><label>复核原因<input v-model="exitForm.clearance_reason" class="input" required /></label><small>凭证将同时固化为已批准的退租交接文档。</small><button class="btn" type="submit">确认外部清账证据</button></form><button v-if="canCloseSelectedExit && canSettle" class="btn" type="button" @click="exitAction('close')">关闭退租并释放占用</button></template></section>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.lease-workspace { display: grid; gap: 1rem; min-width: 0; }
.hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; padding: .25rem 0; }
.hero h2, .dialog-head h3 { margin: .1rem 0; }
.eyebrow { margin: 0; color: var(--primary); font-size: .72rem; font-weight: 800; letter-spacing: .14em; }
.metrics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .75rem; }
.metric-card { min-width: 0; padding: 1rem; border: 1px solid #dfe7e4; border-radius: 14px; background: linear-gradient(145deg, #fff, #f7fbf9); }
.metric-card span, .metric-card small, .link-button small, td small, .document-row small { display: block; color: var(--muted); }
.metric-card strong { display: block; margin: .25rem 0; font-size: 1.65rem; }
.metric-card.warning { background: #fffaf0; border-color: #f2d49b; }
.filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .75rem; align-items: end; padding: 1rem; }
label { display: grid; gap: .3rem; color: #475569; font-size: .82rem; font-weight: 650; }
select, textarea { font: inherit; }
.notice { margin: 0; padding: .8rem 1rem; border-radius: 10px; }
.notice.error { background: #fff1f2; }
.notice.success { color: #07633f; background: #eaf8f1; }
.table-card { min-width: 0; overflow: hidden; }
.section-title, .builder-title, .dialog-head, .change-card header, .approval-card > div { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.section-title { padding: 1rem 1rem .25rem; }
.section-title h3, .section-title h4, .builder-title h4 { margin: 0; }
.section-title p { margin: .1rem 0; }
.table-scroll { width: 100%; overflow-x: auto; }
.table { min-width: 850px; }
.right { text-align: right !important; white-space: nowrap; }
.link-button, .text-button, .icon-button { padding: 0; border: 0; color: var(--primary); background: transparent; cursor: pointer; text-align: left; }
.link-button strong { display: block; }
.compact { padding: .42rem .65rem; font-size: .82rem; }
.status { display: inline-flex; width: fit-content; padding: .2rem .55rem; border-radius: 999px; background: #e7f5f0; color: #075d49; font-size: .78rem; font-weight: 750; }
.status[data-status="EXIT_PENDING"], .status[data-status="EXPIRING"] { background: #fff2d8; color: #875500; }
.status[data-status="TERMINATED"], .status[data-status="CANCELLED"] { background: #eef0f3; color: #596273; }
.empty { padding: 2.5rem !important; text-align: center !important; color: var(--muted); }
.overlay { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 1rem; background: rgba(15, 23, 42, .42); backdrop-filter: blur(4px); }
.dialog { width: min(1000px, 96vw); max-height: 94vh; overflow: auto; padding: 1.25rem; border-radius: 18px; background: #fff; box-shadow: 0 24px 80px rgba(15, 23, 42, .25); }
.dialog-head { position: sticky; top: -1.25rem; z-index: 2; padding: .4rem 0 1rem; background: #fff; }
.icon-button { display: grid; width: 2rem; height: 2rem; place-items: center; border-radius: 999px; color: #475569; background: #eef2f4; font-size: 1.25rem; text-align: center; }
.form-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; }
.builder-section { margin-top: 1rem; padding: 1rem; border-radius: 14px; background: #f7f9fa; }
.line-grid { display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: .6rem; align-items: end; margin-top: .6rem; }
.charge-grid { display: grid; grid-template-columns: 1fr 1fr 1.2fr 1fr 1fr auto; gap: .5rem; align-items: center; margin-top: .6rem; }
.remove { align-self: center; color: #9f1239; background: #ffe4e6; }
.dialog-actions { display: flex; align-items: center; justify-content: flex-end; gap: .75rem; margin-top: 1rem; }
.dialog-actions .muted { margin-right: auto; }
.drawer-overlay { place-items: stretch end; padding: 0; }
.drawer { width: min(960px, 96vw); height: 100vh; overflow: hidden; background: #fff; box-shadow: -20px 0 70px rgba(15, 23, 42, .22); }
.drawer > .dialog-head { position: static; height: 98px; padding: 1rem 1.25rem; border-bottom: 1px solid var(--border); }
.tabs { display: flex; gap: .25rem; padding: 0 1.25rem; overflow-x: auto; border-bottom: 1px solid var(--border); }
.tabs button { flex: 0 0 auto; padding: .8rem .7rem; border: 0; border-bottom: 2px solid transparent; color: #64748b; background: transparent; cursor: pointer; }
.tabs button.active { border-color: var(--primary); color: var(--primary); font-weight: 750; }
.drawer-body { height: calc(100vh - 148px); overflow-y: auto; padding: 1.25rem; }
.detail-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .75rem; }
.fact-card { display: grid; gap: .25rem; min-width: 0; padding: 1rem; border: 1px solid var(--border); border-radius: 12px; }
.fact-card span, .fact-card small { color: var(--muted); }
.wide-block, .wide, .diff-note { grid-column: 1 / -1; }
.wide-block { padding: 1rem; border: 1px solid var(--border); border-radius: 12px; }
.wide-block h4 { margin: 0 0 .75rem; }
.mini-table { display: grid; gap: .4rem; }
.mini-table > div, .document-row { display: grid; grid-template-columns: 1.5fr 1fr 1fr; gap: .75rem; padding: .6rem 0; border-bottom: 1px solid var(--border); }
.compact-table { min-width: 740px; }
.timeline-card { position: relative; margin-left: .45rem; padding: 0 0 1.25rem 1.4rem; border-left: 2px solid #cfe5dc; }
.timeline-dot { position: absolute; left: -.42rem; top: .2rem; width: .72rem; height: .72rem; border-radius: 50%; background: var(--primary); }
.timeline-card p { margin: .2rem 0; color: var(--muted); }
code { overflow-wrap: anywhere; font-size: .75rem; }
.diff-box, .financial-warning { padding: 1rem; border-radius: 12px; background: #f6f8fa; }
.diff-preview { min-width: 0; padding: .85rem; border: 1px solid var(--border); border-radius: 10px; background: #fff; }
.diff-preview h4 { margin: 0; }
.diff-table { min-width: 680px; margin-top: .65rem; }
.diff-table td { max-width: 300px; overflow-wrap: anywhere; white-space: normal; }
.diff-table td:nth-child(2) { color: #9f1239; background: #fff7f8; }
.diff-table td:nth-child(3) { color: #075d49; background: #f2fbf7; }
pre { max-width: 100%; overflow: auto; padding: .75rem; border-radius: 10px; background: #101827; color: #dce8e3; font-size: .75rem; }
.stack { display: grid; gap: 1rem; }
.action-bar, .row-actions, .upload-line { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
.danger-btn { background: #b42318; }
.document-row { grid-template-columns: 1fr auto; }
.approval-card, .change-card { padding: 1rem; border: 1px solid var(--border); border-radius: 12px; }
.approval-card p, .change-card p { margin: .25rem 0; color: var(--muted); }
.approval-card ul { margin-bottom: 0; color: #475569; }
.change-form { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; padding: 1rem; border-radius: 12px; background: #f6f8fa; }
.code-input { resize: vertical; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .78rem; }
.diff-note { color: #7c5b18; }
.financial-warning { color: #714b00; background: #fff7e5; border: 1px solid #f4d59a; }
.settlement-total { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .6rem; }
.settlement-total article { padding: .8rem; border: 1px solid var(--border); border-radius: 10px; }
.settlement-total span, .settlement-total strong { display: block; }
.clearance-form { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; padding: 1rem; border: 1px dashed #d5a94e; border-radius: 12px; }

@media (max-width: 1100px) {
  .metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .charge-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 768px) {
  .hero { align-items: stretch; flex-direction: column; }
  .metrics, .filters, .form-grid, .detail-grid, .settlement-total, .clearance-form { grid-template-columns: 1fr; }
  .line-grid, .charge-grid { grid-template-columns: 1fr; }
  .dialog { width: 100%; max-height: 96vh; padding: 1rem; }
  .drawer { width: 100vw; }
  .drawer-body { padding: .85rem; }
  .dialog-actions { align-items: stretch; flex-direction: column; }
  .dialog-actions .muted { margin: 0; }
  .dialog-actions .btn { width: 100%; }
}
</style>
