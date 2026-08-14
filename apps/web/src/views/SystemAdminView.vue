<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope } from "@/api/types";
import OrganizationGovernancePanel from "@/components/OrganizationGovernancePanel.vue";

type Tab = "governance" | "org" | "users" | "roles" | "menus" | "dict" | "param";
type OrgRow = { id: number; code: string; name: string; status: string };
type ParamRow = {
  id: number;
  param_key: string;
  param_value: string;
  is_secret: boolean;
};
type DictTypeRow = { id: number; code: string; name: string };
type DictItemRow = { id: number; item_label: string; item_value: string };
type ParkRow = { id: number; name: string };
type PermissionRow = { id: number; code: string; name: string; module: string };
type MenuRow = {
  id: number;
  name: string;
  path: string;
  parent_id: number | null;
  menu_type: string;
  status: string;
  permission_code: string | null;
};
type RoleRow = {
  id: number;
  code: string;
  name: string;
  status: string;
  all_parks: boolean;
  permission_codes: string[];
  park_ids: number[];
  menu_ids: number[];
  remark?: string | null;
};
type UserRow = {
  id: number;
  username: string;
  real_name: string;
  phone?: string | null;
  status: string;
  all_parks: boolean;
  role_ids: number[];
  park_ids: number[];
};
type ScopeMode = "ALL" | "LIST" | "NONE";
type UserForm = {
  id: number | null;
  username: string;
  password: string;
  real_name: string;
  phone: string;
  role_ids: number[];
  scope_mode: ScopeMode;
  park_ids: number[];
};
type RoleForm = {
  id: number | null;
  code: string;
  name: string;
  remark: string;
  permission_codes: string[];
  scope_mode: ScopeMode;
  park_ids: number[];
  menu_ids: number[];
};
type MenuForm = {
  id: number | null;
  name: string;
  path: string;
  parent_id: string;
  menu_type: string;
  status: string;
  permission_code: string;
};

const tab = ref<Tab>("governance");
const error = ref("");
const loading = ref(false);
const saving = ref(false);
const success = ref("");
const orgs = ref<OrgRow[]>([]);
const params = ref<ParamRow[]>([]);
const users = ref<UserRow[]>([]);
const roles = ref<RoleRow[]>([]);
const menus = ref<MenuRow[]>([]);
const permissions = ref<PermissionRow[]>([]);
const parks = ref<ParkRow[]>([]);
const dictTypes = ref<DictTypeRow[]>([]);
const dictItems = ref<DictItemRow[]>([]);
const dictCode = ref("intent_level");

const orgForm = ref({ code: "", name: "" });
const paramForm = ref({ param_key: "", param_value: "", is_secret: false });
const userForm = ref<UserForm>(emptyUserForm());
const roleForm = ref<RoleForm>(emptyRoleForm());
const menuForm = ref<MenuForm>(emptyMenuForm());
const dictTypeForm = ref({ code: "", name: "" });
const dictItemForm = ref({ item_label: "", item_value: "" });

function emptyUserForm(): UserForm {
  return {
    id: null,
    username: "",
    password: "",
    real_name: "",
    phone: "",
    role_ids: [],
    scope_mode: "NONE",
    park_ids: [],
  };
}

function emptyRoleForm(): RoleForm {
  return {
    id: null,
    code: "",
    name: "",
    remark: "",
    permission_codes: [],
    scope_mode: "NONE",
    park_ids: [],
    menu_ids: [],
  };
}

function emptyMenuForm(): MenuForm {
  return {
    id: null,
    name: "",
    path: "",
    parent_id: "",
    menu_type: "MENU",
    status: "ACTIVE",
    permission_code: "",
  };
}

function listData<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && Array.isArray((value as { items?: unknown }).items)) {
    return (value as { items: T[] }).items;
  }
  return [];
}

function scopePayload(mode: ScopeMode, parkIds: number[]) {
  return {
    all_parks: mode === "ALL",
    park_ids: mode === "LIST" ? parkIds : [],
  };
}

function scopeMode(row: { all_parks: boolean; park_ids: number[] }): ScopeMode {
  if (row.all_parks) return "ALL";
  return row.park_ids.length ? "LIST" : "NONE";
}

let latestMutationId = 0;
let successTimer: number | undefined;

function beginMutation() {
  error.value = "";
  return ++latestMutationId;
}

