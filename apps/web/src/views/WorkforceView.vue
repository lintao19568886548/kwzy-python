<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type Employee = { id: number; park_id: number; employee_no: string; display_name: string; department_name: string | null; position_name: string | null; mobile_masked: string | null; identity_masked: string | null; start_date: string; end_date: string | null; status: string; lock_version: number };
type ShiftVersion = { id: number; version_no: number; start_time: string; end_time: string; cross_day: boolean; break_minutes: number };
type Shift = { id: number; park_id: number; code: string; name: string; status: string; current_version: number; lock_version: number; versions: ShiftVersion[] };
type Assignment = { id: number; employee_id: number; shift_version_id: number; work_date: string; status: string };
type Location = { id: number; park_id: number; code: string; name: string; config_ref: string; radius_m: number; status: string };
type Summary = { id: number; employee_id: number; work_date: string; scheduled_minutes: number; worked_minutes: number; first_in_at: string | null; last_out_at: string | null; status: string; anomaly_code: string | null; lock_version: number };
type Leave = { id: number; employee_id: number; leave_type: string; start_at: string; end_at: string; status: string; approval_status: string | null };
type Cycle = { id: number; park_id: number; code: string; name: string; start_date: string; end_date: string; status: string; lock_version: number };
type Review = { id: number; cycle_id: number; employee_id: number; rating: number; status: string; published_at: string | null };
type QualificationType = { id: number; code: string; name: string; validity_months: number | null; reminder_days: number; status: string };
type Qualification = { id: number; employee_id: number; qualification_type_id: number; credential_masked: string; issuer: string; effective_on: string; expires_on: string | null; status: string; lock_version: number };
type Overview = { active_employees: number; today_anomalies: number; approved_leave_records: number; qualifications_due_30d: number; device_integration: { status: string; production_contacted: boolean }; payroll_engine: { status: string; summary_ready: boolean } };

const auth = useAuthStore();
const today = new Date().toISOString().slice(0, 10);
const inThirtyDays = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);
const activeTab = ref<"employees" | "roster" | "attendance" | "performance" | "qualifications">("employees");
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const online = ref(navigator.onLine);
const overview = ref<Overview | null>(null);
const employees = ref<Employee[]>([]);
const shifts = ref<Shift[]>([]);
const assignments = ref<Assignment[]>([]);
const locations = ref<Location[]>([]);
const summaries = ref<Summary[]>([]);
const leaves = ref<Leave[]>([]);
const cycles = ref<Cycle[]>([]);
const reviews = ref<Review[]>([]);
const qualificationTypes = ref<QualificationType[]>([]);
const qualifications = ref<Qualification[]>([]);
const showForm = ref(false);

const canManage = computed(() => auth.can("*") || auth.can("workforce:manage"));
const canSchedule = computed(() => auth.can("*") || auth.can("workforce:schedule"));
const canAttendance = computed(() => auth.can("*") || auth.can("workforce:attendance_admin"));
const canPunch = computed(() => auth.can("*") || auth.can("workforce:attendance_punch"));
const canPerformance = computed(() => auth.can("*") || auth.can("workforce:performance_manage"));
const canQualification = computed(() => auth.can("*") || auth.can("workforce:qualification_manage"));

const employeeDraft = ref({ park_id: "", employee_no: "", display_name: "", department_name: "", position_name: "", start_date: today });
const shiftDraft = ref({ park_id: "", code: "", name: "", start_time: "09:00", end_time: "18:00", break_minutes: "60" });
const assignmentDraft = ref({ employee_id: "", shift_version_id: "", work_date: today });
const locationDraft = ref({ park_id: "", code: "", name: "", config_ref: "", radius_m: "300" });
const punchDraft = ref({ employee_id: "", location_id: "", punch_type: "IN", distance_m: "", device_id: "" });
const summaryDraft = ref({ employee_id: "", work_date: today });
const cycleDraft = ref({ park_id: "", code: "", name: "", start_date: today, end_date: inThirtyDays });
const qualificationTypeDraft = ref({ code: "", name: "", validity_months: "36", reminder_days: "30" });
const qualificationDraft = ref({ employee_id: "", qualification_type_id: "", attachment_id: "", credential_number: "", issuer: "", effective_on: today, expires_on: "" });

