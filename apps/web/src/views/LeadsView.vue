<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

type Lead = {
  id: number;
  name: string;
  contact_phone: string;
  status: string;
  intent_level: string | null;
  park_id: number;
};

const items = ref<Lead[]>([]);
const error = ref("");
const loading = ref(true);
const form = ref({
  park_id: "" as string,
  name: "",
  contact_phone: "",
  intent_level: "HIGH",
});
const creating = ref(false);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Lead>>>("/leads", {
      params: { page: 1, page_size: 50 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function createLead() {
  creating.value = true;
  error.value = "";
  try {
    await http.post("/leads", {
      park_id: Number(form.value.park_id),
      name: form.value.name,
      contact_phone: form.value.contact_phone,
      intent_level: form.value.intent_level,
    });
    form.value.name = "";
    form.value.contact_phone = "";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  } finally {
    creating.value = false;
  }
}

async function convert(id: number) {
  try {
    await http.post(`/leads/${id}/convert`, {});
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "转化失败";
  }
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <div>
        <h2>招商线索</h2>
        <p class="muted">创建 → 跟进 → 转化主体/合同草稿</p>
      </div>
      <button class="btn btn-ghost" type="button" @click="load">刷新</button>
    </header>

    <form class="create" @submit.prevent="createLead">
      <input v-model="form.park_id" class="input" placeholder="园区 ID" required />
      <input v-model="form.name" class="input" placeholder="客户名称" required />
      <input v-model="form.contact_phone" class="input" placeholder="联系电话" required />
      <select v-model="form.intent_level" class="input">
        <option value="HIGH">HIGH</option>
        <option value="MEDIUM">MEDIUM</option>
        <option value="LOW">LOW</option>
      </select>
      <button class="btn" type="submit" :disabled="creating">
        {{ creating ? "创建中…" : "新建线索" }}
      </button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="muted">加载中…</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>电话</th>
          <th>意向</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="row.id">
          <td>{{ row.id }}</td>
          <td>{{ row.name }}</td>
          <td>{{ row.contact_phone }}</td>
          <td>{{ row.intent_level || "—" }}</td>
          <td><span class="badge">{{ row.status }}</span></td>
          <td>
            <button
              v-if="row.status === 'NEW' || row.status === 'FOLLOWING'"
              class="btn"
              type="button"
              @click="convert(row.id)"
            >
              转化
            </button>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6" class="muted">暂无线索</td>
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
  align-items: flex-start;
  gap: 1rem;
}
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.6rem;
  margin: 1rem 0;
}
</style>
