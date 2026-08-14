<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type QuoteLine = {
  id: number;
  line_type: string;
  description: string;
  quantity: string;
  unit: string;
  unit_price: string;
  amount: string;
};
type Quote = {
  id: number;
  version_no: number;
  status: string;
  currency: string;
  total_amount: string;
  remark?: string | null;
  lines: QuoteLine[];
};
type TimelineEvent = {
  id: number;
  event_type: string;
  actor_type: string;
  from_status?: string | null;
  to_status?: string | null;
  reason?: string | null;
  occurred_at: string;
};
type CostEntry = {
  id: number;
  entry_type: string;
  description: string;
  quantity: string;
  unit: string;
  unit_price: string;
  amount: string;
  reverses_entry_id?: number | null;
};
type Acceptance = {
  id: number;
  attempt_no: number;
  decision: string;
  comment?: string | null;
  decided_at: string;
};
type Rating = { id: number; score: number; tags: string[]; comment?: string | null };
type WorkOrder = {
  id: number;
  order_no: string;
  park_id: number;
  party_id?: number | null;
  title: string;
  description?: string | null;
  category: string;
  priority: string;
  status: string;
  quote_required: boolean;
  contact_name?: string | null;
  contact_phone_masked?: string | null;
  unit_id?: number | null;
  assignee_user_id?: number | null;
  response_due_at?: string | null;
  resolution_due_at?: string | null;
  sla_status: string;
  lock_version: number;
  resolution_summary?: string | null;
  evidence_refs?: string[];
  accepted_quote_total?: string;
  actual_total?: string;
  cost_variance?: string;
  timeline?: TimelineEvent[];
  quotes?: Quote[];
  cost_entries?: CostEntry[];
  acceptances?: Acceptance[];
  rating?: Rating | null;
};

const auth = useAuthStore();
const tenantMode = computed(
  () => auth.can("tenant_service:read_own") && !auth.can("work_order:read")
);
const basePath = computed(() => (tenantMode.value ? "/tenant-service/requests" : "/work-orders"));
const canIntake = computed(() =>
  tenantMode.value ? auth.can("tenant_service:request") : auth.can(["work_order:intake"])
);
const rows = ref<WorkOrder[]>([]);
const detail = ref<WorkOrder | null>(null);
const loading = ref(false);
const detailLoading = ref(false);
const saving = ref(false);
const showIntake = ref(false);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const filters = ref({ park_id: "", party_id: "", category: "", status: "", assignee_user_id: "" });
const intake = ref({
  park_id: "",
  party_id: "",
  unit_id: "",
  contact_name: "",
  contact_phone: "",
  title: "",
  description: "",
  category: "MAINTENANCE",
  priority: "MEDIUM",
  quote_required: false,
});
const dispatchDraft = ref({ assignee_user_id: "", reason: "" });
const quoteDraft = ref({
  line_type: "LABOR",
  description: "",
  quantity: "1",
  unit: "项",
  unit_price: "0",
  remark: "",
});
const costDraft = ref({
  entry_type: "LABOR",
  description: "",
  quantity: "1",
  unit: "项",
  unit_price: "0",
});
const costReverseReason = ref("");
const completionDraft = ref({ resolution_summary: "", evidence_ref: "", no_evidence_reason: "" });
const quoteDecision = ref({ decision: "ACCEPT", remark: "" });
const acceptanceDraft = ref({ decision: "ACCEPTED", comment: "" });
const ratingDraft = ref({ score: "5", tags: "", comment: "" });
const cancelReason = ref("");

const metrics = computed(() => ({
  total: rows.value.length,
  unassigned: rows.value.filter((row) => row.status === "SUBMITTED").length,
  processing: rows.value.filter((row) =>
    ["ASSIGNED", "IN_PROGRESS", "IN_PROGRESS_AFTER_QUOTE"].includes(row.status)
  ).length,
  breached: rows.value.filter((row) => row.sla_status.includes("BREACHED")).length,
}));

function requestError(value: unknown, fallback: string) {
  error.value = value instanceof Error ? value.message : fallback;
  errorStatus.value = value instanceof ApiRequestError ? value.status : 0;
}

function clearMessages() {
  error.value = "";
  errorStatus.value = 0;
  success.value = "";
}

function commandKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function params() {
  if (tenantMode.value) return { page: 1, page_size: 100 };
  return {
    page: 1,
    page_size: 100,
    park_id: filters.value.park_id ? Number(filters.value.park_id) : undefined,
    party_id: filters.value.party_id ? Number(filters.value.party_id) : undefined,
    assignee_user_id: filters.value.assignee_user_id
      ? Number(filters.value.assignee_user_id)
      : undefined,
    category: filters.value.category || undefined,
    status: filters.value.status || undefined,
  };
}

async function load() {
  clearMessages();
  loading.value = true;
  try {
    const response = await http.get<Envelope<PageResult<WorkOrder>>>(basePath.value, {
      params: params(),
    });
    rows.value = response.data.data.items;
  } catch (value) {
    requestError(value, "工单队列加载失败");
  } finally {
    loading.value = false;
  }
}

async function openDetail(id: number) {
  clearMessages();
  detailLoading.value = true;
  try {
    const response = await http.get<Envelope<WorkOrder>>(`${basePath.value}/${id}`);
    detail.value = response.data.data;
    dispatchDraft.value.assignee_user_id = String(detail.value.assignee_user_id || "");
  } catch (value) {
    detail.value = null;
    requestError(value, "工单不可见或加载失败");
  } finally {
    detailLoading.value = false;
  }
}

async function refreshDetail() {
  if (detail.value) await openDetail(detail.value.id);
  await load();
}

async function createOrder() {
  clearMessages();
  saving.value = true;
  try {
    const payload: Record<string, unknown> = {
      park_id: Number(intake.value.park_id),
      title: intake.value.title,
      description: intake.value.description || undefined,
      category: intake.value.category,
      priority: intake.value.priority,
      unit_id: intake.value.unit_id ? Number(intake.value.unit_id) : undefined,
      contact_name: intake.value.contact_name || undefined,
      contact_phone: intake.value.contact_phone || undefined,
      quote_required: intake.value.quote_required,
    };
    if (!tenantMode.value) {
      payload.party_id = intake.value.party_id ? Number(intake.value.party_id) : undefined;
      payload.request_source = "PROPERTY_STAFF";
    }
    const response = await http.post<Envelope<WorkOrder>>(basePath.value, payload, {
      headers: { "Idempotency-Key": commandKey("pc-intake") },
    });
    intake.value.title = "";
    intake.value.description = "";
    showIntake.value = false;
    await load();
    await openDetail(response.data.data.id);
    success.value = "服务请求已受理";
  } catch (value) {
    requestError(value, "服务请求提交失败，内容已保留");
  } finally {
    saving.value = false;
  }
}

async function mutate(call: () => Promise<unknown>, message: string) {
  clearMessages();
  saving.value = true;
  try {
    await call();
    await refreshDetail();
    success.value = message;
  } catch (value) {
    requestError(value, `${message}失败，已保留输入内容`);
  } finally {
    saving.value = false;
  }
}

function dispatchOrder() {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(`/work-orders/${detail.value?.id}/dispatch`, {
        expected_version: detail.value?.lock_version,
        assignee_user_id: Number(dispatchDraft.value.assignee_user_id),
        reason: dispatchDraft.value.reason,
      }),
    "派单已保存"
  );
}

function startOrder() {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(`/work-orders/${detail.value?.id}/start`, {
        expected_version: detail.value?.lock_version,
      }),
    "工单已接单"
  );
}

function createQuote() {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(`/work-orders/${detail.value?.id}/quotes`, {
        expected_version: detail.value?.lock_version,
        currency: "CNY",
        remark: quoteDraft.value.remark || undefined,
        lines: [
          {
            line_type: quoteDraft.value.line_type,
            description: quoteDraft.value.description,
            quantity: quoteDraft.value.quantity,
            unit: quoteDraft.value.unit,
            unit_price: quoteDraft.value.unit_price,
          },
        ],
      }),
    "报价草稿已创建"
  );
}

function submitQuote(quoteId: number) {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(`/work-orders/${detail.value?.id}/quotes/${quoteId}/submit`, {
        expected_version: detail.value?.lock_version,
      }),
    "报价已提交租户确认"
  );
}

