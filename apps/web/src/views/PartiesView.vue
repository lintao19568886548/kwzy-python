<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type DirectoryRow = {
  party_id: number;
  name: string;
  short_name: string | null;
  credit_code: string | null;
  status: string;
  blacklist_status: string;
  registration_status: string;
  industry_name: string | null;
  employee_size_band: string;
  provider_status: string;
  completeness_score: number;
  park_ids: number[];
  local_risk?: { overall_level: string; unresolved_count: number };
};

type EnterpriseProfile = {
  party_id: number;
  party_name: string;
  credit_code: string | null;
  profile_id: number | null;
  short_name: string | null;
  legal_representative: string | null;
  established_on: string | null;
  registered_capital: string | null;
  capital_currency: string | null;
  registration_status: string;
  registration_authority: string | null;
  industry_code: string | null;
  industry_name: string | null;
  employee_size_band: string;
  website: string | null;
  business_scope: string | null;
  provider_status: string;
  lock_version: number;
  completeness_score: number;
  missing_dimensions: string[];
};

type Subresource = Record<string, unknown>;
type DirectoryPage = { total: number; page: number; page_size: number; items: DirectoryRow[] };
type RiskData = {
  summary: { overall_level: string; unresolved_count: number; label: string };
  items: Subresource[];
};

const auth = useAuthStore();
const items = ref<DirectoryRow[]>([]);
const total = ref(0);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const loading = ref(true);
const saving = ref(false);
const page = ref(1);
const pageSize = 20;
const filters = ref({
  keyword: "",
  status: "",
  blacklist_status: "",
  registration_status: "",
  industry: "",
  min_completeness: "",
  local_risk_level: "",
});
const form = ref({ name: "", party_type: "ORGANIZATION", contact_phone: "", credit_code: "" });
const contactForm = ref({ party_id: "", name: "", phone: "", email: "" });

const drawerOpen = ref(false);
const detailLoading = ref(false);
const detailError = ref("");
const selectedId = ref(0);
const party = ref<Subresource | null>(null);
const profile = ref<EnterpriseProfile | null>(null);
const relationships = ref<Subresource[]>([]);
const contacts = ref<Subresource[]>([]);
const addresses = ref<Subresource[]>([]);
const credentials = ref<Subresource[]>([]);
const tags = ref<Subresource[]>([]);
const risks = ref<RiskData | null>(null);
const conflict = ref(false);
const profileForm = ref({
  short_name: "",
  legal_representative: "",
  established_on: "",
  registered_capital: "",
  capital_currency: "CNY",
  registration_status: "UNKNOWN",
  registration_authority: "",
  industry_code: "",
  industry_name: "",
  employee_size_band: "UNKNOWN",
  website: "",
  business_scope: "",
});
const relationshipForm = ref({ target_party_id: "", relationship_type: "BUSINESS_PARTNER", ownership_percent: "" });
const tagForm = ref({ name: "", tag_type: "CUSTOM" });
const riskForm = ref({ category: "COMPLIANCE", severity: "MEDIUM", summary: "" });
const credentialForm = ref({ credential_type: "BUSINESS_LICENSE", identifier: "", issuer: "", issued_on: "", expires_on: "" });
const credentialFile = ref<File | null>(null);

const canWrite = computed(() => auth.can("party:write") || auth.can("*"));
const canReadCredentials = computed(() => auth.can("party:credential_read") || auth.can("*"));
const canManageCredentials = computed(
  () => (auth.can("party:credential_manage") && auth.can("attachment:write")) || auth.can("*")
);
const canReadRisk = computed(() => auth.can("party:risk_read") || auth.can("*"));
const canManageRisk = computed(() => auth.can("party:risk_manage") || auth.can("*"));
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

function errorText(reason: unknown, fallback: string) {
  errorStatus.value = reason instanceof ApiRequestError ? reason.status : 0;
  return reason instanceof Error ? reason.message : fallback;
}

function optional(value: string) {
  const normalized = value.trim();
  return normalized || undefined;
}

async function load() {
  loading.value = true;
  error.value = "";
  errorStatus.value = 0;
  try {
    const params: Record<string, string | number | undefined> = {
      page: page.value,
      page_size: pageSize,
    };
    Object.entries(filters.value).forEach(([key, value]) => {
      params[key] = optional(value);
    });
    const { data } = await http.get<Envelope<DirectoryPage>>("/enterprise-parties", { params });
    items.value = data.data.items;
    total.value = data.data.total;
  } catch (reason) {
    error.value = errorText(reason, "企业目录加载失败");
  } finally {
    loading.value = false;
  }
}

function applyFilters() {
  page.value = 1;
  void load();
}

async function changePage(next: number) {
  if (next < 1 || next > totalPages.value || next === page.value) return;
  page.value = next;
  await load();
}