function requestError(value: unknown, fallback: string) {
  error.value = value instanceof Error ? value.message : fallback;
  errorStatus.value = value instanceof ApiRequestError ? value.status : 0;
}
function clearMessages() { error.value = ""; errorStatus.value = 0; success.value = ""; }
function employeeName(id: number) { const row = employees.value.find((item) => item.id === id); return row ? `${row.employee_no} · ${row.display_name}` : `#${id}`; }
function statusClass(status: string) { return ["ANOMALY", "ABSENT", "EXPIRED", "REVOKED", "REJECTED", "LEFT"].includes(status) ? "risk" : ["DRAFT", "PENDING_APPROVAL", "RETURNED", "SUSPENDED"].includes(status) ? "pending" : "ok"; }

async function loadAll() {
  clearMessages(); loading.value = true;
  try {
    const [overviewResponse, employeeResponse, shiftResponse, assignmentResponse, locationResponse, summaryResponse, leaveResponse, cycleResponse, reviewResponse, typeResponse, qualificationResponse] = await Promise.all([
      http.get<Envelope<Overview>>("/workforce/overview"),
      http.get<Envelope<PageResult<Employee>>>("/workforce/employees", { params: { page: 1, page_size: 200 } }),
      http.get<Envelope<Shift[]>>("/workforce/shifts"),
      http.get<Envelope<Assignment[]>>("/workforce/assignments", { params: { date_from: today, date_to: inThirtyDays } }),
      http.get<Envelope<Location[]>>("/workforce/attendance/locations"),
      http.get<Envelope<Summary[]>>("/workforce/attendance/summaries", { params: { date_from: today, date_to: today } }),
      http.get<Envelope<Leave[]>>("/workforce/leaves"),
      http.get<Envelope<Cycle[]>>("/workforce/performance/cycles"),
      http.get<Envelope<Review[]>>("/workforce/performance/reviews"),
      http.get<Envelope<QualificationType[]>>("/workforce/qualification-types"),
      http.get<Envelope<Qualification[]>>("/workforce/qualifications"),
    ]);
    overview.value = overviewResponse.data.data;
    employees.value = employeeResponse.data.data.items;
    shifts.value = shiftResponse.data.data;
    assignments.value = assignmentResponse.data.data;
    locations.value = locationResponse.data.data;
    summaries.value = summaryResponse.data.data;
    leaves.value = leaveResponse.data.data;
    cycles.value = cycleResponse.data.data;
    reviews.value = reviewResponse.data.data;
    qualificationTypes.value = typeResponse.data.data;
    qualifications.value = qualificationResponse.data.data;
  } catch (value) { requestError(value, "人力运营数据加载失败"); }
  finally { loading.value = false; }
}

async function command(action: () => Promise<unknown>, message: string) {
  clearMessages(); saving.value = true;
  try { await action(); showForm.value = false; await loadAll(); success.value = message; }
  catch (value) { requestError(value, message.replace("已", "失败：")); }
  finally { saving.value = false; }
}

