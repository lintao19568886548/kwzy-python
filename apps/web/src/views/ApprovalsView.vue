<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ApiRequestError } from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import {
  createDefinition,
  createDefinitionDraft,
  createDelegation,
  decideTask,
  exportAuditLogs,
  getApproval,
  getAuditLog,
  getDefinition,
  listApprovals,
  listAuditLogs,
  listDefinitions,
  listDelegations,
  listTasks,
  publishDefinition,
  resubmitApproval,
  retireDefinition,
  revokeDelegation,
  submitApproval,
  updateDefinition,
  verifyAuditChain,
  withdrawApproval,
  type Approval,
  type ApprovalDefinition,
  type ApprovalDelegation,
  type ApprovalTask,
  type AuditEvidence,
  type AuditFilters,
  type AuditVerification,
  type DefinitionStep,
} from "@/api/approvalAudit";

type Tab = "applications" | "tasks" | "definitions" | "delegations" | "audit";
type Dialog = "application" | "decision" | "definition" | "delegation" | null;

const auth = useAuthStore();
const activeTab = ref<Tab>("applications");
const dialog = ref<Dialog>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");
const selectedApproval = ref<Approval | null>(null);
const selectedTask = ref<ApprovalTask | null>(null);
const selectedDefinition = ref<ApprovalDefinition | null>(null);
const selectedAudit = ref<AuditEvidence | null>(null);
const verification = ref<AuditVerification | null>(null);
const taskProcessed = ref(false);
const definitionHasDraft = ref(false);
const approvals = ref<Approval[]>([]);
const tasks = ref<ApprovalTask[]>([]);
const definitions = ref<ApprovalDefinition[]>([]);
const delegations = ref<ApprovalDelegation[]>([]);
const audits = ref<AuditEvidence[]>([]);
const totals = reactive({ approvals: 0, tasks: 0, definitions: 0, audits: 0 });

const canApply = computed(() => auth.can("approval:write") || auth.can("*"));
const canTask = computed(() => auth.can("approval.task.decide") || auth.can("*"));
const canDefinitionWrite = computed(() => auth.can("approval.definition.write") || auth.can("*"));
const canDelegate = computed(() => auth.can("approval.delegation.manage") || auth.can("*"));
const canAuditExport = computed(() => auth.can("audit.export") || auth.can("*"));

const applicationFilters = reactive({ status: "", biz_type: "", park_id: "", priority: "", mine: false, created_from: "", created_to: "" });
const auditFilters = reactive<AuditFilters>({
  user_id: "",
  park_id: "",
  action: "",
  resource_type: "",
  resource_id: "",
  request_id: "",
  integrity_state: "",
  created_from: "",
  created_to: "",
});
const applicationForm = reactive({
  definition_code: "",
  biz_type: "PURCHASE",
  biz_id: "",
  title: "",
  park_id: "",
  priority: "MEDIUM",
  remark: "",
});
const decisionForm = reactive({ action: "APPROVE", remark: "", override_reason: "" });
const definitionForm = reactive({
  id: 0,
  code: "",
  name: "",
  biz_type: "PURCHASE",
  park_id: "",
  description: "",
  lock_version: 0,
  steps: [{ step_order: 1, name: "园区经理审批", approval_mode: "ANY", min_approvals: 1, sla_hours: 24, assignees: [{ user_id: "", role_id: "" }] }],
});
const delegationForm = reactive({ delegate_user_id: "", biz_type: "", starts_at: "", ends_at: "" });

const tabs: Array<{ key: Tab; label: string; show: boolean }> = [
  { key: "applications", label: "审批申请", show: auth.can("approval:read") || auth.can("approval:write") || auth.can("*") },
  { key: "tasks", label: "我的待办", show: auth.can("approval.task.read") || auth.can("approval.task.decide") || auth.can("*") },
  { key: "definitions", label: "流程定义", show: auth.can("approval.definition.read") || auth.can("approval.definition.write") || auth.can("*") },
  { key: "delegations", label: "审批委托", show: auth.can("approval.delegation.manage") || auth.can("*") },
  { key: "audit", label: "审计中心", show: auth.can("audit.read") || auth.can("*") },
];

function clean(input: object): Record<string, unknown> {
  return Object.fromEntries(Object.entries(input).filter(([, value]) => value !== "" && value !== null && value !== undefined));
}

function requestKey(prefix: string): string {
  const random = globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2);
  return (prefix + "-" + random).slice(0, 64);
}

function messageOf(reason: unknown): string {
  if (reason instanceof ApiRequestError) {
    if (reason.status === 409) return reason.message + "（数据已变化，表单内容已保留，请刷新后重试）";
    if (reason.status === 403) return "当前账号无权执行此操作";
    if (reason.status === 0) return "网络不可用，数据未丢失，请恢复连接后重试";
    return reason.message;
  }
  return reason instanceof Error ? reason.message : "操作失败";
}

function flashOk(message: string) {
  success.value = message;
  error.value = "";
}

async function loadApplications() {
  const result = await listApprovals({ ...clean(applicationFilters), page: 1, page_size: 100 });
  approvals.value = result.items;
  totals.approvals = result.total;
}

async function loadTasks() {
  const result = await listTasks(taskProcessed.value);
  tasks.value = result.items;
  totals.tasks = result.total;
}

async function loadDefinitions() {
  const result = await listDefinitions();
  definitions.value = result.items;
  totals.definitions = result.total;
}

async function loadDelegations() {
  delegations.value = await listDelegations();
}

async function loadAudits() {
  const result = await listAuditLogs(auditFilters);
  audits.value = result.items;
  totals.audits = result.total;
}

