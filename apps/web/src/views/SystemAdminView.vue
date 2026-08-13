<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope } from "@/api/types";

const tab = ref<"org" | "dict" | "param" | "users" | "roles">("org");
const error = ref("");
const loading = ref(false);
const success = ref("");
const orgs = ref<Array<Record<string, unknown>>>([]);
const params = ref<Array<Record<string, unknown>>>([]);
const users = ref<Array<Record<string, unknown>>>([]);
const roles = ref<Array<Record<string, unknown>>>([]);
const dictTypes = ref<Array<Record<string, unknown>>>([]);
const dictItems = ref<Array<Record<string, unknown>>>([]);
const dictCode = ref("intent_level");

const orgForm = ref({ code: "", name: "" });
const paramForm = ref({ param_key: "", param_value: "", is_secret: false });
const userForm = ref({ username: "", password: "", real_name: "" });
const roleForm = ref({ code: "", name: "" });
const dictTypeForm = ref({ code: "", name: "" });
const dictItemForm = ref({ item_label: "", item_value: "" });
const saving = ref(false);

function flash(msg: string) {
  success.value = msg;
  setTimeout(() => {
    success.value = "";
  }, 2500);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [o, p, u, r, d] = await Promise.all([
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/org-units"),
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/params"),
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/users"),
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/roles"),
      http.get<Envelope<Array<Record<string, unknown>>>>("/system/dict-types"),
    ]);
    orgs.value = o.data.data;
    params.value = p.data.data;
    users.value = u.data.data;
    roles.value = r.data.data;
    dictTypes.value = d.data.data;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadDictItems() {
  try {
    const { data } = await http.get<Envelope<Array<Record<string, unknown>>>>(
      `/system/dict-types/${dictCode.value}/items`
    );
    dictItems.value = data.data;
  } catch {
    dictItems.value = [];
  }
}

async function createOrg() {
  if (saving.value) return;
  saving.value = true;
  try {
    await http.post("/system/org-units", orgForm.value);
    orgForm.value = { code: "", name: "" };
    flash("组织已创建");
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "失败";
  } finally {
    saving.value = false;
  }
}

async function saveParam() {
  if (saving.value) return;
  saving.value = true;
  try {
    await http.put("/system/params", paramForm.value);
    paramForm.value = { param_key: "", param_value: "", is_secret: false };
    flash("参数已保存");
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "失败";
  } finally {
    saving.value = false;
  }
}

async function createUser() {
  if (saving.value) return;
  if (userForm.value.password.length < 6) {
    error.value = "密码至少6位";
    return;
  }
  saving.value = true;
  try {
    await http.post("/system/users", userForm.value);
    userForm.value = { username: "", password: "", real_name: "" };
    flash("用户已创建");
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "失败";
  } finally {
    saving.value = false;
  }
}

async function createRole() {
  if (saving.value) return;
  saving.value = true;
  try {
    await http.post("/system/roles", roleForm.value);
    roleForm.value = { code: "", name: "" };
    flash("角色已创建");
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "失败";
  } finally {
    saving.value = false;
  }
}

async function createDictType() {
  if (saving.value) return;
  saving.value = true;
  try {
    await http.post("/system/dict-types", dictTypeForm.value);
    dictCode.value = dictTypeForm.value.code;
    dictTypeForm.value = { code: "", name: "" };
    flash("字典类型已创建");
    await load();
    await loadDictItems();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "失败";
  } finally {
    saving.value = false;
  }
}

async function createDictItem() {
  if (saving.value) return;
  saving.value = true;
  try {
    await http.post(`/system/dict-types/${dictCode.value}/items`, dictItemForm.value);
    dictItemForm.value = { item_label: "", item_value: "" };
    flash("字典项已创建");
    await loadDictItems();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "失败";
  } finally {
    saving.value = false;
  }
}

async function disableUser(id: number) {
  if (!window.confirm("确认停用该用户？")) return;
  await http.delete(`/system/users/${id}`);
  flash("用户已停用");
  await load();
}

onMounted(async () => {
  await load();
  await loadDictItems();
});
</script>

<template>
  <section class="stack">
    <div class="card panel">
      <h2>系统管理</h2>
      <p class="muted">用户 / 角色 / 组织 / 字典 / 参数 — 真实 CRUD</p>
      <div class="tabs">
        <button type="button" :class="{ on: tab === 'org' }" @click="tab = 'org'">组织</button>
        <button type="button" :class="{ on: tab === 'users' }" @click="tab = 'users'">用户</button>
        <button type="button" :class="{ on: tab === 'roles' }" @click="tab = 'roles'">角色</button>
        <button type="button" :class="{ on: tab === 'dict' }" @click="tab = 'dict'">字典</button>
        <button type="button" :class="{ on: tab === 'param' }" @click="tab = 'param'">参数</button>
      </div>
      <p v-if="loading" class="muted">加载中…</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="success" class="ok">{{ success }}</p>
    </div>

    <div v-show="tab === 'org'" class="card panel">
      <h3>组织架构</h3>
      <form class="create" @submit.prevent="createOrg">
        <input v-model="orgForm.code" class="input" placeholder="编码" required />
        <input v-model="orgForm.name" class="input" placeholder="名称" required />
        <button v-permission="'identity.org.write'" class="btn" type="submit" :disabled="saving">
          新增组织
        </button>
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
          <tr v-if="!orgs.length"><td colspan="3" class="muted">暂无数据</td></tr>
        </tbody>
      </table>
    </div>

    <div v-show="tab === 'users'" class="card panel">
      <h3>用户</h3>
      <form class="create" @submit.prevent="createUser">
        <input v-model="userForm.username" class="input" placeholder="用户名" required />
        <input v-model="userForm.password" class="input" type="password" placeholder="密码" required />
        <input v-model="userForm.real_name" class="input" placeholder="姓名" />
        <button v-permission="'identity.user.write'" class="btn" type="submit" :disabled="saving">
          创建用户
        </button>
      </form>
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>状态</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="String(u.id)">
            <td>{{ u.id }}</td>
            <td>{{ u.username }}</td>
            <td>{{ u.status }}</td>
            <td>
              <button
                v-if="u.status === 'ACTIVE'"
                v-permission="'identity.user.write'"
                class="btn"
                type="button"
                @click="disableUser(Number(u.id))"
              >
                停用
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-show="tab === 'roles'" class="card panel">
      <h3>角色</h3>
      <form class="create" @submit.prevent="createRole">
        <input v-model="roleForm.code" class="input" placeholder="角色码" required />
        <input v-model="roleForm.name" class="input" placeholder="名称" required />
        <button v-permission="'identity.role.write'" class="btn" type="submit" :disabled="saving">
          创建角色
        </button>
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
          <tr v-for="r in roles" :key="String(r.id)">
            <td>{{ r.code }}</td>
            <td>{{ r.name }}</td>
            <td>{{ r.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-show="tab === 'dict'" class="card panel">
      <h3>字典</h3>
      <form class="create" @submit.prevent="createDictType">
        <input v-model="dictTypeForm.code" class="input" placeholder="类型编码" required />
        <input v-model="dictTypeForm.name" class="input" placeholder="类型名称" required />
        <button v-permission="'identity.dict.write'" class="btn" type="submit" :disabled="saving">
          新增类型
        </button>
      </form>
      <div class="tools">
        <select v-model="dictCode" class="input" @change="loadDictItems">
          <option v-for="d in dictTypes" :key="String(d.id)" :value="String(d.code)">
            {{ d.code }} — {{ d.name }}
          </option>
        </select>
      </div>
      <form class="create" @submit.prevent="createDictItem">
        <input v-model="dictItemForm.item_label" class="input" placeholder="标签" required />
        <input v-model="dictItemForm.item_value" class="input" placeholder="值" required />
        <button v-permission="'identity.dict.write'" class="btn" type="submit" :disabled="saving">
          新增项
        </button>
      </form>
      <table class="table">
        <thead>
          <tr>
            <th>标签</th>
            <th>值</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in dictItems" :key="String(it.id)">
            <td>{{ it.item_label }}</td>
            <td>{{ it.item_value }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-show="tab === 'param'" class="card panel">
      <h3>系统参数</h3>
      <form class="create" @submit.prevent="saveParam">
        <input v-model="paramForm.param_key" class="input" placeholder="key" required />
        <input v-model="paramForm.param_value" class="input" placeholder="value" required />
        <label class="chk">
          <input v-model="paramForm.is_secret" type="checkbox" /> 敏感
        </label>
        <button v-permission="'identity.param.write'" class="btn" type="submit" :disabled="saving">
          保存
        </button>
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
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.75rem 0;
}
.tabs button {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
}
.tabs button.on {
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 600;
}
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.6rem;
  margin: 0.8rem 0;
}
.tools {
  margin-bottom: 0.5rem;
}
.ok {
  color: #047857;
}
.chk {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
</style>