async function createEmployee() { await command(() => http.post("/workforce/employees", { park_id: Number(employeeDraft.value.park_id), employee_no: employeeDraft.value.employee_no, display_name: employeeDraft.value.display_name, department_name: employeeDraft.value.department_name || null, position_name: employeeDraft.value.position_name || null, start_date: employeeDraft.value.start_date }), "员工已建立受控档案"); }
async function createShift() { await command(() => http.post("/workforce/shifts", { park_id: Number(shiftDraft.value.park_id), code: shiftDraft.value.code, name: shiftDraft.value.name, start_time: `${shiftDraft.value.start_time}:00`, end_time: `${shiftDraft.value.end_time}:00`, cross_day: false, break_minutes: Number(shiftDraft.value.break_minutes), late_grace_minutes: 5, early_grace_minutes: 5 }), "班次版本已发布"); }
async function createAssignment() { await command(() => http.post("/workforce/assignments", { employee_id: Number(assignmentDraft.value.employee_id), shift_version_id: Number(assignmentDraft.value.shift_version_id), work_date: assignmentDraft.value.work_date, reason: "PC 人力运营工作区排班" }), "排班已保存并完成冲突校验"); }
async function createLocation() { await command(() => http.post("/workforce/attendance/locations", { park_id: Number(locationDraft.value.park_id), code: locationDraft.value.code, name: locationDraft.value.name, config_ref: locationDraft.value.config_ref, radius_m: Number(locationDraft.value.radius_m) }), "考勤地点已登记；数据库不保存精确坐标"); }
async function createPunch() { await command(() => http.post("/workforce/attendance/punches", { employee_id: Number(punchDraft.value.employee_id), punch_type: punchDraft.value.punch_type, punched_at: new Date().toISOString(), source: "MOBILE", location_id: punchDraft.value.location_id ? Number(punchDraft.value.location_id) : null, distance_m: punchDraft.value.distance_m ? Number(punchDraft.value.distance_m) : null, device_id: punchDraft.value.device_id || null }, { headers: { "Idempotency-Key": `pc-punch-${crypto.randomUUID()}` } }), "打卡已记录，精确坐标未持久化"); }
async function generateSummary() { await command(() => http.post("/workforce/attendance/summaries/generate", { employee_id: Number(summaryDraft.value.employee_id), work_date: summaryDraft.value.work_date }), "考勤汇总已重新计算"); }
async function createCycle() { await command(() => http.post("/workforce/performance/cycles", { park_id: Number(cycleDraft.value.park_id), code: cycleDraft.value.code, name: cycleDraft.value.name, start_date: cycleDraft.value.start_date, end_date: cycleDraft.value.end_date }), "绩效周期已创建"); }
async function createQualificationType() { await command(() => http.post("/workforce/qualification-types", { code: qualificationTypeDraft.value.code, name: qualificationTypeDraft.value.name, validity_months: qualificationTypeDraft.value.validity_months ? Number(qualificationTypeDraft.value.validity_months) : null, reminder_days: Number(qualificationTypeDraft.value.reminder_days) }), "资质类型已创建"); }
async function createQualification() { await command(() => http.post("/workforce/qualifications", { employee_id: Number(qualificationDraft.value.employee_id), qualification_type_id: Number(qualificationDraft.value.qualification_type_id), attachment_id: Number(qualificationDraft.value.attachment_id), credential_number: qualificationDraft.value.credential_number, issuer: qualificationDraft.value.issuer, effective_on: qualificationDraft.value.effective_on, expires_on: qualificationDraft.value.expires_on || null }), "员工资质已绑定真实附件证据"); }

function onlineUpdate() { online.value = navigator.onLine; }
onMounted(() => { window.addEventListener("online", onlineUpdate); window.addEventListener("offline", onlineUpdate); void loadAll(); });
onBeforeUnmount(() => { window.removeEventListener("online", onlineUpdate); window.removeEventListener("offline", onlineUpdate); });
</script>

