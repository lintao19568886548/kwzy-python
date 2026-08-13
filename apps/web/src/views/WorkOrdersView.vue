<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
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
  try {
    await http.post("/work-orders", {
      park_id: Number(form.value.park_id),
      title: form.value.title,
      priority: form.value.priority,
    });
    form.value.title = "";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  }
}

async function complete(id: number) {
  await http.post(`/work-orders/${id}/complete`);
  await load();
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <h2>运维工单</h2>
    <form class="create" @submit.prevent="create">
      <input v-model="form.park_id" class="input" placeholder="园区 ID" required />
      <input v-model="form.title" class="input" placeholder="标题" required />
      <select v-model="form.priority" class="input">
        <option>LOW</option>
        <option>MEDIUM</option>
        <option>HIGH</option>
        <option>URGENT</option>
      </select>
      <button class="btn" type="submit">创建</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <table class="table">
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
        <tr v-for="row in items" :key="String(row.id)">
          <td>{{ row.id }}</td>
          <td>{{ row.title }}</td>
          <td>{{ row.priority }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>
            <button
              v-if="row.status !== 'DONE' && row.status !== 'CANCELLED'"
              class="btn"
              type="button"
              @click="complete(Number(row.id))"
            >
              完成
            </button>
          </td>
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
</style>