async function refresh() {
  loading.value = true;
  error.value = "";
  try {
    if (activeTab.value === "applications") await loadApplications();
    if (activeTab.value === "tasks") await loadTasks();
    if (activeTab.value === "definitions") await loadDefinitions();
    if (activeTab.value === "delegations") await loadDelegations();
    if (activeTab.value === "audit") await loadAudits();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    loading.value = false;
  }
}

async function switchTab(tab: Tab) {
  activeTab.value = tab;
  selectedApproval.value = null;
  selectedAudit.value = null;
  await refresh();
}

async function openApproval(id: number) {
  try {
    selectedApproval.value = await getApproval(id);
  } catch (reason) {
    error.value = messageOf(reason);
  }
}

async function submitApplication() {
  saving.value = true;
  try {
    await submitApproval({
      ...clean(applicationForm),
      park_id: applicationForm.park_id ? Number(applicationForm.park_id) : undefined,
      idempotency_key: requestKey("submit"),
      snapshot: { source: "approval-center-pc" },
    });
    applicationForm.biz_id = "";
    applicationForm.title = "";
    applicationForm.remark = "";
    dialog.value = null;
    flashOk("审批申请已提交并进入定义版本链");
    await loadApplications();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    saving.value = false;
  }
}

async function withdraw(row: Approval) {
  if (!window.confirm("确认撤回该审批申请？")) return;
  try {
    await withdrawApproval(row.id, { expected_version: row.lock_version, idempotency_key: requestKey("withdraw"), remark: "申请人撤回" });
    flashOk("审批已撤回");
    await loadApplications();
  } catch (reason) {
    error.value = messageOf(reason);
  }
}

async function resubmit(row: Approval) {
  try {
    await resubmitApproval(row.id, { expected_version: row.lock_version, idempotency_key: requestKey("resubmit"), remark: "修改后重新提交" });
    flashOk("审批已重新提交");
    await loadApplications();
  } catch (reason) {
    error.value = messageOf(reason);
  }
}

function openDecision(task: ApprovalTask) {
  selectedTask.value = task;
  decisionForm.action = "APPROVE";
  decisionForm.remark = "";
  decisionForm.override_reason = "";
  dialog.value = "decision";
}

async function saveDecision() {
  if (!selectedTask.value) return;
  saving.value = true;
  try {
    await decideTask(selectedTask.value.id, {
      ...decisionForm,
      expected_version: selectedTask.value.approval_lock_version,
      idempotency_key: requestKey("decision"),
      remark: decisionForm.remark || undefined,
      override_reason: decisionForm.override_reason || undefined,
    });
    dialog.value = null;
    flashOk("审批决定已提交并写入不可串改审计链");
    await loadTasks();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    saving.value = false;
  }
}

function emptyStep(order: number) {
  return { step_order: order, name: "审批节点 " + order, approval_mode: "ANY", min_approvals: 1, sla_hours: 24, assignees: [{ user_id: "", role_id: "" }] };
}

function normalizeSteps(): DefinitionStep[] {
  return definitionForm.steps.map((step, index) => ({
    step_order: index + 1,
    name: step.name,
    approval_mode: step.approval_mode as "ANY" | "ALL",
    min_approvals: Number(step.min_approvals),
    sla_hours: Number(step.sla_hours),
    assignees: step.assignees.map((item) => item.user_id ? { user_id: Number(item.user_id), role_id: null } : { user_id: null, role_id: Number(item.role_id) }),
  }));
}

function openNewDefinition() {
  definitionHasDraft.value = true;
  Object.assign(definitionForm, { id: 0, code: "", name: "", biz_type: "PURCHASE", park_id: "", description: "", lock_version: 0, steps: [emptyStep(1)] });
  dialog.value = "definition";
}

async function openDefinition(id: number) {
  try {
    const row = await getDefinition(id);
    selectedDefinition.value = row;
    const draft = row.versions?.find((version) => version.status === "DRAFT") || row.versions?.at(-1);
    definitionHasDraft.value = Boolean(row.versions?.some((version) => version.status === "DRAFT"));
    Object.assign(definitionForm, {
      id: row.id,
      code: row.code,
      name: row.name,
      biz_type: row.biz_type,
      park_id: row.park_id ? String(row.park_id) : "",
      description: row.description || "",
      lock_version: row.lock_version,
      steps: draft?.steps?.map((step) => ({ ...step, assignees: step.assignees.map((item) => ({ user_id: item.user_id ? String(item.user_id) : "", role_id: item.role_id ? String(item.role_id) : "" })) })) || [emptyStep(1)],
    });
    dialog.value = "definition";
  } catch (reason) {
    error.value = messageOf(reason);
  }
}

async function saveDefinition() {
  if (definitionForm.id && !definitionHasDraft.value) {
    error.value = "已发布版本只读，请先从列表创建新草稿";
    return;
  }
  saving.value = true;
  try {
    if (!definitionForm.id) {
      await createDefinition({ code: definitionForm.code, name: definitionForm.name, biz_type: definitionForm.biz_type, park_id: definitionForm.park_id ? Number(definitionForm.park_id) : undefined, description: definitionForm.description || undefined, steps: normalizeSteps() });
    } else {
      await updateDefinition(definitionForm.id, { expected_lock_version: definitionForm.lock_version, name: definitionForm.name, description: definitionForm.description || undefined, steps: normalizeSteps() });
    }
    dialog.value = null;
    flashOk("审批定义草稿已保存");
    await loadDefinitions();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    saving.value = false;
  }
}

async function makeDraft(row: ApprovalDefinition) {
  try { await createDefinitionDraft(row.id, row.lock_version); flashOk("新草稿版本已创建"); await loadDefinitions(); } catch (reason) { error.value = messageOf(reason); }
}

