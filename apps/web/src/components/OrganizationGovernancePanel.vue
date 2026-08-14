<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type ParkRow = { id: number; name: string; status?: string };
type OrgRow = { id: number; code: string; name: string };
type UserRow = { id: number; username: string; real_name: string; phone?: string | null };
type RoleRow = { id: number; code: string; name: string };
type RegionRow = {
  id: number;
  group_id: number;
  code: string;
  name: string;
  status: string;
  parks: Array<ParkRow & { assignment_id: number; effective_from: string }>;
};
type GroupRow = {
  id: number;
  code: string;
  name: string;
  status: string;
  regions: RegionRow[];
};
type PositionRow = {
  id: number;
  org_unit_id: number | null;
  code: string;
  name: string;
  status: string;
  responsibilities?: string | null;
};
type AssignmentRow = {
  id: number;
  user_id: number;
  position_id: number;
  park_id: number | null;
  starts_at: string;
  ends_at: string | null;
  is_primary: boolean;
};
type PolicyRow = {
  id: number;
  role_id: number;
  resource_type: string;
  field_name: string;
  access_mode: "VISIBLE" | "MASKED" | "HIDDEN";
  status: string;
};
type ProtectedField = { resource_type: string; field_name: string; mask_strategy: string };

function listData<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && Array.isArray((value as { items?: unknown }).items)) {
    return (value as { items: T[] }).items;
  }
  return [];
}

const auth = useAuthStore();
const canWrite = computed(() => auth.can("identity.org_governance.write"));
const canPolicyRead = computed(() => auth.can("identity.field_policy.read"));
const canPolicyWrite = computed(() => auth.can("identity.field_policy.write"));
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const groups = ref<GroupRow[]>([]);
const positions = ref<PositionRow[]>([]);
const assignments = ref<AssignmentRow[]>([]);
const policies = ref<PolicyRow[]>([]);
const protectedFields = ref<ProtectedField[]>([]);
const parks = ref<ParkRow[]>([]);
const orgs = ref<OrgRow[]>([]);
const users = ref<UserRow[]>([]);
const roles = ref<RoleRow[]>([]);

const allRegions = computed(() => groups.value.flatMap((group) => group.regions));
const groupForm = ref({ code: "", name: "" });
const regionForm = ref({ group_id: 0, code: "", name: "" });
const parkForm = ref({ region_id: 0, park_id: 0, reason: "" });
const positionForm = ref({ code: "", name: "", org_unit_id: 0, responsibilities: "" });
const assignmentForm = ref({ user_id: 0, position_id: 0, park_id: 0, is_primary: false });
const policyForm = ref({
  role_id: 0,
  resource_type: "USER",
  field_name: "phone",
  access_mode: "MASKED" as PolicyRow["access_mode"],
});

function fail(reason: unknown) {
  errorStatus.value = reason instanceof ApiRequestError ? reason.status : 0;
  error.value = reason instanceof Error ? reason.message : "操作失败";
}

async function load() {
  loading.value = true;
  error.value = "";
  errorStatus.value = 0;
  try {
    const [hierarchyResult, positionResult, assignmentResult, parkResult, orgResult, userResult, roleResult] =
      await Promise.all([
        http.get<Envelope<{ groups: GroupRow[] }>>("/system/organization-governance/hierarchy"),
        http.get<Envelope<PositionRow[]>>("/system/organization-governance/positions"),
        http.get<Envelope<AssignmentRow[]>>("/system/organization-governance/user-assignments"),
        http.get<Envelope<unknown>>("/parks", { params: { page_size: 200 } }),
        http.get<Envelope<OrgRow[]>>("/system/org-units"),
        http.get<Envelope<UserRow[]>>("/system/users"),
        http.get<Envelope<RoleRow[]>>("/system/roles"),
      ]);
    groups.value = hierarchyResult.data.data.groups;
    positions.value = positionResult.data.data;
    assignments.value = assignmentResult.data.data;
    parks.value = listData<ParkRow>(parkResult.data.data);
    orgs.value = orgResult.data.data;
    users.value = userResult.data.data;
    roles.value = roleResult.data.data;
    if (canPolicyRead.value) {
      const [policyResult, protectedResult] = await Promise.all([
        http.get<Envelope<PolicyRow[]>>("/system/organization-governance/field-policies"),
        http.get<Envelope<ProtectedField[]>>("/system/organization-governance/protected-fields"),
      ]);
      policies.value = policyResult.data.data;
      protectedFields.value = protectedResult.data.data;
    } else {
      policies.value = [];
      protectedFields.value = [];
    }
    if (!regionForm.value.group_id) regionForm.value.group_id = groups.value[0]?.id || 0;
    if (!parkForm.value.region_id) parkForm.value.region_id = allRegions.value[0]?.id || 0;
    if (!parkForm.value.park_id) parkForm.value.park_id = parks.value[0]?.id || 0;
    if (!positionForm.value.org_unit_id) positionForm.value.org_unit_id = orgs.value[0]?.id || 0;
    if (!assignmentForm.value.user_id) assignmentForm.value.user_id = users.value[0]?.id || 0;
    if (!assignmentForm.value.position_id) assignmentForm.value.position_id = positions.value[0]?.id || 0;
    if (!policyForm.value.role_id) policyForm.value.role_id = roles.value[0]?.id || 0;
  } catch (reason) {
    fail(reason);
  } finally {
    loading.value = false;
  }
}

