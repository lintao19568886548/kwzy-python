<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const loading = ref(true);
const status = ref("");
const form = ref({
  park_id: "",
  party_id: "",
  bill_id: "",
  level: "L1",
});
const updateForm = ref({ id: "", level: "L2", note: "" });

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
  error.value = "";
  try {
    await http.post("/collection/cases", {
      park_id: Number(form.value.park_id),
      party_id: Number(form.value.party_id),
      bill_id: Number(form.value.bill_id),
      level: form.value.level,
    });
    success.value = "案件已创建";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  }
}

async function updateCase() {
  error.value = "";
  try {
    await http.patch(`/collection/cases/${Number(updateForm.value.id)}`, {
      level: updateForm.value.level,
      note: updateForm.value.note || undefined,
    });
    success.value = "案件已更新";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "更新失败";
  }
}

async function closeCase(id: number) {
  if (!window.confirm("确认关闭该催缴案件？")) return;
  try {
    await http.patch(`/collection/cases/${id}`, { status: "CLOSED" });
    success.value = "案件已关闭";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "关闭失败";
  }
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <div>
        <h2 data-testid="collection-title">催缴案件</h2>
        <p class="muted">过程记录，不替代收款核销</p>
      </div>
      <div class="tools">
        <select v-model="status" class="input" data-testid="collection-status-filter" @change="load">
          <option value="">全部状态</option>
          <option value="OPEN">OPEN</option>
          <option value="CLOSED">CLOSED</option>
        </select>
        <button class="btn btn-ghost" type="button" @click="load">刷新</button>
      </div>
    </header>

    <form class="create" data-testid="collection-create-form" @submit.prevent="create">
      <input
        v-model="form.park_id"
        class="input"
        data-testid="collection-park-id"
        placeholder="园区ID"
        required
      />
      <input
        v-model="form.party_id"
        class="input"
        data-testid="collection-party-id"
        placeholder="主体ID"
        required
      />
      <input
        v-model="form.bill_id"
        class="input"
        data-testid="collection-bill-id"
        placeholder="账单ID"
        required
      />
      <select v-model="form.level" class="input" data-testid="collection-level">
        <option>L1</option>
        <option>L2</option>
        <option>L3</option>
      </select>
      <button
        v-permission="'collection:write'"
        class="btn"
        data-testid="collection-create-btn"
        type="submit"
      >
        创建案件
      </button>
    </form>

    <form class="create" data-testid="collection-update-form" @submit.prevent="updateCase">
      <input
        v-model="updateForm.id"
        class="input"
        data-testid="collection-update-id"
        placeholder="案件ID"
        required
      />
      <select v-model="updateForm.level" class="input" data-testid="collection-update-level">
        <option>L1</option>
        <option>L2</option>
        <option>L3</option>
      </select>
      <input
        v-model="updateForm.note"
        class="input"
        data-testid="collection-note"
        placeholder="备注"
      />
      <button
        v-permission="'collection:write'"
        class="btn"
        data-testid="collection-update-btn"
        type="submit"
      >
        更新
      </button>
    </form>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-if="error" class="error" data-testid="collection-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="collection-success">{{ success }}</p>
    <table v-if="!loading" class="table" data-testid="collection-table">
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
        <tr v-for="row in items" :key="String(row.id)" :data-testid="`collection-row-${row.id}`">
          <td data-testid="collection-id-cell">{{ row.id }}</td>
          <td>{{ row.bill_id }}</td>
          <td>{{ row.party_id }}</td>
          <td data-testid="collection-level-cell">{{ row.level }}</td>
          <td><span class="badge" data-testid="collection-status-cell">{{ row.status }}</span></td>
          <td>
            <button
              v-if="row.status === 'OPEN'"
              v-permission="'collection:write'"
              class="btn"
              type="button"
              data-testid="collection-close-btn"
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
.ok {
  color: #047857;
}
</style>