function decideQuote(quoteId: number) {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(
        `/tenant-service/requests/${detail.value?.id}/quotes/${quoteId}/decision`,
        {
          expected_version: detail.value?.lock_version,
          decision: quoteDecision.value.decision,
          remark: quoteDecision.value.remark || undefined,
        },
        { headers: { "Idempotency-Key": commandKey("pc-quote-decision") } }
      ),
    "报价决定已提交"
  );
}

function addCost() {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(
        `/work-orders/${detail.value?.id}/cost-entries`,
        { expected_version: detail.value?.lock_version, ...costDraft.value },
        { headers: { "Idempotency-Key": commandKey("pc-cost") } }
      ),
    "实际成本已登记"
  );
}

function reverseCost(costId: number) {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(
        `/work-orders/${detail.value?.id}/cost-entries/${costId}/reverse`,
        {
          expected_version: detail.value?.lock_version,
          reason: costReverseReason.value,
        },
        { headers: { "Idempotency-Key": commandKey("pc-cost-reverse") } }
      ),
    "成本冲正已登记"
  );
}

function submitCompletion() {
  if (!detail.value) return;
  const evidence = completionDraft.value.evidence_ref
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return mutate(
    () =>
      http.post(`/work-orders/${detail.value?.id}/complete`, {
        expected_version: detail.value?.lock_version,
        resolution_summary: completionDraft.value.resolution_summary,
        evidence_refs: evidence,
        no_evidence_reason: completionDraft.value.no_evidence_reason || undefined,
      }),
    "完工结果已提交验收"
  );
}

function decideAcceptance() {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(
        `/tenant-service/requests/${detail.value?.id}/acceptance`,
        {
          expected_version: detail.value?.lock_version,
          decision: acceptanceDraft.value.decision,
          comment: acceptanceDraft.value.comment || undefined,
        },
        { headers: { "Idempotency-Key": commandKey("pc-acceptance") } }
      ),
    "验收决定已提交"
  );
}

function rateOrder() {
  if (!detail.value) return;
  const tags = ratingDraft.value.tags
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return mutate(
    () =>
      http.post(
        `/tenant-service/requests/${detail.value?.id}/rating`,
        { score: Number(ratingDraft.value.score), tags, comment: ratingDraft.value.comment || undefined },
        { headers: { "Idempotency-Key": commandKey("pc-rating") } }
      ),
    "评价已提交"
  );
}

function cancelOrder() {
  if (!detail.value) return;
  return mutate(
    () =>
      http.post(`/work-orders/${detail.value?.id}/cancel`, {
        expected_version: detail.value?.lock_version,
        reason: cancelReason.value,
      }),
    "工单已取消"
  );
}

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function latestSubmittedQuote(order: WorkOrder) {
  return order.quotes?.find((quote) => quote.status === "SUBMITTED");
}

onMounted(load);
</script>

