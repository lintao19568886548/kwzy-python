<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiRequestError, http } from "@/api/http";
import {
  engagementIdempotencyHeaders,
  fetchEngagementWorkspace,
  type Activity,
  type ActivityRegistration,
  type Announcement,
  type EngagementMode,
  type EngagementOverview,
  type Policy,
  type ServiceCase,
  type ServiceCatalog,
} from "@/api/engagement";
import { useAuthStore } from "@/stores/auth";

type Tab = "overview" | "policies" | "services" | "activities" | "announcements";
type Drawer = "policy" | "service" | "activity" | "announcement" | null;

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const canStaff = computed(
  () =>
    auth.can("*") ||
    [
      "engagement:policy_manage",
      "engagement:service_manage",
      "engagement:activity_manage",
      "engagement:announcement_manage",
    ].some((code) => auth.can(code))
);
const canTenant = computed(
  () =>
    auth.can("*") ||
    auth.can("engagement:read") ||
    auth.can("engagement:service_request") ||
    auth.can("engagement:activity_register")
);
const mode = ref<EngagementMode>(canStaff.value ? "staff" : "tenant");
const tabs: Array<[Tab, string]> = [
  ["overview", "总览"],
  ["policies", "政策"],
  ["services", "企业服务"],
  ["activities", "园区活动"],
  ["announcements", "公告"],
];
const activeTab = ref<Tab>(
  tabs.some(([value]) => value === route.query.tab) ? (route.query.tab as Tab) : "overview"
);
const loading = ref(true);
const saving = ref(false);
const online = ref(navigator.onLine);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const drawer = ref<Drawer>(null);
const overview = ref<EngagementOverview | null>(null);
const policies = ref<Policy[]>([]);
const services = ref<ServiceCatalog[]>([]);
const cases = ref<ServiceCase[]>([]);
const activities = ref<Activity[]>([]);
const registrations = ref<ActivityRegistration[]>([]);
const announcements = ref<Announcement[]>([]);
const inbox = ref<Array<{ delivery_id: number; announcement_id: number; title: string; content_text: string; status: string; read_at: string | null }>>([]);
const matches = reactive<Record<number, { local_relevance: boolean; matched_reasons: string[]; unmet_reasons: string[] }>>({});

const defaultParkId = Number(auth.parkIds[0] || 0);
const nowLocal = (hours: number) => {
  const value = new Date(Date.now() + hours * 3_600_000);
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
};
const policyDraft = reactive({ park_id: defaultParkId, code: "", title: "", content_text: "", category: "GENERAL" });
const serviceDraft = reactive({ park_id: defaultParkId, code: "", title: "", description: "", sla_hours: 24 });
const activityDraft = reactive({ park_id: defaultParkId, code: "", title: "", description: "", location: "", starts_at: nowLocal(24), ends_at: nowLocal(26), registration_opens_at: nowLocal(-1), registration_closes_at: nowLocal(12), capacity: 30, cancellation_terms: "活动开始前可取消。" });
const announcementDraft = reactive({ park_id: defaultParkId, code: "", title: "", content_text: "", priority: "NORMAL", publish_at: nowLocal(0), expires_at: nowLocal(168) });

const metricCards = computed(() => [
  ["已发布政策", overview.value?.published_policies ?? 0],
  ["服务目录", overview.value?.published_services ?? 0],
  ["开放服务单", overview.value?.open_service_cases ?? 0],
  ["活动 / 公告", `${overview.value?.published_activities ?? 0} / ${overview.value?.published_announcements ?? 0}`],
]);

function setConnectivity() {
  online.value = navigator.onLine;
}

function statusClass(status: string) {
  if (["PUBLISHED", "CONFIRMED", "COMPLETED", "DELIVERED", "READ", "ACTIVE"].includes(status)) return "ok";
  if (["EXPIRED", "WITHDRAWN", "CANCELLED", "FAILED", "REJECTED"].includes(status)) return "risk";
  return "pending";
}

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function apiError(value: unknown) {
  if (value instanceof ApiRequestError) {
    errorStatus.value = value.status;
    return value.message;
  }
  errorStatus.value = 0;
  return value instanceof Error ? value.message : "请求失败";
}

async function loadAll() {
  loading.value = true;
  error.value = "";
  try {
    const data = await fetchEngagementWorkspace(mode.value);
    overview.value = data.overview;
    policies.value = data.policies;
    services.value = data.services;
    cases.value = data.cases;
    activities.value = data.activities;
    registrations.value = data.registrations;
    announcements.value = data.announcements;
    inbox.value = data.inbox;
  } catch (value) {
    error.value = apiError(value);
  } finally {
    loading.value = false;
  }
}