function flash(message: string, mutationId: number) {
  if (mutationId !== latestMutationId) return;
  success.value = message;
  if (successTimer !== undefined) window.clearTimeout(successTimer);
  successTimer = window.setTimeout(() => {
    if (mutationId === latestMutationId) success.value = "";
  }, 2500);
}

function fail(reason: unknown, mutationId?: number) {
  if (mutationId !== undefined && mutationId !== latestMutationId) return;
  error.value = reason instanceof Error ? reason.message : "操作失败";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [o, p, u, r, d, permissionResult, menuResult, parkResult] =
      await Promise.all([
        http.get<Envelope<OrgRow[]>>("/system/org-units"),
        http.get<Envelope<ParamRow[]>>("/system/params"),
        http.get<Envelope<UserRow[]>>("/system/users"),
        http.get<Envelope<RoleRow[]>>("/system/roles"),
        http.get<Envelope<DictTypeRow[]>>("/system/dict-types"),
        http.get<Envelope<PermissionRow[]>>("/system/permissions"),
        http.get<Envelope<MenuRow[]>>("/system/menus"),
        http.get<Envelope<unknown>>("/parks", { params: { page_size: 200 } }),
      ]);
    orgs.value = o.data.data;
    params.value = p.data.data;
    users.value = u.data.data;
    roles.value = r.data.data;
    dictTypes.value = d.data.data;
    if (!dictTypes.value.some((item) => item.code === dictCode.value)) {
      dictCode.value = dictTypes.value[0]?.code || "";
    }
    permissions.value = permissionResult.data.data;
    menus.value = menuResult.data.data;
    parks.value = listData<ParkRow>(parkResult.data.data);
  } catch (reason) {
    fail(reason);
  } finally {
    loading.value = false;
  }
}

async function loadDictItems() {
  if (!dictCode.value) {
    dictItems.value = [];
    return;
  }
  try {
    const { data } = await http.get<Envelope<DictItemRow[]>>(
      `/system/dict-types/${dictCode.value}/items`
    );
    dictItems.value = data.data;
  } catch {
    dictItems.value = [];
  }
}

async function createOrg() {
  if (saving.value) return;
  const mutationId = beginMutation();
  saving.value = true;
  try {
    await http.post("/system/org-units", orgForm.value);
    orgForm.value = { code: "", name: "" };
    flash("组织已创建", mutationId);
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  } finally {
    saving.value = false;
  }
}

async function saveParam() {
  if (saving.value) return;
  const mutationId = beginMutation();
  saving.value = true;
  try {
    await http.put("/system/params", paramForm.value);
    paramForm.value = { param_key: "", param_value: "", is_secret: false };
    flash("参数已保存", mutationId);
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  } finally {
    saving.value = false;
  }
}

function passwordPolicyError(password: string, username: string): string | null {
  if (password.length < 10) return "密码至少 10 位";
  const categories = [/[a-z]/.test(password), /[A-Z]/.test(password), /\d/.test(password), /[^A-Za-z0-9]/.test(password)].filter(Boolean).length;
  if (categories < 3) return "密码须包含大写、小写、数字、特殊字符中的至少三类";
  if (username.length >= 3 && password.toLowerCase().includes(username.toLowerCase())) return "密码不得包含完整账号名";
  if (["password", "qwerty", "123456", "admin123"].some((part) => password.toLowerCase().includes(part))) return "密码包含常见弱口令片段";
  return null;
}

async function saveUser() {
  if (saving.value) return;
  const passwordError = userForm.value.password
    ? passwordPolicyError(userForm.value.password, userForm.value.username)
    : null;
  if ((!userForm.value.id && !userForm.value.password) || passwordError) {
    error.value = passwordError || "新用户必须设置密码";
    return;
  }
  const mutationId = beginMutation();
  saving.value = true;
  try {
    const scope = scopePayload(userForm.value.scope_mode, userForm.value.park_ids);
    const common = {
      real_name: userForm.value.real_name,
      phone: userForm.value.phone || null,
      role_ids: userForm.value.role_ids,
      ...scope,
    };
    if (userForm.value.id) {
      await http.put(`/system/users/${userForm.value.id}`, {
        ...common,
        ...(userForm.value.password ? { password: userForm.value.password } : {}),
      });
      flash("用户授权已更新，旧会话已失效", mutationId);
    } else {
      await http.post("/system/users", {
        username: userForm.value.username,
        password: userForm.value.password,
        ...common,
      });
      flash("用户已创建", mutationId);
    }
    userForm.value = emptyUserForm();
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  } finally {
    saving.value = false;
  }
}