async function mutate(message: string, operation: () => Promise<unknown>): Promise<boolean> {
  saving.value = true;
  error.value = "";
  errorStatus.value = 0;
  success.value = "";
  try {
    await operation();
    await load();
    success.value = message;
    return true;
  } catch (reason) {
    fail(reason);
    return false;
  } finally {
    saving.value = false;
  }
}

async function createGroup() {
  if (
    await mutate("集团已创建", () =>
      http.post("/system/organization-governance/groups", groupForm.value)
    )
  ) {
    groupForm.value = { code: "", name: "" };
  }
}

async function createRegion() {
  if (
    await mutate("区域已创建", () =>
      http.post("/system/organization-governance/regions", regionForm.value)
    )
  ) {
    regionForm.value.code = "";
    regionForm.value.name = "";
  }
}

async function assignPark() {
  await mutate("园区归属已更新并保留历史", () =>
    http.post("/system/organization-governance/park-assignments", {
      region_id: parkForm.value.region_id,
      park_id: parkForm.value.park_id,
      reason: parkForm.value.reason || null,
    })
  );
}

async function disableGroup(group: GroupRow) {
  await mutate("集团已停用", () =>
    http.patch(`/system/organization-governance/groups/${group.id}`, { status: "DISABLED" })
  );
}

async function disableRegion(region: RegionRow) {
  await mutate("区域已停用", () =>
    http.patch(`/system/organization-governance/regions/${region.id}`, { status: "DISABLED" })
  );
}

async function createPosition() {
  if (
    await mutate("岗位已创建", () =>
      http.post("/system/organization-governance/positions", {
        code: positionForm.value.code,
        name: positionForm.value.name,
        org_unit_id: positionForm.value.org_unit_id || null,
        responsibilities: positionForm.value.responsibilities || null,
      })
    )
  ) {
    positionForm.value.code = "";
    positionForm.value.name = "";
    positionForm.value.responsibilities = "";
  }
}

async function disablePosition(position: PositionRow) {
  await mutate("岗位已停用", () =>
    http.patch(`/system/organization-governance/positions/${position.id}`, { status: "DISABLED" })
  );
}

async function assignUser() {
  await mutate("任职已创建，RBAC 与园区授权未改变", () =>
    http.post("/system/organization-governance/user-assignments", {
      user_id: assignmentForm.value.user_id,
      position_id: assignmentForm.value.position_id,
      park_id: assignmentForm.value.park_id || null,
      is_primary: assignmentForm.value.is_primary,
    })
  );
}

async function endAssignment(assignment: AssignmentRow) {
  await mutate("任职已结束并保留历史", () =>
    http.post(`/system/organization-governance/user-assignments/${assignment.id}/end`, {})
  );
}

async function savePolicy() {
  await mutate("字段策略已在服务端生效", () =>
    http.put("/system/organization-governance/field-policies", {
      ...policyForm.value,
      mask_strategy: "PHONE",
      status: "ACTIVE",
    })
  );
}

function userName(id: number) {
  const user = users.value.find((item) => item.id === id);
  return user ? user.real_name || user.username : `#${id}`;
}

function roleName(id: number) {
  const role = roles.value.find((item) => item.id === id);
  return role ? role.name : `#${id}`;
}

function positionName(id: number) {
  return positions.value.find((item) => item.id === id)?.name || `#${id}`;
}

