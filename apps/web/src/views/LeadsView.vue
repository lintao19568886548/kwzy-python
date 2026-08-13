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
  owner_user_id?: number | null;
  remark?: string | null;
};

const items = ref<Lead[]>([]);
const error = ref("");
const success = ref("");
const loading = ref(true);
const form = ref({
  park_id: "" as string,
  name: "",
  contact_phone: "",
  intent_level: "HIGH",
});
const editForm = ref({
  id: "",
  name: "",
  intent_level: "MEDIUM",
  status: "FOLLOWING",
  owner_user_id: "",
  remark: "",
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
    success.value = "线索已创建";
    form.value.name = "";
    form.value.contact_phone = "";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  } finally {
    creating.value = false;
  }
}

async function updateLead() {
  error.value = "";
  try {
    const id = Number(editForm.value.id);
    const body: Record<string, unknown> = {
      name: editForm.value.name || undefined,
      intent_level: editForm.value.intent_level,
      status: editForm.value.status,
      remark: editForm.value.remark || undefined,
    };
    if (editForm.value.owner_user_id) {
      body.owner_user_id = Number(editForm.value.owner_user_id);
    }
    await http.patch(`/leads/${id}`, body);
    success.value = "线索已更新";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "更新失败";
  }
}

async function convert(id: number) {
  try {
    await http.post(`/leads/${id}/convert`, {});
    success.value = "已转化为主体";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "转化失败";
  }
}

async function lose(id: number) {
  if (!window.confirm("确认标记丢失？")) return;
  try {
    await http.post(`/leads/${id}/lose`, { reason: "e2e-lose" });
    success.value = "已标记丢失";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "操作失败";
  }
}

function fillEdit(row: Lead) {
  editForm.value = {
    id: String(row.id),
    name: row.name,
    intent_level: row.intent_level || "MEDIUM",
    status: row.status === "NEW" ? "FOLLOWING" : row.status,
    owner_user_id: row.owner_user_id ? String(row.owner_user_id) : "1",
    remark: row.remark || "跟进备注",
  };
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <div>
        <h2 data-testid="leads-title">招商线索</h2>
        <p class="muted">创建 → 跟进 → 转化主体/合同草稿</p>
      </div>
      <button class="btn btn-ghost" type="button" data-testid="lead-refresh" @click="load">
        刷新
      </button>
    </header>

    <form class="create" data-testid="lead-create-form" @submit.prevent="createLead">
      <input
        v-model="form.park_id"
        class="input"
        data-testid="lead-park-id"
        placeholder="园区 ID"
        required
      />
      <input
        v-model="form.name"
        class="input"
        data-testid="lead-name"
        placeholder="客户名称"
        required
      />
      <input
        v-model="form.contact_phone"
        class="input"
        data-testid="lead-phone"
        placeholder="联系电话"
        required
      />
      <select v-model="form.intent_level" class="input" data-testid="lead-intent">
        <option value="HIGH">HIGH</option>
        <option value="MEDIUM">MEDIUM</option>
        <option value="LOW">LOW</option>
      </select>
      <button
        v-permission="'lead:write'"
        class="btn"
        data-testid="lead-create-btn"
        type="submit"
        :disabled="creating"
      >
        {{ creating ? "创建中…" : "新建线索" }}
      </button>
    </form>

    <form class="create" data-testid="lead-edit-form" @submit.prevent="updateLead">
      <input
        v-model="editForm.id"
        class="input"
        data-testid="lead-edit-id"
        placeholder="线索ID"
        required
      />
      <input v-model="editForm.name" class="input" data-testid="lead-edit-name" placeholder="名称" />
      <select v-model="editForm.status" class="input" data-testid="lead-edit-status">
        <option value="NEW">NEW</option>
        <option value="FOLLOWING">FOLLOWING</option>
        <option value="WON">WON</option>
        <option value="LOST">LOST</option>
      </select>
      <input
        v-model="editForm.owner_user_id"
        class="input"
        data-testid="lead-assignee"
        placeholder="负责人用户ID"
      />
      <input
        v-model="editForm.remark"
        class="input"
        data-testid="lead-remark"
        placeholder="跟进备注"
      />
      <button v-permission="'lead:write'" class="btn" data-testid="lead-update-btn" type="submit">
        更新/跟进
      </button>
    </form>

    <p v-if="error" class="error" data-testid="lead-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="lead-success">{{ success }}</p>
    <p v-if="loading" class="muted">加载中…</p>
    <table v-if="!loading" class="table" data-testid="lead-table">
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
        <tr v-for="row in items" :key="row.id" :data-testid="`lead-row-${row.id}`">
          <td data-testid="lead-id-cell">{{ row.id }}</td>
          <td data-testid="lead-name-cell">{{ row.name }}</td>
          <td>{{ row.contact_phone }}</td>
          <td>{{ row.intent_level || "—" }}</td>
          <td><span class="badge" data-testid="lead-status-cell">{{ row.status }}</span></td>
          <td class="ops">
            <button class="btn btn-ghost" type="button" @click="fillEdit(row)">编辑</button>
            <button
              v-if="row.status === 'NEW' || row.status === 'FOLLOWING'"
              v-permission="'lead:convert'"
              class="btn"
              type="button"
              data-testid="lead-convert-btn"
              @click="convert(row.id)"
            >
              转化
            </button>
            <button
              v-if="row.status === 'NEW' || row.status === 'FOLLOWING'"
              v-permission="'lead:write'"
              class="btn"
              type="button"
              data-testid="lead-lose-btn"
              @click="lose(row.id)"
            >
              丢失
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
.ops {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}
.ok {
  color: #047857;
}
</style>
