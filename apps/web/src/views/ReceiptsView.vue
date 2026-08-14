<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

type Row = Record<string, unknown>;
type Capability = { channel: string; status: string; mode: string };

const items = ref<Row[]>([]);
const capabilities = ref<Capability[]>([]);
const automaticPosting = ref(false);
const selected = ref<Row | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const success = ref("");
const offline = ref(false);
const status = ref("");
const form = ref({
  park_id: "",
  party_id: "",
  amount: "",
  received_at: new Date().toISOString().slice(0, 16),
  channel: "BANK_IMPORT",
  source_provider: "MANUAL",
  source_ref: "",
  payer_name: "",
  payer_account: "",
  bank_reference: "",
  purpose: "",
});
const review = ref({ party_id: "", reason: "", exception_code: "UNIDENTIFIED_PAYMENT" });

const availableChannels = computed(() =>
  capabilities.value.filter((item) => item.status === "AVAILABLE")
);

function messageOf(value: unknown, fallback: string) {
  const problem = value as ApiRequestError;
  offline.value = problem?.code === "NETWORK_ERROR" || problem?.status === 0;
  return value instanceof Error ? value.message : fallback;
}

async function load() {
  loading.value = true;
  error.value = "";
  offline.value = false;
  try {
    const [capabilityResponse, receiptResponse] = await Promise.all([
      http.get<Envelope<{ channels: Capability[]; automatic_financial_posting: boolean }>>(
        "/receipts/capabilities"
      ),
      http.get<Envelope<PageResult<Row>>>("/receipts", {
        params: { page: 1, page_size: 100, status: status.value || undefined },
      }),
    ]);
    capabilities.value = capabilityResponse.data.data.channels;
    automaticPosting.value = capabilityResponse.data.data.automatic_financial_posting;
    items.value = receiptResponse.data.data.items;
  } catch (value) {
    error.value = messageOf(value, "到账中心加载失败");
  } finally {
    loading.value = false;
  }
}

async function ingest() {
  if (saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    await http.post("/receipts", {
      park_id: Number(form.value.park_id),
      party_id: form.value.party_id ? Number(form.value.party_id) : null,
      amount: form.value.amount,
      received_at: form.value.received_at,
      channel: form.value.channel,
      source_provider: form.value.source_provider,
      source_ref: form.value.source_ref,
      payer_name: form.value.payer_name || null,
      payer_account: form.value.payer_account || null,
      bank_reference: form.value.bank_reference || null,
      purpose: form.value.purpose || null,
    });
    success.value = "到账流水已持久化；尚未形成收款或核销。";
    form.value.source_ref = "";
    await load();
  } catch (value) {
    error.value = messageOf(value, "导入失败");
  } finally {
    saving.value = false;
  }
}

async function openDetail(id: number) {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<Row>>(`/receipts/${id}`);
    selected.value = data.data;
    review.value.party_id = String(data.data.party_id || "");
    review.value.reason = "";
  } catch (value) {
    error.value = messageOf(value, "详情加载失败");
  }
}

async function command(path: string, body: Row, done: string) {
  if (!selected.value || saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    await http.post(path, body);
    success.value = done;
    const id = Number(selected.value.id);
    await load();
    await openDetail(id);
  } catch (value) {
    error.value = messageOf(value, "操作失败");
    if ((value as ApiRequestError)?.status === 409) await openDetail(Number(selected.value.id));
  } finally {
    saving.value = false;
  }
}

async function match() {
  if (!selected.value) return;
  await command(
    `/receipts/${selected.value.id}/match`,
    { expected_version: Number(selected.value.lock_version) },
    "匹配建议已重算；没有自动记账。"
  );
}

async function confirmReceipt() {
  if (!selected.value || !window.confirm("确认将该到账登记为收款，并按当前建议核销？")) return;
  await command(
    `/receipts/${selected.value.id}/confirm`,
    {
      expected_version: Number(selected.value.lock_version),
      party_id: review.value.party_id ? Number(review.value.party_id) : null,
      allocations: null,
      remark: "财务到账中心人工复核",
    },
    "到账已由财务确认，收款与核销结果已落库。"
  );
}