onMounted(load);
</script>

<template>
  <section class="governance-stack" data-testid="organization-governance-panel">
    <div class="governance-head">
      <div>
        <p class="eyebrow">GROUP · REGION · PARK</p>
        <h3>组织治理中心</h3>
        <p class="muted">集团与区域定义经营管辖；岗位只表达任职，不会隐式授予角色或园区权限。</p>
      </div>
      <button class="btn secondary" type="button" data-testid="governance-retry" :disabled="loading" @click="load">
        {{ loading ? "加载中…" : "重新加载" }}
      </button>
    </div>

    <p v-if="loading" class="state" role="status" data-testid="governance-loading">正在读取真实组织治理数据…</p>
    <div v-if="error" class="state error-state" role="alert" data-testid="governance-error">
      <strong>{{ errorStatus === 409 ? "数据冲突" : errorStatus === 403 ? "权限不足" : "加载或操作失败" }}</strong>
      <span>{{ error }}</span>
      <button class="link-btn" type="button" @click="load">刷新后重试</button>
    </div>
    <p v-if="success" class="state success-state" role="status" data-testid="governance-success">{{ success }}</p>
    <p v-if="!canWrite" class="state readonly-state" data-testid="governance-readonly">当前为只读模式，治理数据可查但变更操作不可用。</p>

    <div class="governance-grid">
      <article class="subcard">
        <div class="section-title"><h4>集团与区域</h4><span>{{ groups.length }} 个集团</span></div>
        <form v-if="canWrite" class="compact-form" data-testid="group-form" @submit.prevent="createGroup">
          <label>集团编码<input v-model.trim="groupForm.code" class="input" required data-testid="group-code" /></label>
          <label>集团名称<input v-model.trim="groupForm.name" class="input" required data-testid="group-name" /></label>
          <button class="btn" type="submit" :disabled="saving">创建集团</button>
        </form>
        <form v-if="canWrite" class="compact-form" data-testid="region-form" @submit.prevent="createRegion">
          <label>所属集团<select v-model.number="regionForm.group_id" class="input" required data-testid="region-group"><option v-for="group in groups" :key="group.id" :value="group.id">{{ group.name }}</option></select></label>
          <label>区域编码<input v-model.trim="regionForm.code" class="input" required data-testid="region-code" /></label>
          <label>区域名称<input v-model.trim="regionForm.name" class="input" required data-testid="region-name" /></label>
          <button class="btn" type="submit" :disabled="saving || !groups.length">创建区域</button>
        </form>
        <div v-if="!groups.length && !loading" class="empty-state" data-testid="governance-empty">尚未创建集团；从集团开始建立经营层级。</div>
        <div v-for="group in groups" :key="group.id" class="hierarchy-block" :data-testid="`group-row-${group.code}`">
          <header><div><strong>{{ group.name }}</strong><span>{{ group.code }} · {{ group.status }}</span></div><button v-if="canWrite && group.status === 'ACTIVE'" class="link-btn danger" type="button" @click="disableGroup(group)">停用</button></header>
          <div v-for="region in group.regions" :key="region.id" class="region-row" :data-testid="`region-row-${region.code}`">
            <div><strong>{{ region.name }}</strong><span>{{ region.code }} · {{ region.status }}</span></div>
            <span class="pill">{{ region.parks.length }} 园区</span>
            <button v-if="canWrite && region.status === 'ACTIVE'" class="link-btn danger" type="button" @click="disableRegion(region)">停用</button>
            <p v-if="region.parks.length" class="park-list">{{ region.parks.map((park) => park.name).join("、") }}</p>
          </div>
        </div>
      </article>

      <article class="subcard">
        <div class="section-title"><h4>园区调区</h4><span>保留历史</span></div>
        <form v-if="canWrite" class="compact-form one" data-testid="park-assignment-form" @submit.prevent="assignPark">
          <label>区域<select v-model.number="parkForm.region_id" class="input" required data-testid="assignment-region"><option v-for="region in allRegions" :key="region.id" :value="region.id">{{ region.name }}</option></select></label>
          <label>园区<select v-model.number="parkForm.park_id" class="input" required data-testid="assignment-park"><option v-for="park in parks" :key="park.id" :value="park.id">{{ park.name }}</option></select></label>
          <label>调区原因<input v-model.trim="parkForm.reason" class="input" maxlength="500" data-testid="assignment-reason" /></label>
          <button class="btn risk" type="submit" :disabled="saving || !allRegions.length || !parks.length">确认归属</button>
        </form>
        <p class="muted small">同一园区仅允许一个当前区域；并发冲突返回 409，不覆盖旧记录。</p>
      </article>

      <article class="subcard wide-card">
        <div class="section-title"><h4>岗位与有效期任职</h4><span>{{ assignments.filter((item) => !item.ends_at).length }} 条当前任职</span></div>
        <form v-if="canWrite" class="compact-form" data-testid="position-form" @submit.prevent="createPosition">
          <label>岗位编码<input v-model.trim="positionForm.code" class="input" required data-testid="position-code" /></label>
          <label>岗位名称<input v-model.trim="positionForm.name" class="input" required data-testid="position-name" /></label>
          <label>所属部门<select v-model.number="positionForm.org_unit_id" class="input"><option :value="0">租户级</option><option v-for="org in orgs" :key="org.id" :value="org.id">{{ org.name }}</option></select></label>
          <label>职责<input v-model.trim="positionForm.responsibilities" class="input" maxlength="5000" /></label>
          <button class="btn" type="submit" :disabled="saving">创建岗位</button>
        </form>
        <div class="table-wrap"><table class="table"><thead><tr><th>岗位</th><th>部门</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="position in positions" :key="position.id" :data-testid="`position-row-${position.code}`"><td>{{ position.name }}<small>{{ position.code }}</small></td><td>{{ orgs.find((org) => org.id === position.org_unit_id)?.name || "租户级" }}</td><td>{{ position.status }}</td><td><button v-if="canWrite && position.status === 'ACTIVE'" class="link-btn danger" type="button" @click="disablePosition(position)">停用</button></td></tr><tr v-if="!positions.length"><td colspan="4" class="muted">暂无岗位</td></tr></tbody></table></div>
        <form v-if="canWrite" class="compact-form" data-testid="user-assignment-form" @submit.prevent="assignUser">
          <label>用户<select v-model.number="assignmentForm.user_id" class="input" required data-testid="position-user"><option v-for="user in users" :key="user.id" :value="user.id">{{ user.real_name || user.username }}</option></select></label>
          <label>岗位<select v-model.number="assignmentForm.position_id" class="input" required data-testid="position-select"><option v-for="position in positions.filter((item) => item.status === 'ACTIVE')" :key="position.id" :value="position.id">{{ position.name }}</option></select></label>
          <label>园区<select v-model.number="assignmentForm.park_id" class="input"><option :value="0">租户级</option><option v-for="park in parks" :key="park.id" :value="park.id">{{ park.name }}</option></select></label>
          <label class="check"><input v-model="assignmentForm.is_primary" type="checkbox" data-testid="position-primary" /> 主岗位</label>
          <button class="btn" type="submit" :disabled="saving || !users.length || !positions.length">创建任职</button>
        </form>
        <div class="table-wrap"><table class="table" data-testid="assignment-table"><thead><tr><th>用户</th><th>岗位</th><th>范围</th><th>有效期</th><th>操作</th></tr></thead><tbody><tr v-for="assignment in assignments" :key="assignment.id"><td>{{ userName(assignment.user_id) }}<span v-if="assignment.is_primary" class="pill">主</span></td><td>{{ positionName(assignment.position_id) }}</td><td>{{ parks.find((park) => park.id === assignment.park_id)?.name || "租户级" }}</td><td>{{ assignment.starts_at.slice(0, 10) }} → {{ assignment.ends_at?.slice(0, 10) || "当前" }}</td><td><button v-if="canWrite && !assignment.ends_at" class="link-btn danger" type="button" @click="endAssignment(assignment)">结束任职</button></td></tr><tr v-if="!assignments.length"><td colspan="5" class="muted">暂无任职</td></tr></tbody></table></div>
      </article>

      <article class="subcard wide-card">
        <div class="section-title"><h4>字段访问策略</h4><span>服务端投影 · 拒绝优先</span></div>
        <p v-if="!canPolicyRead" class="state readonly-state">无字段策略查看权限；受保护字段仍由后端默认脱敏。</p>
        <form v-if="canPolicyWrite" class="compact-form" data-testid="field-policy-form" @submit.prevent="savePolicy">
          <label>角色<select v-model.number="policyForm.role_id" class="input" required data-testid="policy-role"><option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option></select></label>
          <label>受保护字段<select class="input" disabled><option v-for="field in protectedFields" :key="`${field.resource_type}.${field.field_name}`">{{ field.resource_type }}.{{ field.field_name }}</option></select></label>
          <label>访问模式<select v-model="policyForm.access_mode" class="input" data-testid="policy-mode"><option value="VISIBLE">可见</option><option value="MASKED">脱敏</option><option value="HIDDEN">隐藏</option></select></label>
          <button class="btn" type="submit" :disabled="saving || !roles.length">保存策略</button>
        </form>
        <div v-if="canPolicyRead" class="table-wrap"><table class="table" data-testid="field-policy-table"><thead><tr><th>角色</th><th>字段</th><th>模式</th><th>状态</th></tr></thead><tbody><tr v-for="policy in policies" :key="policy.id"><td>{{ roleName(policy.role_id) }}</td><td>{{ policy.resource_type }}.{{ policy.field_name }}</td><td>{{ policy.access_mode }}</td><td>{{ policy.status }}</td></tr><tr v-if="!policies.length"><td colspan="4" class="muted">暂无显式策略；受保护字段默认脱敏</td></tr></tbody></table></div>
        <h5>当前请求用户看到的真实用户手机号</h5>
        <div class="projection-list" data-testid="field-projection-preview"><span v-for="user in users" :key="user.id"><strong>{{ user.username }}</strong>{{ Object.prototype.hasOwnProperty.call(user, "phone") ? user.phone || "—" : "字段已隐藏" }}</span></div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.governance-stack { display: grid; gap: 1rem; }
