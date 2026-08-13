<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const loading = ref(true);
const keyword = ref("");
const form = ref({ name: "", party_type: "ORGANIZATION", contact_phone: "" });
const contactForm = ref({ party_id: "", name: "", phone: "", email: "" });
const saving = ref(false);

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
  if (saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    await http.post("/parties", {
      name: form.value.name.trim(),
      party_type: form.value.party_type,
      contact_phone: form.value.contact_phone || undefined,
    });
    success.value = "主体已创建";
    form.value.name = "";
    form.value.contact_phone = "";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  } finally {
    saving.value = false;
  }
}

async function addContact() {
  if (saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    const partyId = Number(contactForm.value.party_id);
    await http.post(`/parties/${partyId}/contacts`, {
      name: contactForm.value.name,
      phone: contactForm.value.phone || undefined,
      email: contactForm.value.email || undefined,
      is_primary: true,
    });
    success.value = "联系人已添加";
    contactForm.value = { party_id: "", name: "", phone: "", email: "" };
  } catch (e) {
    error.value = e instanceof Error ? e.message : "添加联系人失败";
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <h2 data-testid="parties-title">主体</h2>
      <div class="tools">
        <input
          v-model="keyword"
          class="input"
          data-testid="party-keyword"
          placeholder="关键词"
          @keyup.enter="load"
        />
        <button class="btn btn-ghost" type="button" data-testid="party-filter-btn" @click="load">
          筛选
        </button>
      </div>
    </header>
    <form class="create" data-testid="party-create-form" @submit.prevent="create">
      <input v-model="form.name" class="input" data-testid="party-name" placeholder="名称" required />
      <select v-model="form.party_type" class="input" data-testid="party-type">
        <option value="ORGANIZATION">ORGANIZATION</option>
        <option value="PERSON">PERSON</option>
      </select>
      <input
        v-model="form.contact_phone"
        class="input"
        data-testid="party-phone"
        placeholder="联系电话"
      />
      <button
        v-permission="'party:write'"
        class="btn"
        data-testid="party-create-btn"
        type="submit"
        :disabled="saving"
      >
        新建
      </button>
    </form>
    <form class="create" data-testid="party-contact-form" @submit.prevent="addContact">
      <input
        v-model="contactForm.party_id"
        class="input"
        data-testid="contact-party-id"
        placeholder="主体ID"
        required
      />
      <input
        v-model="contactForm.name"
        class="input"
        data-testid="contact-name"
        placeholder="联系人姓名"
        required
      />
      <input v-model="contactForm.phone" class="input" data-testid="contact-phone" placeholder="电话" />
      <button
        v-permission="'party:write'"
        class="btn"
        data-testid="contact-create-btn"
        type="submit"
        :disabled="saving"
      >
        添加联系人
      </button>
    </form>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-if="error" class="error" data-testid="party-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="party-success">{{ success }}</p>
    <table v-if="!loading" class="table" data-testid="party-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>类型</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in items" :key="String(p.id)" :data-testid="`party-row-${p.id}`">
          <td data-testid="party-id-cell">{{ p.id }}</td>
          <td data-testid="party-name-cell">{{ p.name }}</td>
          <td>{{ p.party_type }}</td>
          <td data-testid="party-status-cell">{{ p.status }}</td>
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
.ok {
  color: #047857;
}
</style>