async function create() {
  if (!form.value.name.trim() || saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    await http.post("/parties", {
      name: form.value.name.trim(),
      party_type: form.value.party_type,
      contact_phone: optional(form.value.contact_phone),
      credit_code: optional(form.value.credit_code),
    });
    success.value = form.value.party_type === "ORGANIZATION" ? "企业主体已创建" : "自然人主体已创建";
    form.value = { name: "", party_type: "ORGANIZATION", contact_phone: "", credit_code: "" };
    await load();
  } catch (reason) {
    error.value = errorText(reason, "创建失败");
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
      phone: optional(contactForm.value.phone),
      email: optional(contactForm.value.email),
      is_primary: true,
    });
    success.value = "联系人已添加";
    contactForm.value = { party_id: "", name: "", phone: "", email: "" };
    if (selectedId.value === partyId) await loadDetail(false);
  } catch (reason) {
    error.value = errorText(reason, "添加联系人失败");
  } finally {
    saving.value = false;
  }
}

function hydrateProfile(value: EnterpriseProfile) {
  profile.value = value;
  profileForm.value = {
    short_name: value.short_name || "",
    legal_representative: value.legal_representative || "",
    established_on: value.established_on || "",
    registered_capital: value.registered_capital || "",
    capital_currency: value.capital_currency || "CNY",
    registration_status: value.registration_status,
    registration_authority: value.registration_authority || "",
    industry_code: value.industry_code || "",
    industry_name: value.industry_name || "",
    employee_size_band: value.employee_size_band,
    website: value.website || "",
    business_scope: value.business_scope || "",
  };
}

async function loadDetail(resetDraft = true) {
  if (!selectedId.value) return;
  detailLoading.value = true;
  detailError.value = "";
  try {
    const requests = [
      http.get<Envelope<Subresource>>(`/parties/${selectedId.value}`),
      http.get<Envelope<EnterpriseProfile>>(`/parties/${selectedId.value}/enterprise-profile`),
      http.get<Envelope<Subresource[]>>(`/parties/${selectedId.value}/enterprise-relationships`),
      http.get<Envelope<Subresource[]>>(`/parties/${selectedId.value}/contacts`),
      http.get<Envelope<Subresource[]>>(`/parties/${selectedId.value}/addresses`),
      http.get<Envelope<Subresource[]>>(`/parties/${selectedId.value}/enterprise-tags`),
    ];
    const [partyResult, profileResult, relationResult, contactResult, addressResult, tagResult] =
      await Promise.all(requests);
    party.value = partyResult.data.data as Subresource;
    if (resetDraft) hydrateProfile(profileResult.data.data as EnterpriseProfile);
    else profile.value = profileResult.data.data as EnterpriseProfile;
    relationships.value = relationResult.data.data as Subresource[];
    contacts.value = contactResult.data.data as Subresource[];
    addresses.value = addressResult.data.data as Subresource[];
    tags.value = tagResult.data.data as Subresource[];
    credentials.value = canReadCredentials.value
      ? (await http.get<Envelope<Subresource[]>>(`/parties/${selectedId.value}/enterprise-credentials`)).data.data
      : [];
    risks.value = canReadRisk.value
      ? (await http.get<Envelope<RiskData>>(`/parties/${selectedId.value}/enterprise-risk-signals`)).data.data
      : null;
    conflict.value = false;
  } catch (reason) {
    detailError.value = errorText(reason, "企业详情加载失败");
  } finally {
    detailLoading.value = false;
  }
}

async function openDetail(row: DirectoryRow) {
  selectedId.value = row.party_id;
  drawerOpen.value = true;
  await loadDetail();
}

function closeDrawer() {
  drawerOpen.value = false;
  selectedId.value = 0;
  detailError.value = "";
  conflict.value = false;
}

async function saveProfile() {
  if (!profile.value || saving.value) return;
  saving.value = true;
  detailError.value = "";
  try {
    const payload: Record<string, string | number | undefined> = {
      expected_lock_version: profile.value.lock_version,
    };
    Object.entries(profileForm.value).forEach(([key, value]) => {
      payload[key] = optional(value);
    });
    const result = await http.put<Envelope<EnterpriseProfile>>(
      `/parties/${selectedId.value}/enterprise-profile`,
      payload
    );
    hydrateProfile(result.data.data);
    conflict.value = false;
    success.value = "企业画像已保存";
    await load();
  } catch (reason) {
    conflict.value = reason instanceof ApiRequestError && reason.status === 409;
    detailError.value = errorText(reason, "企业画像保存失败");
  } finally {
    saving.value = false;
  }
}