function editUser(user: UserRow) {
  tab.value = "users";
  userForm.value = {
    id: user.id,
    username: user.username,
    password: "",
    real_name: user.real_name || "",
    phone: user.phone || "",
    role_ids: [...user.role_ids],
    scope_mode: scopeMode(user),
    park_ids: [...user.park_ids],
  };
}

async function setUserStatus(user: UserRow, enabled: boolean) {
  if (!window.confirm(enabled ? "确认启用该用户？" : "确认停用该用户？")) return;
  const mutationId = beginMutation();
  try {
    if (enabled) {
      await http.put(`/system/users/${user.id}`, { status: "ACTIVE" });
    } else {
      await http.delete(`/system/users/${user.id}`);
    }
    flash(enabled ? "用户已启用" : "用户已停用，旧会话已失效", mutationId);
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  }
}

async function revokeUserSessions(user: UserRow) {
  if (!window.confirm(`确认撤销 ${user.username} 的全部会话？`)) return;
  const mutationId = beginMutation();
  try {
    await http.post(`/system/users/${user.id}/revoke-sessions`);
    flash("用户会话已撤销", mutationId);
  } catch (reason) {
    fail(reason, mutationId);
  }
}

async function saveRole() {
  if (saving.value) return;
  const mutationId = beginMutation();
  saving.value = true;
  try {
    const payload = {
      name: roleForm.value.name,
      remark: roleForm.value.remark || null,
      permission_codes: roleForm.value.permission_codes,
      menu_ids: roleForm.value.menu_ids,
      ...scopePayload(roleForm.value.scope_mode, roleForm.value.park_ids),
    };
    if (roleForm.value.id) {
      await http.put(`/system/roles/${roleForm.value.id}`, payload);
      flash("角色授权已更新，相关用户旧会话已失效", mutationId);
    } else {
      await http.post("/system/roles", {
        code: roleForm.value.code,
        ...payload,
      });
      flash("角色已创建", mutationId);
    }
    roleForm.value = emptyRoleForm();
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  } finally {
    saving.value = false;
  }
}

function editRole(role: RoleRow) {
  tab.value = "roles";
  roleForm.value = {
    id: role.id,
    code: role.code,
    name: role.name,
    remark: role.remark || "",
    permission_codes: [...role.permission_codes],
    scope_mode: scopeMode(role),
    park_ids: [...role.park_ids],
    menu_ids: [...role.menu_ids],
  };
}

async function deactivateRole(role: RoleRow) {
  if (!window.confirm(`确认停用角色 ${role.code}？`)) return;
  const mutationId = beginMutation();
  try {
    await http.put(`/system/roles/${role.id}`, { status: "DISABLED" });
    flash("角色已停用，相关用户旧会话已失效", mutationId);
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  }
}

async function saveMenu() {
  if (saving.value) return;
  const mutationId = beginMutation();
  saving.value = true;
  try {
    const payload = {
      name: menuForm.value.name,
      path: menuForm.value.path,
      parent_id: menuForm.value.parent_id ? Number(menuForm.value.parent_id) : null,
      menu_type: menuForm.value.menu_type,
      status: menuForm.value.status,
      permission_code: menuForm.value.permission_code || null,
    };
    if (menuForm.value.id) {
      await http.put(`/system/menus/${menuForm.value.id}`, payload);
      flash("菜单已更新", mutationId);
    } else {
      await http.post("/system/menus", payload);
      flash("菜单已创建", mutationId);
    }
    menuForm.value = emptyMenuForm();
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  } finally {
    saving.value = false;
  }
}

function editMenu(menu: MenuRow) {
  menuForm.value = {
    id: menu.id,
    name: menu.name,
    path: menu.path,
    parent_id: menu.parent_id ? String(menu.parent_id) : "",
    menu_type: menu.menu_type,
    status: menu.status,
    permission_code: menu.permission_code || "",
  };
}