<template>
  <section class="workforce-page" data-testid="workforce-page">
    <header class="page-head">
      <div><p class="eyebrow">WORKFORCE OPERATIONS</p><h1 data-testid="workforce-title">人力、排班与现场履职</h1><p>员工身份、班次、考勤、请假、绩效与资质使用同一园区范围和证据链。</p></div>
      <button class="btn btn-quiet" type="button" :disabled="loading" data-testid="workforce-refresh" @click="loadAll">刷新真实数据</button>
    </header>

    <div v-if="!online" class="notice warning" data-testid="workforce-offline"><b>当前离线</b><span>操作不会伪成功；网络恢复后请重试。</span><button type="button" @click="loadAll">重试</button></div>
    <div v-if="error" class="notice danger" data-testid="workforce-error"><b>{{ errorStatus === 403 ? '权限不足' : errorStatus === 409 ? '数据冲突' : '加载失败' }}</b><span>{{ error }}</span><button type="button" @click="loadAll">重试</button></div>
    <div v-if="success" class="notice success" data-testid="workforce-success">{{ success }}</div>

    <section class="metric-grid" aria-label="人力运营指标">
      <article class="card metric"><span>在职员工</span><strong>{{ overview?.active_employees ?? '—' }}</strong><small>范围内实时档案</small></article>
      <article class="card metric risk-metric"><span>今日异常</span><strong>{{ overview?.today_anomalies ?? '—' }}</strong><small>自动生成待办</small></article>
      <article class="card metric"><span>已批请假记录</span><strong>{{ overview?.approved_leave_records ?? '—' }}</strong><small>审批平台真值</small></article>
      <article class="card metric risk-metric"><span>30 天到期资质</span><strong>{{ overview?.qualifications_due_30d ?? '—' }}</strong><small>到期扫描可追溯</small></article>
    </section>
    <section class="truth-bar"><span><b>设备接入</b> {{ overview?.device_integration.status || 'NOT_CONNECTED' }}</span><span><b>工资引擎</b> {{ overview?.payroll_engine.status || 'NOT_IMPLEMENTED' }}</span><span>考勤汇总可用于后续工资规则，但不会伪造工资计算结果。</span></section>

    <nav class="card tabs" aria-label="人力运营模块">
      <button :class="{ active: activeTab === 'employees' }" type="button" @click="activeTab = 'employees'; showForm = false">员工档案</button>
      <button :class="{ active: activeTab === 'roster' }" type="button" @click="activeTab = 'roster'; showForm = false">班次排班</button>
      <button :class="{ active: activeTab === 'attendance' }" type="button" @click="activeTab = 'attendance'; showForm = false">考勤请假</button>
      <button :class="{ active: activeTab === 'performance' }" type="button" @click="activeTab = 'performance'; showForm = false">绩效评价</button>
      <button :class="{ active: activeTab === 'qualifications' }" type="button" @click="activeTab = 'qualifications'; showForm = false">员工资质</button>
    </nav>

    <div v-if="loading" class="card state"><span class="spinner" /><p>正在读取 PostgreSQL 实时数据…</p></div>

    <template v-else-if="activeTab === 'employees'">
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">IDENTITY LINK</p><h2>员工生命周期</h2></div><button v-if="canManage" class="btn" data-testid="add-workforce-employee" type="button" @click="showForm = !showForm">新增员工</button></div>
        <form v-if="showForm" class="form-grid" @submit.prevent="createEmployee"><label>园区 ID<input v-model="employeeDraft.park_id" class="input" required type="number" min="1" /></label><label>员工编号<input v-model="employeeDraft.employee_no" class="input" required pattern="[A-Za-z][A-Za-z0-9_-]*" /></label><label>姓名<input v-model="employeeDraft.display_name" class="input" required /></label><label>入职日期<input v-model="employeeDraft.start_date" class="input" required type="date" /></label><label>部门<input v-model="employeeDraft.department_name" class="input" /></label><label>岗位<input v-model="employeeDraft.position_name" class="input" /></label><button class="btn align-end" :disabled="saving" type="submit">建立员工档案</button></form>
        <div class="table-wrap"><table class="table" data-testid="workforce-employee-table"><thead><tr><th>员工</th><th>组织岗位</th><th>隐私投影</th><th>在职周期</th><th>状态</th></tr></thead><tbody><tr v-for="employee in employees" :key="employee.id"><td data-label="员工"><b>{{ employee.employee_no }}</b><small>{{ employee.display_name }}</small></td><td data-label="组织岗位">{{ employee.department_name || '—' }}<small>{{ employee.position_name || '—' }}</small></td><td data-label="隐私投影">{{ employee.mobile_masked || '未登记' }}<small>{{ employee.identity_masked || '未登记证件' }}</small></td><td data-label="在职周期">{{ employee.start_date }}<small>{{ employee.end_date || '至今' }}</small></td><td data-label="状态"><span class="status" :class="statusClass(employee.status)">{{ employee.status }}</span></td></tr><tr v-if="employees.length === 0"><td class="empty" colspan="5">当前权限范围内没有员工档案</td></tr></tbody></table></div>
      </section>
    </template>

    <template v-else-if="activeTab === 'roster'">
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">IMMUTABLE SHIFT VERSION</p><h2>班次模板</h2></div><button v-if="canSchedule" class="btn" type="button" @click="showForm = !showForm">发布班次</button></div><form v-if="showForm" class="form-grid" @submit.prevent="createShift"><label>园区 ID<input v-model="shiftDraft.park_id" class="input" required type="number" min="1" /></label><label>编码<input v-model="shiftDraft.code" class="input" required /></label><label>名称<input v-model="shiftDraft.name" class="input" required /></label><label>开始<input v-model="shiftDraft.start_time" class="input" type="time" required /></label><label>结束<input v-model="shiftDraft.end_time" class="input" type="time" required /></label><label>休息分钟<input v-model="shiftDraft.break_minutes" class="input" type="number" min="0" max="480" /></label><button class="btn align-end" :disabled="saving" type="submit">发布版本 1</button></form><div class="card-grid"><article v-for="shift in shifts" :key="shift.id" class="item-card"><header><b>{{ shift.code }}</b><span class="status ok">{{ shift.status }}</span></header><h3>{{ shift.name }}</h3><p>v{{ shift.current_version }} · {{ shift.versions[0]?.start_time }} — {{ shift.versions[0]?.end_time }} · 休息 {{ shift.versions[0]?.break_minutes }} 分钟</p></article><p v-if="shifts.length === 0" class="empty">尚未发布班次</p></div></section>
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">CONFLICT SAFE ROSTER</p><h2>未来 30 天排班</h2></div></div><form v-if="canSchedule" class="form-grid compact" @submit.prevent="createAssignment"><label>员工<select v-model="assignmentDraft.employee_id" class="input" required><option value="" disabled>请选择</option><option v-for="row in employees" :key="row.id" :value="String(row.id)">{{ row.employee_no }} · {{ row.display_name }}</option></select></label><label>班次版本<select v-model="assignmentDraft.shift_version_id" class="input" required><option value="" disabled>请选择</option><option v-for="row in shifts" :key="row.id" :value="String(row.versions[0]?.id)">{{ row.code }} · v{{ row.current_version }}</option></select></label><label>日期<input v-model="assignmentDraft.work_date" class="input" type="date" required /></label><button class="btn align-end" :disabled="saving" type="submit">校验并排班</button></form><div class="compact-list"><p v-for="row in assignments" :key="row.id"><b>{{ employeeName(row.employee_id) }}</b><span>{{ row.work_date }} · 班次版本 #{{ row.shift_version_id }}</span><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></p><p v-if="assignments.length === 0" class="empty">未来 30 天暂无排班</p></div></section>
    </template>

    <template v-else-if="activeTab === 'attendance'">
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">PRIVACY MINIMIZED</p><h2>考勤地点与打卡</h2></div><button v-if="canAttendance" class="btn" type="button" @click="showForm = !showForm">登记地点</button></div><form v-if="showForm" class="form-grid" @submit.prevent="createLocation"><label>园区 ID<input v-model="locationDraft.park_id" class="input" required type="number" min="1" /></label><label>地点编码<input v-model="locationDraft.code" class="input" required /></label><label>地点名称<input v-model="locationDraft.name" class="input" required /></label><label>加密配置引用<input v-model="locationDraft.config_ref" class="input" required placeholder="secret://attendance/gate" /></label><label>半径（米）<input v-model="locationDraft.radius_m" class="input" type="number" min="10" max="5000" /></label><button class="btn align-end" :disabled="saving" type="submit">登记引用</button></form><form v-if="canPunch" class="form-grid compact" @submit.prevent="createPunch"><label>员工<select v-model="punchDraft.employee_id" class="input" required><option value="" disabled>请选择</option><option v-for="row in employees" :key="row.id" :value="String(row.id)">{{ row.employee_no }} · {{ row.display_name }}</option></select></label><label>动作<select v-model="punchDraft.punch_type" class="input"><option value="IN">上班签到</option><option value="OUT">下班签退</option></select></label><label>地点<select v-model="punchDraft.location_id" class="input"><option value="">不校验地点</option><option v-for="row in locations" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.name }}</option></select></label><label>距离（米）<input v-model="punchDraft.distance_m" class="input" type="number" min="0" /></label><label>设备标识<input v-model="punchDraft.device_id" class="input" /></label><button class="btn align-end" :disabled="saving" type="submit">记录打卡</button></form><div class="chip-list"><span v-for="row in locations" :key="row.id" class="chip">{{ row.code }} · {{ row.name }} · {{ row.radius_m }}m</span><span v-if="locations.length === 0" class="empty">暂无考勤地点</span></div></section>
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">PAYROLL READY SUMMARY</p><h2>今日考勤汇总与请假</h2></div></div><form v-if="canAttendance" class="form-grid compact" @submit.prevent="generateSummary"><label>员工<select v-model="summaryDraft.employee_id" class="input" required><option value="" disabled>请选择</option><option v-for="row in employees" :key="row.id" :value="String(row.id)">{{ row.employee_no }} · {{ row.display_name }}</option></select></label><label>日期<input v-model="summaryDraft.work_date" class="input" type="date" required /></label><button class="btn align-end" :disabled="saving" type="submit">重新计算</button></form><div class="table-wrap"><table class="table" data-testid="attendance-summary-table"><thead><tr><th>员工</th><th>日期</th><th>排班/实到</th><th>首末打卡</th><th>状态</th></tr></thead><tbody><tr v-for="row in summaries" :key="row.id"><td data-label="员工">{{ employeeName(row.employee_id) }}</td><td data-label="日期">{{ row.work_date }}</td><td data-label="排班/实到">{{ row.scheduled_minutes }} / {{ row.worked_minutes }} 分钟</td><td data-label="首末打卡">{{ row.first_in_at || '—' }}<small>{{ row.last_out_at || '—' }}</small></td><td data-label="状态"><span class="status" :class="statusClass(row.status)">{{ row.status }}</span><small>{{ row.anomaly_code || '' }}</small></td></tr><tr v-if="summaries.length === 0"><td class="empty" colspan="5">今日尚未生成考勤汇总</td></tr></tbody></table></div><div class="compact-list"><p v-for="row in leaves" :key="row.id"><b>{{ employeeName(row.employee_id) }} · {{ row.leave_type }}</b><span>{{ row.start_at }} — {{ row.end_at }}</span><span class="status" :class="statusClass(row.status)">{{ row.approval_status || row.status }}</span></p></div></section>
    </template>

    <template v-else-if="activeTab === 'performance'">
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">SEPARATION OF DUTIES</p><h2>绩效周期与评价证据</h2></div><button v-if="canPerformance" class="btn" type="button" @click="showForm = !showForm">新建周期</button></div><form v-if="showForm" class="form-grid" @submit.prevent="createCycle"><label>园区 ID<input v-model="cycleDraft.park_id" class="input" type="number" required min="1" /></label><label>周期编码<input v-model="cycleDraft.code" class="input" required /></label><label>周期名称<input v-model="cycleDraft.name" class="input" required /></label><label>开始日期<input v-model="cycleDraft.start_date" class="input" type="date" required /></label><label>结束日期<input v-model="cycleDraft.end_date" class="input" type="date" required /></label><button class="btn align-end" :disabled="saving" type="submit">创建草稿周期</button></form><div class="card-grid"><article v-for="cycle in cycles" :key="cycle.id" class="item-card"><header><b>{{ cycle.code }}</b><span class="status" :class="statusClass(cycle.status)">{{ cycle.status }}</span></header><h3>{{ cycle.name }}</h3><p>{{ cycle.start_date }} — {{ cycle.end_date }}</p><footer><span>评价 {{ reviews.filter((row) => row.cycle_id === cycle.id).length }} 条</span><span>发布后不可覆盖</span></footer></article><p v-if="cycles.length === 0" class="empty">暂无绩效周期</p></div></section>
    </template>

    <template v-else>
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">EVIDENCE AND EXPIRY</p><h2>资质类型与员工资质</h2></div><button v-if="canQualification" class="btn" type="button" @click="showForm = !showForm">维护资质</button></div><form v-if="showForm" class="form-grid" @submit.prevent="createQualificationType"><label>类型编码<input v-model="qualificationTypeDraft.code" class="input" required /></label><label>类型名称<input v-model="qualificationTypeDraft.name" class="input" required /></label><label>有效月数<input v-model="qualificationTypeDraft.validity_months" class="input" type="number" min="1" /></label><label>提前提醒天数<input v-model="qualificationTypeDraft.reminder_days" class="input" type="number" min="0" /></label><button class="btn align-end" :disabled="saving" type="submit">保存类型</button></form><form v-if="canQualification && qualificationTypes.length" class="form-grid" @submit.prevent="createQualification"><label>员工<select v-model="qualificationDraft.employee_id" class="input" required><option value="" disabled>请选择</option><option v-for="row in employees" :key="row.id" :value="String(row.id)">{{ row.employee_no }} · {{ row.display_name }}</option></select></label><label>资质类型<select v-model="qualificationDraft.qualification_type_id" class="input" required><option value="" disabled>请选择</option><option v-for="row in qualificationTypes" :key="row.id" :value="String(row.id)">{{ row.code }} · {{ row.name }}</option></select></label><label>已上传证据附件 ID<input v-model="qualificationDraft.attachment_id" class="input" type="number" min="1" required /></label><label>证书编号<input v-model="qualificationDraft.credential_number" class="input" required /></label><label>发证机构<input v-model="qualificationDraft.issuer" class="input" required /></label><label>生效日期<input v-model="qualificationDraft.effective_on" class="input" type="date" required /></label><label>到期日期<input v-model="qualificationDraft.expires_on" class="input" type="date" /></label><button class="btn align-end" :disabled="saving" type="submit">绑定证据</button></form><div class="table-wrap"><table class="table" data-testid="qualification-table"><thead><tr><th>员工</th><th>资质</th><th>凭证投影</th><th>机构</th><th>有效期</th><th>状态</th></tr></thead><tbody><tr v-for="row in qualifications" :key="row.id"><td data-label="员工">{{ employeeName(row.employee_id) }}</td><td data-label="资质">{{ qualificationTypes.find((item) => item.id === row.qualification_type_id)?.name || `#${row.qualification_type_id}` }}</td><td data-label="凭证投影">{{ row.credential_masked }}</td><td data-label="机构">{{ row.issuer }}</td><td data-label="有效期">{{ row.effective_on }}<small>{{ row.expires_on || '长期有效' }}</small></td><td data-label="状态"><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></td></tr><tr v-if="qualifications.length === 0"><td class="empty" colspan="6">暂无员工资质证据</td></tr></tbody></table></div></section>
    </template>
  </section>