async function command(run: () => Promise<unknown>, message: string) {
  if (!online.value) {
    errorStatus.value = 0;
    error.value = "当前离线，操作未提交；请恢复网络后重试。";
    return;
  }
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await run();
    success.value = message;
    drawer.value = null;
    await loadAll();
  } catch (value) {
    error.value = apiError(value);
  } finally {
    saving.value = false;
  }
}

async function selectMode(value: EngagementMode) {
  mode.value = value;
  await loadAll();
}

async function selectTab(value: Tab) {
  activeTab.value = value;
  await router.replace({ query: { ...route.query, tab: value } });
}

async function createPolicy() {
  await command(
    () =>
      http.post("/engagement/staff/policies", {
        ...policyDraft,
        summary: "本地相关性提示，不替代政府资格认定。",
        region_code: null,
        source_type: "LOCAL",
        source_system: "KWZY_PC",
        source_identifier: `PC-${Date.now()}`,
        source_publisher: "园区企业服务中心",
        source_url: null,
        allowed_hosts: [],
        source_published_at: new Date().toISOString(),
        effective_on: new Date().toISOString().slice(0, 10),
        expires_on: null,
        attachment_ids: [],
        applicability: [],
      }),
    "政策草稿已建立"
  );
}

async function createService() {
  await command(
    () =>
      http.post("/engagement/staff/services", {
        ...serviceDraft,
        category: "ADVISORY",
        provider_type: "INTERNAL",
        provider_name: "园区企业服务中心",
        provider_state: "LOCAL",
        appointment_required: false,
        eligibility: [],
        evidence_rules: [],
        price_amount: null,
        currency: "CNY",
      }),
    "服务目录草稿已建立"
  );
}

async function createActivity() {
  await command(
    () =>
      http.post("/engagement/staff/activities", {
        ...activityDraft,
        starts_at: new Date(activityDraft.starts_at).toISOString(),
        ends_at: new Date(activityDraft.ends_at).toISOString(),
        registration_opens_at: new Date(activityDraft.registration_opens_at).toISOString(),
        registration_closes_at: new Date(activityDraft.registration_closes_at).toISOString(),
        attachment_ids: [],
        attendee_rules: [],
        audience: [],
      }),
    "活动草稿已建立"
  );
}

async function createAnnouncement() {
  await command(
    () =>
      http.post("/engagement/staff/announcements", {
        ...announcementDraft,
        pin_from: null,
        pin_to: null,
        publish_at: new Date(announcementDraft.publish_at).toISOString(),
        expires_at: announcementDraft.expires_at ? new Date(announcementDraft.expires_at).toISOString() : null,
        attachment_ids: [],
        audience: [{ type: "TENANT_PRINCIPAL", ids: [], codes: [] }],
      }),
    "公告草稿已建立"
  );
}

async function submit(kind: "policies" | "services" | "activities" | "announcements", row: { id: number; lock_version: number }) {
  const definition = window.prompt("请输入与该业务类型匹配的原生审批定义编码");
  if (!definition) return;
  await command(
    () =>
      http.post(
        `/engagement/staff/${kind}/${row.id}/submit`,
        { expected_version: row.lock_version, definition_code: definition, priority: "MEDIUM" },
        { headers: engagementIdempotencyHeaders(`pc-engagement-${kind}-submit`) }
      ),
    "已提交原生审批；审批通过后再发布"
  );
}

async function publish(kind: "policies" | "services" | "activities" | "announcements", row: { id: number; lock_version: number }) {
  await command(
    () => http.post(`/engagement/staff/${kind}/${row.id}/publish`, { expected_version: row.lock_version }),
    "已发布审批通过的精确版本"
  );
}

async function matchPolicy(row: Policy) {
  await command(async () => {
    const response = await http.post(`/engagement/tenant/policies/${row.id}/match`, undefined, { headers: engagementIdempotencyHeaders("pc-policy-match") });
    matches[row.id] = response.data.data;
  }, "已生成可解释的本地相关性结果");
}

async function consultPolicy(row: Policy) {
  const question = window.prompt("请输入本地政策咨询问题");
  if (!question) return;
  await command(
    () => http.post(`/engagement/tenant/policies/${row.id}/consultations`, { park_id: row.park_id, subject: `咨询：${row.version.title}`, question }, { headers: engagementIdempotencyHeaders("pc-policy-consult") }),
    "本地咨询已建立；未向政府系统申报"
  );
}