<template>
  <main class="service-page" :class="{ 'tenant-mode': tenantMode }">
    <header class="hero card">
      <div>
        <p class="eyebrow">TENANT SERVICE · LIVE OPERATIONS</p>
        <h1 data-testid="work-orders-title">
          {{ tenantMode ? "企业服务中心" : "租户服务与工单中心" }}
        </h1>
        <p>
          {{ tenantMode ? "提交服务请求、确认报价并完成验收评价" : "统一受理、SLA 派单、报价、履约与租户验收" }}
        </p>
      </div>
      <div class="hero-actions">
        <button class="btn btn-ghost" type="button" :disabled="loading" @click="load">
          {{ loading ? "刷新中…" : "刷新队列" }}
        </button>
        <button
          v-if="canIntake"
          class="btn"
          type="button"
          data-testid="wo-open-intake"
          @click="showIntake = !showIntake"
        >
          {{ showIntake ? "收起受理" : "新建服务请求" }}
        </button>
      </div>
    </header>

    <section class="metric-grid" aria-label="工单指标">
      <article class="metric-card card"><span>当前队列</span><strong>{{ metrics.total }}</strong></article>
      <article class="metric-card card"><span>待派单</span><strong>{{ metrics.unassigned }}</strong></article>
      <article class="metric-card card"><span>处理中</span><strong>{{ metrics.processing }}</strong></article>
      <article class="metric-card risk card"><span>SLA 超时</span><strong>{{ metrics.breached }}</strong></article>
    </section>

    <form
      v-if="showIntake"
      class="intake card"
      data-testid="wo-create-form"
      @submit.prevent="createOrder"
    >
      <header><div><b>服务受理</b><span>提交失败时表单内容会保留</span></div></header>
      <label>园区 ID<input v-model="intake.park_id" class="input" inputmode="numeric" required /></label>
      <label v-if="!tenantMode">企业主体 ID<input v-model="intake.party_id" class="input" inputmode="numeric" /></label>
      <label>出租单元 ID<input v-model="intake.unit_id" class="input" inputmode="numeric" /></label>
      <label>联系人<input v-model="intake.contact_name" class="input" maxlength="64" /></label>
      <label>联系电话<input v-model="intake.contact_phone" class="input" maxlength="32" /></label>
      <label>分类<input v-model="intake.category" class="input" maxlength="64" required /></label>
      <label>优先级<select v-model="intake.priority" class="input"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>URGENT</option></select></label>
      <label class="wide">标题<input v-model="intake.title" class="input" maxlength="255" required /></label>
      <label class="wide">问题描述<textarea v-model="intake.description" class="input textarea" maxlength="2000" /></label>
      <label class="check wide"><input v-model="intake.quote_required" type="checkbox" /> 此工单执行前需要租户确认报价</label>
      <button class="btn submit" type="submit" :disabled="saving" data-testid="wo-create-btn">
        {{ saving ? "提交中…" : "确认受理" }}
      </button>
    </form>

    <section v-if="!tenantMode" class="filters card" aria-label="工单筛选">
      <input v-model="filters.park_id" class="input" inputmode="numeric" placeholder="园区 ID" />
      <input v-model="filters.party_id" class="input" inputmode="numeric" placeholder="企业 ID" />
      <input v-model="filters.assignee_user_id" class="input" inputmode="numeric" placeholder="处理人 ID" />
      <input v-model="filters.category" class="input" placeholder="分类" />
      <select v-model="filters.status" class="input">
        <option value="">全部状态</option><option>SUBMITTED</option><option>ASSIGNED</option>
        <option>IN_PROGRESS</option><option>WAITING_QUOTE_APPROVAL</option>
        <option>IN_PROGRESS_AFTER_QUOTE</option><option>WAITING_ACCEPTANCE</option>
        <option>COMPLETED</option><option>CANCELLED</option>
      </select>
      <button class="btn" type="button" @click="load">应用筛选</button>
    </section>

    <p v-if="error" class="notice error" data-testid="wo-error" role="alert">
      {{ errorStatus === 409 ? "数据已被他人更新：" : errorStatus === 0 ? "网络暂不可用：" : "" }}{{ error }}
      <button v-if="errorStatus === 409 || errorStatus === 0" type="button" @click="refreshDetail">重新加载后重试</button>
    </p>
    <p v-if="success" class="notice ok" data-testid="wo-success" role="status">{{ success }}</p>

    <section class="queue card">
      <div class="queue-head"><div><b>实时工单队列</b><span>{{ loading ? "正在读取服务…" : `共 ${rows.length} 条` }}</span></div></div>
      <div v-if="loading" class="state" data-testid="wo-loading">正在加载真实工单数据…</div>
      <div v-else-if="!rows.length" class="state" data-testid="wo-empty">暂无符合条件的工单</div>
      <div v-else class="table-wrap">
        <table class="table" data-testid="wo-table">
          <thead><tr><th>工单</th><th>企业 / 园区</th><th>优先级</th><th>状态</th><th>SLA</th><th>处理人</th></tr></thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.id"
              :data-testid="`wo-row-${row.id}`"
              tabindex="0"
              @click="openDetail(row.id)"
              @keydown.enter="openDetail(row.id)"
            >
              <td data-label="工单"><b>{{ row.order_no }}</b><span>{{ row.title }}</span></td>
              <td data-label="企业 / 园区"><b>{{ row.party_id ? `企业 #${row.party_id}` : "内部请求" }}</b><span>园区 #{{ row.park_id }}</span></td>
              <td data-label="优先级"><span class="priority" :class="row.priority.toLowerCase()">{{ row.priority }}</span></td>
              <td data-label="状态"><span class="badge" data-testid="wo-status-cell">{{ row.status }}</span></td>
              <td data-label="SLA"><span class="sla" :class="{ breached: row.sla_status.includes('BREACHED') }">{{ row.sla_status }}</span><small>{{ formatTime(row.resolution_due_at) }}</small></td>
              <td data-label="处理人">{{ row.assignee_user_id ? `#${row.assignee_user_id}` : "待派单" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="detail || detailLoading" class="drawer-mask" data-testid="wo-drawer" @click.self="detail = null">
      <aside class="drawer" aria-label="工单详情">
        <div v-if="detailLoading" class="state">详情加载中…</div>
        <template v-else-if="detail">
          <header class="drawer-head">
            <div><span>{{ detail.order_no }}</span><h2>{{ detail.title }}</h2></div>
            <button type="button" aria-label="关闭详情" @click="detail = null">×</button>
          </header>
          <div class="drawer-body">
            <section class="status-band">
              <div><span>当前状态</span><strong>{{ detail.status }}</strong></div>
              <div><span>SLA</span><strong :class="{ danger: detail.sla_status.includes('BREACHED') }">{{ detail.sla_status }}</strong></div>
              <div><span>版本</span><strong>v{{ detail.lock_version }}</strong></div>
            </section>
            <dl class="facts">
              <div><dt>园区 / 企业</dt><dd>#{{ detail.park_id }} / {{ detail.party_id ? `#${detail.party_id}` : "—" }}</dd></div>
              <div><dt>联系信息</dt><dd>{{ detail.contact_name || "—" }} {{ detail.contact_phone_masked || "" }}</dd></div>
              <div><dt>响应时限</dt><dd>{{ formatTime(detail.response_due_at) }}</dd></div>
              <div><dt>解决时限</dt><dd>{{ formatTime(detail.resolution_due_at) }}</dd></div>
            </dl>
            <p class="description">{{ detail.description || "未填写问题描述" }}</p>

            <section v-if="!tenantMode" class="action-section">
              <h3>派单与履约</h3>
              <form v-if="['SUBMITTED', 'ASSIGNED'].includes(detail.status)" class="compact" @submit.prevent="dispatchOrder">
                <input v-model="dispatchDraft.assignee_user_id" class="input" inputmode="numeric" placeholder="处理人用户 ID" required />
                <input v-model="dispatchDraft.reason" class="input" placeholder="派单 / 改派原因" maxlength="1000" required />
                <button class="btn" :disabled="saving">{{ detail.status === "ASSIGNED" ? "确认改派" : "确认派单" }}</button>
              </form>
              <button v-if="detail.status === 'ASSIGNED'" class="btn" type="button" :disabled="saving" data-testid="wo-start-btn" @click="startOrder">接单并开始处理</button>

              <form v-if="['IN_PROGRESS', 'WAITING_QUOTE_APPROVAL'].includes(detail.status)" class="form-card" @submit.prevent="createQuote">
                <b>新建报价版本</b>
                <select v-model="quoteDraft.line_type" class="input"><option>LABOR</option><option>MATERIAL</option><option>OUTSOURCE</option><option>OTHER</option></select>
                <input v-model="quoteDraft.description" class="input" placeholder="报价项目" required />
                <input v-model="quoteDraft.quantity" class="input" inputmode="decimal" placeholder="数量" required />
                <input v-model="quoteDraft.unit" class="input" placeholder="单位" required />
                <input v-model="quoteDraft.unit_price" class="input" inputmode="decimal" placeholder="单价" required />
                <input v-model="quoteDraft.remark" class="input" placeholder="报价说明" />
                <button class="btn" :disabled="saving">保存报价草稿</button>
              </form>
              <form v-if="['IN_PROGRESS', 'IN_PROGRESS_AFTER_QUOTE'].includes(detail.status)" class="form-card" @submit.prevent="addCost">
                <b>登记实际成本</b>
                <select v-model="costDraft.entry_type" class="input"><option>LABOR</option><option>MATERIAL</option><option>OUTSOURCE</option><option>OTHER</option></select>
                <input v-model="costDraft.description" class="input" placeholder="成本说明" required />
                <input v-model="costDraft.quantity" class="input" inputmode="decimal" placeholder="数量" required />
                <input v-model="costDraft.unit" class="input" placeholder="单位" required />
                <input v-model="costDraft.unit_price" class="input" inputmode="decimal" placeholder="单价" required />
                <button class="btn" :disabled="saving">登记成本</button>
              </form>
              <form v-if="['IN_PROGRESS', 'IN_PROGRESS_AFTER_QUOTE'].includes(detail.status)" class="form-card" @submit.prevent="submitCompletion">
                <b>提交完工验收</b>
                <textarea v-model="completionDraft.resolution_summary" class="input textarea" placeholder="处理结果" required />
                <textarea v-model="completionDraft.evidence_ref" class="input textarea" placeholder="证据引用，每行一个" />
                <input v-model="completionDraft.no_evidence_reason" class="input" placeholder="无证据时填写原因" />
                <button class="btn" :disabled="saving" data-testid="wo-complete-btn">提交租户验收</button>
              </form>
              <form v-if="!['COMPLETED', 'CANCELLED'].includes(detail.status)" class="danger-form" @submit.prevent="cancelOrder">
                <input v-model="cancelReason" class="input" placeholder="取消原因" required />
                <button class="btn danger-btn" :disabled="saving">取消工单</button>
              </form>
            </section>

            <section v-else class="action-section">
              <h3>企业确认</h3>
              <form v-if="detail.status === 'WAITING_QUOTE_APPROVAL' && latestSubmittedQuote(detail)" class="form-card" @submit.prevent="decideQuote(latestSubmittedQuote(detail)!.id)">
                <b>报价 v{{ latestSubmittedQuote(detail)?.version_no }} · ¥{{ latestSubmittedQuote(detail)?.total_amount }}</b>
                <select v-model="quoteDecision.decision" class="input"><option value="ACCEPT">同意报价</option><option value="REJECT">拒绝并退回</option></select>
                <textarea v-model="quoteDecision.remark" class="input textarea" placeholder="拒绝时必须填写原因" />
                <button class="btn" :disabled="saving">提交报价决定</button>
              </form>
              <form v-if="detail.status === 'WAITING_ACCEPTANCE'" class="form-card" @submit.prevent="decideAcceptance">
                <b>验收处理结果</b>
                <select v-model="acceptanceDraft.decision" class="input"><option value="ACCEPTED">验收通过</option><option value="REWORK">要求返工</option></select>
                <textarea v-model="acceptanceDraft.comment" class="input textarea" placeholder="返工时必须填写原因" />
                <button class="btn" :disabled="saving">提交验收决定</button>
              </form>
              <form v-if="detail.status === 'COMPLETED' && !detail.rating" class="form-card" @submit.prevent="rateOrder">
                <b>服务评价</b>
                <select v-model="ratingDraft.score" class="input"><option value="5">5 分</option><option value="4">4 分</option><option value="3">3 分</option><option value="2">2 分</option><option value="1">1 分</option></select>
                <input v-model="ratingDraft.tags" class="input" placeholder="标签，以逗号分隔" />
                <textarea v-model="ratingDraft.comment" class="input textarea" placeholder="评价内容" />
                <button class="btn" :disabled="saving">提交不可修改的评价</button>
              </form>
              <p v-if="detail.rating" class="rating">已评价 {{ detail.rating.score }} 分 · {{ detail.rating.tags.join(" / ") }}</p>
            </section>

            <section v-if="detail.quotes?.length" class="detail-section">
              <h3>报价版本</h3>
              <article v-for="quote in detail.quotes" :key="quote.id" class="record">
                <header><b>v{{ quote.version_no }} · ¥{{ quote.total_amount }}</b><span>{{ quote.status }}</span></header>
                <div v-for="line in quote.lines" :key="line.id">{{ line.description }} · {{ line.quantity }} {{ line.unit }} × ¥{{ line.unit_price }}</div>
                <button v-if="!tenantMode && quote.status === 'DRAFT'" class="btn btn-small" type="button" @click="submitQuote(quote.id)">提交租户确认</button>
              </article>
            </section>
            <section v-if="!tenantMode && detail.cost_entries?.length" class="detail-section">
              <h3>报价 / 实际 / 差异</h3>
              <div class="money-strip"><b>¥{{ detail.accepted_quote_total }}</b><b>¥{{ detail.actual_total }}</b><b>¥{{ detail.cost_variance }}</b></div>
              <input v-model="costReverseReason" class="input" maxlength="1000" placeholder="冲正原因（冲正前必填）" />
              <article v-for="cost in detail.cost_entries" :key="cost.id" class="record">
                <span>{{ cost.entry_type }} · {{ cost.description }}</span><b>¥{{ cost.amount }}</b>
                <button v-if="!cost.reverses_entry_id && Number(cost.amount) > 0" class="btn btn-small" type="button" :disabled="saving || !costReverseReason.trim()" @click="reverseCost(cost.id)">冲正此条</button>
              </article>
            </section>
            <section v-if="detail.acceptances?.length" class="detail-section">
              <h3>验收记录</h3>
              <article v-for="item in detail.acceptances" :key="item.id" class="record"><b>第 {{ item.attempt_no }} 次 · {{ item.decision }}</b><span>{{ item.comment || "无备注" }}</span></article>
            </section>
            <section class="detail-section">
              <h3>不可变时间线</h3>
              <ol class="timeline">
                <li v-for="event in detail.timeline" :key="event.id"><i></i><div><b>{{ event.event_type }}</b><span>{{ event.actor_type }} · {{ formatTime(event.occurred_at) }}</span><small v-if="event.reason">{{ event.reason }}</small></div></li>
              </ol>
            </section>
          </div>
        </template>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.service-page { display: grid; min-width: 0; gap: 1rem; color: #173247; }.hero { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 1.25rem; background: linear-gradient(135deg, #fff 55%, #edf8fa); }.hero h1 { margin: .15rem 0; font-size: clamp(1.5rem, 3vw, 2.15rem); }.hero p { margin: .2rem 0; color: #607887; }.eyebrow { color: #158493 !important; font-size: .7rem; font-weight: 900; letter-spacing: .14em; }.hero-actions { display: flex; gap: .55rem; flex-wrap: wrap; }.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .75rem; }.metric-card { padding: .85rem 1rem; border-top: 3px solid #1ca1ad; }.metric-card span { color: #6a808c; font-size: .72rem; }.metric-card strong { display: block; margin-top: .1rem; font-size: 1.6rem; }.metric-card.risk { border-color: #e05b3f; }.metric-card.risk strong { color: #c2412f; }.intake { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .7rem; padding: 1rem; }.intake header, .intake .wide { grid-column: 1 / -1; }.intake header div, .queue-head div { display: grid; }.intake header span, .queue-head span { color: #718894; font-size: .7rem; }.intake label, .form-card { display: grid; gap: .3rem; color: #526b78; font-size: .75rem; font-weight: 700; }.textarea { min-height: 78px; resize: vertical; }.check { display: flex !important; align-items: center; }.submit { grid-column: 3; }.filters { display: grid; grid-template-columns: repeat(6, minmax(100px, 1fr)); gap: .55rem; padding: .75rem; }.notice { display: flex; align-items: center; justify-content: space-between; gap: .5rem; margin: 0; padding: .75rem 1rem; border-radius: 10px; background: #edf8f4; }.notice.error { background: #fff0ed; }.notice button { border: 0; color: #087f8d; background: transparent; cursor: pointer; text-decoration: underline; }.ok { color: #08755d; }.queue { min-width: 0; overflow: hidden; }.queue-head { padding: .9rem 1rem; border-bottom: 1px solid #dce7eb; }.table-wrap { max-width: 100%; overflow-x: auto; }.table { min-width: 880px; }.table tbody tr { cursor: pointer; }.table tbody tr:hover, .table tbody tr:focus { outline: 0; background: #f0f8f8; }.table td b, .table td span, .table td small { display: block; }.table td span, .table td small { color: #708692; font-size: .72rem; }.priority { display: inline-block !important; width: fit-content; padding: .18rem .45rem; border-radius: 6px; background: #edf2f5; font-weight: 800; }.priority.high, .priority.urgent { color: #b64029; background: #fff0eb; }.sla.breached, .danger { color: #c2412f !important; font-weight: 800; }.state { padding: 2.5rem 1rem; color: #708692; text-align: center; }.drawer-mask { position: fixed; inset: 0; z-index: 60; display: flex; justify-content: flex-end; max-width: 100vw; overflow-x: hidden; background: rgba(5, 25, 40, .46); backdrop-filter: blur(2px); }.drawer { width: min(760px, 94vw); height: 100%; overflow-y: auto; background: #f5f8fa; box-shadow: -20px 0 60px rgba(5, 32, 48, .2); }.drawer-head { position: sticky; top: 0; z-index: 2; display: flex; justify-content: space-between; gap: 1rem; padding: 1rem 1.2rem; border-bottom: 1px solid #d9e5ea; background: rgba(255,255,255,.97); }.drawer-head span { color: #14838f; font-size: .7rem; font-weight: 800; }.drawer-head h2 { margin: .2rem 0; overflow-wrap: anywhere; }.drawer-head button { border: 0; color: #627986; background: transparent; font-size: 1.8rem; cursor: pointer; }.drawer-body { display: grid; min-width: 0; gap: .8rem; padding: 1rem; }.status-band, .money-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; }.status-band > div, .money-strip > b { min-width: 0; padding: .7rem; border-radius: 10px; background: #0b3348; color: #e6f2f5; }.status-band span { display: block; color: #a8c7d2; font-size: .65rem; }.facts { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: 0; }.facts div { min-width: 0; padding: .65rem; border-radius: 9px; background: #fff; }.facts dt { color: #718894; font-size: .65rem; }.facts dd { margin: .15rem 0 0; overflow-wrap: anywhere; font-size: .78rem; font-weight: 800; }.description { margin: 0; padding: .8rem; border-left: 3px solid #1ca1ad; background: #fff; overflow-wrap: anywhere; }.action-section, .detail-section { padding: .9rem; border-radius: 12px; background: #fff; }.action-section h3, .detail-section h3 { margin: 0 0 .65rem; }.compact { display: grid; grid-template-columns: 1fr 2fr auto; gap: .5rem; }.form-card { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: .7rem; padding: .75rem; border: 1px solid #dce7eb; border-radius: 10px; background: #f7fafb; }.form-card > b, .form-card .textarea { grid-column: 1 / -1; }.form-card .btn { grid-column: 2; }.danger-form { display: grid; grid-template-columns: 1fr auto; gap: .5rem; margin-top: .75rem; }.danger-btn { background: #bd432f; }.record { display: grid; gap: .25rem; margin-bottom: .5rem; padding: .65rem; border-radius: 9px; background: #f2f7f8; font-size: .75rem; }.record header { display: flex; justify-content: space-between; gap: .5rem; }.record > b:last-child { color: #0d7781; }.btn-small { width: fit-content; margin-top: .35rem; padding: .4rem .65rem; font-size: .72rem; }.rating { padding: .7rem; border-radius: 8px; background: #ecf8f4; color: #08755d; font-weight: 800; }.timeline { display: grid; gap: .55rem; padding: 0; list-style: none; }.timeline li { display: grid; grid-template-columns: 10px minmax(0,1fr); gap: .5rem; }.timeline i { width: 8px; height: 8px; margin-top: .35rem; border-radius: 50%; background: #1ca1ad; }.timeline div { display: grid; min-width: 0; }.timeline span, .timeline small { color: #718894; font-size: .68rem; overflow-wrap: anywhere; }
@media (max-width: 820px) { .hero { align-items: stretch; flex-direction: column; }.metric-grid { grid-template-columns: repeat(2, 1fr); }.intake { grid-template-columns: repeat(2, 1fr); }.submit { grid-column: 2; }.filters { grid-template-columns: repeat(2, 1fr); }.drawer { width: 100%; }.compact { grid-template-columns: 1fr 1fr; }.compact .btn { grid-column: 1 / -1; } }
@media (max-width: 520px) { .service-page { gap: .7rem; }.hero, .intake { padding: .8rem; }.hero-actions { display: grid; grid-template-columns: 1fr 1fr; }.intake, .filters, .form-card, .facts { grid-template-columns: 1fr; }.intake .wide, .submit, .form-card > b, .form-card .textarea, .form-card .btn { grid-column: auto; }.metric-grid { gap: .45rem; }.metric-card { padding: .65rem; }.table { display: block; min-width: 0; }.table thead { display: none; }.table tbody, .table tr, .table td { display: block; width: 100%; }.table tr { margin: .65rem; padding: .7rem; border: 1px solid #dce7eb; border-radius: 12px; }.table td { display: grid; grid-template-columns: 105px minmax(0,1fr); padding: .3rem 0; border: 0; overflow-wrap: anywhere; }.table td::before { content: attr(data-label); color: #718894; font-size: .68rem; }.drawer-body { padding: .65rem; }.status-band { grid-template-columns: 1fr 1fr; }.status-band > div:last-child { grid-column: 1 / -1; }.compact, .danger-form { grid-template-columns: 1fr; } }
</style>
