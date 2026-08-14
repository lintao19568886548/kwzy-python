<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const saving = ref(false);
const loading = ref(true);
const selected = ref<Record<string, unknown> | null>(null);
const allocationForm = ref({ bill_id: "", amount: "" });
const form = ref({
  park_id: "",
  party_id: "",
  bill_id: "",
  amount: "100",
  paid_at: "2026-03-15T10:00:00",
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/payments", {
      params: { page: 1, page_size: 50 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function openPayment(id: number) {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<Record<string, unknown>>>(`/payments/${id}`);
    selected.value = data.data;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "收款详情加载失败";
  }
}

async function allocate() {
  if (!selected.value || saving.value) return;
  saving.value = true;
  try {
    await http.post(
      `/payments/${selected.value.id}/allocations`,
      { allocations: [{ bill_id: Number(allocationForm.value.bill_id), amount: allocationForm.value.amount }] },
      { headers: { "Idempotency-Key": `allocation-${selected.value.id}-${Date.now()}` } }
    );
    success.value = "未分配余额已核销到指定账单。";
    allocationForm.value = { bill_id: "", amount: "" };
    await load();
    await openPayment(Number(selected.value.id));
  } catch (e) {
    error.value = e instanceof Error ? e.message : "核销失败";
  } finally {
    saving.value = false;
  }
}

async function create() {
  if (saving.value) return;
  saving.value = true;
  try {
    await http.post(
      "/payments",
      {
        park_id: Number(form.value.park_id),
        party_id: Number(form.value.party_id),
        amount: form.value.amount,
        method: "TRANSFER",
        paid_at: form.value.paid_at,
        allocations: [
          { bill_id: Number(form.value.bill_id), amount: form.value.amount },
        ],
      },
      { headers: { "Idempotency-Key": `pay-${Date.now()}` } }
    );
    success.value = "收款已登记";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "登记失败";
  } finally {
    saving.value = false;
  }
}

async function reverse(id: number) {
  if (!window.confirm("确认冲正收款？")) return;
  try {
    await http.post(`/payments/${id}/reverse`);
    success.value = "已冲正；原核销记录保留并标记冲正。";
    selected.value = null;
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "冲正失败";
  }
}

onMounted(load);
</script>

<template>
  <section class="workspace">
  <section class="card panel">
    <h2 data-testid="payments-title">收款与核销</h2>
    <p class="muted">收款金额、已核销与未分配余额分别展示；冲正不删除历史。</p>
    <form class="create" data-testid="payment-create-form" @submit.prevent="create">
      <input v-model="form.park_id" class="input" data-testid="pay-park-id" placeholder="园区ID" required />
      <input v-model="form.party_id" class="input" data-testid="pay-party-id" placeholder="主体ID" required />
      <input v-model="form.bill_id" class="input" data-testid="pay-bill-id" placeholder="账单ID" required />
      <input v-model="form.amount" class="input" data-testid="pay-amount" placeholder="金额" required />
      <input v-model="form.paid_at" class="input" data-testid="pay-at" placeholder="支付时间" required />
      <button v-permission="'payment:write'" class="btn" data-testid="pay-create-btn" type="submit" :disabled="saving">
        登记收款
      </button>
    </form>
    <p v-if="error" class="error" data-testid="pay-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="pay-success">{{ success }}</p>
    <p v-if="loading" class="muted">加载真实收款记录…</p>
    <div class="table-wrap"><table v-if="!loading" class="table" data-testid="payment-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>收款号</th>
          <th>状态</th>
          <th>金额</th>
          <th>已核销</th>
          <th>未分配</th>
          <th>来源</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)" :data-testid="`pay-row-${row.id}`">
          <td>{{ row.id }}</td>
          <td>{{ row.payment_no }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>{{ row.amount }}</td>
          <td>{{ row.allocated_amount }}</td>
          <td :class="Number(row.unapplied_amount) > 0 ? 'risk-text' : ''">{{ row.unapplied_amount }}</td>
          <td>{{ row.source_receipt_id ? `到账 #${row.source_receipt_id}` : '人工登记' }}</td>
          <td class="ops">
            <button class="btn btn-ghost" type="button" data-testid="payment-detail-btn" @click="openPayment(Number(row.id))">详情</button>
            <button
              v-if="row.status === 'CONFIRMED'"
              v-permission="'payment:write'"
              class="btn"
              type="button"
              data-testid="pay-reverse-btn"
              @click="reverse(Number(row.id))"
            >
              冲正
            </button>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="8" class="muted">暂无数据</td>
        </tr>
      </tbody>
    </table></div>
  </section>
  <div v-if="selected" class="drawer-backdrop" @click.self="selected = null">
    <aside class="drawer card" data-testid="payment-allocation-drawer">
      <header class="head"><div><p class="eyebrow">PAYMENT LEDGER</p><h3>{{ selected.payment_no }}</h3></div><button class="close" type="button" aria-label="关闭" @click="selected = null">×</button></header>
      <div class="facts"><span>收款金额<b>{{ selected.amount }}</b></span><span>已核销<b>{{ selected.allocated_amount }}</b></span><span>未分配<b class="risk-text">{{ selected.unapplied_amount }}</b></span><span>状态<b>{{ selected.status }}</b></span></div>
      <h4>核销轨迹</h4>
      <table class="table"><thead><tr><th>账单</th><th>金额</th><th>状态</th></tr></thead><tbody><tr v-for="row in (selected.allocations as Array<Record<string, unknown>> || [])" :key="String(row.id)"><td>{{ row.bill_id }}</td><td>{{ row.amount }}</td><td>{{ row.reversed_at ? 'REVERSED' : 'ACTIVE' }}</td></tr><tr v-if="!(selected.allocations as unknown[] || []).length"><td colspan="3" class="muted">尚未核销</td></tr></tbody></table>
      <form v-if="selected.status === 'CONFIRMED' && Number(selected.unapplied_amount) > 0" class="allocate-form" data-testid="payment-allocation-form" @submit.prevent="allocate">
        <h4>分配未核销余额</h4>
        <input v-model="allocationForm.bill_id" class="input" data-testid="allocation-bill-id" placeholder="同主体、同园区账单 ID" required />
        <input v-model="allocationForm.amount" class="input" data-testid="allocation-amount" placeholder="核销金额" required />
        <button v-permission="'payment:allocate'" class="btn" data-testid="payment-allocate-btn" type="submit" :disabled="saving">确认核销</button>
      </form>
    </aside>
  </div>
  </section>
</template>

<style scoped>
.panel {
  padding: 1rem;
}
.workspace { display: grid; gap: 1rem; }.table-wrap { overflow-x: auto; }.table { min-width: 760px; }
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 0.5rem;
  margin: 0.8rem 0;
}
.ok {
  color: #047857;
}
.ops { display: flex; gap: .4rem; }.risk-text { color: #c2410c; font-weight: 700; }.drawer-backdrop { position: fixed; inset: 0; z-index: 40; display: flex; justify-content: flex-end; background: rgba(3,19,35,.44); }.drawer { width: min(560px,100%); height: 100%; overflow-y: auto; padding: 1.25rem; border-radius: 18px 0 0 18px; }.head { display: flex; justify-content: space-between; }.close { border: 0; background: transparent; font-size: 2rem; cursor: pointer; }.eyebrow { color: #0e7490; font-size: .72rem; font-weight: 800; letter-spacing: .14em; }.facts { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; margin: 1rem 0; }.facts span { padding: .75rem; background: #f4f7fa; border-radius: 10px; }.facts b { display: block; font-size: 1.2rem; }.allocate-form { display: grid; gap: .6rem; margin-top: 1rem; }@media(max-width:600px){.drawer{border-radius:0}.facts{grid-template-columns:1fr}}
</style>