</template>

<style scoped>
.workforce-page { display: grid; gap: 1rem; width: 100%; min-width: 0; overflow-x: hidden; }.workforce-page > * { min-width: 0; max-width: 100%; }
.page-head,.section-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }.page-head > div,.section-head > div { min-width: 0; }.page-head h1 { margin: .15rem 0; font-size: clamp(1.6rem,3vw,2.35rem); letter-spacing: -.035em; overflow-wrap: anywhere; }.page-head p:last-child { color: var(--muted); }.eyebrow { margin: 0; color: var(--primary); font-size: .68rem; font-weight: 900; letter-spacing: .14em; }
.metric-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: .8rem; }.metric { padding: 1rem; border-top: 3px solid #1484a8; }.metric span,.metric small { display: block; color: var(--muted); }.metric strong { display: block; margin: .2rem 0; color: #12394b; font-size: 1.8rem; }.risk-metric { border-top-color: #d85b39; }
.truth-bar { display: grid; grid-template-columns: auto auto minmax(0,1fr); gap: 1rem; padding: .8rem 1rem; border-left: 4px solid #d85b39; border-radius: 10px; background: #fff3ed; color: #74341f; font-size: .76rem; }.tabs { display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); gap: .35rem; padding: .45rem; }.tabs button { min-width: 0; border: 0; border-radius: 9px; padding: .65rem .35rem; background: transparent; color: var(--muted); cursor: pointer; overflow-wrap: anywhere; }.tabs button.active { background: #e7f3f7; color: #0c6e8d; font-weight: 800; }
.panel { padding: 1rem; }.section-head h2 { margin: .15rem 0; font-size: 1.05rem; }.form-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: .7rem; padding: .85rem; margin: .8rem 0; border: 1px solid var(--border); border-radius: 12px; background: #f7fafb; }.form-grid.compact { grid-template-columns: repeat(5,minmax(0,1fr)); }.form-grid label { display: grid; gap: .3rem; color: var(--muted); font-size: .75rem; }.align-end { align-self: end; }
.table-wrap { width: 100%; max-width: 100%; overflow-x: auto; }.table small { display: block; color: var(--muted); font-size: .7rem; }.table td { vertical-align: middle; }.card-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; margin-top: .8rem; }.item-card { padding: .85rem; border: 1px solid var(--border); border-radius: 12px; background: #fbfcfd; }.item-card header,.item-card footer { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }.item-card h3 { margin: .6rem 0 .1rem; }.item-card p,.item-card footer { color: var(--muted); font-size: .72rem; }
.compact-list p { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr) auto; align-items: center; gap: .7rem; padding: .65rem; margin: 0; border-bottom: 1px solid var(--border); }.chip-list { display: flex; flex-wrap: wrap; gap: .5rem; }.chip { padding: .4rem .6rem; border-radius: 99px; background: #edf5f7; color: #355b69; font-size: .72rem; }.status { display: inline-flex; width: max-content; padding: .18rem .5rem; border-radius: 99px; font-size: .68rem; font-weight: 800; }.status.ok { background: #e5f5ef; color: #0f6e56; }.status.pending { background: #fff3d5; color: #8a5b00; }.status.risk { background: #ffebe5; color: #b53d23; }
.notice { display: flex; align-items: center; gap: .7rem; padding: .7rem .9rem; border-radius: 10px; font-size: .8rem; }.notice button { margin-left: auto; border: 0; background: transparent; color: inherit; font-weight: 800; cursor: pointer; }.notice.success { background: #e7f5f0; color: #0f6e56; }.notice.warning { background: #fff4d9; color: #855d08; }.notice.danger { background: #ffebe5; color: #a63820; }.btn-quiet { border: 1px solid #91b7c4; background: #fff; color: #0c6e8d; }.state,.empty { min-height: 140px; display: grid; place-content: center; justify-items: center; color: var(--muted); text-align: center; }.spinner { width: 1.6rem; height: 1.6rem; border: 3px solid #dce8e4; border-top-color: #0c6e8d; border-radius: 50%; animation: spin .8s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1080px) { .metric-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }.form-grid,.form-grid.compact { grid-template-columns: repeat(2,minmax(0,1fr)); }.card-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }.truth-bar { grid-template-columns: 1fr 1fr; }.truth-bar span:last-child { grid-column: 1/-1; } }
@media (max-width: 640px) { .page-head,.section-head { align-items: flex-start; }.metric-grid,.form-grid,.form-grid.compact,.card-grid { grid-template-columns: 1fr; }.tabs { grid-template-columns: repeat(5,minmax(0,1fr)); }.tabs button { font-size: .7rem; }.truth-bar { grid-template-columns: 1fr; }.truth-bar span:last-child { grid-column: auto; }.panel { padding: .8rem; }.table-wrap { overflow: visible; }.table,.table tbody { display: block; width: 100%; min-width: 0; }.table thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }.table tr { display: grid; gap: .45rem; width: 100%; padding: .75rem 0; border-bottom: 1px solid var(--border); }.table td { display: grid; grid-template-columns: minmax(6.3rem,42%) minmax(0,1fr); gap: .55rem; width: 100%; padding: 0; border: 0; overflow-wrap: anywhere; }.table td::before { content: attr(data-label); color: var(--muted); font-size: .72rem; font-weight: 700; }.table td.empty { grid-template-columns: 1fr; }.table td.empty::before { content: none; }.compact-list p { grid-template-columns: 1fr; }.notice { align-items: flex-start; flex-wrap: wrap; }.notice button { margin-left: 0; } }
</style>