.governance-head, .section-title, .hierarchy-block header, .region-row { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
.governance-head h3, .section-title h4 { margin: 0; }
.eyebrow { margin: 0 0 .25rem; color: #0891b2; font-size: .72rem; font-weight: 800; letter-spacing: .12em; }
.governance-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.subcard { min-width: 0; padding: 1rem; border: 1px solid #dbe4ee; border-radius: 14px; background: linear-gradient(145deg, #fff, #f8fbfd); }
.wide-card { grid-column: 1 / -1; }
.compact-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: .65rem; align-items: end; margin: .8rem 0; }
.compact-form.one { grid-template-columns: 1fr; }
label { display: grid; gap: .3rem; color: #475569; font-size: .82rem; }
.check { display: flex; align-items: center; gap: .45rem; min-height: 2.5rem; }
.hierarchy-block { margin-top: .75rem; padding: .75rem; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; }
.hierarchy-block header div, .region-row div, td small { display: grid; gap: .15rem; }
.hierarchy-block span, .region-row span, td small { color: #64748b; font-size: .75rem; }
.region-row { flex-wrap: wrap; margin-top: .55rem; padding-top: .55rem; border-top: 1px dashed #dbe4ee; }
.park-list { flex-basis: 100%; margin: 0; color: #475569; font-size: .78rem; }
.pill { display: inline-flex; width: fit-content; margin-left: .35rem; padding: .12rem .42rem; border-radius: 999px; color: #0369a1 !important; background: #e0f2fe; font-size: .7rem !important; }
.state, .empty-state { display: flex; flex-wrap: wrap; gap: .5rem; padding: .7rem .85rem; border-radius: 10px; background: #f1f5f9; }
.error-state { color: #b42318; background: #fff1f0; border: 1px solid #fecaca; }
.success-state { color: #047857; background: #ecfdf5; }
.readonly-state { color: #475569; background: #f8fafc; border: 1px dashed #cbd5e1; }
.risk { background: #c2410c; border-color: #c2410c; }
.table-wrap { overflow-x: auto; }
.table { min-width: 620px; }
.link-btn { border: 0; background: transparent; color: #0369a1; cursor: pointer; }
.link-btn.danger { color: #b42318; }
.projection-list { display: flex; flex-wrap: wrap; gap: .5rem; }
.projection-list span { display: grid; gap: .15rem; min-width: 150px; padding: .55rem .7rem; border-radius: 8px; background: #eef6fa; font-size: .78rem; }
.small { font-size: .78rem; }
@media (max-width: 900px) { .governance-grid { grid-template-columns: 1fr; } .wide-card { grid-column: auto; } }
@media (max-width: 640px) { .governance-head { align-items: flex-start; flex-direction: column; } .compact-form { grid-template-columns: 1fr; } .subcard { padding: .8rem; } }
</style>
