<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const saving = ref(false);
const loading = ref(true);
const runDate = ref(new Date().toISOString().slice(0, 10));
const runParkId = ref("");
const preview = ref<Record<string, unknown> | null>(null);
const selectedBill = ref<Record<string, unknown> | null>(null);
const adjustments = ref<Array<Record<string, unknown>>>([]);
const adjustmentForm = ref({
  adjustment_type: "WAIVER",
  amount: "",
  requested_due_date: "",
  reason: "",
});
const form = ref({
  park_id: "",
  party_id: "",
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  unit_price: "100",
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/bills", {
      params: { page: 1, page_size: 50 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function previewRun() {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<Record<string, unknown>>>("/billing/runs/preview", {
      params: { as_of: runDate.value, park_id: runParkId.value ? Number(runParkId.value) : undefined },
    });
    preview.value = data.data;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "出账预览失败";
  }
}

async function applyRun() {
  if (!preview.value || !window.confirm(`确认签发 ${preview.value.group_count || 0} 张计划账单？`)) return;
  try {
    await http.post(
      "/billing/runs",
      { as_of: runDate.value, park_id: runParkId.value ? Number(runParkId.value) : null },
      { headers: { "Idempotency-Key": `billing-${runDate.value}-${runParkId.value || "all"}-${Date.now()}` } }
    );
    success.value = "合同履约计划已生成正式账单。";
    preview.value = null;
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "自动出账失败";
  }
}

async function openAdjustments(row: Record<string, unknown>) {
  selectedBill.value = row;
  error.value = "";
  const { data } = await http.get<Envelope<Array<Record<string, unknown>>>>(
    "/receivable-adjustments",
    { params: { bill_id: Number(row.id) } }
  );
  adjustments.value = data.data;
}

async function requestAdjustment() {
  if (!selectedBill.value || saving.value) return;
  saving.value = true;
  try {
    const kind = adjustmentForm.value.adjustment_type;
    await http.post(
      "/receivable-adjustments",
      {
        bill_id: Number(selectedBill.value.id),
        adjustment_type: kind,
        amount: ["WAIVER", "BAD_DEBT"].includes(kind) ? adjustmentForm.value.amount : null,
        requested_due_date: kind === "EXTENSION" ? adjustmentForm.value.requested_due_date : null,
        reason: adjustmentForm.value.reason,
      },
      { headers: { "Idempotency-Key": `adjustment-${selectedBill.value.id}-${Date.now()}` } }
    );
    success.value = "调整申请已提交审批；账单尚未变更。";
    adjustmentForm.value.reason = "";
    await openAdjustments(selectedBill.value);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "调整申请失败";
  } finally {
    saving.value = false;
  }
}

async function applyAdjustment(row: Record<string, unknown>) {
  if (!window.confirm("确认应用已批准的应收调整？")) return;
  try {
    await http.post(`/receivable-adjustments/${row.id}/apply`, {
      expected_version: Number(row.lock_version),
    });
    success.value = "已批准调整已应用。";
    await load();
    if (selectedBill.value) {
      const current = items.value.find((item) => Number(item.id) === Number(selectedBill.value?.id));
      if (current) await openAdjustments(current);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "应用失败";
  }
}

async function create() {
  if (saving.value) return;
  saving.value = true;
  try {
    await http.post("/bills", {
      park_id: Number(form.value.park_id),
      party_id: Number(form.value.party_id),
      period_start: form.value.period_start,
      period_end: form.value.period_end,
      lines: [
        {
          fee_code: "RENT",
          quantity: "1",
          unit_price: form.value.unit_price,
        },
      ],
    });
    success.value = "账单草稿已创建";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  } finally {
    saving.value = false;
  }
}

async function issue(id: number) {
  if (!window.confirm("确认签发账单？")) return;
  await http.post(`/bills/${id}/issue`);
  success.value = "已签发";
  await load();
}

async function voidBill(id: number) {
  if (!window.confirm("确认作废账单？")) return;
  await http.post(`/bills/${id}/void`);
  success.value = "已作废";
  await load();
}

onMounted(load);
</script>

<template>
  <section class="workspace">
  <section class="card panel">
    <h2 data-testid="bills-title">账单与自动出账</h2>
    <p class="muted">正式账单保留合同履约计划来源；减免、延期、坏账及争议均须审批。</p>
    <div class="runbar" data-testid="billing-run-panel">
      <input v-model="runDate" class="input" type="date" aria-label="出账截止日" />
      <input v-model="runParkId" class="input" placeholder="园区 ID（可空）" />
      <button class="btn btn-ghost" type="button" data-testid="billing-preview-btn" @click="previewRun">预览计划</button>
      <button v-if="preview" v-permission="'bill:generate'" class="btn" type="button" data-testid="billing-apply-btn" @click="applyRun">确认出账</button>
    </div>
    <div v-if="preview" class="preview card" data-testid="billing-preview-result">
      <b>{{ preview.group_count }} 张账单 / {{ preview.schedule_count }} 条计划 / ¥ {{ preview.total_amount }}</b>
      <span v-if="(preview.conflicts as unknown[] || []).length" class="error">{{ (preview.conflicts as unknown[]).length }} 个历史版本冲突不会被覆盖</span>
    </div>
    <form class="create" data-testid="bill-create-form" @submit.prevent="create">
      <input v-model="form.park_id" class="input" data-testid="bill-park-id" placeholder="园区ID" required />
      <input v-model="form.party_id" class="input" data-testid="bill-party-id" placeholder="主体ID" required />
      <input v-model="form.period_start" class="input" type="date" required />
      <input v-model="form.period_end" class="input" type="date" required />
      <input v-model="form.unit_price" class="input" data-testid="bill-amount" placeholder="金额" required />
      <button v-permission="'bill:write'" class="btn" data-testid="bill-create-btn" type="submit" :disabled="saving">
        创建草稿
      </button>
    </form>
    <p v-if="error" class="error" data-testid="bill-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="bill-success">{{ success }}</p>
    <p v-if="loading" class="muted">加载真实账单…</p>
    <div class="table-wrap"><table v-if="!loading" class="table" data-testid="bill-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>账单号</th>
          <th>状态</th>
          <th>金额</th>
          <th>已付</th>
          <th>可收余额</th>
          <th>到期/争议</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)" :data-testid="`bill-row-${row.id}`">
          <td>{{ row.id }}</td>
          <td>{{ row.bill_no }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>{{ row.total_amount }}</td>
          <td>{{ row.paid_amount }}</td>
          <td>{{ row.open_amount }}</td>
          <td><small>{{ row.effective_due_date || '未设置' }}</small><span v-if="row.collection_hold" class="badge risk-badge">{{ row.dispute_status }}</span></td>
          <td class="ops">
            <button
              v-if="row.status === 'DRAFT'"
              v-permission="'bill:issue'"
              class="btn"
              type="button"
              data-testid="bill-issue-btn"
              @click="issue(Number(row.id))"
            >
              签发
            </button>
            <button
              v-if="row.status === 'ISSUED' || row.status === 'PARTIALLY_PAID'"
              v-permission="'bill:issue'"
              class="btn"
              type="button"
              @click="voidBill(Number(row.id))"
            >
              作废
            </button>
            <button v-permission="'receivable:adjust'" class="btn btn-ghost" type="button" data-testid="bill-adjust-btn" @click="openAdjustments(row)">调整</button>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="8" class="muted">暂无数据</td>
        </tr>
      </tbody>
    </table></div>
  </section>
  <div v-if="selectedBill" class="drawer-backdrop" @click.self="selectedBill = null">
    <aside class="drawer card" data-testid="bill-adjustment-drawer">
      <header class="head"><div><p class="eyebrow">GOVERNED CHANGE</p><h3>账单 {{ selectedBill.bill_no }}</h3></div><button class="close" type="button" aria-label="关闭" @click="selectedBill = null">×</button></header>
      <div class="facts"><span>原始金额 <b>{{ selectedBill.total_amount }}</b></span><span>现金已付 <b>{{ selectedBill.paid_amount }}</b></span><span>已减免 <b>{{ selectedBill.waiver_amount }}</b></span><span>坏账 <b>{{ selectedBill.bad_debt_amount }}</b></span><span>可收余额 <b>{{ selectedBill.open_amount }}</b></span><span>争议 <b>{{ selectedBill.dispute_status }}</b></span></div>
      <form class="adjust-form" @submit.prevent="requestAdjustment">
        <select v-model="adjustmentForm.adjustment_type" class="input" data-testid="adjustment-type"><option>WAIVER</option><option>EXTENSION</option><option>BAD_DEBT</option><option>DISPUTE</option><option>DISPUTE_RESOLUTION</option></select>
        <input v-if="['WAIVER','BAD_DEBT'].includes(adjustmentForm.adjustment_type)" v-model="adjustmentForm.amount" class="input" placeholder="调整金额" required />
        <input v-if="adjustmentForm.adjustment_type === 'EXTENSION'" v-model="adjustmentForm.requested_due_date" class="input" type="date" required />
        <textarea v-model="adjustmentForm.reason" class="input textarea" placeholder="依据与原因" maxlength="1000" required />
        <button v-permission="['receivable:adjust','approval:write']" class="btn" data-testid="adjustment-request-btn" type="submit" :disabled="saving">提交审批</button>
      </form>
      <h4>调整历史</h4>
      <article v-for="row in adjustments" :key="String(row.id)" class="history-row">
        <div><b>{{ row.adjustment_type }}</b> <span class="badge">{{ row.approval_status || row.status }}</span><small>{{ row.reason }}</small></div>
        <button v-if="row.approval_status === 'APPROVED' && row.status !== 'APPLIED'" v-permission="'receivable:adjust'" class="btn" type="button" data-testid="adjustment-apply-btn" @click="applyAdjustment(row)">应用</button>
      </article>
      <p v-if="!adjustments.length" class="muted">暂无调整申请</p>
    </aside>
  </div>
  </section>
</template>

<style scoped>
.panel {
  padding: 1rem;
}
.workspace { display: grid; gap: 1rem; }
.runbar { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: .55rem; margin: 1rem 0; }
.preview { display: flex; justify-content: space-between; gap: .75rem; padding: .8rem; margin-bottom: .8rem; background: #edf7fb; }
.table-wrap { overflow-x: auto; }.table { min-width: 940px; }
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 0.5rem;
  margin: 0.8rem 0;
}
.ops {
  display: flex;
  gap: 0.35rem;
}
.ok {
  color: #047857;
}
.risk-badge { background: #fff1e8; color: #c2410c; }.drawer-backdrop { position: fixed; inset: 0; z-index: 40; display: flex; justify-content: flex-end; background: rgba(3,19,35,.44); }.drawer { width: min(620px,100%); height: 100%; overflow-y: auto; padding: 1.25rem; border-radius: 18px 0 0 18px; }.head { display: flex; justify-content: space-between; }.close { border: 0; background: transparent; font-size: 2rem; cursor: pointer; }.eyebrow { color: #0e7490; font-size: .72rem; font-weight: 800; letter-spacing: .14em; }.facts { display: grid; grid-template-columns: repeat(2,1fr); gap: .6rem; }.facts span, .history-row { padding: .7rem; background: #f4f7fa; border-radius: 10px; }.facts b, small { display: block; }.adjust-form { display: grid; gap: .6rem; margin: 1rem 0; }.textarea { min-height: 90px; }.history-row { display: flex; justify-content: space-between; gap: .6rem; margin: .5rem 0; }
@media (max-width: 720px) { .runbar { grid-template-columns: 1fr 1fr; }.drawer { border-radius: 0; }.preview { flex-direction: column; } }
</style>