async function deactivateMenu(menu: MenuRow) {
  if (!window.confirm(`确认停用菜单 ${menu.name} 及其子菜单？`)) return;
  const mutationId = beginMutation();
  try {
    await http.delete(`/system/menus/${menu.id}`);
    flash("菜单及子菜单已停用", mutationId);
    await load();
  } catch (reason) {
    fail(reason, mutationId);
  }
}

async function createDictType() {
  if (saving.value) return;
  const mutationId = beginMutation();
  saving.value = true;
  try {
    await http.post("/system/dict-types", dictTypeForm.value);
    dictCode.value = dictTypeForm.value.code;
    dictTypeForm.value = { code: "", name: "" };
    flash("字典类型已创建", mutationId);
    await load();
    await loadDictItems();
  } catch (reason) {
    fail(reason, mutationId);
  } finally {
    saving.value = false;
  }
}

async function createDictItem() {
  if (saving.value) return;
  const mutationId = beginMutation();
  saving.value = true;
  try {
    await http.post(`/system/dict-types/${dictCode.value}/items`, dictItemForm.value);
    dictItemForm.value = { item_label: "", item_value: "" };
    flash("字典项已创建", mutationId);
    await loadDictItems();
  } catch (reason) {
    fail(reason, mutationId);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await load();
  await loadDictItems();
});
</script>

