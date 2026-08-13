<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const loading = ref(true);
const status = ref("");
const form = ref({
  park_id: "",
  party_id: "",
  bill_id: "",
  level: "L1",
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>(
      "/collection/cases",
      { params: { page: 1, page_size: 50, status: status.value || undefined } }
    );
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function create() {
  try {
    await http.post("/collection/cases", {
      park_id: Number(form.value.park_id),
      party_id: Number(form.value.party_id),
      bill_id: Number(form.value.bill_id),
      level: form.value.level,
    });
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  }
}

async function closeCase(id: number) {
  if (!window.confirm("确认关闭该催缴案件？")) return;
  await http.patch(`/collection/cases/${id}`, { status: "CLOSED" });
  await load();
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <div>
        <h2>催缴案件</h2>
        <p class="muted">过程记录，不替代收款核销</p>
      </div>
      <div class="tools">
        <select v-model="status" class="input" @change="load">
          <option value="">全部状态</option>
          <option value="OPEN">OPEN</option>
          <option value="CLOSED">CLOSED</option>
        </select>
        <button class="btn btn-ghost" type="button" @click="load">刷新</button>
      </div>
    </header>

    <form class="create" @submit.prevent="create">
      <input v-model="form.park_id" class="input" placeholder="园区ID" required />
      <input v-model="form.party_id" class="input" placeholder="主体ID" required />
      <input v-model="form.bill_id" class="input" placeholder="账单ID" required />
      <select v-model="form.level" class="input">
        <option>L1</option>
        <option>L2</option>
        <option>L3</option>
      </select>
      <button v-permission="'collection:write'" class="btn" type="submit">创建案件</button>
    </form>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>账单</th>
          <th>主体</th>
          <th>级别</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)">
          <td>{{ row.id }}</td>
          <td>{{ row.bill_id }}</td>
          <td>{{ row.party_id }}</td>
          <td>{{ row.level }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>
            <button
              v-if="row.status === 'OPEN'"
              v-permission="'collection:write'"
              class="btn"
              type="button"
              @click="closeCase(Number(row.id))"
            >
              关闭
            </button>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6" class="muted">暂无案件</td>
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
  gap: 1rem;
  align-items: flex-start;
}
.tools {
  display: flex;
  gap: 0.5rem;
}
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.6rem;
  margin: 1rem 0;
}
</style>