async function createRelationship() {
  if (saving.value) return;
  saving.value = true;
  detailError.value = "";
  try {
    await http.post(`/parties/${selectedId.value}/enterprise-relationships`, {
      target_party_id: Number(relationshipForm.value.target_party_id),
      relationship_type: relationshipForm.value.relationship_type,
      ownership_percent: optional(relationshipForm.value.ownership_percent),
    });
    relationshipForm.value = { target_party_id: "", relationship_type: "BUSINESS_PARTNER", ownership_percent: "" };
    await loadDetail(false);
  } catch (reason) {
    detailError.value = errorText(reason, "企业关系保存失败");
  } finally {
    saving.value = false;
  }
}

async function createTag() {
  if (saving.value) return;
  saving.value = true;
  detailError.value = "";
  try {
    await http.post(`/parties/${selectedId.value}/enterprise-tags`, tagForm.value);
    tagForm.value = { name: "", tag_type: "CUSTOM" };
    await loadDetail(false);
  } catch (reason) {
    detailError.value = errorText(reason, "企业标签保存失败");
  } finally {
    saving.value = false;
  }
}

async function createRisk() {
  if (saving.value) return;
  saving.value = true;
  detailError.value = "";
  try {
    await http.post(`/parties/${selectedId.value}/enterprise-risk-signals`, riskForm.value);
    riskForm.value.summary = "";
    await loadDetail(false);
  } catch (reason) {
    detailError.value = errorText(reason, "风险信号保存失败");
  } finally {
    saving.value = false;
  }
}

async function resolveRisk(row: Subresource) {
  if (saving.value) return;
  saving.value = true;
  detailError.value = "";
  try {
    await http.post(`/parties/${selectedId.value}/enterprise-risk-signals/${String(row.id)}/resolve`, {
      resolution_type: "MITIGATED",
      reason: "已由企业画像工作区人工确认处置",
    });
    await loadDetail(false);
  } catch (reason) {
    detailError.value = errorText(reason, "风险处置失败");
  } finally {
    saving.value = false;
  }
}

function fileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("文件读取失败"));
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.readAsDataURL(file);
  });
}

async function createCredential() {
  if (!credentialFile.value || saving.value) return;
  saving.value = true;
  detailError.value = "";
  try {
    const file = credentialFile.value;
    const uploaded = await http.post<Envelope<{ id: number }>>("/attachments", {
      biz_type: "PARTY_ENTERPRISE",
      biz_id: String(selectedId.value),
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      content_base64: await fileBase64(file),
    });
    await http.post(`/parties/${selectedId.value}/enterprise-credentials`, {
      attachment_id: uploaded.data.data.id,
      credential_type: credentialForm.value.credential_type,
      identifier: optional(credentialForm.value.identifier),
      issuer: optional(credentialForm.value.issuer),
      issued_on: optional(credentialForm.value.issued_on),
      expires_on: optional(credentialForm.value.expires_on),
    });
    credentialFile.value = null;
    credentialForm.value = { credential_type: "BUSINESS_LICENSE", identifier: "", issuer: "", issued_on: "", expires_on: "" };
    await loadDetail(false);
  } catch (reason) {
    detailError.value = errorText(reason, "证照上传失败");
  } finally {
    saving.value = false;
  }
}

function pickCredentialFile(event: Event) {
  credentialFile.value = (event.target as HTMLInputElement).files?.[0] || null;
}

onMounted(load);
</script>

