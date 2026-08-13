<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

type Todo = {
  id: number;
  title: string;
  status: string;
  priority: string;
  item_type: string;
  due_at: string | null;
  source_type?: string | null;
  source_id?: string | null;
};

const items = ref<Todo[]>([]);
const error = ref("");
const success = ref("");
const loading = ref(true);
const statusFilter = ref("OPEN");
const router = useRouter();

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Todo>>>("/work-items", {
      params: {
        page: 1,
        page_size: 50,
        status: statusFilter.value || undefined,
      },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function complete(id: number) {
  if (!window.confirm("确认完成该待办？")) return;
  try {
    await http.post(`/work-items/${id}/complete`);
    success.value = "已完成";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "操作失败";
  }
}

async function cancel(id: number) {
  if (!window.confirm("确认取消该待办？")) return;
  try {
    await http.post(`/work-items/${id}/cancel`);
    success.value = "已取消";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "操作失败";
  }
}

async function reopen(id: number) {
  try {
    await http.post(`/work-items/${id}/reopen`);
    success.value = "已重新打开";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "操作失败";
  }
}

function jumpSource(t: Todo) {
  const st = (t.source_type || "").toUpperCase();
  if (st.includes("BILL")) router.push("/bills");
  else if (st.includes("LEASE") || st.includes("CONTRACT")) router.push("/leases");
  else if (st.includes("LEAD")) router.push("/leads");
  else if (st.includes("WORK_ORDER") || st.includes("ORDER")) router.push("/work-orders");
  else router.push("/workbench");
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <h2 data-testid="todos-title">待办列表</h2>
      <div class="tools">
        <select
          v-model="statusFilter"
          class="input"
          data-testid="todo-status-filter"
          @change="load"
        >
          <option value="OPEN">OPEN</option>
          <option value="DONE">DONE</option>
          <option value="CANCELLED">CANCELLED</option>
          <option value="">全部</option>
        </select>
        <button class="btn btn-ghost" type="button" data-testid="todo-refresh" @click="load">
          刷新
        </button>
      </div>
    </header>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-if="error" class="error" data-testid="todo-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="todo-success">{{ success }}</p>
    <table v-if="!loading" class="table" data-testid="todo-table">
      <thead>
        <tr>
          <th>标题</th>
          <th>类型</th>
          <th>状态</th>
          <th>优先级</th>
          <th>截止</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.id" :data-testid="`todo-row-${t.id}`">
          <td data-testid="todo-title-cell">{{ t.title }}</td>
          <td data-testid="todo-type-cell">{{ t.item_type }}</td>
          <td data-testid="todo-status-cell">{{ t.status }}</td>
          <td>{{ t.priority }}</td>
          <td>{{ t.due_at || "—" }}</td>
          <td class="ops">
            <button
              class="btn btn-ghost"
              type="button"
              data-testid="todo-jump-btn"
              @click="jumpSource(t)"
            >
              来源
            </button>
            <button
              v-if="t.status === 'OPEN'"
              v-permission="'work_item:write'"
              class="btn"
              type="button"
              data-testid="todo-complete-btn"
              @click="complete(t.id)"
            >
              完成
            </button>
            <button
              v-if="t.status === 'OPEN'"
              v-permission="'work_item:write'"
              class="btn"
              type="button"
              data-testid="todo-cancel-btn"
              @click="cancel(t.id)"
            >
              取消
            </button>
            <button
              v-if="t.status === 'DONE' || t.status === 'CANCELLED'"
              v-permission="'work_item:write'"
              class="btn"
              type="button"
              data-testid="todo-reopen-btn"
              @click="reopen(t.id)"
            >
              重开
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
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}
.tools {
  display: flex;
  gap: 0.5rem;
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
