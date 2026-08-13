<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const form = ref({ park_id: "", title: "", priority: "MEDIUM" });

async function load() {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/work-orders", {
      params: { page: 1, page_size: 50 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  }
}

async function create() {
  error.value = "";
  try {
    await http.post("/work-orders", {
      park_id: Number(form.value.park_id),
      title: form.value.title,
      priority: form.value.priority,
    });
    success.value = "工单已创建";
    form.value.title = "";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  }
}

async function start(id: number) {
  try {
    await http.post(`/work-orders/${id}/start`);
    success.value = "已开始";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "开始失败";
  }
}

async function complete(id: number) {
  try {
    await http.post(`/work-orders/${id}/complete`);
    success.value = "已完成";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "完成失败";
  }
}

async function cancel(id: number) {
  if (!window.confirm("确认取消工单？")) return;
  try {
    await http.post(`/work-orders/${id}/cancel`);
    success.value = "已取消";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "取消失败";
  }
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <h2 data-testid="work-orders-title">运维工单</h2>
    <form class="create" data-testid="wo-create-form" @submit.prevent="create">
      <input
        v-model="form.park_id"
        class="input"
        data-testid="wo-park-id"
        placeholder="园区 ID"
        required
      />
      <input v-model="form.title" class="input" data-testid="wo-title" placeholder="标题" required />
      <select v-model="form.priority" class="input" data-testid="wo-priority">
        <option>LOW</option>
        <option>MEDIUM</option>
        <option>HIGH</option>
        <option>URGENT</option>
      </select>
      <button
        v-permission="'work_order:write'"
        class="btn"
        data-testid="wo-create-btn"
        type="submit"
      >
        创建
      </button>
    </form>
    <p v-if="error" class="error" data-testid="wo-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="wo-success">{{ success }}</p>
    <table class="table" data-testid="wo-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>标题</th>
          <th>优先级</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)" :data-testid="`wo-row-${row.id}`">
          <td data-testid="wo-id-cell">{{ row.id }}</td>
          <td data-testid="wo-title-cell">{{ row.title }}</td>
          <td>{{ row.priority }}</td>
          <td><span class="badge" data-testid="wo-status-cell">{{ row.status }}</span></td>
          <td class="ops">
            <button
              v-if="row.status === 'OPEN' || row.status === 'NEW' || row.status === 'PENDING'"
              v-permission="'work_order:write'"
              class="btn"
              type="button"
              data-testid="wo-start-btn"
              @click="start(Number(row.id))"
            >
              开始
            </button>
            <button
              v-if="row.status !== 'DONE' && row.status !== 'CANCELLED' && row.status !== 'CLOSED'"
              v-permission="'work_order:write'"
              class="btn"
              type="button"
              data-testid="wo-complete-btn"
              @click="complete(Number(row.id))"
            >
              完成
            </button>
            <button
              v-if="row.status !== 'DONE' && row.status !== 'CANCELLED' && row.status !== 'CLOSED'"
              v-permission="'work_order:write'"
              class="btn"
              type="button"
              data-testid="wo-cancel-btn"
              @click="cancel(Number(row.id))"
            >
              取消
            </button>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="5" class="muted">暂无工单</td>
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
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.6rem;
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