async function requestService(row: ServiceCatalog) {
  const description = window.prompt("请描述服务需求");
  if (!description) return;
  await command(
    () => http.post("/engagement/tenant/service-cases", { catalog_id: row.id, priority: "MEDIUM", subject: row.version.title, description, contact_last4: null }, { headers: engagementIdempotencyHeaders("pc-service-case") }),
    "服务申请已绑定当前企业主体"
  );
}

async function advanceCase(row: ServiceCase) {
  const next: Record<string, string> = { SUBMITTED: "ACCEPTED", ACCEPTED: "ASSIGNED", ASSIGNED: "IN_PROGRESS", IN_PROGRESS: "RESULT_READY" };
  const target = next[row.status];
  if (!target) return;
  const body: Record<string, unknown> = { expected_version: row.lock_version, target_status: target, note: "PC 企业服务工作台推进" };
  if (target === "ASSIGNED") body.assigned_to = auth.userId;
  if (target === "RESULT_READY") body.result_summary = window.prompt("请输入本地服务结果") || "本地服务结果已形成";
  await command(
    () => http.post(`/engagement/staff/service-cases/${row.id}/transition`, body, { headers: engagementIdempotencyHeaders("pc-service-transition") }),
    `服务单已推进至 ${target}`
  );
}

async function confirmCase(row: ServiceCase) {
  await command(
    () => http.post(`/engagement/tenant/service-cases/${row.id}/transition`, { expected_version: row.lock_version, target_status: "CONFIRMED" }, { headers: engagementIdempotencyHeaders("pc-service-confirm") }),
    "已确认本地服务结果"
  );
}

async function registerActivity(row: Activity) {
  await command(
    () => http.post(`/engagement/tenant/activities/${row.id}/registrations`, { attendee_count: 1 }, { headers: engagementIdempotencyHeaders("pc-activity-register") }),
    "活动报名已记录；满员时进入有序候补"
  );
}

async function checkIn(row: ActivityRegistration) {
  await command(
    () => http.post(`/engagement/staff/activity-registrations/${row.id}/check-in`, { expected_version: row.lock_version, evidence_note: "PC 工作台现场身份核验" }, { headers: engagementIdempotencyHeaders("pc-activity-checkin") }),
    "签到证据已追加"
  );
}

async function fanout() {
  await command(() => http.post("/engagement/staff/announcements/fanout", { limit: 200 }), "站内信批次已处理；外部渠道仍未连接");
}

async function markRead(deliveryId: number) {
  await command(() => http.post(`/engagement/tenant/announcement-inbox/${deliveryId}/read`), "公告已标记为已读");
}

onMounted(() => {
  window.addEventListener("online", setConnectivity);
  window.addEventListener("offline", setConnectivity);
  void loadAll();
});
onBeforeUnmount(() => {
  window.removeEventListener("online", setConnectivity);
  window.removeEventListener("offline", setConnectivity);
});
watch(
  () => route.query.tab,
  (value) => {
    if (tabs.some(([tab]) => tab === value)) activeTab.value = value as Tab;
  }
);
</script>