async function publish(row: ApprovalDefinition) {
  try {
    const detail = await getDefinition(row.id);
    const draft = detail.versions?.find((version) => version.status === "DRAFT");
    if (!draft) throw new Error("没有可发布的草稿版本");
    await publishDefinition(row.id, draft.id, detail.lock_version);
    flashOk("审批定义已发布，已有申请仍绑定原版本");
    await loadDefinitions();
  } catch (reason) { error.value = messageOf(reason); }
}

async function retire(row: ApprovalDefinition) {
  if (!window.confirm("停用后新申请不能再使用该定义，确认继续？")) return;
  try { await retireDefinition(row.id, row.lock_version); flashOk("审批定义已停用"); await loadDefinitions(); } catch (reason) { error.value = messageOf(reason); }
}

async function saveDelegation() {
  saving.value = true;
  try {
    await createDelegation({ delegate_user_id: Number(delegationForm.delegate_user_id), biz_type: delegationForm.biz_type || undefined, starts_at: new Date(delegationForm.starts_at).toISOString(), ends_at: new Date(delegationForm.ends_at).toISOString() });
    Object.assign(delegationForm, { delegate_user_id: "", biz_type: "", starts_at: "", ends_at: "" });
    dialog.value = null;
    flashOk("委托已生效");
    await loadDelegations();
  } catch (reason) { error.value = messageOf(reason); } finally { saving.value = false; }
}

async function revoke(row: ApprovalDelegation) {
  try { await revokeDelegation(row.id); flashOk("委托已撤销"); await loadDelegations(); } catch (reason) { error.value = messageOf(reason); }
}

async function openAudit(id: number) {
  try { selectedAudit.value = await getAuditLog(id); } catch (reason) { error.value = messageOf(reason); }
}

async function verifyChain() {
  try { verification.value = await verifyAuditChain(); flashOk("审计链独立校验完成"); } catch (reason) { error.value = messageOf(reason); }
}

async function downloadAudit() {
  try {
    const blob = await exportAuditLogs(auditFilters);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "audit-logs.csv";
    anchor.click();
    URL.revokeObjectURL(url);
    flashOk("审计证据已导出，导出动作同时留痕");
  } catch (reason) { error.value = messageOf(reason); }
}

onMounted(async () => {
  const first = tabs.find((tab) => tab.show);
  if (first) activeTab.value = first.key;
  await refresh();
});
</script>

