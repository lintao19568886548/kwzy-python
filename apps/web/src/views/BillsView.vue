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
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  unit_price: "100",
});

async function load() {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/bills", {
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
  <section class="card panel">
    <h2 data-testid="bills-title">账单</h2>
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
    <table class="table" data-testid="bill-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>账单号</th>
          <th>状态</th>
          <th>金额</th>
          <th>已付</th>
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
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6" class="muted">暂无数据</td>
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
.ops {
  display: flex;
  gap: 0.35rem;
}
.ok {
  color: #047857;
}
</style>