<template>
  <main class="enterprise-page">
    <section class="hero card">
      <div>
        <span class="eyebrow">PARTY · ENTERPRISE GOVERNANCE</span>
        <h1 data-testid="parties-title">企业主体与画像</h1>
        <p>企业主档、证照证据、关联关系和本地风险保持同一租户与园区权限边界。</p>
      </div>
      <div class="hero-metrics" aria-label="企业目录摘要">
        <article><strong>{{ total }}</strong><span>当前筛选企业</span></article>
        <article><strong>{{ items.filter((row) => row.completeness_score === 100).length }}</strong><span>本页完整画像</span></article>
        <article><strong>{{ items.filter((row) => row.local_risk?.overall_level === 'CRITICAL').length }}</strong><span>本页重大风险</span></article>
      </div>
    </section>

    <section class="card filters" aria-label="企业筛选">
      <div class="filter-grid">
        <label>搜索<input v-model="filters.keyword" class="input" data-testid="party-keyword" placeholder="企业名、简称或统一信用代码" @keyup.enter="applyFilters" /></label>
        <label>主体状态<select v-model="filters.status" class="input"><option value="">全部</option><option value="ACTIVE">启用</option><option value="INACTIVE">停用</option></select></label>
        <label>登记状态<select v-model="filters.registration_status" class="input" data-testid="enterprise-registration-filter"><option value="">全部</option><option value="ACTIVE">存续</option><option value="SUSPENDED">停业</option><option value="REVOKED">吊销</option><option value="CANCELLED">注销</option><option value="UNKNOWN">未知</option></select></label>
        <label>黑名单<select v-model="filters.blacklist_status" class="input"><option value="">全部</option><option value="NORMAL">正常</option><option value="BLACKLISTED">黑名单</option></select></label>
        <label>行业<input v-model="filters.industry" class="input" placeholder="行业编码或名称" /></label>
        <label>最低完整度<input v-model="filters.min_completeness" class="input" type="number" min="0" max="100" placeholder="0—100" /></label>
        <label v-if="canReadRisk">本地风险<select v-model="filters.local_risk_level" class="input"><option value="">全部</option><option value="NONE">无未解决信号</option><option value="LOW">低</option><option value="MEDIUM">中</option><option value="HIGH">高</option><option value="CRITICAL">重大</option></select></label>
        <button class="btn" type="button" data-testid="party-filter-btn" @click="applyFilters">应用筛选</button>
      </div>
    </section>

    <section v-if="error" class="state-card error-state" data-testid="party-error" role="alert">
      <strong>{{ errorStatus === 0 ? "网络不可用" : "目录读取失败" }}</strong><span>{{ error }}</span><button type="button" class="btn btn-ghost" data-testid="party-retry" @click="load">重试</button>
    </section>
    <section v-else-if="loading" class="state-card" data-testid="party-loading"><span class="spinner"></span><strong>正在读取企业目录</strong><span>所有记录来自当前 API 与数据库</span></section>

    <section v-else class="card directory">
      <header class="section-head"><div><h2>企业目录</h2><p>共 {{ total }} 家，当前第 {{ page }} / {{ totalPages }} 页</p></div><span class="live-badge">LIVE API</span></header>
      <div v-if="!items.length" class="empty" data-testid="party-empty"><strong>没有匹配企业</strong><span>调整筛选条件后重试。</span></div>
      <div v-else class="table-wrap">
        <table class="table enterprise-table" data-testid="party-table">
          <thead><tr><th>企业</th><th>登记 / 行业</th><th>园区</th><th>画像完整度</th><th>风险</th><th></th></tr></thead>
          <tbody>
            <tr v-for="row in items" :key="row.party_id" :data-testid="`party-row-${row.party_id}`">
              <td><strong data-testid="party-name-cell">{{ row.name }}</strong><small>#{{ row.party_id }} · {{ row.credit_code || "未登记统一信用代码" }}</small></td>
              <td><span class="status-pill">{{ row.registration_status }}</span><small>{{ row.industry_name || "行业待补全" }}</small></td>
              <td>{{ row.park_ids.length ? row.park_ids.map((id) => `#${id}`).join(" · ") : "租户级" }}</td>
              <td><div class="progress"><i :style="{ width: `${row.completeness_score}%` }"></i></div><small>{{ row.completeness_score }}%</small></td>
              <td><span :class="['risk-pill', `risk-${row.local_risk?.overall_level || 'HIDDEN'}`]">{{ canReadRisk ? (row.local_risk?.overall_level || "NONE") : "无权限" }}</span><small v-if="row.blacklist_status === 'BLACKLISTED'">黑名单</small></td>
              <td><button class="text-button" type="button" :data-testid="`enterprise-open-${row.party_id}`" @click="openDetail(row)">打开画像</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <footer class="pager"><button type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button><span>{{ page }} / {{ totalPages }}</span><button type="button" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button></footer>
    </section>

    <section class="entry-grid">
      <form class="card entry-card" data-testid="party-create-form" @submit.prevent="create">
        <header><h2>新建主体</h2><span>企业进入画像目录，自然人留在主体主档</span></header>
        <input v-model="form.name" class="input" data-testid="party-name" placeholder="名称" required />
        <select v-model="form.party_type" class="input" data-testid="party-type"><option value="ORGANIZATION">企业组织</option><option value="PERSON">自然人</option></select>
        <input v-model="form.credit_code" class="input" placeholder="统一社会信用代码（企业可选）" />
        <input v-model="form.contact_phone" class="input" data-testid="party-phone" placeholder="联系电话" />
        <button v-permission="'party:write'" class="btn" data-testid="party-create-btn" type="submit" :disabled="saving">新建主体</button>
      </form>
      <form class="card entry-card" data-testid="party-contact-form" @submit.prevent="addContact">
        <header><h2>快速补充主联系人</h2><span>联系人属于 Party 子资源</span></header>
        <input v-model="contactForm.party_id" class="input" data-testid="contact-party-id" placeholder="主体 ID" required />
        <input v-model="contactForm.name" class="input" data-testid="contact-name" placeholder="联系人姓名" required />
        <input v-model="contactForm.phone" class="input" data-testid="contact-phone" placeholder="电话" />
        <button v-permission="'party:write'" class="btn btn-ghost" data-testid="contact-create-btn" type="submit" :disabled="saving">添加主联系人</button>
      </form>
    </section>
    <p v-if="success" class="toast" data-testid="party-success" role="status">{{ success }}</p>

    <div v-if="drawerOpen" class="drawer-mask" @click.self="closeDrawer">
      <aside class="drawer" data-testid="enterprise-drawer" aria-label="企业画像详情">
        <header class="drawer-head"><div><span class="eyebrow">ENTERPRISE PROFILE</span><h2>{{ profile?.party_name || `企业 #${selectedId}` }}</h2><p>{{ profile?.credit_code || "统一信用代码待补全" }}</p></div><button class="close-button" type="button" aria-label="关闭企业画像" @click="closeDrawer">×</button></header>
        <div v-if="detailError" class="detail-error" role="alert"><strong>{{ conflict ? "版本冲突，草稿已保留" : "详情操作失败" }}</strong><span>{{ detailError }}</span><button type="button" class="btn btn-ghost" data-testid="enterprise-detail-retry" @click="() => loadDetail()">{{ conflict ? "重新载入服务器版本" : "重试" }}</button></div>
        <div v-if="detailLoading" class="state-card"><span class="spinner"></span><strong>读取企业全景</strong></div>
        <div v-else-if="profile" class="drawer-body">
          <section class="profile-summary">
            <div class="score-ring"><strong>{{ profile.completeness_score }}</strong><span>画像完整度</span></div>
            <div><span :class="['risk-pill', `risk-${risks?.summary.overall_level || 'HIDDEN'}`]">本地风险 {{ canReadRisk ? (risks?.summary.overall_level || "NONE") : "无权限" }}</span><p>{{ risks?.summary.label || "本地风险信号与黑名单分别治理" }}</p><small>外部企业数据：{{ profile.provider_status }}</small></div>
          </section>

          <section class="detail-section" data-testid="enterprise-profile-section">
            <header><h3>基础画像</h3><span>版本 {{ profile.lock_version }}</span></header>
            <div class="profile-form">
              <label>企业简称<input v-model="profileForm.short_name" class="input" /></label><label>法定代表人<input v-model="profileForm.legal_representative" class="input" /></label>
              <label>成立日期<input v-model="profileForm.established_on" class="input" type="date" /></label><label>注册资本<input v-model="profileForm.registered_capital" class="input" type="number" min="0" step="0.01" /></label>
              <label>币种<input v-model="profileForm.capital_currency" class="input" maxlength="3" /></label><label>登记状态<select v-model="profileForm.registration_status" class="input"><option value="ACTIVE">存续</option><option value="SUSPENDED">停业</option><option value="REVOKED">吊销</option><option value="CANCELLED">注销</option><option value="UNKNOWN">未知</option></select></label>
              <label>登记机关<input v-model="profileForm.registration_authority" class="input" /></label><label>行业编码<input v-model="profileForm.industry_code" class="input" /></label>
              <label>行业名称<input v-model="profileForm.industry_name" class="input" /></label><label>企业规模<select v-model="profileForm.employee_size_band" class="input"><option value="MICRO">微型</option><option value="SMALL">小型</option><option value="MEDIUM">中型</option><option value="LARGE">大型</option><option value="UNKNOWN">未知</option></select></label>
              <label class="wide">网站<input v-model="profileForm.website" class="input" type="url" placeholder="https://" /></label><label class="wide">经营范围<textarea v-model="profileForm.business_scope" class="input" rows="3"></textarea></label>
            </div>
            <div class="missing-list"><span v-for="dimension in profile.missing_dimensions" :key="dimension">待补：{{ dimension }}</span><span v-if="!profile.missing_dimensions.length" class="complete">全部必需维度已具备</span></div>
            <button v-if="canWrite" class="btn" type="button" data-testid="enterprise-profile-save" :disabled="saving" @click="saveProfile">保存画像</button>
          </section>

          <section class="detail-section"><header><h3>联系人、地址与园区关系</h3><span>实时主档</span></header><div class="three-columns"><article><b>联系人</b><p v-for="row in contacts" :key="String(row.id)">{{ row.name || "未命名" }} · {{ row.phone || row.email || "未留联系方式" }}</p><p v-if="!contacts.length" class="muted">暂无联系人</p></article><article><b>注册地址</b><p v-for="row in addresses" :key="String(row.id)">{{ row.province }}{{ row.city }}{{ row.district }}{{ row.detail }}</p><p v-if="!addresses.length" class="muted">暂无地址</p></article><article><b>园区角色</b><p v-for="row in (party?.park_relations as Subresource[] || [])" :key="String(row.id)">园区 #{{ row.park_id }} · {{ row.role_code || row.party_role_id }}</p><p v-if="!(party?.park_relations as Subresource[] || []).length" class="muted">租户级未关联企业</p></article></div></section>

          <section class="detail-section" data-testid="enterprise-relationship-section"><header><h3>关联企业</h3><span>{{ relationships.length }} 条有效关系</span></header><div class="record-list"><article v-for="row in relationships" :key="String(row.id)"><b>{{ row.source_party_name }} → {{ row.target_party_name }}</b><span>{{ row.relationship_type }}<template v-if="row.ownership_percent"> · {{ row.ownership_percent }}%</template></span></article><p v-if="!relationships.length" class="muted">暂无关联企业</p></div><form v-if="canWrite" class="inline-form" @submit.prevent="createRelationship"><input v-model="relationshipForm.target_party_id" class="input" type="number" min="1" placeholder="目标企业 ID" required /><select v-model="relationshipForm.relationship_type" class="input"><option value="PARENT_OF">母子关系</option><option value="INVESTED_IN">投资关系</option><option value="COMMON_CONTROL">共同控制</option><option value="BUSINESS_PARTNER">业务伙伴</option></select><input v-model="relationshipForm.ownership_percent" class="input" type="number" min="0" max="100" step="0.01" placeholder="持股比例" /><button class="btn btn-ghost" type="submit">新增关系</button></form></section>

          <section class="detail-section" data-testid="enterprise-tag-section"><header><h3>企业标签</h3><span>来源与置信度可追溯</span></header><div class="tag-cloud"><span v-for="row in tags" :key="String(row.id)">{{ row.name }} · {{ row.source_type }}</span><p v-if="!tags.length" class="muted">暂无标签</p></div><form v-if="canWrite" class="inline-form" @submit.prevent="createTag"><input v-model="tagForm.name" class="input" placeholder="标签名称" required /><select v-model="tagForm.tag_type" class="input"><option value="INDUSTRY">行业</option><option value="CAPABILITY">能力</option><option value="QUALIFICATION">资质</option><option value="INTENT">意向</option><option value="CUSTOM">自定义</option></select><button class="btn btn-ghost" type="submit">新增标签</button></form></section>

          <section class="detail-section" data-testid="enterprise-credential-section"><header><h3>证照证据</h3><span>{{ canReadCredentials ? `${credentials.length} 份` : "权限受限" }}</span></header><div v-if="!canReadCredentials" class="permission-state">你没有企业证照读取权限，系统未发起证照请求。</div><template v-else><div class="record-list"><article v-for="row in credentials" :key="String(row.id)"><b>{{ row.credential_type }} · {{ row.identifier_masked || "无标识" }}</b><span>{{ row.status }} / {{ row.verification_status }} · 附件 #{{ row.attachment_id }}</span></article><p v-if="!credentials.length" class="muted">暂无证照</p></div><form v-if="canManageCredentials" class="credential-form" @submit.prevent="createCredential"><select v-model="credentialForm.credential_type" class="input"><option value="BUSINESS_LICENSE">营业执照</option><option value="TAX_REGISTRATION">税务登记</option><option value="ORGANIZATION_CODE">组织机构代码</option><option value="INDUSTRY_LICENSE">行业许可</option><option value="OTHER">其他</option></select><input v-model="credentialForm.identifier" class="input" placeholder="组织证照标识（仅保存指纹和掩码）" /><input v-model="credentialForm.issuer" class="input" placeholder="签发机构" /><input v-model="credentialForm.issued_on" class="input" type="date" /><input v-model="credentialForm.expires_on" class="input" type="date" /><input type="file" required @change="pickCredentialFile" /><button class="btn btn-ghost" type="submit">上传证照证据</button></form></template></section>

          <section class="detail-section" data-testid="enterprise-risk-section"><header><h3>本地风险历史</h3><span>{{ canReadRisk ? `${risks?.summary.unresolved_count || 0} 条未解决` : "权限受限" }}</span></header><div v-if="!canReadRisk" class="permission-state">你没有企业风险读取权限，风险筛选和明细均已隐藏。</div><template v-else><div class="record-list"><article v-for="row in risks?.items || []" :key="String(row.id)"><b>{{ row.severity }} · {{ row.category }}</b><span>{{ row.summary }}</span><small>{{ row.resolution ? "已处置" : "待处置" }}</small><button v-if="canManageRisk && !row.resolution" type="button" class="text-button" @click="resolveRisk(row)">标记已缓释</button></article><p v-if="!risks?.items.length" class="muted">暂无本地风险信号</p></div><form v-if="canManageRisk" class="inline-form" @submit.prevent="createRisk"><select v-model="riskForm.category" class="input"><option value="LEGAL">法律</option><option value="FINANCIAL">财务</option><option value="COMPLIANCE">合规</option><option value="OPERATIONAL">经营</option><option value="REPUTATION">声誉</option><option value="OTHER">其他</option></select><select v-model="riskForm.severity" class="input"><option value="LOW">低</option><option value="MEDIUM">中</option><option value="HIGH">高</option><option value="CRITICAL">重大</option></select><input v-model="riskForm.summary" class="input" placeholder="风险摘要" required /><button class="btn btn-ghost" type="submit">记录风险</button></form></template></section>
        </div>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.enterprise-page { display: grid; min-width: 0; gap: 1rem; overflow-x: hidden; color: #17243a; }
.card { border: 1px solid #dbe4ef; border-radius: 18px; background: #fff; box-shadow: 0 12px 30px rgb(30 64 96 / 7%); }
.hero, .filters, .directory, .entry-grid { min-width: 0; }
.hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 2rem; padding: 1.5rem; background: linear-gradient(135deg, #fff 20%, #eef8fb); }
.hero h1 { margin: .25rem 0; font-size: clamp(1.55rem, 3vw, 2.25rem); }
.hero p, .section-head p, .entry-card header span { margin: 0; color: #64748b; }
.eyebrow { color: #0891b2; font-size: .72rem; font-weight: 800; letter-spacing: .12em; }
.hero-metrics { display: flex; gap: .6rem; }
.hero-metrics article { min-width: 108px; padding: .8rem; border: 1px solid #d8e7ed; border-radius: 14px; background: rgb(255 255 255 / 80%); }
.hero-metrics strong, .hero-metrics span { display: block; }.hero-metrics strong { font-size: 1.45rem; color: #0f5471; }.hero-metrics span { color: #64748b; font-size: .75rem; }
.filters, .directory { padding: 1rem; }.filter-grid { display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: .7rem; align-items: end; }
label { display: grid; gap: .35rem; color: #526177; font-size: .78rem; font-weight: 700; }.input { min-width: 0; width: 100%; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: .8rem; }.section-head h2 { margin: 0; }.live-badge { padding: .3rem .55rem; border-radius: 999px; background: #e6f8fb; color: #087f9b; font-size: .68rem; font-weight: 900; letter-spacing: .08em; }
.table-wrap { overflow-x: auto; }.enterprise-table { min-width: 850px; width: 100%; }.enterprise-table td { vertical-align: middle; }.enterprise-table strong, .enterprise-table small { display: block; }.enterprise-table small { margin-top: .25rem; color: #64748b; }
.status-pill, .risk-pill { display: inline-flex; width: fit-content; padding: .25rem .5rem; border-radius: 999px; background: #edf4f7; color: #31556a; font-size: .7rem; font-weight: 800; }.risk-CRITICAL { background: #fff0ed; color: #c2412d; }.risk-HIGH { background: #fff6df; color: #b45309; }.risk-MEDIUM { background: #fff8e8; color: #a16207; }.risk-LOW, .risk-NONE { background: #e9f9f4; color: #047857; }.risk-HIDDEN { background: #eef2f7; color: #64748b; }
.progress { width: 110px; height: 7px; overflow: hidden; border-radius: 999px; background: #e8eef3; }.progress i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #0e7490, #22c1c3); }
.text-button, .pager button { border: 0; background: transparent; color: #087f9b; cursor: pointer; font-weight: 750; }.pager { display: flex; justify-content: flex-end; align-items: center; gap: 1rem; margin-top: .75rem; }.pager button:disabled { color: #a8b3c1; cursor: not-allowed; }
.state-card, .empty { display: grid; place-items: center; gap: .4rem; min-height: 140px; padding: 1rem; border: 1px dashed #cbd9e5; border-radius: 16px; background: #f8fbfd; color: #64748b; text-align: center; }.error-state { border-color: #fecaca; background: #fff8f7; color: #9f3125; }.spinner { width: 24px; height: 24px; border: 3px solid #d9e8ee; border-top-color: #0891b2; border-radius: 50%; animation: spin .8s linear infinite; }
.entry-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }.entry-card { display: grid; grid-template-columns: repeat(2, 1fr); gap: .65rem; padding: 1rem; }.entry-card header { grid-column: 1 / -1; }.entry-card h2 { margin: 0; font-size: 1rem; }.toast { position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 50; padding: .8rem 1rem; border-radius: 12px; background: #064e5c; color: white; box-shadow: 0 12px 30px rgb(0 0 0 / 22%); }
.drawer-mask { position: fixed; inset: 0; z-index: 60; display: flex; max-width: 100vw; overflow-x: hidden; justify-content: flex-end; background: rgb(6 24 40 / 46%); backdrop-filter: blur(2px); }.drawer { width: min(820px, 92vw); max-width: 100vw; height: 100%; overflow-x: hidden; overflow-y: auto; background: #f4f8fb; box-shadow: -20px 0 48px rgb(4 24 41 / 20%); }.drawer-head { position: sticky; top: 0; z-index: 2; display: flex; min-width: 0; justify-content: space-between; padding: 1.15rem 1.25rem; border-bottom: 1px solid #d9e4ed; background: rgb(255 255 255 / 96%); }.drawer-head h2, .drawer-head p { margin: .15rem 0; overflow-wrap: anywhere; }.drawer-head p { color: #64748b; }.close-button { width: 38px; height: 38px; border: 1px solid #d8e2ea; border-radius: 12px; background: white; color: #536477; font-size: 1.5rem; cursor: pointer; }.drawer-body { display: grid; min-width: 0; gap: .8rem; padding: 1rem; }.profile-summary { display: flex; min-width: 0; gap: 1rem; align-items: center; padding: 1rem; border-radius: 16px; background: #092d43; color: #dceef5; }.profile-summary p { margin: .35rem 0; color: #aac4d2; }.score-ring { display: grid; place-items: center; flex: 0 0 110px; height: 110px; border: 8px solid #22c1c3; border-radius: 50%; }.score-ring strong { font-size: 1.8rem; }.score-ring span { font-size: .7rem; }
.detail-section { min-width: 0; padding: 1rem; overflow: hidden; border: 1px solid #dbe5ed; border-radius: 16px; background: white; }.detail-section > header { display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin-bottom: .8rem; }.detail-section h3 { margin: 0; font-size: 1rem; }.detail-section header span { color: #64748b; font-size: .75rem; }.profile-form { display: grid; min-width: 0; grid-template-columns: 1fr 1fr; gap: .65rem; }.profile-form .wide { grid-column: 1 / -1; }.missing-list, .tag-cloud { display: flex; flex-wrap: wrap; gap: .35rem; margin: .75rem 0; }.missing-list span, .tag-cloud span { padding: .25rem .5rem; border-radius: 8px; background: #fff5e8; color: #9a5b08; font-size: .72rem; }.missing-list .complete { background: #e7f8f1; color: #047857; }.three-columns { display: grid; min-width: 0; grid-template-columns: repeat(3, 1fr); gap: .65rem; }.three-columns article { min-width: 0; padding: .7rem; border-radius: 12px; background: #f6f9fb; }.three-columns p { overflow-wrap: anywhere; color: #536477; font-size: .78rem; }.record-list { display: grid; min-width: 0; gap: .45rem; }.record-list article { display: grid; min-width: 0; gap: .2rem; overflow-wrap: anywhere; padding: .65rem; border-left: 3px solid #22a6bd; border-radius: 8px; background: #f7fafc; }.record-list span, .record-list small { color: #64748b; font-size: .78rem; }.inline-form { display: grid; min-width: 0; grid-template-columns: repeat(4, minmax(100px, 1fr)); gap: .5rem; margin-top: .75rem; }.credential-form { display: grid; min-width: 0; grid-template-columns: 1fr 1fr; gap: .5rem; margin-top: .75rem; }.permission-state { padding: .8rem; border-radius: 10px; background: #f1f4f7; color: #64748b; }.detail-error { position: sticky; top: 94px; z-index: 2; display: grid; gap: .25rem; margin: .8rem; padding: .75rem; border: 1px solid #f8b4aa; border-radius: 12px; background: #fff4f2; color: #a63c2d; }.muted { color: #7a899a; }
button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 3px solid rgb(34 193 195 / 35%); outline-offset: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 900px) { .hero { align-items: stretch; flex-direction: column; }.hero-metrics { overflow-x: auto; }.filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.entry-grid { grid-template-columns: 1fr; }.drawer { width: 100%; }.three-columns { grid-template-columns: 1fr; }.inline-form { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .enterprise-page { gap: .75rem; }.hero, .filters, .directory { padding: .8rem; }.hero-metrics article { min-width: 92px; }.filter-grid, .profile-form, .entry-card, .credential-form, .inline-form { grid-template-columns: 1fr; }.profile-form .wide { grid-column: auto; }.profile-summary { align-items: flex-start; flex-direction: column; }.score-ring { flex-basis: 92px; width: 92px; height: 92px; }.drawer-body { padding: .65rem; }.drawer-head { padding: .8rem; }.enterprise-table { display: block; min-width: 0; }.enterprise-table thead { display: none; }.enterprise-table tbody, .enterprise-table tr, .enterprise-table td { display: block; width: 100%; }.enterprise-table tr { margin-bottom: .65rem; padding: .8rem; border: 1px solid #dbe5ed; border-radius: 14px; background: #fff; }.enterprise-table td { padding: .3rem 0; border: 0; }.table-wrap { overflow: visible; }.progress { width: 100%; }.toast { right: .75rem; bottom: .75rem; left: .75rem; }.drawer-mask { overflow-x: hidden; } }
</style>
