<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const loading = ref(false);
const saving = ref(false);
const form = ref({
  park_id: "",
  party_id: "",
  unit_id: "",
  start_date: "2026-01-01",
  end_date: "2026-12-31",
  occupied_area: "50",
  unit_rent_price: "30",
  deposit_amount: "1000",
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/leases", {
      params: { page: 1, page_size: 50 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    const body = {
      park_id: Number(form.value.park_id),
      party_id: Number(form.value.party_id),
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      deposit_amount: form.value.deposit_amount,
      units: form.value.unit_id
        ? [
            {
              unit_id: Number(form.value.unit_id),
              occupied_area: form.value.occupied_area,
              unit_rent_price: form.value.unit_rent_price,
            },
          ]
        : [],
    };
    await http.post("/leases", body);
    success.value = "合同已创建";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  } finally {
    saving.value = false;
  }
}

async function submit(id: number) {
  await http.post(`/leases/${id}/submit`);
  success.value = "已提交";
  await load();
}

async function activate(id: number) {
  if (!window.confirm("确认激活合同？")) return;
  await http.post(`/leases/${id}/activate`);
  success.value = "已激活";
  await load();
}

async function terminate(id: number) {
  if (!window.confirm("确认终止合同？")) return;
  await http.post(`/leases/${id}/terminate`);
  success.value = "已终止";
  await load();
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <h2 data-testid="leases-title">租赁合同</h2>
    <form class="create" data-testid="lease-create-form" @submit.prevent="create">
      <input v-model="form.park_id" class="input" data-testid="lease-park-id" placeholder="园区ID" required />
      <input v-model="form.party_id" class="input" data-testid="lease-party-id" placeholder="主体ID" required />
      <input v-model="form.unit_id" class="input" data-testid="lease-unit-id" placeholder="单元ID" />
      <input v-model="form.start_date" class="input" type="date" data-testid="lease-start" required />
      <input v-model="form.end_date" class="input" type="date" data-testid="lease-end" required />
      <input v-model="form.occupied_area" class="input" data-testid="lease-area" placeholder="占用面积" />
      <input v-model="form.deposit_amount" class="input" data-testid="lease-deposit" placeholder="押金" />
      <button v-permission="'lease:write'" class="btn" data-testid="lease-create-btn" type="submit" :disabled="saving">
        创建草稿
      </button>
    </form>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-if="error" class="error" data-testid="lease-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="lease-success">{{ success }}</p>
    <table class="table" data-testid="lease-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>合同号</th>
          <th>状态</th>
          <th>起止</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)" :data-testid="`lease-row-${row.id}`">
          <td>{{ row.id }}</td>
          <td>{{ row.contract_no }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>{{ row.start_date }} ~ {{ row.end_date }}</td>
          <td class="ops">
            <button
              v-if="row.status === 'DRAFT'"
              v-permission="'lease:activate'"
              class="btn"
              type="button"
              @click="submit(Number(row.id))"
            >
              提交
            </button>
            <button
              v-if="row.status === 'PENDING_ACTIVE'"
              v-permission="'lease:activate'"
              class="btn"
              type="button"
              data-testid="lease-activate-btn"
              @click="activate(Number(row.id))"
            >
              激活
            </button>
            <button
              v-if="row.status === 'ACTIVE'"
              v-permission="'lease:terminate'"
              class="btn"
              type="button"
              @click="terminate(Number(row.id))"
            >
              终止
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
.ops {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}
.ok {
  color: #047857;
}
</style>
