<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

type Todo = {
  id: number;
  title: string;
  status: string;
  priority: string;
  item_type: string;
  due_at: string | null;
};

const items = ref<Todo[]>([]);
const error = ref("");
const loading = ref(true);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Todo>>>("/work-items", {
      params: { page: 1, page_size: 50, status: "OPEN" },
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
  await http.post(`/work-items/${id}/complete`);
  await load();
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <h2>待办列表</h2>
      <button class="btn btn-ghost" type="button" @click="load">刷新</button>
    </header>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th>标题</th>
          <th>类型</th>
          <th>优先级</th>
          <th>截止</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.id">
          <td>{{ t.title }}</td>
          <td>{{ t.item_type }}</td>
          <td>{{ t.priority }}</td>
          <td>{{ t.due_at || "—" }}</td>
          <td>
            <button class="btn" type="button" @click="complete(t.id)">完成</button>
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
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
