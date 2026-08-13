<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const saving = ref(false);
const form = ref({
  park_id: "",
  party_id: "",
  bill_id: "",
  amount: "100",
  paid_at: "2026-03-15T10:00:00",
});

async function load() {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/payments", {
      params: { page: 1, page_size: 50 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
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
  await http.post(`/payments/${id}/reverse`);
  success.value = "已冲正";
  await load();
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <h2 data-testid="payments-title">收款</h2>
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
    <table class="table" data-testid="payment-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>收款号</th>
          <th>状态</th>
          <th>金额</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)" :data-testid="`pay-row-${row.id}`">
          <td>{{ row.id }}</td>
          <td>{{ row.payment_no }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>{{ row.amount }}</td>
          <td>
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
          <td colspan="5" class="muted">暂无数据</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.panel {
  padding: 1rem;
}
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 0.5rem;
  margin: 0.8rem 0;
}
.ok {
  color: #047857;
}
</style>