<template>
  <section class="approval-center" data-testid="approval-center">
    <header class="hero card">
      <div>
        <p class="eyebrow">PLATFORM GOVERNANCE · REAL DATA</p>
        <h1 data-testid="approval-center-title">审批与审计中心</h1>
        <p>版本化流程、待办委托与可验证审计证据统一闭环</p>
      </div>
      <div class="hero-actions">
        <button class="ghost-button" type="button" data-testid="approval-refresh" :disabled="loading" @click="refresh">{{ loading ? "加载中…" : "刷新数据" }}</button>
        <button v-if="activeTab === 'applications' && canApply" class="accent-button" type="button" data-testid="approval-create-open" @click="dialog = 'application'">发起审批</button>
        <button v-if="activeTab === 'definitions' && canDefinitionWrite" class="accent-button" type="button" data-testid="definition-create-open" @click="openNewDefinition">新建定义</button>
        <button v-if="activeTab === 'delegations' && canDelegate" class="accent-button" type="button" data-testid="delegation-create-open" @click="dialog = 'delegation'">新建委托</button>
      </div>
    </header>

    <section class="metric-grid" aria-label="审批审计指标">
      <article><span>审批申请</span><strong data-testid="metric-approvals">{{ totals.approvals }}</strong><small>按当前筛选</small></article>
      <article><span>我的待办</span><strong data-testid="metric-tasks">{{ totals.tasks }}</strong><small>只统计待处理</small></article>
      <article><span>流程定义</span><strong data-testid="metric-definitions">{{ totals.definitions }}</strong><small>版本不可覆盖</small></article>
      <article class="risk"><span>审计证据</span><strong data-testid="metric-audits">{{ totals.audits }}</strong><small>链式完整性</small></article>
    </section>

    <nav class="tabs card" aria-label="审批与审计分类" data-testid="approval-tabs">
      <button v-for="tab in tabs.filter((item) => item.show)" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" :data-testid="'tab-' + tab.key" @click="switchTab(tab.key)">{{ tab.label }}</button>
    </nav>

    <p v-if="error" class="state error-state" role="alert" data-testid="approval-error">{{ error }} <button type="button" data-testid="approval-retry" @click="refresh">重试</button></p>
    <p v-if="success" class="state success-state" role="status" data-testid="approval-success">{{ success }}</p>
    <p v-if="loading" class="state loading-state" role="status" data-testid="approval-loading">正在读取真实业务数据…</p>

    <main v-if="!loading" class="workspace card">
      <section v-if="activeTab === 'applications'" data-testid="applications-panel">
        <div class="section-head"><div><h2>审批申请</h2><p>原始申请快照与流程版本永久绑定</p></div></div>
        <form class="filters" data-testid="approval-filters" @submit.prevent="loadApplications">
          <select v-model="applicationFilters.status" class="input" data-testid="approval-status-filter"><option value="">全部状态</option><option value="PENDING">待审批</option><option value="APPROVED">已通过</option><option value="REJECTED">已驳回</option><option value="RETURNED">已退回</option><option value="WITHDRAWN">已撤回</option></select>
          <input v-model.trim="applicationFilters.biz_type" class="input" placeholder="业务类型" data-testid="approval-biz-filter" />
          <input v-model.trim="applicationFilters.park_id" class="input" inputmode="numeric" placeholder="园区 ID" data-testid="approval-park-filter" />
          <select v-model="applicationFilters.priority" class="input"><option value="">全部优先级</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>URGENT</option></select>
          <input v-model="applicationFilters.created_from" class="input" type="datetime-local" title="创建时间起" data-testid="approval-created-from" />
          <input v-model="applicationFilters.created_to" class="input" type="datetime-local" title="创建时间止" data-testid="approval-created-to" />
          <label class="check"><input v-model="applicationFilters.mine" type="checkbox" /> 只看我发起</label>
          <button class="ghost-button" type="submit">查询</button>
        </form>
        <div v-if="!approvals.length" class="empty" data-testid="approvals-empty">暂无符合条件的审批申请</div>
        <div v-else class="table-wrap"><table class="data-table" data-testid="approvals-table"><thead><tr><th>申请单号</th><th>标题 / 业务</th><th>园区</th><th>优先级</th><th>状态</th><th>当前节点</th><th>操作</th></tr></thead><tbody><tr v-for="row in approvals" :key="row.id" :data-testid="'approval-row-' + row.id"><td><button class="link-button" type="button" @click="openApproval(row.id)">{{ row.request_no || '#' + row.id }}</button></td><td><b>{{ row.title }}</b><small>{{ row.biz_type }} · {{ row.biz_id }}</small></td><td>{{ row.park_id || '集团级' }}</td><td><span :class="['priority', row.priority.toLowerCase()]">{{ row.priority }}</span></td><td><span :class="['status', row.status.toLowerCase()]">{{ row.status }}</span></td><td>{{ row.current_step_order || '—' }}</td><td class="row-actions"><button type="button" @click="openApproval(row.id)">详情</button><button v-if="canApply && row.status === 'PENDING' && row.applicant_user_id === auth.userId" type="button" @click="withdraw(row)">撤回</button><button v-if="canApply && (row.status === 'RETURNED' || row.status === 'WITHDRAWN') && row.applicant_user_id === auth.userId" type="button" @click="resubmit(row)">重提</button></td></tr></tbody></table></div>
      </section>

      <section v-else-if="activeTab === 'tasks'" data-testid="tasks-panel">
        <div class="section-head"><div><h2>{{ taskProcessed ? '我的已处理审批' : '我的审批待办' }}</h2><p>本人任务与有效委托任务合并呈现</p></div><select v-model="taskProcessed" class="input task-mode" data-testid="task-processed-filter" @change="loadTasks"><option :value="false">待处理</option><option :value="true">已处理</option></select></div>
        <p v-if="!canTask" class="readonly" data-testid="tasks-readonly">当前为只读模式，仅可查看任务。</p>
        <div v-if="!tasks.length" class="empty" data-testid="tasks-empty">当前没有{{ taskProcessed ? '已处理记录' : '待处理审批' }}</div>
        <div v-else class="task-grid"><article v-for="task in tasks" :key="task.id" class="task-card" :data-testid="'task-card-' + task.id"><header><span :class="['priority', task.priority.toLowerCase()]">{{ task.priority }}</span><span>第 {{ task.step_order }} 节点 · {{ task.status }}</span></header><h3>{{ task.title }}</h3><p>{{ task.request_no }} · {{ task.biz_type }}#{{ task.biz_id }}</p><dl><div><dt>原审批人</dt><dd>{{ task.assignee_user_id }}</dd></div><div><dt>到期时间</dt><dd>{{ task.due_at ? new Date(task.due_at).toLocaleString() : '未设置' }}</dd></div></dl><button v-if="canTask && task.status === 'PENDING'" class="accent-button" type="button" :data-testid="'task-decide-' + task.id" @click="openDecision(task)">处理待办</button></article></div>
      </section>

      <section v-else-if="activeTab === 'definitions'" data-testid="definitions-panel">
        <div class="section-head"><div><h2>流程定义治理</h2><p>草稿可编辑，发布版本只读且申请不可漂移</p></div></div>
        <p v-if="!canDefinitionWrite" class="readonly" data-testid="definitions-readonly">当前为只读模式，不能修改或发布流程。</p>
        <div v-if="!definitions.length" class="empty" data-testid="definitions-empty">尚未创建审批定义</div>
        <div v-else class="definition-grid"><article v-for="row in definitions" :key="row.id" class="definition-card" :data-testid="'definition-card-' + row.id"><header><span class="code">{{ row.code }}</span><span :class="['status', row.status.toLowerCase()]">{{ row.status }}</span></header><h3>{{ row.name }}</h3><p>{{ row.biz_type }} · {{ row.park_id ? '园区 ' + row.park_id : '集团通用' }}</p><div class="version">当前版本 <strong>v{{ row.current_version }}</strong><small>锁版本 {{ row.lock_version }}</small></div><div class="row-actions"><button type="button" @click="openDefinition(row.id)">{{ canDefinitionWrite ? '查看/编辑' : '查看' }}</button><button v-if="canDefinitionWrite && row.current_version > 0" type="button" @click="makeDraft(row)">新草稿</button><button v-if="canDefinitionWrite && row.status === 'ACTIVE'" type="button" @click="publish(row)">发布草稿</button><button v-if="canDefinitionWrite && row.status === 'ACTIVE'" class="danger-link" type="button" @click="retire(row)">停用</button></div></article></div>
      </section>

      <section v-else-if="activeTab === 'delegations'" data-testid="delegations-panel">
        <div class="section-head"><div><h2>审批委托</h2><p>委托不改变原审批人，决定会同时记录实际操作者</p></div></div>
        <p v-if="!canDelegate" class="readonly">当前账号无委托管理权限。</p>
        <div v-if="!delegations.length" class="empty" data-testid="delegations-empty">没有有效或历史委托</div>
        <div v-else class="table-wrap"><table class="data-table" data-testid="delegations-table"><thead><tr><th>委托人</th><th>受托人</th><th>业务范围</th><th>有效期</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="row in delegations" :key="row.id"><td>{{ row.grantor_user_id }}</td><td>{{ row.delegate_user_id }}</td><td>{{ row.biz_type || '全部业务' }}</td><td>{{ new Date(row.starts_at).toLocaleString() }}<small>至 {{ new Date(row.ends_at).toLocaleString() }}</small></td><td><span :class="['status', row.status.toLowerCase()]">{{ row.status }}</span></td><td><button v-if="canDelegate && row.status === 'ACTIVE'" class="link-button" type="button" @click="revoke(row)">撤销</button></td></tr></tbody></table></div>
      </section>

      <section v-else data-testid="audit-panel">
        <div class="section-head"><div><h2>审计证据中心</h2><p>敏感字段脱敏、租户级哈希链与独立验证</p></div><div class="head-actions"><button class="ghost-button" type="button" data-testid="audit-verify" @click="verifyChain">校验完整性</button><button v-if="canAuditExport" class="accent-button" type="button" data-testid="audit-export" @click="downloadAudit">导出 CSV</button></div></div>
        <form class="filters audit-filters" data-testid="audit-filters" @submit.prevent="loadAudits"><input v-model.trim="auditFilters.action" class="input" placeholder="动作" data-testid="audit-action-filter" /><input v-model.trim="auditFilters.resource_type" class="input" placeholder="资源类型" /><input v-model.trim="auditFilters.resource_id" class="input" placeholder="资源 ID" /><input v-model.trim="auditFilters.request_id" class="input" placeholder="请求 ID" /><input v-model.trim="auditFilters.user_id" class="input" inputmode="numeric" placeholder="操作者 ID" /><input v-model.trim="auditFilters.park_id" class="input" inputmode="numeric" placeholder="园区 ID" /><input v-model="auditFilters.created_from" class="input" type="datetime-local" title="发生时间起" /><input v-model="auditFilters.created_to" class="input" type="datetime-local" title="发生时间止" /><select v-model="auditFilters.integrity_state" class="input" data-testid="audit-integrity-filter"><option value="">全部完整性</option><option value="VERIFIED">已验证</option><option value="FAILED">验证失败</option><option value="LEGACY_UNVERIFIED">历史未验证</option></select><button class="ghost-button" type="submit">查询证据</button></form>
        <aside v-if="verification" :class="['verification', verification.state.toLowerCase()]" data-testid="audit-verification"><strong>{{ verification.state }}</strong><span>验证 {{ verification.verified_count }} · 历史 {{ verification.legacy_count }} · 失败 {{ verification.failed_count }}</span></aside>
        <div v-if="!audits.length" class="empty" data-testid="audits-empty">没有符合条件的审计证据</div>
        <div v-else class="table-wrap"><table class="data-table" data-testid="audit-table"><thead><tr><th>序号</th><th>动作</th><th>资源</th><th>操作者</th><th>请求 ID</th><th>完整性</th><th>时间</th></tr></thead><tbody><tr v-for="row in audits" :key="row.id" :data-testid="'audit-row-' + row.id" @click="openAudit(row.id)"><td>{{ row.sequence_no || '历史' }}</td><td>{{ row.action }}</td><td>{{ row.resource_type }}<small>{{ row.resource_id || '—' }}</small></td><td>{{ row.user_id || '系统' }}</td><td class="mono">{{ row.request_id }}</td><td><span :class="['status', row.integrity_state.toLowerCase()]">{{ row.integrity_state }}</span></td><td>{{ new Date(row.created_at).toLocaleString() }}</td></tr></tbody></table></div>
      </section>
    </main>

    <aside v-if="selectedApproval" class="drawer card" data-testid="approval-detail-drawer"><header><div><span>审批申请详情</span><h2>{{ selectedApproval.request_no }}</h2></div><button type="button" aria-label="关闭" @click="selectedApproval = null">×</button></header><h3>{{ selectedApproval.title }}</h3><dl class="facts"><div><dt>业务</dt><dd>{{ selectedApproval.biz_type }}#{{ selectedApproval.biz_id }}</dd></div><div><dt>状态</dt><dd>{{ selectedApproval.status }}</dd></div><div><dt>版本</dt><dd>{{ selectedApproval.definition_version_id || '兼容模式' }}</dd></div><div><dt>轮次</dt><dd>{{ selectedApproval.round_no }}</dd></div></dl><section><h4>节点任务</h4><article v-for="task in selectedApproval.tasks || []" :key="task.id" class="history-row"><b>节点 {{ task.step_order }} · {{ task.status }}</b><span>原审批人 {{ task.assignee_user_id }} / 实际操作人 {{ task.acted_by_user_id || '—' }}</span></article></section><section><h4>不可改写事件链</h4><article v-for="event in selectedApproval.events || []" :key="event.id" class="history-row"><b>{{ event.action }}</b><span>{{ event.remark || '无备注' }} · {{ event.created_at ? new Date(event.created_at).toLocaleString() : '' }}</span></article></section></aside>

    <aside v-if="selectedAudit" class="drawer card" data-testid="audit-detail-drawer"><header><div><span>审计证据详情</span><h2>#{{ selectedAudit.sequence_no || selectedAudit.id }}</h2></div><button type="button" aria-label="关闭" @click="selectedAudit = null">×</button></header><dl class="facts"><div><dt>动作</dt><dd>{{ selectedAudit.action }}</dd></div><div><dt>完整性</dt><dd>{{ selectedAudit.integrity_state }}</dd></div><div><dt>资源</dt><dd>{{ selectedAudit.resource_type }}#{{ selectedAudit.resource_id }}</dd></div><div><dt>请求 ID</dt><dd class="mono">{{ selectedAudit.request_id }}</dd></div></dl><h4>已脱敏详情</h4><pre>{{ JSON.stringify(selectedAudit.detail, null, 2) }}</pre><h4>链证据</h4><p class="hash">previous {{ selectedAudit.previous_hash || 'legacy' }}</p><p class="hash">record {{ selectedAudit.record_hash || 'legacy' }}</p></aside>

    <div v-if="dialog" class="modal-backdrop" data-testid="approval-modal" @click.self="dialog = null"><section class="modal card" :class="{ wide: dialog === 'definition' }">
      <header><div><span>审批与审计中心</span><h2>{{ dialog === 'application' ? '发起审批' : dialog === 'decision' ? '处理审批待办' : dialog === 'definition' ? (definitionForm.id ? (definitionHasDraft ? '编辑流程草稿' : '查看已发布版本') : '新建流程定义') : '新建审批委托' }}</h2></div><button type="button" aria-label="关闭" @click="dialog = null">×</button></header>
      <form v-if="dialog === 'application'" class="form-grid" data-testid="approval-create-form" @submit.prevent="submitApplication"><label>定义编码<input v-model.trim="applicationForm.definition_code" class="input" required data-testid="approval-definition-code" /></label><label>业务类型<input v-model.trim="applicationForm.biz_type" class="input" required /></label><label>业务 ID<input v-model.trim="applicationForm.biz_id" class="input" required data-testid="approval-biz-id" /></label><label>标题<input v-model.trim="applicationForm.title" class="input" required data-testid="approval-title" /></label><label>园区 ID<input v-model.trim="applicationForm.park_id" class="input" inputmode="numeric" /></label><label>优先级<select v-model="applicationForm.priority" class="input"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>URGENT</option></select></label><label class="span-two">说明<textarea v-model.trim="applicationForm.remark" class="input" rows="3"></textarea></label><button class="accent-button span-two" type="submit" data-testid="approval-create-submit" :disabled="saving">{{ saving ? '提交中…' : '提交审批' }}</button></form>
      <form v-else-if="dialog === 'decision'" class="form-grid" data-testid="task-decision-drawer" @submit.prevent="saveDecision"><label>处理动作<select v-model="decisionForm.action" class="input" data-testid="task-action"><option value="APPROVE">通过</option><option value="REJECT">驳回并终止</option><option value="RETURN">退回申请人</option></select></label><label class="span-two">处理意见<textarea v-model.trim="decisionForm.remark" class="input" rows="4" :required="decisionForm.action !== 'APPROVE'" data-testid="task-remark"></textarea></label><label class="span-two">本人发起时的特批原因<textarea v-model.trim="decisionForm.override_reason" class="input" rows="2" placeholder="仅有 override_self 权限时有效"></textarea></label><button class="accent-button span-two" type="submit" data-testid="task-decision-submit" :disabled="saving">提交决定</button></form>
      <form v-else-if="dialog === 'delegation'" class="form-grid" data-testid="delegation-form" @submit.prevent="saveDelegation"><label>受托用户 ID<input v-model.trim="delegationForm.delegate_user_id" class="input" required inputmode="numeric" data-testid="delegation-user" /></label><label>业务类型（可空）<input v-model.trim="delegationForm.biz_type" class="input" /></label><label>开始时间<input v-model="delegationForm.starts_at" class="input" type="datetime-local" required data-testid="delegation-start" /></label><label>结束时间<input v-model="delegationForm.ends_at" class="input" type="datetime-local" required data-testid="delegation-end" /></label><button class="accent-button span-two" type="submit" data-testid="delegation-submit" :disabled="saving">创建委托</button></form>
      <form v-else class="definition-form" data-testid="definition-form" @submit.prevent="saveDefinition"><p v-if="definitionForm.id && !definitionHasDraft" class="readonly" data-testid="definition-published-readonly">已发布版本不可覆盖；如需修改，请关闭后点击“新草稿”。</p><fieldset class="definition-fieldset" :disabled="Boolean(definitionForm.id && !definitionHasDraft)"><div class="form-grid"><label>定义编码<input v-model.trim="definitionForm.code" class="input" required :disabled="Boolean(definitionForm.id)" data-testid="definition-code" /></label><label>名称<input v-model.trim="definitionForm.name" class="input" required data-testid="definition-name" /></label><label>业务类型<input v-model.trim="definitionForm.biz_type" class="input" required :disabled="Boolean(definitionForm.id)" /></label><label>园区 ID<input v-model.trim="definitionForm.park_id" class="input" inputmode="numeric" :disabled="Boolean(definitionForm.id)" /></label><label class="span-two">说明<textarea v-model.trim="definitionForm.description" class="input" rows="2"></textarea></label></div><section class="steps"><header><h3>审批节点</h3><button class="ghost-button" type="button" @click="definitionForm.steps.push(emptyStep(definitionForm.steps.length + 1))">增加节点</button></header><article v-for="(step, stepIndex) in definitionForm.steps" :key="stepIndex" class="step"><b>节点 {{ stepIndex + 1 }}</b><input v-model.trim="step.name" class="input" required placeholder="节点名称" /><select v-model="step.approval_mode" class="input"><option value="ANY">任一通过</option><option value="ALL">多人会签</option></select><input v-model.number="step.min_approvals" class="input" type="number" min="1" required title="最少通过人数" /><input v-model.number="step.sla_hours" class="input" type="number" min="1" required title="SLA 小时" /><label v-for="(assignee, assigneeIndex) in step.assignees" :key="assigneeIndex" class="assignee">审批用户 ID<input v-model.trim="assignee.user_id" class="input" inputmode="numeric" :required="!assignee.role_id" /> 或角色 ID<input v-model.trim="assignee.role_id" class="input" inputmode="numeric" :required="!assignee.user_id" /></label><div class="step-actions"><button type="button" @click="step.assignees.push({ user_id: '', role_id: '' })">增加审批人</button><button v-if="definitionForm.steps.length > 1" class="danger-link" type="button" @click="definitionForm.steps.splice(stepIndex, 1)">删除节点</button></div></article></section></fieldset><button v-if="canDefinitionWrite && (!definitionForm.id || definitionHasDraft)" class="accent-button save-definition" type="submit" data-testid="definition-submit" :disabled="saving">保存草稿</button></form>
    </section></div>
  </section>
