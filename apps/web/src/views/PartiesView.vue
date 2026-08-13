<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");

onMounted(async () => {
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/parties", {
      params: { page: 1, page_size: 20 },
    });
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  }
});
</script>

<template>
  <section class="card panel">
    <h2>主体</h2>
    <p v-if="error" class="error">{{ error }}</p>
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
</style>
