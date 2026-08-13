<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const loading = ref(true);
const keyword = ref("");
const form = ref({ name: "", party_type: "ORGANIZATION", contact_phone: "" });

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/parties", {
      params: { page: 1, page_size: 50, keyword: keyword.value || undefined },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!form.value.name.trim()) {
    error.value = "名称必填";
    return;
  }
  try {
    await http.post("/parties", {
      name: form.value.name.trim(),
      party_type: form.value.party_type,
      contact_phone: form.value.contact_phone || undefined,
    });
    form.value.name = "";
    form.value.contact_phone = "";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  }
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <h2>主体</h2>
      <div class="tools">
        <input v-model="keyword" class="input" placeholder="关键词" @keyup.enter="load" />
        <button class="btn btn-ghost" type="button" @click="load">筛选</button>
      </div>
    </header>
    <form class="create" @submit.prevent="create">
      <input v-model="form.name" class="input" placeholder="名称" required />
      <select v-model="form.party_type" class="input">
        <option value="ORGANIZATION">ORGANIZATION</option>
        <option value="PERSON">PERSON</option>
      </select>
      <input v-model="form.contact_phone" class="input" placeholder="联系电话" />
      <button v-permission="'party:write'" class="btn" type="submit">新建</button>
    </form>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>类型</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in items" :key="String(p.id)">
          <td>{{ p.id }}</td>
          <td>{{ p.name }}</td>
          <td>{{ p.party_type }}</td>
          <td>{{ p.status }}</td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="4" class="muted">暂无数据</td>
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
  align-items: center;
}
.tools {
  display: flex;
  gap: 0.5rem;
}
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.6rem;
  margin: 0.8rem 0;
}
</style>
