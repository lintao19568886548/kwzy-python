<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, WorkbenchSummary } from "@/api/types";

const loading = ref(true);
const error = ref("");
const data = ref<WorkbenchSummary | null>(null);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data: body } = await http.get<Envelope<WorkbenchSummary>>("/workbench/summary");
    data.value = body.data;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <header class="head">
      <div>
        <h2>运营工作台</h2>
        <p class="muted">待办、逾期风险与经营信号一屏掌握</p>
      </div>
      <button class="btn btn-ghost" type="button" @click="load">刷新</button>
    </header>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="data">
      <div class="grid-metrics">
        <div class="card metric">
          <span class="muted">开放待办</span>
          <strong>{{ data.metrics.open_todos }}</strong>
        </div>
        <div class="card metric">
          <span class="muted">已逾期待办</span>
          <strong>{{ data.metrics.overdue_todos }}</strong>
        </div>
        <div class="card metric">
          <span class="muted">7 日内到期</span>
          <strong>{{ data.metrics.due_soon_todos }}</strong>
        </div>
        <div class="card metric">
          <span class="muted">未结账单</span>
          <strong>{{ data.metrics.unpaid_bills }}</strong>
        </div>
        <div class="card metric">
          <span class="muted">即将到期合同</span>
          <strong>{{ data.metrics.expiring_contracts }}</strong>
        </div>
      </div>

      <div class="card list">
        <h3>最近待办</h3>
        <table class="table">
          <thead>
            <tr>
              <th>标题</th>
              <th>类型</th>
              <th>优先级</th>
              <th>截止</th>
              <th>来源</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in data.recent_todos" :key="t.id">
              <td>{{ t.title }}</td>
              <td><span class="badge">{{ t.item_type }}</span></td>
              <td>{{ t.priority }}</td>
              <td>{{ t.due_at || "—" }}</td>
              <td>{{ t.source_type }}#{{ t.source_id }}</td>
            </tr>
            <tr v-if="!data.recent_todos.length">
              <td colspan="5" class="muted">暂无开放待办</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}
h2 {
  margin: 0;
}
.list {
  margin-top: 1rem;
  padding: 1rem;
}
h3 {
  margin: 0 0 0.75rem;
}
</style>