<template>
  <section class="engagement-page" data-testid="engagement-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">PARK · ENTERPRISE ENGAGEMENT</p>
        <h1 data-testid="engagement-title">政策、企业服务、活动与公告</h1>
        <p>本地业务真值、版本证据和 Party 范围共用一套工作台；政府、外部服务商与外部通知不会被伪装成已连接。</p>
      </div>
      <div class="head-actions">
        <div class="mode-switch" aria-label="工作台角色模式">
          <button v-if="canStaff" type="button" :class="{ active: mode === 'staff' }" data-testid="engagement-mode-staff" @click="selectMode('staff')">工作人员</button>
          <button v-if="canTenant" type="button" :class="{ active: mode === 'tenant' }" data-testid="engagement-mode-tenant" @click="selectMode('tenant')">企业主体</button>
        </div>
        <button class="btn secondary" type="button" :disabled="loading" data-testid="engagement-refresh" @click="loadAll">刷新真实数据</button>
      </div>
    </header>

    <div v-if="!online" class="notice warning" data-testid="engagement-offline"><b>当前离线</b><span>所有命令已阻止，不会展示伪成功。</span><button type="button" @click="loadAll">重试</button></div>
    <div v-if="error" class="notice danger" data-testid="engagement-error"><b>{{ errorStatus === 403 ? '权限不足' : errorStatus === 409 ? '版本或状态冲突' : '加载或操作失败' }}</b><span>{{ error }}</span><button type="button" @click="loadAll">刷新后重试</button></div>
    <div v-if="success" class="notice success" data-testid="engagement-success">{{ success }}</div>

    <section class="metric-grid" aria-label="真实业务指标">
      <article v-for="card in metricCards" :key="card[0]" class="card metric"><span>{{ card[0] }}</span><strong>{{ card[1] }}</strong><small>当前数据库范围</small></article>
    </section>

    <section class="truth-strip" data-testid="engagement-truth">
      <b>能力边界</b>
      <span>政策：本地相关性 ≠ 官方资格</span>
      <span>外部服务商：未连接</span>
      <span>通知：仅站内信</span>
      <span>生产触达：否</span>
    </section>

    <nav class="card tabs" aria-label="企业参与工作台">
      <button v-for="tab in tabs" :key="tab[0]" type="button" :class="{ active: activeTab === tab[0] }" :data-testid="`engagement-tab-${tab[0]}`" @click="selectTab(tab[0])">{{ tab[1] }}</button>
    </nav>

    <section v-if="loading" class="card state" data-testid="engagement-loading"><span class="spinner" /><p>正在读取 PostgreSQL engagement 真值…</p></section>

    <template v-else-if="activeTab === 'overview'">
      <section class="overview-grid">
        <article class="card panel"><p class="eyebrow">ROLE-AWARE WORKSPACE</p><h2>{{ mode === 'staff' ? '工作人员治理视图' : '企业主体自助视图' }}</h2><p>{{ mode === 'staff' ? '可管理草稿、审批发布、服务进度、签到和站内分发。' : '只显示持久化主体和园区授权下的政策、申请、报名与收件箱。' }}</p></article>
        <article class="card panel"><p class="eyebrow">MIGRATION TRUTH</p><h2>真实旧库迁移仍阻塞</h2><p>当前页面只使用本地新模型。独立 notice 导出、Party/park 键映射和生产负责人批准前，不声称旧数据已迁移。</p></article>
      </section>
    </template>

    <template v-else-if="activeTab === 'policies'">
      <section class="card panel">
        <div class="section-head"><div><p class="eyebrow">VERSION + PROVENANCE</p><h2>政策治理</h2></div><button v-if="mode === 'staff' && auth.can(['engagement:policy_manage'])" class="btn" type="button" data-testid="engagement-add-policy" @click="drawer = 'policy'">新建政策</button></div>
        <div class="card-grid">
          <article v-for="row in policies" :key="row.id" class="item-card" :data-testid="`policy-card-${row.id}`">
            <header><b>{{ row.code }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header>
            <h3>{{ row.version.title }}</h3><p>{{ row.version.summary || '无摘要' }}</p>
            <dl><div><dt>版本 / 校验和</dt><dd>v{{ row.version.version }} · {{ row.version.checksum.slice(0, 12) }}</dd></div><div><dt>来源</dt><dd>{{ row.version.source_publisher }}</dd></div><div><dt>有效期</dt><dd>{{ row.version.effective_on || '即时' }} → {{ row.version.expires_on || '长期' }}</dd></div></dl>
            <div v-if="matches[row.id]" class="match-result" :class="{ matched: matches[row.id].local_relevance }"><b>{{ matches[row.id].local_relevance ? '本地相关' : '本地条件未满足' }}</b><span>{{ matches[row.id].local_relevance ? matches[row.id].matched_reasons.join('；') || '无附加规则' : matches[row.id].unmet_reasons.join('；') }}</span><small>不构成政府资格认定</small></div>
            <footer><span>适用规则 {{ row.version.applicability.length }}</span><div class="inline-actions"><button v-if="mode === 'staff' && row.status === 'DRAFT'" class="link-btn" type="button" @click="submit('policies', row)">提交审批</button><button v-if="mode === 'staff' && row.status === 'PENDING_APPROVAL'" class="link-btn" type="button" @click="publish('policies', row)">发布已批准版本</button><button v-if="mode === 'tenant'" class="link-btn" type="button" @click="matchPolicy(row)">相关性匹配</button><button v-if="mode === 'tenant'" class="link-btn" type="button" @click="consultPolicy(row)">本地咨询</button></div></footer>
          </article>
          <p v-if="policies.length === 0" class="empty">当前范围没有可见政策；不会用外部链接或假数据填充</p>
        </div>
      </section>
    </template>

    <template v-else-if="activeTab === 'services'">
      <section class="card panel">
        <div class="section-head"><div><p class="eyebrow">PARTY-BOUND CASES</p><h2>企业服务目录与申请</h2></div><button v-if="mode === 'staff' && auth.can(['engagement:service_manage'])" class="btn" type="button" data-testid="engagement-add-service" @click="drawer = 'service'">新建服务</button></div>
        <div class="card-grid"><article v-for="row in services" :key="row.id" class="item-card"><header><b>{{ row.code }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header><h3>{{ row.version.title }}</h3><p>{{ row.version.description }}</p><dl><div><dt>服务方</dt><dd>{{ row.version.provider.name }} · {{ row.version.provider.state }}</dd></div><div><dt>SLA</dt><dd>{{ row.version.sla_hours }} 小时</dd></div><div><dt>价格真值</dt><dd>{{ row.version.price.amount ?? '未定价' }} {{ row.version.price.currency }}</dd></div></dl><footer><span>v{{ row.version.version }} · {{ row.version.checksum.slice(0, 10) }}</span><div class="inline-actions"><button v-if="mode === 'staff' && row.status === 'DRAFT'" class="link-btn" type="button" @click="submit('services', row)">提交审批</button><button v-if="mode === 'staff' && row.status === 'PENDING_APPROVAL'" class="link-btn" type="button" @click="publish('services', row)">发布</button><button v-if="mode === 'tenant'" class="link-btn" type="button" @click="requestService(row)">申请服务</button></div></footer></article><p v-if="services.length === 0" class="empty">当前范围没有可申请的服务目录</p></div>
        <h3 class="subhead">服务单证据</h3><div class="case-list"><article v-for="row in cases" :key="row.id" class="case-row"><div><b>{{ row.case_no }} · {{ row.subject }}</b><span>Party #{{ row.party_id }} · SLA {{ formatTime(row.sla_due_at) }}</span></div><div><span class="status" :class="statusClass(row.status)">{{ row.status }}</span><small>{{ row.events.length }} 条追加事件</small></div><div class="inline-actions"><button v-if="mode === 'staff' && ['SUBMITTED','ACCEPTED','ASSIGNED','IN_PROGRESS'].includes(row.status)" class="link-btn" type="button" @click="advanceCase(row)">推进</button><button v-if="mode === 'tenant' && row.status === 'RESULT_READY'" class="link-btn" type="button" @click="confirmCase(row)">确认结果</button></div></article><p v-if="cases.length === 0" class="empty compact">暂无服务申请</p></div>
      </section>
    </template>

    <template v-else-if="activeTab === 'activities'">
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">SERIALIZED CAPACITY</p><h2>园区活动与报名</h2></div><button v-if="mode === 'staff' && auth.can(['engagement:activity_manage'])" class="btn" type="button" data-testid="engagement-add-activity" @click="drawer = 'activity'">新建活动</button></div><div class="card-grid"><article v-for="row in activities" :key="row.id" class="item-card"><header><b>{{ row.code }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header><h3>{{ row.version.title }}</h3><p>{{ row.version.location }} · {{ formatTime(row.version.starts_at) }}</p><div class="capacity"><span :style="{ width: `${Math.min(100, (row.version.confirmed_count / row.version.capacity) * 100)}%` }" /></div><dl><div><dt>容量</dt><dd>{{ row.version.confirmed_count }} / {{ row.version.capacity }}</dd></div><div><dt>候补</dt><dd>{{ row.version.waitlist_count }}</dd></div><div><dt>报名截止</dt><dd>{{ formatTime(row.version.registration_closes_at) }}</dd></div></dl><footer><span>v{{ row.version.version }} · {{ row.version.cancellation_terms }}</span><div class="inline-actions"><button v-if="mode === 'staff' && row.status === 'DRAFT'" class="link-btn" type="button" @click="submit('activities', row)">提交审批</button><button v-if="mode === 'staff' && row.status === 'PENDING_APPROVAL'" class="link-btn" type="button" @click="publish('activities', row)">发布</button><button v-if="mode === 'tenant'" class="link-btn" type="button" @click="registerActivity(row)">报名</button></div></footer></article><p v-if="activities.length === 0" class="empty">当前没有开放活动</p></div><h3 class="subhead">报名与签到</h3><div class="case-list"><article v-for="row in registrations" :key="row.id" class="case-row"><div><b>报名 #{{ row.id }}</b><span>活动 #{{ row.activity_id }} · 精确版本 #{{ row.activity_version_id }} · {{ row.attendee_count }} 人</span></div><div><span class="status" :class="statusClass(row.status)">{{ row.status }}</span><small>{{ row.waitlist_position ? `候补 ${row.waitlist_position}` : formatTime(row.checked_in_at) }}</small></div><button v-if="mode === 'staff' && row.status === 'CONFIRMED'" class="link-btn" type="button" @click="checkIn(row)">签到核验</button></article><p v-if="registrations.length === 0" class="empty compact">暂无报名记录</p></div></section>
    </template>

    <template v-else>
      <section class="card panel"><div class="section-head"><div><p class="eyebrow">FROZEN AUDIENCE + IN-APP ONLY</p><h2>公告与送达证据</h2></div><div class="inline-actions"><button v-if="mode === 'staff'" class="btn secondary" type="button" @click="fanout">处理站内分发</button><button v-if="mode === 'staff' && auth.can(['engagement:announcement_manage'])" class="btn" type="button" data-testid="engagement-add-announcement" @click="drawer = 'announcement'">新建公告</button></div></div><div class="card-grid"><article v-for="row in announcements" :key="row.id" class="item-card"><header><b>{{ row.version.priority }}</b><span class="status" :class="statusClass(row.status)">{{ row.status }}</span></header><h3>{{ row.version.title }}</h3><p>{{ row.version.content_text }}</p><dl><div><dt>发布</dt><dd>{{ formatTime(row.version.publish_at) }}</dd></div><div><dt>到期</dt><dd>{{ formatTime(row.version.expires_at) }}</dd></div><div><dt>冻结受众规则</dt><dd>{{ row.version.audience.length }}</dd></div></dl><footer><span>v{{ row.version.version }} · {{ row.version.checksum.slice(0, 12) }}</span><div class="inline-actions"><button v-if="mode === 'staff' && row.status === 'DRAFT'" class="link-btn" type="button" @click="submit('announcements', row)">提交审批</button><button v-if="mode === 'staff' && row.status === 'PENDING_APPROVAL'" class="link-btn" type="button" @click="publish('announcements', row)">发布 / 定时</button></div></footer></article><p v-if="announcements.length === 0" class="empty">当前没有有效公告</p></div><template v-if="mode === 'tenant'"><h3 class="subhead">站内收件箱</h3><div class="case-list"><article v-for="row in inbox" :key="row.delivery_id" class="case-row"><div><b>{{ row.title }}</b><span>{{ row.content_text }}</span></div><span class="status" :class="statusClass(row.status)">{{ row.status }}</span><button v-if="row.status === 'DELIVERED'" class="link-btn" type="button" @click="markRead(row.delivery_id)">标记已读</button></article><p v-if="inbox.length === 0" class="empty compact">当前没有站内投递</p></div></template></section>
    </template>

    <aside v-if="drawer" class="drawer-backdrop" data-testid="engagement-drawer" @click.self="drawer = null"><section class="drawer card"><header><div><p class="eyebrow">GOVERNED DRAFT</p><h2>新建{{ drawer === 'policy' ? '政策' : drawer === 'service' ? '服务目录' : drawer === 'activity' ? '活动' : '公告' }}草稿</h2></div><button class="close" type="button" aria-label="关闭" @click="drawer = null">×</button></header>
      <form v-if="drawer === 'policy'" class="form" @submit.prevent="createPolicy"><label>园区 ID<input v-model.number="policyDraft.park_id" type="number" min="1" required /></label><label>政策编码<input v-model="policyDraft.code" required pattern="[A-Za-z][A-Za-z0-9_-]+" /></label><label>标题<input v-model="policyDraft.title" required /></label><label>分类<input v-model="policyDraft.category" required /></label><label>正文<textarea v-model="policyDraft.content_text" required /></label><p class="form-hint">保存的是本地草稿；来源、版本、校验和与审批门禁会保留。</p><button class="btn" type="submit" :disabled="saving">保存政策草稿</button></form>
      <form v-else-if="drawer === 'service'" class="form" @submit.prevent="createService"><label>园区 ID<input v-model.number="serviceDraft.park_id" type="number" min="1" required /></label><label>服务编码<input v-model="serviceDraft.code" required pattern="[A-Za-z][A-Za-z0-9_-]+" /></label><label>标题<input v-model="serviceDraft.title" required /></label><label>描述<textarea v-model="serviceDraft.description" required /></label><label>SLA 小时<input v-model.number="serviceDraft.sla_hours" type="number" min="1" max="8760" required /></label><p class="form-hint">外部服务商必须显示 NOT_CONNECTED；本表单只建立园区内部服务。</p><button class="btn" type="submit" :disabled="saving">保存服务草稿</button></form>
      <form v-else-if="drawer === 'activity'" class="form" @submit.prevent="createActivity"><label>园区 ID<input v-model.number="activityDraft.park_id" type="number" min="1" required /></label><label>活动编码<input v-model="activityDraft.code" required pattern="[A-Za-z][A-Za-z0-9_-]+" /></label><label>标题<input v-model="activityDraft.title" required /></label><label>描述<textarea v-model="activityDraft.description" required /></label><label>地点<input v-model="activityDraft.location" required /></label><div class="form-grid"><label>报名开始<input v-model="activityDraft.registration_opens_at" type="datetime-local" required /></label><label>报名截止<input v-model="activityDraft.registration_closes_at" type="datetime-local" required /></label><label>活动开始<input v-model="activityDraft.starts_at" type="datetime-local" required /></label><label>活动结束<input v-model="activityDraft.ends_at" type="datetime-local" required /></label></div><label>容量<input v-model.number="activityDraft.capacity" type="number" min="1" required /></label><label>取消条款<textarea v-model="activityDraft.cancellation_terms" required /></label><button class="btn" type="submit" :disabled="saving">保存活动草稿</button></form>
      <form v-else class="form" @submit.prevent="createAnnouncement"><label>园区 ID<input v-model.number="announcementDraft.park_id" type="number" min="1" required /></label><label>公告编码<input v-model="announcementDraft.code" required pattern="[A-Za-z][A-Za-z0-9_-]+" /></label><label>标题<input v-model="announcementDraft.title" required /></label><label>正文<textarea v-model="announcementDraft.content_text" required /></label><label>优先级<select v-model="announcementDraft.priority"><option>NORMAL</option><option>IMPORTANT</option><option>URGENT</option></select></label><div class="form-grid"><label>发布时间<input v-model="announcementDraft.publish_at" type="datetime-local" required /></label><label>到期时间<input v-model="announcementDraft.expires_at" type="datetime-local" /></label></div><p class="form-hint">受众在实际发布时冻结；当前只会生成站内信。</p><button class="btn" type="submit" :disabled="saving">保存公告草稿</button></form>
    </section></aside>
  </section>
</template>

<style scoped>
.engagement-page{display:grid;gap:1rem;width:100%;min-width:0;overflow-x:hidden}.engagement-page>*{min-width:0;max-width:100%}.page-head,.section-head,.drawer header,.head-actions{display:flex;align-items:center;justify-content:space-between;gap:1rem}.page-head h1{margin:.15rem 0;font-size:clamp(1.65rem,3vw,2.45rem);letter-spacing:-.04em}.page-head p:last-child,.panel>p,.item-card p{color:var(--muted)}.eyebrow{margin:0;color:#8a5d12;font-size:.67rem;font-weight:900;letter-spacing:.14em}.head-actions{align-items:flex-end;flex-direction:column}.mode-switch{display:flex;padding:.25rem;border-radius:10px;background:#e8eff1}.mode-switch button{border:0;border-radius:8px;padding:.5rem .75rem;background:transparent;color:var(--muted);cursor:pointer}.mode-switch button.active{background:#fff;color:#123f50;box-shadow:0 2px 8px rgba(17,61,80,.12);font-weight:800}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8rem}.metric{padding:1rem;border-top:3px solid #d49326}.metric span,.metric small{display:block;color:var(--muted)}.metric strong{display:block;margin:.25rem 0;color:#153f4d;font-size:1.75rem}.truth-strip{display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;padding:.75rem 1rem;border-left:4px solid #db6d42;border-radius:10px;background:#fff2ea;color:#713722;font-size:.74rem}.truth-strip span{padding:.2rem .5rem;border-radius:99px;background:#fff}.tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.35rem;padding:.45rem}.tabs button{border:0;border-radius:9px;padding:.65rem;background:transparent;color:var(--muted);cursor:pointer}.tabs button.active{background:#fff1cf;color:#80550b;font-weight:800}.overview-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.panel{padding:1rem}.section-head h2,.drawer h2{margin:.15rem 0}.card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem;margin-top:.9rem}.item-card{display:grid;gap:.55rem;padding:.9rem;border:1px solid var(--border);border-radius:13px;background:#fbfcfd}.item-card header,.item-card footer{display:flex;align-items:center;justify-content:space-between;gap:.5rem;flex-wrap:wrap}.item-card h3{margin:0}.item-card p{margin:0;font-size:.78rem;white-space:pre-wrap}.item-card dl{display:grid;gap:.35rem;margin:0}.item-card dl div{display:grid;grid-template-columns:6.3rem minmax(0,1fr);gap:.5rem;font-size:.72rem}.item-card dt{color:var(--muted)}.item-card dd{margin:0;overflow-wrap:anywhere}.item-card footer{padding-top:.55rem;border-top:1px solid var(--border);color:var(--muted);font-size:.72rem}.status{display:inline-flex;width:max-content;padding:.18rem .5rem;border-radius:99px;font-size:.66rem;font-weight:850}.status.ok{background:#e2f4ed;color:#0e6e53}.status.pending{background:#fff0c9;color:#805600}.status.risk{background:#ffe7df;color:#a63d23}.inline-actions,.form-grid{display:flex;gap:.55rem;flex-wrap:wrap}.link-btn{border:0;background:transparent;color:#087b9c;font-weight:800;cursor:pointer}.match-result{display:grid;gap:.2rem;padding:.55rem;border-radius:9px;background:#fff2e8;color:#83441f;font-size:.7rem}.match-result.matched{background:#e4f4ed;color:#126b51}.case-list{display:grid;gap:.55rem}.case-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:.8rem;align-items:center;padding:.75rem;border:1px solid var(--border);border-radius:10px}.case-row>div{display:grid;gap:.2rem}.case-row span,.case-row small{color:var(--muted);font-size:.72rem}.subhead{margin:1.2rem 0 .6rem}.capacity{height:.35rem;border-radius:99px;background:#e5edef;overflow:hidden}.capacity span{display:block;height:100%;background:#d49326}.secondary{border:1px solid #9ab7c1;background:#fff;color:#155d75}.notice{display:flex;align-items:center;gap:.7rem;padding:.7rem .9rem;border-radius:10px;font-size:.8rem}.notice button{margin-left:auto;border:0;background:transparent;color:inherit;font-weight:800}.notice.success{background:#e5f5ef;color:#0e6e53}.notice.warning{background:#fff2d5;color:#805b09}.notice.danger{background:#ffe9e2;color:#a33720}.state,.empty{min-height:120px;display:grid;place-content:center;justify-items:center;color:var(--muted);text-align:center}.empty.compact{min-height:70px}.spinner{width:1.6rem;height:1.6rem;border:3px solid #dce8e4;border-top-color:#b87513;border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.drawer-backdrop{position:fixed;inset:0;z-index:40;display:flex;justify-content:flex-end;background:rgba(6,25,34,.4)}.drawer{width:min(480px,100%);height:100%;padding:1.2rem;border-radius:18px 0 0 18px;overflow:auto}.close{border:0;background:transparent;font-size:1.8rem;color:var(--muted);cursor:pointer}.form{display:grid;gap:.8rem;margin-top:1rem}.form label{display:grid;gap:.35rem;color:var(--muted);font-size:.76rem}.form input,.form textarea,.form select{width:100%;padding:.65rem;border:1px solid var(--border);border-radius:9px;background:#fff;color:var(--text)}.form textarea{min-height:96px;resize:vertical}.form-grid>*{flex:1 1 180px}.form-hint{padding:.65rem;border-radius:9px;background:#fff2d8;color:#74510c;font-size:.73rem}
@media(max-width:1050px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:820px){.page-head,.section-head{align-items:flex-start;flex-direction:column}.head-actions{width:100%;align-items:stretch}.mode-switch>*{flex:1}.tabs{overflow-x:auto;scrollbar-width:thin}.tabs button{min-width:7rem}.overview-grid,.card-grid{grid-template-columns:1fr}.case-row{grid-template-columns:1fr auto}.case-row>.inline-actions{grid-column:1/-1}.truth-strip{align-items:flex-start}}
@media(max-width:480px){.metric-grid{grid-template-columns:1fr 1fr;gap:.5rem}.metric{padding:.75rem}.metric strong{font-size:1.3rem}.tabs{grid-template-columns:repeat(5,max-content)}.case-row{grid-template-columns:1fr}.item-card dl div{grid-template-columns:1fr}.drawer{border-radius:0;padding:1rem}.page-head h1{font-size:1.55rem}.inline-actions{width:100%}.inline-actions button{min-height:34px}.notice{align-items:flex-start;flex-wrap:wrap}.notice button{margin-left:0}}
</style>
