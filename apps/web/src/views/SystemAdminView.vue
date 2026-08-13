<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope } from "@/api/types";

const orgs = ref<Array<Record<string, unknown>>>([]);
const params = ref<Array<Record<string, unknown>>>([]);
const users = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const orgForm = ref({ code: "", name: "" });
const paramForm = ref({ param_key: "", param_value: "" });

async function load() {
  error.value = "";
  try {
    const [o, p, u] = await Promise.all([
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/org-units"),
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/params"),
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/users"),
    ]);
    orgs.value = o.data.data;
    params.value = p.data.data;
    users.value = u.data.data;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  }
}

async function createOrg() {
  await http.post("/system/org-units", orgForm.value);
  orgForm.value = { code: "", name: "" };
  await load();
}

async function saveParam() {
  await http.put("/system/params", {
    param_key: paramForm.value.param_key,
    param_value: paramForm.value.param_value,
  });
  paramForm.value = { param_key: "", param_value: "" };
  await load();
}

onMounted(load);
</script>

<template>
  <section class="stack">
    <div class="card panel">
      <h2>系统管理</h2>
      <p class="muted">组织 / 参数 / 用户（管理端最小页）</p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div class="card panel">
      <h3>组织</h3>
      <form class="create" @submit.prevent="createOrg">
        <input v-model="orgForm.code" class="input" placeholder="编码" required />
        <input v-model="orgForm.name" class="input" placeholder="名称" required />
        <button class="btn" type="submit">新增组织</button>
      </form>
      <table class="table">
        <thead>
          <tr>
            <th>编码</th>
            <th>名称</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orgs" :key="String(o.id)">
            <td>{{ o.code }}</td>
            <td>{{ o.name }}</td>
            <td>{{ o.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card panel">
      <h3>系统参数</h3>
      <form class="create" @submit.prevent="saveParam">
        <input v-model="paramForm.param_key" class="input" placeholder="key" required />
        <input v-model="paramForm.param_value" class="input" placeholder="value" required />
        <button class="btn" type="submit">保存</button>
      </form>
      <table class="table">
        <thead>
          <tr>
            <th>Key</th>
            <th>Value</th>
            <th>Secret</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in params" :key="String(p.id)">
            <td>{{ p.param_key }}</td>
            <td>{{ p.param_value }}</td>
            <td>{{ p.is_secret ? "Y" : "N" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card panel">
      <h3>用户</h3>
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="String(u.id)">
            <td>{{ u.id }}</td>
            <td>{{ u.username }}</td>
            <td>{{ u.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.stack {
  display: grid;
  gap: 1rem;
}
.panel {
  padding: 1rem;
}
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.6rem;
  margin: 0.8rem 0;
}
</style>
