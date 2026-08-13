<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");

onMounted(async () => {
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/bills", {
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
    <h2>账单</h2>
    <p v-if="error" class="error">{{ error }}</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>账单号</th>
          <th>状态</th>
          <th>金额</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)">
          <td>{{ row.id }}</td>
          <td>{{ row.bill_no }}</td>
          <td>{{ row.status }}</td>
          <td>{{ row.total_amount }}</td>
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