async function markException() {
  if (!selected.value || !review.value.reason.trim()) return;
  await command(
    `/receipts/${selected.value.id}/exception`,
    {
      expected_version: Number(selected.value.lock_version),
      code: review.value.exception_code,
      remark: review.value.reason,
    },
    "异常原因已记录。"
  );
}

async function raiseDispute() {
  if (!selected.value || !review.value.reason.trim()) return;
  await command(
    `/receipts/${selected.value.id}/dispute`,
    { expected_version: Number(selected.value.lock_version), reason: review.value.reason },
    "争议已提交经理复核。"
  );
}

async function resolveDispute(decision: "RETURN_TO_FINANCE" | "REJECT_RECEIPT") {
  if (!selected.value || !review.value.reason.trim()) return;
  await command(
    `/receipts/${selected.value.id}/dispute/resolve`,
    {
      expected_version: Number(selected.value.lock_version),
      decision,
      remark: review.value.reason,
    },
    decision === "RETURN_TO_FINANCE" ? "已退回财务重新匹配。" : "到账已驳回。"
  );
}

onMounted(load);
</script>

<template>
  <section class="workspace" data-testid="receipts-workspace">
    <header class="hero card">
      <div>
        <p class="eyebrow">FINANCE CONTROL</p>
        <h2 data-testid="receipts-title">到账匹配中心</h2>
        <p class="muted">到账流水、匹配建议与财务确认分层处理；建议永不自动记账。</p>
      </div>
      <button class="btn btn-ghost" type="button" data-testid="receipt-retry" @click="load">
        刷新
      </button>
    </header>

    <div class="grid-metrics">
      <article class="card metric">
        <span class="muted">待处理</span><strong>{{ items.filter((x) => x.status !== 'CONFIRMED' && x.status !== 'REJECTED').length }}</strong>
      </article>
      <article class="card metric">
        <span class="muted">已确认</span><strong>{{ items.filter((x) => x.status === 'CONFIRMED').length }}</strong>
      </article>
      <article class="card metric risk">
        <span class="muted">争议/异常</span><strong>{{ items.filter((x) => x.status === 'DISPUTED' || x.status === 'EXCEPTION').length }}</strong>
      </article>
      <article class="card metric">
        <span class="muted">自动财务记账</span><strong class="truth">{{ automaticPosting ? '已启用' : '未启用' }}</strong>
      </article>
    </div>

    <section class="card panel provider-panel">
      <h3>渠道真实状态</h3>
      <div class="provider-grid" data-testid="receipt-provider-status">
        <span v-for="item in capabilities" :key="item.channel" class="provider">
          {{ item.channel }}
          <b :class="item.status === 'AVAILABLE' ? 'available' : 'not-connected'">{{ item.status }}</b>
        </span>
      </div>
    </section>

    <section class="card panel">
      <h3>录入到账</h3>
      <form class="form-grid" data-testid="receipt-create-form" @submit.prevent="ingest">
        <input v-model="form.park_id" class="input" data-testid="receipt-park-id" placeholder="园区 ID" required />
        <input v-model="form.party_id" class="input" data-testid="receipt-party-id" placeholder="主体 ID（可空）" />
        <input v-model="form.amount" class="input" data-testid="receipt-amount" inputmode="decimal" placeholder="到账金额" required />
        <input v-model="form.received_at" class="input" type="datetime-local" required />
        <select v-model="form.channel" class="input" data-testid="receipt-channel">
          <option v-for="item in availableChannels" :key="item.channel" :value="item.channel">{{ item.channel }}</option>
        </select>
        <input v-model="form.source_provider" class="input" placeholder="来源提供方" required />
        <input v-model="form.source_ref" class="input" data-testid="receipt-source-ref" placeholder="来源流水号（幂等）" required />
        <input v-model="form.payer_name" class="input" placeholder="付款户名" />
        <input v-model="form.payer_account" class="input" placeholder="付款账号（仅存掩码）" />
        <input v-model="form.bank_reference" class="input" placeholder="银行附言 / 账单号" />
        <input v-model="form.purpose" class="input" placeholder="用途" />
        <button v-permission="'payment:import'" class="btn" data-testid="receipt-create-btn" type="submit" :disabled="saving">
          {{ saving ? '提交中…' : '保存到账流水' }}
        </button>
      </form>
    </section>

    <section class="card panel">
      <div class="toolbar">
        <h3>到账收件箱</h3>
        <select v-model="status" class="input compact" data-testid="receipt-status-filter" @change="load">
          <option value="">全部状态</option><option>PENDING</option><option>SUGGESTED</option>
          <option>EXCEPTION</option><option>DISPUTED</option><option>CONFIRMED</option><option>REJECTED</option>
        </select>
      </div>
      <p v-if="loading" class="muted" data-testid="receipt-loading">正在读取真实到账流水…</p>
      <div v-if="offline" class="state error" data-testid="receipt-offline">网络不可用，数据未被替换为本地假数据。请恢复连接后重试。</div>
      <p v-if="error" class="error" data-testid="receipt-error">{{ error }}</p>
      <p v-if="success" class="ok" data-testid="receipt-success">{{ success }}</p>
      <div class="table-wrap">
        <table v-if="!loading" class="table" data-testid="receipt-table">
          <thead><tr><th>到账号</th><th>时间</th><th>付款方</th><th>金额</th><th>渠道</th><th>状态</th><th></th></tr></thead>
          <tbody>
            <tr v-for="row in items" :key="String(row.id)" :data-testid="`receipt-row-${row.id}`">
              <td>{{ row.transaction_no }}</td><td>{{ row.received_at }}</td>
              <td>{{ row.payer_name || '待识别' }}<small>{{ row.payer_account_masked }}</small></td>
              <td class="money">¥ {{ row.amount }}</td><td>{{ row.channel }}</td>
              <td><span class="badge" :class="`status-${String(row.status).toLowerCase()}`">{{ row.status }}</span></td>
              <td><button class="btn btn-ghost" type="button" data-testid="receipt-review-btn" @click="openDetail(Number(row.id))">复核</button></td>
            </tr>
            <tr v-if="!items.length"><td colspan="7" class="empty">没有符合条件的到账流水</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="selected" class="drawer-backdrop" data-testid="receipt-review-drawer" @click.self="selected = null">
      <aside class="drawer card">
        <header class="drawer-head"><div><p class="eyebrow">MANUAL REVIEW</p><h3>{{ selected.transaction_no }}</h3></div><button class="close" type="button" aria-label="关闭" @click="selected = null">×</button></header>
        <div class="fact-grid">
          <span><small>到账金额</small><b>¥ {{ selected.amount }}</b></span>
          <span><small>当前状态</small><b>{{ selected.status }}</b></span>
          <span><small>来源</small><b>{{ selected.source_provider }} / {{ selected.source_ref }}</b></span>
          <span><small>版本</small><b>{{ selected.lock_version }}</b></span>
        </div>
        <label>确认主体 ID<input v-model="review.party_id" class="input" data-testid="receipt-review-party" /></label>
        <h4>可解释匹配建议</h4>
        <table class="table candidate-table"><thead><tr><th>账单</th><th>得分</th><th>建议金额</th><th>规则</th></tr></thead>
          <tbody><tr v-for="candidate in (selected.candidates as Row[] || [])" :key="String(candidate.id)"><td>{{ candidate.bill_id }}</td><td>{{ candidate.score }}</td><td>{{ candidate.proposed_amount }}</td><td>{{ (candidate.rule_codes as string[] || []).join(' · ') }}</td></tr><tr v-if="!(selected.candidates as Row[] || []).length"><td colspan="4" class="empty">尚无匹配建议</td></tr></tbody>
        </table>
        <div class="drawer-actions">
          <button v-if="['PENDING','SUGGESTED','EXCEPTION'].includes(String(selected.status))" v-permission="'payment:review'" class="btn btn-ghost" type="button" data-testid="receipt-match-btn" :disabled="saving" @click="match">重新匹配</button>
          <button v-if="['PENDING','SUGGESTED','EXCEPTION'].includes(String(selected.status))" v-permission="'payment:review'" class="btn" type="button" data-testid="receipt-confirm-btn" :disabled="saving" @click="confirmReceipt">人工确认入账</button>
        </div>
        <label>复核原因 / 处理意见<textarea v-model="review.reason" class="input textarea" data-testid="receipt-review-reason" maxlength="1000" /></label>
        <div v-if="['PENDING','SUGGESTED','EXCEPTION'].includes(String(selected.status))" class="danger-zone">
          <select v-model="review.exception_code" class="input"><option>UNIDENTIFIED_PAYMENT</option><option>AMOUNT_MISMATCH</option><option>PARTY_MISMATCH</option></select>
          <button v-permission="'payment:review'" class="btn btn-ghost" type="button" :disabled="!review.reason.trim()" @click="markException">标记异常</button>
          <button v-permission="'payment:review'" class="btn risk-btn" type="button" data-testid="receipt-dispute-btn" :disabled="!review.reason.trim()" @click="raiseDispute">发起争议</button>
        </div>
        <div v-if="selected.status === 'DISPUTED'" class="danger-zone">
          <p class="error">争议：{{ selected.dispute_reason }}</p>
          <button v-permission="'payment:dispute_review'" class="btn btn-ghost" type="button" :disabled="!review.reason.trim()" @click="resolveDispute('RETURN_TO_FINANCE')">退回财务</button>
          <button v-permission="'payment:dispute_review'" class="btn risk-btn" type="button" :disabled="!review.reason.trim()" @click="resolveDispute('REJECT_RECEIPT')">经理驳回</button>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.workspace { display: grid; grid-template-columns: minmax(0, 1fr); min-width: 0; gap: 1rem; }
