<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const form = ref({ biz_type: "LEASE", biz_id: "", title: "" });

async function load() {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/approvals", {
      params: { page: 1, page_size: 50 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  }
}

async function create() {
  try {
    await http.post("/approvals", form.value);
    form.value.biz_id = "";
    form.value.title = "";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  }
}

async function approve(id: number) {
  if (!window.confirm("确认通过？")) return;
  await http.post(`/approvals/${id}/approve`, { remark: "通过" });
  await load();
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <h2>审批</h2>
    <p class="muted">最小审批适配（非完整 BPM）</p>
    <form class="create" @submit.prevent="create">
      <input v-model="form.biz_type" class="input" placeholder="业务类型" required />
      <input v-model="form.biz_id" class="input" placeholder="业务ID" required />
      <input v-model="form.title" class="input" placeholder="标题" required />
      <button v-permission="'approval:write'" class="btn" type="submit">提交</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <table class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>标题</th>
          <th>业务</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)">
          <td>{{ row.id }}</td>
          <td>{{ row.title }}</td>
          <td>{{ row.biz_type }}#{{ row.biz_id }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>
            <button
              v-if="row.status === 'PENDING'"
              v-permission="'approval:decide'"
              class="btn"
              type="button"
              @click="approve(Number(row.id))"
            >
              通过
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
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.5rem;
  margin: 0.8rem 0;
}
</style>
