<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const parks = ref<Array<Record<string, unknown>>>([]);
const units = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const parkForm = ref({ name: "", address: "e2e-addr" });
const unitForm = ref({ park_id: "", code: "", name: "", rentable_area: "100" });

async function load() {
  error.value = "";
  try {
    const p = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/parks", {
      params: { page: 1, page_size: 50 },
    });
    parks.value = p.data.data.items;
    const u = await http.get<Envelope<PageResult<Record<string, unknown>>>>("/units", {
      params: { page: 1, page_size: 50 },
    });
    units.value = u.data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  }
}

async function createPark() {
  await http.post("/parks", parkForm.value);
  success.value = "园区已创建";
  parkForm.value.name = "";
  await load();
}

async function createUnit() {
  await http.post("/units", {
    park_id: Number(unitForm.value.park_id),
    code: unitForm.value.code,
    name: unitForm.value.name,
    rentable_area: Number(unitForm.value.rentable_area),
    status: "VACANT",
  });
  success.value = "单元已创建";
  await load();
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <h2 data-testid="parks-title">园区与单元</h2>
    <form class="create" data-testid="park-create-form" @submit.prevent="createPark">
      <input v-model="parkForm.name" class="input" data-testid="park-name" placeholder="园区名称" required />
      <input v-model="parkForm.address" class="input" placeholder="地址" />
      <button v-permission="'park:write'" class="btn" data-testid="park-create-btn" type="submit">创建园区</button>
    </form>
    <form class="create" data-testid="unit-create-form" @submit.prevent="createUnit">
      <input v-model="unitForm.park_id" class="input" data-testid="unit-park-id" placeholder="园区ID" required />
      <input v-model="unitForm.code" class="input" data-testid="unit-code" placeholder="单元编码" required />
      <input v-model="unitForm.name" class="input" data-testid="unit-name" placeholder="单元名称" required />
      <input v-model="unitForm.rentable_area" class="input" placeholder="面积" />
      <button v-permission="'unit:write'" class="btn" data-testid="unit-create-btn" type="submit">创建单元</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="park-success">{{ success }}</p>
    <table class="table" data-testid="park-table">
      <thead>
        <tr>
          <th>园区ID</th>
          <th>名称</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in parks" :key="String(p.id)">
          <td data-testid="park-id-cell">{{ p.id }}</td>
          <td>{{ p.name }}</td>
        </tr>
      </tbody>
    </table>
    <table class="table" data-testid="unit-table">
      <thead>
        <tr>
          <th>单元ID</th>
          <th>编码</th>
          <th>园区</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in units" :key="String(u.id)">
          <td>{{ u.id }}</td>
          <td>{{ u.code }}</td>
          <td>{{ u.park_id }}</td>
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
  gap: 0.5rem;
  margin: 0.6rem 0;
}
.ok {
  color: #047857;
}
</style>