.hero, .toolbar, .drawer-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.hero, .panel { min-width: 0; padding: 1.1rem; }
.hero > div { min-width: 0; }
h2, h3, h4, p { margin-top: 0; }
.eyebrow { margin-bottom: .25rem; color: #0e7490; font-size: .72rem; font-weight: 800; letter-spacing: .14em; }
.risk { border-top: 3px solid #ea580c; }
.truth { font-size: 1.05rem !important; color: #c2410c; }
.provider-grid { display: flex; flex-wrap: wrap; gap: .5rem; }
.provider { border: 1px solid var(--border); border-radius: 999px; padding: .35rem .65rem; font-size: .78rem; }
.provider b { margin-left: .35rem; }.available { color: #047857; }.not-connected { color: #c2410c; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: .65rem; }
.compact { width: min(220px, 100%); }.table-wrap { width: 100%; max-width: 100%; overflow-x: auto; }.money { font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }
small { display: block; color: var(--muted); }.empty, .state { padding: 1.4rem; text-align: center; color: var(--muted); }.ok { color: #047857; }
.status-disputed, .status-exception { background: #fff1e8; color: #c2410c; }.status-confirmed { background: #e7f5f0; color: #047857; }
.drawer-backdrop { position: fixed; inset: 0; z-index: 40; display: flex; justify-content: flex-end; background: rgba(3, 19, 35, .44); }
.drawer { width: min(680px, 100%); height: 100%; overflow-y: auto; padding: 1.25rem; border-radius: 18px 0 0 18px; }
.close { border: 0; background: transparent; font-size: 2rem; cursor: pointer; }.fact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin: 1rem 0; }
.fact-grid span { padding: .75rem; border-radius: 10px; background: #f4f7fa; }.fact-grid b { display: block; overflow-wrap: anywhere; }
label { display: grid; gap: .35rem; margin: .8rem 0; }.textarea { min-height: 80px; resize: vertical; }.drawer-actions, .danger-zone { display: flex; flex-wrap: wrap; gap: .55rem; margin-top: .8rem; }
.risk-btn { background: #c2410c; }.candidate-table { min-width: 540px; }
@media (max-width: 640px) { .hero { align-items: flex-start; }.fact-grid { grid-template-columns: 1fr; }.drawer { border-radius: 0; }.toolbar { align-items: flex-start; flex-direction: column; } }
</style>