</template>

<style scoped>
.approval-center { display: grid; gap: 1rem; color: #173247; }
.card { border: 1px solid #dbe5ea; border-radius: 16px; background: #fff; box-shadow: 0 8px 24px rgba(18, 53, 71, .06); }
.hero { display: flex; justify-content: space-between; align-items: center; gap: 1.5rem; padding: 1.5rem; color: #f5fbff; background: radial-gradient(circle at 82% 12%, rgba(20, 184, 166, .22), transparent 28%), linear-gradient(135deg, #092b46, #0d4960 68%, #0d6170); border: 0; }
.hero h1 { margin: .2rem 0; color: #fff; font-size: clamp(1.45rem, 2.4vw, 2.25rem); }.hero p { margin: 0; color: #bcd3dd; }.eyebrow { color: #66e0d5 !important; font-size: .68rem; font-weight: 800; letter-spacing: .16em; }
.hero-actions, .head-actions, .row-actions { display: flex; align-items: center; gap: .55rem; flex-wrap: wrap; }
.accent-button, .ghost-button { min-height: 38px; padding: .55rem .9rem; border: 1px solid transparent; border-radius: 9px; font: inherit; font-weight: 700; cursor: pointer; }.accent-button { color: #fff; background: #0b8b92; }.ghost-button { color: #155269; border-color: #bed1da; background: #fff; }.hero .ghost-button { color: #eaf8fb; border-color: rgba(255,255,255,.32); background: rgba(255,255,255,.08); }.accent-button:disabled, .ghost-button:disabled { opacity: .55; cursor: progress; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: .75rem; }.metric-grid article { display: grid; gap: .15rem; padding: 1rem 1.1rem; border: 1px solid #dce7eb; border-left: 4px solid #21a4af; border-radius: 12px; background: #f8fbfc; }.metric-grid article.risk { border-left-color: #ec6f45; }.metric-grid span, .metric-grid small { color: #6d8290; font-size: .72rem; }.metric-grid strong { color: #123e56; font-size: 1.65rem; }
.tabs { display: flex; gap: .2rem; overflow-x: auto; padding: .4rem; }.tabs button { flex: 0 0 auto; padding: .65rem .9rem; border: 0; border-radius: 9px; color: #617986; background: transparent; font: inherit; cursor: pointer; }.tabs button.active { color: #0b5868; background: #e6f5f5; font-weight: 800; }
.state { margin: 0; padding: .8rem 1rem; border-radius: 10px; }.state button { margin-left: .5rem; border: 0; background: transparent; text-decoration: underline; cursor: pointer; }.error-state { color: #a23828; background: #fff0ec; }.success-state { color: #106c5b; background: #e9f8f3; }.loading-state { color: #155269; background: #eef7f9; }
.workspace { min-width: 0; padding: 1.15rem; }.section-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-bottom: .9rem; }.section-head h2 { margin: 0; font-size: 1.15rem; }.section-head p { margin: .2rem 0 0; color: #6d8290; font-size: .78rem; }
.task-mode { width: auto; min-width: 130px; }
.filters { display: grid; grid-template-columns: repeat(5, minmax(110px, 1fr)); gap: .6rem; margin-bottom: 1rem; }.audit-filters { grid-template-columns: repeat(6, minmax(100px, 1fr)); }.input { width: 100%; min-height: 39px; box-sizing: border-box; padding: .55rem .65rem; border: 1px solid #cddce2; border-radius: 8px; color: #173247; background: #fff; font: inherit; }.input:focus { border-color: #168b96; outline: 3px solid rgba(22,139,150,.12); }.check { display: flex; align-items: center; gap: .45rem; color: #596f7c; font-size: .8rem; }
.empty { padding: 2.5rem 1rem; color: #728894; text-align: center; border: 1px dashed #cad9df; border-radius: 12px; background: #f9fbfc; }.readonly { padding: .65rem .8rem; color: #7b5b23; border-radius: 8px; background: #fff8e7; }
.table-wrap { width: 100%; overflow-x: auto; }.data-table { width: 100%; min-width: 780px; border-collapse: collapse; }.data-table th { padding: .65rem; color: #68808c; font-size: .68rem; text-align: left; background: #f4f8f9; }.data-table td { padding: .72rem .65rem; border-bottom: 1px solid #e5ecef; font-size: .78rem; vertical-align: middle; }.data-table td small, .task-card p, .definition-card p { display: block; margin-top: .2rem; color: #758a95; }.data-table tbody tr { cursor: default; }.data-table tbody tr:hover { background: #f8fbfc; }
.link-button, .row-actions button, .step-actions button { padding: 0; border: 0; color: #097785; background: transparent; font: inherit; font-weight: 700; cursor: pointer; }.danger-link { color: #bc4c31 !important; }.mono { max-width: 180px; overflow: hidden; font-family: ui-monospace, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.status, .priority { display: inline-flex; padding: .2rem .48rem; border-radius: 999px; font-size: .64rem; font-weight: 800; background: #eaf1f4; }.status.approved, .status.active, .status.verified { color: #0c6b5a; background: #dff6ed; }.status.pending, .priority.medium, .status.legacy_unverified { color: #8a6117; background: #fff2d2; }.status.rejected, .status.failed, .priority.urgent { color: #a83f2a; background: #ffe7df; }.status.returned, .status.withdrawn, .status.retired, .status.revoked { color: #647581; background: #eaf0f2; }.priority.high { color: #a83f2a; background: #fff0e8; }.priority.low { color: #236a82; background: #e6f3f8; }
.task-grid, .definition-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; }.task-card, .definition-card { display: grid; gap: .65rem; padding: 1rem; border: 1px solid #dbe6ea; border-radius: 12px; background: linear-gradient(180deg, #fff, #f8fbfc); }.task-card header, .definition-card header { display: flex; justify-content: space-between; align-items: center; color: #718691; font-size: .7rem; }.task-card h3, .definition-card h3 { margin: 0; font-size: .98rem; }.task-card p, .definition-card p { margin: 0; }.task-card dl { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: 0; }.task-card dl div { padding: .5rem; border-radius: 8px; background: #edf4f6; }.task-card dt { color: #718691; font-size: .62rem; }.task-card dd { margin: .1rem 0 0; font-size: .72rem; }.code { color: #0b7681; font-family: ui-monospace, Consolas, monospace; font-weight: 800; }.version { display: flex; align-items: baseline; gap: .35rem; color: #617783; font-size: .72rem; }.version strong { color: #103f56; font-size: 1.1rem; }.version small { margin-left: auto; }
.verification { display: flex; gap: 1rem; align-items: center; margin-bottom: .8rem; padding: .7rem .8rem; border-radius: 9px; color: #0c6b5a; background: #e5f7f0; }.verification.failed { color: #a33e2b; background: #ffe8e1; }
.drawer { position: fixed; z-index: 40; top: 1rem; right: 1rem; bottom: 1rem; width: min(440px, calc(100vw - 2rem)); overflow-y: auto; padding: 1rem; box-shadow: 0 24px 70px rgba(8, 38, 55, .24); }.drawer > header, .modal > header, .steps > header { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }.drawer header span, .modal header span { color: #76909b; font-size: .68rem; }.drawer h2, .modal h2 { margin: .2rem 0; }.drawer header button, .modal header button { border: 0; color: #607681; background: transparent; font-size: 1.7rem; cursor: pointer; }.facts { display: grid; grid-template-columns: 1fr 1fr; gap: .55rem; }.facts div { min-width: 0; padding: .65rem; border-radius: 9px; background: #f1f6f7; }.facts dt { color: #728994; font-size: .63rem; }.facts dd { margin: .15rem 0 0; overflow-wrap: anywhere; font-size: .76rem; font-weight: 800; }.history-row { display: grid; gap: .15rem; padding: .6rem; margin-bottom: .45rem; border-left: 3px solid #28a3ac; border-radius: 7px; background: #f3f8f9; font-size: .72rem; }.history-row span { color: #718691; }.drawer pre { max-height: 280px; overflow: auto; padding: .7rem; color: #d5ecf1; border-radius: 9px; background: #0b3045; font-size: .7rem; white-space: pre-wrap; overflow-wrap: anywhere; }.hash { overflow-wrap: anywhere; color: #657b87; font-family: ui-monospace, Consolas, monospace; font-size: .66rem; }
.modal-backdrop { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; padding: 1rem; background: rgba(5, 29, 43, .46); backdrop-filter: blur(2px); }.modal { width: min(560px, 100%); max-height: calc(100vh - 2rem); overflow-y: auto; padding: 1rem; }.modal.wide { width: min(920px, 100%); }.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-top: 1rem; }.form-grid label { display: grid; gap: .3rem; color: #607681; font-size: .72rem; }.span-two { grid-column: span 2; }.definition-form { margin-top: .8rem; }.definition-fieldset { min-width: 0; margin: 0; padding: 0; border: 0; }.definition-fieldset:disabled { opacity: .72; }.steps { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #dce7eb; }.steps h3 { margin: 0; }.step { display: grid; grid-template-columns: 90px 2fr 1fr 90px 90px; gap: .5rem; align-items: center; margin-top: .65rem; padding: .75rem; border: 1px solid #dce7eb; border-radius: 10px; background: #f8fbfc; }.assignee { display: grid; grid-column: 1 / -1; grid-template-columns: auto 1fr auto 1fr; gap: .45rem; align-items: center; color: #607681; font-size: .7rem; }.step-actions { grid-column: 1 / -1; display: flex; gap: .75rem; }.save-definition { width: 100%; margin-top: .85rem; }
@media (max-width: 1100px) { .metric-grid { grid-template-columns: repeat(2, 1fr); }.task-grid, .definition-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.filters, .audit-filters { grid-template-columns: repeat(3, 1fr); }.step { grid-template-columns: 80px 2fr 1fr 80px 80px; } }
@media (max-width: 720px) { .hero, .section-head { align-items: stretch; flex-direction: column; }.hero-actions, .head-actions { display: grid; grid-template-columns: 1fr 1fr; }.metric-grid, .task-grid, .definition-grid { grid-template-columns: 1fr; }.filters, .audit-filters, .form-grid { grid-template-columns: 1fr; }.span-two { grid-column: auto; }.workspace { padding: .8rem; }.step { grid-template-columns: 1fr 1fr; }.step > b, .step .assignee, .step-actions { grid-column: 1 / -1; }.assignee { grid-template-columns: 1fr; }.drawer { top: .5rem; right: .5rem; bottom: .5rem; width: calc(100vw - 1rem); }.facts { grid-template-columns: 1fr; } }
@media (max-width: 420px) { .metric-grid { grid-template-columns: 1fr 1fr; gap: .45rem; }.metric-grid article { padding: .75rem; }.hero-actions, .head-actions { grid-template-columns: 1fr; }.tabs button { padding: .55rem .68rem; } }
</style>