<template>
  <section class="stack">
    <div class="card panel">
      <h2 data-testid="system-title">系统管理</h2>
      <p class="muted">用户、角色、动作权限、菜单与园区范围独立授权；安全变更即时撤销旧会话。</p>
      <nav class="tabs" data-testid="system-tabs" aria-label="系统管理分类">
        <button type="button" data-testid="tab-governance" :class="{ on: tab === 'governance' }" @click="tab = 'governance'">组织治理</button>
        <button type="button" data-testid="tab-org" :class="{ on: tab === 'org' }" @click="tab = 'org'">部门树</button>
        <button type="button" data-testid="tab-users" :class="{ on: tab === 'users' }" @click="tab = 'users'">用户</button>
        <button type="button" data-testid="tab-roles" :class="{ on: tab === 'roles' }" @click="tab = 'roles'">角色</button>
        <button type="button" data-testid="tab-menus" :class="{ on: tab === 'menus' }" @click="tab = 'menus'">菜单</button>
        <button type="button" data-testid="tab-dict" :class="{ on: tab === 'dict' }" @click="tab = 'dict'">字典</button>
        <button type="button" data-testid="tab-param" :class="{ on: tab === 'param' }" @click="tab = 'param'">参数</button>
      </nav>
      <p v-if="loading" class="muted" role="status">加载中…</p>
      <p v-if="error" class="error" data-testid="system-error" role="alert">{{ error }}</p>
      <p v-if="success" class="ok" data-testid="system-success" role="status">{{ success }}</p>
    </div>

    <div v-show="tab === 'governance'" class="card panel">
      <OrganizationGovernancePanel />
    </div>

    <div v-show="tab === 'org'" class="card panel">
      <h3>组织架构</h3>
      <form class="form-grid" data-testid="org-create-form" @submit.prevent="createOrg">
        <label>编码<input v-model="orgForm.code" class="input" data-testid="org-code" required /></label>
        <label>名称<input v-model="orgForm.name" class="input" data-testid="org-name" required /></label>
        <button v-permission="'identity.org.write'" class="btn align-end" data-testid="org-create-btn" type="submit" :disabled="saving">新增组织</button>
      </form>
      <div class="table-wrap">
        <table class="table" data-testid="org-table">
          <thead><tr><th>编码</th><th>名称</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="o in orgs" :key="o.id"><td data-testid="org-code-cell">{{ o.code }}</td><td>{{ o.name }}</td><td>{{ o.status }}</td></tr>
            <tr v-if="!orgs.length"><td colspan="3" class="muted">暂无数据</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-show="tab === 'users'" class="card panel">
      <div class="section-head">
        <h3>{{ userForm.id ? '编辑用户授权' : '创建用户' }}</h3>
        <button v-if="userForm.id" class="btn secondary" type="button" @click="userForm = emptyUserForm()">取消编辑</button>
      </div>
      <form class="form-grid wide" data-testid="user-create-form" @submit.prevent="saveUser">
        <label>用户名<input v-model="userForm.username" class="input" data-testid="user-username" :disabled="Boolean(userForm.id)" required /></label>
        <label>{{ userForm.id ? '新密码（留空不改）' : '密码' }}<input v-model="userForm.password" class="input" data-testid="user-password" type="password" :required="!userForm.id" /></label>
        <label>姓名<input v-model="userForm.real_name" class="input" data-testid="user-realname" /></label>
        <label>手机号<input v-model="userForm.phone" class="input" data-testid="user-phone" autocomplete="tel" /></label>
        <label>角色
          <select v-model="userForm.role_ids" class="input multi" data-testid="user-roles" multiple>
            <option v-for="role in roles.filter((item) => item.status === 'ACTIVE')" :key="role.id" :value="role.id">{{ role.code }} — {{ role.name }}</option>
          </select>
        </label>
        <label>园区范围
          <select v-model="userForm.scope_mode" class="input" data-testid="user-scope-mode">
            <option value="NONE">无园区</option><option value="LIST">指定园区</option><option value="ALL">全部园区</option>
          </select>
        </label>
        <label v-if="userForm.scope_mode === 'LIST'">指定园区
          <select v-model="userForm.park_ids" class="input multi" data-testid="user-parks" multiple>
            <option v-for="park in parks" :key="park.id" :value="park.id">{{ park.name }}</option>
          </select>
        </label>
        <button v-permission="'identity.user.write'" class="btn align-end" data-testid="user-create-btn" type="submit" :disabled="saving">{{ userForm.id ? '保存用户' : '创建用户' }}</button>
      </form>
      <div class="table-wrap">
        <table class="table" data-testid="user-table">
          <thead><tr><th>用户名</th><th>手机号（服务端策略）</th><th>角色</th><th>园区范围</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="user in users" :key="user.id" :data-testid="`user-row-${user.username}`">
              <td data-testid="user-name-cell">{{ user.username }}</td>
              <td data-testid="user-phone-projected">{{ Object.prototype.hasOwnProperty.call(user, "phone") ? user.phone || "—" : "字段已隐藏" }}</td>
              <td>{{ user.role_ids.length }}</td>
              <td>{{ scopeMode(user) }}<span v-if="user.park_ids.length"> ({{ user.park_ids.length }})</span></td>
              <td data-testid="user-status-cell">{{ user.status }}</td>
              <td class="actions">
                <button v-permission="'identity.user.write'" class="link-btn" type="button" :data-testid="`user-edit-${user.username}`" @click="editUser(user)">编辑</button>
                <button v-permission="'identity.user.write'" class="link-btn" type="button" :data-testid="`user-revoke-${user.username}`" @click="revokeUserSessions(user)">撤销会话</button>
                <button v-if="user.username !== 'admin'" v-permission="'identity.user.write'" class="link-btn danger" type="button" :data-testid="`user-status-${user.username}`" @click="setUserStatus(user, user.status !== 'ACTIVE')">{{ user.status === 'ACTIVE' ? '停用' : '启用' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-show="tab === 'roles'" class="card panel">
      <div class="section-head">
        <h3>{{ roleForm.id ? '编辑角色授权' : '创建角色' }}</h3>
        <button v-if="roleForm.id" class="btn secondary" type="button" @click="roleForm = emptyRoleForm()">取消编辑</button>
      </div>
      <form class="form-grid wide" data-testid="role-create-form" @submit.prevent="saveRole">
        <label>角色码<input v-model="roleForm.code" class="input" data-testid="role-code" :disabled="Boolean(roleForm.id)" required /></label>
        <label>名称<input v-model="roleForm.name" class="input" data-testid="role-name" required /></label>
        <label>备注<input v-model="roleForm.remark" class="input" data-testid="role-remark" /></label>
        <label>动作权限
          <select v-model="roleForm.permission_codes" class="input multi tall" data-testid="role-perms" multiple>
            <option v-for="permission in permissions" :key="permission.id" :value="permission.code">{{ permission.module }} / {{ permission.name }} / {{ permission.code }}</option>
          </select>
        </label>
        <label>园区范围
          <select v-model="roleForm.scope_mode" class="input" data-testid="role-scope-mode">
            <option value="NONE">无园区</option><option value="LIST">指定园区</option><option value="ALL">全部园区</option>
          </select>
        </label>
        <label v-if="roleForm.scope_mode === 'LIST'">指定园区
          <select v-model="roleForm.park_ids" class="input multi" data-testid="role-parks" multiple>
            <option v-for="park in parks" :key="park.id" :value="park.id">{{ park.name }}</option>
          </select>
        </label>
        <label>可见菜单
          <select v-model="roleForm.menu_ids" class="input multi tall" data-testid="role-menus" multiple>
            <option v-for="menu in menus.filter((item) => item.status === 'ACTIVE')" :key="menu.id" :value="menu.id">{{ menu.name }} — {{ menu.path || menu.menu_type }}</option>
          </select>
        </label>
        <button v-permission="'identity.role.write'" class="btn align-end" data-testid="role-create-btn" type="submit" :disabled="saving">{{ roleForm.id ? '保存角色' : '创建角色' }}</button>
      </form>
      <div class="table-wrap">
        <table class="table" data-testid="role-table">
          <thead><tr><th>编码</th><th>权限</th><th>园区范围</th><th>菜单</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="role in roles" :key="role.id" :data-testid="`role-row-${role.code}`">
              <td data-testid="role-code-cell">{{ role.code }}<div class="muted small">{{ role.name }}</div></td>
              <td>{{ role.permission_codes.length }}</td><td>{{ scopeMode(role) }}</td><td>{{ role.menu_ids.length }}</td><td>{{ role.status }}</td>
              <td class="actions">
                <button v-permission="'identity.role.write'" class="link-btn" type="button" :data-testid="`role-edit-${role.code}`" @click="editRole(role)">编辑</button>
                <button v-if="role.code !== 'ADMIN' && role.status === 'ACTIVE'" v-permission="'identity.role.write'" class="link-btn danger" type="button" :data-testid="`role-disable-${role.code}`" @click="deactivateRole(role)">停用</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-show="tab === 'menus'" class="card panel">
      <div class="section-head"><h3>{{ menuForm.id ? '编辑菜单' : '创建菜单' }}</h3><button v-if="menuForm.id" class="btn secondary" type="button" @click="menuForm = emptyMenuForm()">取消编辑</button></div>
      <form class="form-grid wide" data-testid="menu-form" @submit.prevent="saveMenu">
        <label>名称<input v-model="menuForm.name" class="input" data-testid="menu-name" required /></label>
        <label>路径<input v-model="menuForm.path" class="input" data-testid="menu-path" /></label>
        <label>上级
          <select v-model="menuForm.parent_id" class="input" data-testid="menu-parent"><option value="">根节点</option><option v-for="menu in menus.filter((item) => item.id !== menuForm.id)" :key="menu.id" :value="String(menu.id)">{{ menu.name }}</option></select>
        </label>
        <label>类型<select v-model="menuForm.menu_type" class="input" data-testid="menu-type"><option value="DIR">目录</option><option value="MENU">页面</option><option value="BUTTON">按钮</option></select></label>
        <label>动作权限<select v-model="menuForm.permission_code" class="input" data-testid="menu-permission"><option value="">无</option><option v-for="permission in permissions" :key="permission.id" :value="permission.code">{{ permission.code }}</option></select></label>
        <label>状态<select v-model="menuForm.status" class="input" data-testid="menu-status"><option value="ACTIVE">启用</option><option value="DISABLED">停用</option></select></label>
        <button v-permission="'identity.menu.write'" class="btn align-end" data-testid="menu-save-btn" type="submit" :disabled="saving">{{ menuForm.id ? '保存菜单' : '创建菜单' }}</button>
      </form>
      <div class="table-wrap"><table class="table" data-testid="menu-table"><thead><tr><th>名称</th><th>路径</th><th>类型</th><th>权限</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="menu in menus" :key="menu.id" :data-testid="`menu-row-${menu.id}`"><td>{{ menu.name }}</td><td>{{ menu.path || '—' }}</td><td>{{ menu.menu_type }}</td><td>{{ menu.permission_code || '—' }}</td><td>{{ menu.status }}</td><td class="actions"><button v-permission="'identity.menu.write'" class="link-btn" type="button" :data-testid="`menu-edit-${menu.id}`" @click="editMenu(menu)">编辑</button><button v-if="menu.status === 'ACTIVE'" v-permission="'identity.menu.write'" class="link-btn danger" type="button" :data-testid="`menu-disable-${menu.id}`" @click="deactivateMenu(menu)">停用</button></td></tr></tbody></table></div>
    </div>

    <div v-show="tab === 'dict'" class="card panel">
      <h3>字典</h3>
      <form class="form-grid" data-testid="dict-type-form" @submit.prevent="createDictType"><label>类型编码<input v-model="dictTypeForm.code" class="input" data-testid="dict-type-code" required /></label><label>类型名称<input v-model="dictTypeForm.name" class="input" data-testid="dict-type-name" required /></label><button v-permission="'identity.dict.write'" class="btn align-end" data-testid="dict-type-btn" type="submit" :disabled="saving">新增类型</button></form>
      <label>当前类型<select v-model="dictCode" class="input" data-testid="dict-type-select" @change="loadDictItems"><option v-for="d in dictTypes" :key="d.id" :value="d.code">{{ d.code }} — {{ d.name }}</option></select></label>
      <form class="form-grid" data-testid="dict-item-form" @submit.prevent="createDictItem"><label>标签<input v-model="dictItemForm.item_label" class="input" data-testid="dict-item-label" required /></label><label>值<input v-model="dictItemForm.item_value" class="input" data-testid="dict-item-value" required /></label><button v-permission="'identity.dict.write'" class="btn align-end" data-testid="dict-item-btn" type="submit" :disabled="saving">新增项</button></form>
      <div class="table-wrap"><table class="table" data-testid="dict-item-table"><thead><tr><th>标签</th><th>值</th></tr></thead><tbody><tr v-for="item in dictItems" :key="item.id"><td data-testid="dict-label-cell">{{ item.item_label }}</td><td>{{ item.item_value }}</td></tr></tbody></table></div>
    </div>

    <div v-show="tab === 'param'" class="card panel">
      <h3>系统参数</h3>
      <form class="form-grid" data-testid="param-form" @submit.prevent="saveParam"><label>Key<input v-model="paramForm.param_key" class="input" data-testid="param-key" required /></label><label>Value<input v-model="paramForm.param_value" class="input" data-testid="param-value" required /></label><label class="checkbox align-end"><input v-model="paramForm.is_secret" type="checkbox" data-testid="param-secret" /> 敏感参数</label><button v-permission="'identity.param.write'" class="btn align-end" data-testid="param-save-btn" type="submit" :disabled="saving">保存</button></form>
      <div class="table-wrap"><table class="table" data-testid="param-table"><thead><tr><th>Key</th><th>Value</th><th>Secret</th></tr></thead><tbody><tr v-for="param in params" :key="param.id" :data-testid="`param-row-${param.param_key}`"><td data-testid="param-key-cell">{{ param.param_key }}</td><td data-testid="param-value-cell">{{ param.param_value }}</td><td>{{ param.is_secret ? 'Y' : 'N' }}</td></tr></tbody></table></div>
    </div>
  </section>
</template>

<style scoped>
.stack { display: grid; gap: 1rem; min-width: 0; }
.panel { min-width: 0; padding: 1rem; }
.tabs { display: flex; flex-wrap: wrap; gap: .4rem; margin: .75rem 0; }
.tabs button { border: 1px solid var(--border); background: #fff; border-radius: 8px; padding: .45rem .8rem; cursor: pointer; }
.tabs button.on { background: var(--primary-soft); color: var(--primary); font-weight: 600; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; margin: .8rem 0 1rem; align-items: start; }
.form-grid.wide { grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
label { display: grid; gap: .35rem; color: var(--text-secondary, #475569); font-size: .88rem; }
.multi { min-height: 5rem; }
.multi.tall { min-height: 8rem; }
.align-end { align-self: end; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.table-wrap { overflow-x: auto; }
.actions { display: flex; flex-wrap: wrap; gap: .5rem; min-width: 160px; }
.link-btn { border: 0; background: transparent; color: var(--primary); padding: .15rem; cursor: pointer; }
.link-btn.danger { color: #b91c1c; }
.secondary { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ok { color: #047857; }
.checkbox { display: flex; grid-auto-flow: column; justify-content: start; align-items: center; }
.small { font-size: .78rem; }
@media (max-width: 720px) {
  .panel { padding: .8rem; }
  .form-grid, .form-grid.wide { grid-template-columns: 1fr; }
  .tabs { overflow-x: auto; flex-wrap: nowrap; padding-bottom: .25rem; }
  .tabs button { white-space: nowrap; }
}
</style>
