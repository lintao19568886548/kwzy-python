<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type Category = {
  id: number;
  code: string;
  name: string;
  retention_mode: "YEARS" | "PERMANENT";
  retention_years: number | null;
  confidentiality_max: string;
  status: string;
  lock_version: number;
};
type Revision = {
  id: number;
  version_no: number;
  attachment_id: number;
  checksum_sha256: string;
  size_bytes: number;
  status: string;
  created_at: string;
};
type RecordFile = {
  id: number;
  park_id: number | null;
  category_id: number;
  record_no: string;
  title: string;
  description: string | null;
  confidentiality: string;
  source_type: string;
  source_id: string;
  status: string;
  retention_mode: string;
  retention_years: number | null;
  retention_until: string | null;
  lock_version: number;
  revisions?: Revision[];
  holds?: Array<{ id: number; status: string; reason: string; placed_at: string }>;
  integrity_events?: Array<{ id: number; result: string; verified_at: string }>;
};
type Seal = {
  id: number;
  park_id: number | null;
  seal_code: string;
  name: string;
  kind: string;
  status: string;
  custodian_user_id: number;
  lock_version: number;
  custody_events?: Array<{
    id: number;
    event_type: string;
    status: string;
    reason: string;
    occurred_at: string;
  }>;
};
type Provider = {
  id: number;
  code: string;
  name: string;
  adapter_kind: string;
  status: string;
  credential_ref_configured: boolean;
  live_verified: boolean;
};
type SignatureEnvelope = {
  id: number;
  envelope_no: string;
  provider_id: number;
  record_id: number;
  revision_id: number;
  revision_checksum: string;
  purpose: string;
  status: string;
  provider_ref: string | null;
  live_verified: boolean;
  lock_version: number;
};
type AccessRequest = { id: number; status: string; mode: string };
type Disposition = { id: number; status: string; storage_deletion_status: string | null };
type SealUse = { id: number; status: string; approval_status: string | null };

const auth = useAuthStore();
const activeTab = ref<"records" | "seals" | "signatures">("records");
const categories = ref<Category[]>([]);
const records = ref<RecordFile[]>([]);
const seals = ref<Seal[]>([]);
const providers = ref<Provider[]>([]);
const envelopes = ref<SignatureEnvelope[]>([]);
const accessRequests = ref<AccessRequest[]>([]);
const dispositions = ref<Disposition[]>([]);
const sealUses = ref<SealUse[]>([]);
const detailRecord = ref<RecordFile | null>(null);
const detailSeal = ref<Seal | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const online = ref(navigator.onLine);
const showCategoryForm = ref(false);
const showRecordForm = ref(false);
const showSealForm = ref(false);
const showProviderForm = ref(false);
const showEnvelopeForm = ref(false);
const revisionAttachmentId = ref("");

const categoryDraft = ref({
  code: "",
  name: "",
  retention_mode: "YEARS" as "YEARS" | "PERMANENT",
  retention_years: "10",
  confidentiality_max: "CONFIDENTIAL",
});
const recordDraft = ref({
  park_id: "",
  category_id: "",
  title: "",
  description: "",
  confidentiality: "INTERNAL",
  source_type: "LEASE_CONTRACT",
  source_id: "",
});
const sealDraft = ref({
  park_id: "",
  seal_code: "",
  name: "",
  kind: "OFFICIAL",
  custodian_user_id: "",
  description: "",
});
const providerDraft = ref({ code: "", name: "", adapter_kind: "LOCAL_SANDBOX" });
const envelopeDraft = ref({
  provider_id: "",
  record_id: "",
  revision_id: "",
  source_type: "LEASE_CONTRACT",
  source_id: "",
  purpose: "",
  display_name: "",
  contact_masked: "",
});

const canRecordRead = computed(() => auth.can("*") || auth.can("record:read"));
const canRecordWrite = computed(() => auth.can("*") || auth.can("record:write"));
const canRecordManage = computed(() => auth.can("*") || auth.can("record:manage"));
const canVerify = computed(() => auth.can("*") || auth.can("record:verify"));
const canHold = computed(() => auth.can("*") || auth.can("record:hold"));
const canSealRead = computed(() => auth.can("*") || auth.can("seal:read"));
const canSealManage = computed(() => auth.can("*") || auth.can("seal:manage"));
const canSignatureRead = computed(() => auth.can("*") || auth.can("signature:read"));
const canSignatureManage = computed(() => auth.can("*") || auth.can("signature:manage"));
const canSignatureWrite = computed(() => auth.can("*") || auth.can("signature:write"));
const canSignatureDispatch = computed(() => auth.can("*") || auth.can("signature:dispatch"));

const metrics = computed(() => ({
  filed: records.value.filter((row) => row.status === "FILED").length,
  held: records.value.filter((row) => row.status === "ON_HOLD").length,
  activeSeals: seals.value.filter((row) => row.status === "ACTIVE").length,
  pendingGovernance:
    accessRequests.value.filter((row) => row.status.includes("PENDING")).length +
    dispositions.value.filter((row) => !["DISPOSED", "REJECTED", "CANCELLED"].includes(row.status)).length +
    sealUses.value.filter((row) => !["EXECUTED", "REJECTED", "CANCELLED"].includes(row.status)).length,
}));

function clearMessages() {
  error.value = "";
  errorStatus.value = 0;
  success.value = "";
}

function requestError(value: unknown, fallback: string) {
  error.value = value instanceof Error ? value.message : fallback;
  errorStatus.value = value instanceof ApiRequestError ? value.status : 0;
}

function commandKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function statusClass(status: string) {
  return ["LOST", "REJECTED", "FAILED"].includes(status)
    ? "risk"
    : ["PENDING_APPROVAL", "CONFIRMING", "TRANSFER_PENDING", "DRAFT"].includes(status)
      ? "pending"
      : "ok";
}

function shortHash(value?: string | null) {
  return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : "—";
}

async function loadAll() {
  clearMessages();
  loading.value = true;
  try {
    const calls: Promise<void>[] = [];
    if (canRecordRead.value) {
      calls.push(
        http
          .get<Envelope<Category[]>>("/record-categories", { params: { include_retired: true } })
          .then((response) => {
            categories.value = response.data.data;
          }),
        http
          .get<Envelope<PageResult<RecordFile>>>("/records", { params: { page: 1, page_size: 200 } })
          .then((response) => {
            records.value = response.data.data.items;
          })
      );
      if (auth.can("*") || auth.can("record:access_request") || auth.can("record:access_review")) {
        calls.push(
          http.get<Envelope<AccessRequest[]>>("/record-access-requests").then((response) => {
            accessRequests.value = response.data.data;
          })
        );
      }
      if (auth.can("*") || auth.can("record:dispose_request") || auth.can("record:dispose_review")) {
        calls.push(
          http.get<Envelope<Disposition[]>>("/record-dispositions").then((response) => {
            dispositions.value = response.data.data;
          })
        );
      }
    }
    if (canSealRead.value) {
      calls.push(
        http.get<Envelope<Seal[]>>("/seals").then((response) => {
          seals.value = response.data.data;
        }),
        http.get<Envelope<SealUse[]>>("/seal-use-applications").then((response) => {
          sealUses.value = response.data.data;
        })
      );
    }
    if (canSignatureRead.value) {
      calls.push(
        http.get<Envelope<Provider[]>>("/signature-providers").then((response) => {
          providers.value = response.data.data;
        }),
        http.get<Envelope<SignatureEnvelope[]>>("/signature-envelopes").then((response) => {
          envelopes.value = response.data.data;
        })
      );
    }
    await Promise.all(calls);
  } catch (value) {
    requestError(value, "档案治理数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function createCategory() {
  clearMessages();
  saving.value = true;
  try {
    await http.post("/record-categories", {
      ...categoryDraft.value,
      retention_years:
        categoryDraft.value.retention_mode === "PERMANENT"
          ? null
          : Number(categoryDraft.value.retention_years),
    });
    showCategoryForm.value = false;
    categoryDraft.value = {
      code: "",
      name: "",
      retention_mode: "YEARS",
      retention_years: "10",
      confidentiality_max: "CONFIDENTIAL",
    };
    await loadAll();
    success.value = "档案分类已保存";
  } catch (value) {
    requestError(value, "档案分类保存失败");
  } finally {
    saving.value = false;
  }
}

async function createRecord() {
  clearMessages();
  saving.value = true;
  try {
    const response = await http.post<Envelope<RecordFile>>("/records", {
      park_id: recordDraft.value.park_id ? Number(recordDraft.value.park_id) : null,
      category_id: Number(recordDraft.value.category_id),
      title: recordDraft.value.title,
      description: recordDraft.value.description || null,
      confidentiality: recordDraft.value.confidentiality,
      source_type: recordDraft.value.source_type,
      source_id: recordDraft.value.source_id,
    });
    showRecordForm.value = false;
    recordDraft.value.title = "";
    recordDraft.value.description = "";
    recordDraft.value.source_id = "";
    await loadAll();
    await openRecord(response.data.data.id);
    success.value = "档案已创建，可绑定真实附件版本";
  } catch (value) {
    requestError(value, "档案创建失败");
  } finally {
    saving.value = false;
  }
}

async function openRecord(recordId: number) {
  clearMessages();
  try {
    const response = await http.get<Envelope<RecordFile>>(`/records/${recordId}`);
    detailRecord.value = response.data.data;
    revisionAttachmentId.value = "";
  } catch (value) {
    requestError(value, "档案详情加载失败");
  }
}

async function addRevision() {
  if (!detailRecord.value) return;
  clearMessages();
  saving.value = true;
  try {
    const response = await http.post<Envelope<RecordFile>>(
      `/records/${detailRecord.value.id}/revisions`,
      {
        expected_version: detailRecord.value.lock_version,
        attachment_id: Number(revisionAttachmentId.value),
      }
    );
    detailRecord.value = response.data.data;
    revisionAttachmentId.value = "";
    await loadAll();
    success.value = "真实附件已哈希并生成不可变档案版本";
  } catch (value) {
    requestError(value, "新增档案版本失败");
  } finally {
    saving.value = false;
  }
}

async function fileRecord() {
  if (!detailRecord.value) return;
  clearMessages();
  saving.value = true;
  try {
    const response = await http.post<Envelope<RecordFile>>(`/records/${detailRecord.value.id}/file`, {
      expected_version: detailRecord.value.lock_version,
      reason: "档案管理员核对后正式归档",
    });
    detailRecord.value = response.data.data;
    await loadAll();
    success.value = "档案已正式归档";
  } catch (value) {
    requestError(value, "档案归档失败");
  } finally {
    saving.value = false;
  }
}

async function verifyRecord() {
  if (!detailRecord.value) return;
  clearMessages();
  saving.value = true;
  try {
    await http.post(
      `/records/${detailRecord.value.id}/verify`,
      { revision_id: null },
      { headers: { "Idempotency-Key": commandKey("record-verify") } }
    );
    await openRecord(detailRecord.value.id);
    success.value = "档案对象与 SHA-256 校验值一致";
  } catch (value) {
    requestError(value, "档案完整性校验失败");
  } finally {
    saving.value = false;
  }
}

async function placeHold() {
  if (!detailRecord.value) return;
  clearMessages();
  saving.value = true;
  try {
    const response = await http.post<Envelope<RecordFile>>(
      `/records/${detailRecord.value.id}/holds`,
      { expected_version: detailRecord.value.lock_version, reason: "合规调查证据保全" }
    );
    detailRecord.value = response.data.data;
    await loadAll();
    success.value = "档案已进入保全状态，处置被阻断";
  } catch (value) {
    requestError(value, "档案保全失败");
  } finally {
    saving.value = false;
  }
}

async function createSeal() {
  clearMessages();
  saving.value = true;
  try {
    await http.post("/seals", {
      park_id: sealDraft.value.park_id ? Number(sealDraft.value.park_id) : null,
      seal_code: sealDraft.value.seal_code,
      name: sealDraft.value.name,
      kind: sealDraft.value.kind,
      custodian_user_id: Number(sealDraft.value.custodian_user_id),
      description: sealDraft.value.description || null,
    });
    showSealForm.value = false;
    sealDraft.value.seal_code = "";
    sealDraft.value.name = "";
    sealDraft.value.description = "";
    await loadAll();
    success.value = "印章已登记并生成首条保管事件";
  } catch (value) {
    requestError(value, "印章登记失败");
  } finally {
    saving.value = false;
  }
}

async function openSeal(sealId: number) {
  clearMessages();
  try {
    const response = await http.get<Envelope<Seal>>(`/seals/${sealId}`);
    detailSeal.value = response.data.data;
  } catch (value) {
    requestError(value, "印章详情加载失败");
  }
}

async function markSealLost() {
  if (!detailSeal.value || !window.confirm(`确认将 ${detailSeal.value.name} 标记为遗失？`)) return;
  clearMessages();
  saving.value = true;
  try {
    const response = await http.post<Envelope<Seal>>(`/seals/${detailSeal.value.id}/mark-lost`, {
      expected_version: detailSeal.value.lock_version,
      reason: "保管人报告遗失，立即冻结",
    });
    detailSeal.value = response.data.data;
    await loadAll();
    success.value = "印章已冻结并记录遗失事件";
  } catch (value) {
    requestError(value, "印章状态更新失败");
  } finally {
    saving.value = false;
  }
}

async function createProvider() {
  clearMessages();
  saving.value = true;
  try {
    await http.post("/signature-providers", { ...providerDraft.value, credential_ref: null });
    showProviderForm.value = false;
    providerDraft.value.code = "";
    providerDraft.value.name = "";
    await loadAll();
    success.value =
      providerDraft.value.adapter_kind === "LOCAL_SANDBOX"
        ? "本地签章沙箱已登记：无法律效力"
        : "外部签章已登记为未连接，等待真实凭据与联调";
  } catch (value) {
    requestError(value, "签章服务登记失败");
  } finally {
    saving.value = false;
  }
}

async function createEnvelope() {
  clearMessages();
  saving.value = true;
  try {
    await http.post("/signature-envelopes", {
      provider_id: Number(envelopeDraft.value.provider_id),
      record_id: Number(envelopeDraft.value.record_id),
      revision_id: Number(envelopeDraft.value.revision_id),
      source_type: envelopeDraft.value.source_type,
      source_id: envelopeDraft.value.source_id,
      purpose: envelopeDraft.value.purpose,
      participants: [
        {
          role: "SIGNER",
          display_name: envelopeDraft.value.display_name,
          contact_masked: envelopeDraft.value.contact_masked || null,
        },
      ],
    });
    showEnvelopeForm.value = false;
    await loadAll();
    success.value = "签署信封已绑定档案最新版本";
  } catch (value) {
    requestError(value, "签署信封创建失败");
  } finally {
    saving.value = false;
  }
}

async function dispatchEnvelope(envelope: SignatureEnvelope) {
  clearMessages();
  saving.value = true;
  try {
    await http.post(`/signature-envelopes/${envelope.id}/dispatch`, {
      expected_version: envelope.lock_version,
      reason: "发送签署流程",
    });
    await loadAll();
    success.value = "签署流程已处理；沙箱结果不具法律效力";
  } catch (value) {
    requestError(value, "签署发送失败");
  } finally {
    saving.value = false;
  }
}

function updateConnectivity() {
  online.value = navigator.onLine;
}

onMounted(() => {
  window.addEventListener("online", updateConnectivity);
  window.addEventListener("offline", updateConnectivity);
  void loadAll();
});
onBeforeUnmount(() => {
  window.removeEventListener("online", updateConnectivity);
  window.removeEventListener("offline", updateConnectivity);
});
</script>

<template>
  <section class="governance-page" data-testid="records-seal-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">RECORDS · SEALS · SIGNATURE</p>
        <h1 data-testid="records-seal-title">档案、签章与印章治理</h1>
        <p>以真实附件版本、原生审批和职责分离贯通归档、用印与签署。</p>
      </div>
      <button class="btn btn-quiet" type="button" :disabled="loading" @click="loadAll">
        刷新真实数据
      </button>
    </header>

    <div v-if="!online" class="notice warning" data-testid="records-offline">
      当前离线。页面不会展示缓存为最新数据，请恢复网络后重试。
    </div>
    <div v-if="error" class="notice danger" data-testid="records-error">
      <strong>{{ errorStatus === 409 ? "并发或业务冲突" : errorStatus === 403 ? "权限不足" : "网络或服务异常" }}</strong>
      <span>{{ error }}</span>
      <button type="button" @click="loadAll">重试</button>
    </div>
    <p v-if="success" class="notice success" role="status">{{ success }}</p>

    <div class="metric-grid">
      <article class="card metric"><span>正式归档</span><strong>{{ metrics.filed }}</strong><small>已冻结版本基线</small></article>
      <article class="card metric"><span>证据保全</span><strong>{{ metrics.held }}</strong><small>禁止处置</small></article>
      <article class="card metric"><span>可用印章</span><strong>{{ metrics.activeSeals }}</strong><small>保管责任明确</small></article>
      <article class="card metric risk-metric"><span>待治理</span><strong>{{ metrics.pendingGovernance }}</strong><small>审批 / 确认 / 执行</small></article>
    </div>

    <nav class="tabs card" aria-label="档案治理视图">
      <button type="button" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">档案库</button>
      <button type="button" :class="{ active: activeTab === 'seals' }" @click="activeTab = 'seals'">印章与用印</button>
      <button type="button" :class="{ active: activeTab === 'signatures' }" @click="activeTab = 'signatures'">电子签章</button>
    </nav>

    <div v-if="loading" class="card state"><span class="spinner" aria-hidden="true"></span><p>正在加载真实数据…</p></div>

    <template v-else-if="activeTab === 'records'">
      <section class="card panel">
        <div class="section-head">
          <div><p class="eyebrow">CLASSIFICATION</p><h2>分类与保管规则</h2></div>
          <button v-if="canRecordManage" class="btn" type="button" data-testid="add-record-category" @click="showCategoryForm = !showCategoryForm">新建分类</button>
        </div>
        <form v-if="showCategoryForm" class="form-grid" @submit.prevent="createCategory">
          <label>分类编码<input v-model="categoryDraft.code" class="input" required pattern="[A-Za-z][A-Za-z0-9_-]*" /></label>
          <label>分类名称<input v-model="categoryDraft.name" class="input" required /></label>
          <label>保管方式<select v-model="categoryDraft.retention_mode" class="input"><option value="YEARS">按年</option><option value="PERMANENT">永久</option></select></label>
          <label v-if="categoryDraft.retention_mode === 'YEARS'">保管年限<input v-model="categoryDraft.retention_years" class="input" type="number" min="1" max="100" required /></label>
          <label>最高密级<select v-model="categoryDraft.confidentiality_max" class="input"><option value="PUBLIC">公开</option><option value="INTERNAL">内部</option><option value="CONFIDENTIAL">机密</option><option value="RESTRICTED">严格限制</option></select></label>
          <button class="btn align-end" type="submit" :disabled="saving">保存分类</button>
        </form>
        <div class="chip-list" data-testid="record-categories">
          <span v-for="category in categories" :key="category.id" class="chip"><b>{{ category.code }}</b>{{ category.name }} · {{ category.retention_mode === 'PERMANENT' ? '永久' : `${category.retention_years} 年` }}</span>
          <span v-if="categories.length === 0" class="muted">尚无档案分类</span>
        </div>
      </section>

      <section class="card panel">
        <div class="section-head">
          <div><p class="eyebrow">CONTROLLED RECORDS</p><h2>受控档案</h2></div>
          <button v-if="canRecordWrite" class="btn" type="button" data-testid="add-record" @click="showRecordForm = !showRecordForm">新建档案</button>
        </div>
        <form v-if="showRecordForm" class="form-grid wide" @submit.prevent="createRecord">
          <label>园区 ID（集团档案可留空）<input v-model="recordDraft.park_id" class="input" type="number" min="1" /></label>
          <label>档案分类<select v-model="recordDraft.category_id" class="input" required><option disabled value="">请选择</option><option v-for="category in categories.filter((item) => item.status === 'ACTIVE')" :key="category.id" :value="String(category.id)">{{ category.code }} · {{ category.name }}</option></select></label>
          <label>标题<input v-model="recordDraft.title" class="input" required /></label>
          <label>密级<select v-model="recordDraft.confidentiality" class="input"><option value="PUBLIC">公开</option><option value="INTERNAL">内部</option><option value="CONFIDENTIAL">机密</option><option value="RESTRICTED">严格限制</option></select></label>
          <label>来源类型<input v-model="recordDraft.source_type" class="input" required pattern="[A-Za-z][A-Za-z0-9_]*" /></label>
          <label>来源业务 ID<input v-model="recordDraft.source_id" class="input" required pattern="[A-Za-z0-9._:-]+" /></label>
          <label class="span-2">说明<textarea v-model="recordDraft.description" class="input" rows="2"></textarea></label>
          <button class="btn align-end" type="submit" :disabled="saving">创建受控档案</button>
        </form>
        <div class="table-wrap">
          <table class="table" data-testid="record-table">
            <thead><tr><th>档案号 / 标题</th><th>来源</th><th>密级</th><th>保管</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="record in records" :key="record.id">
                <td data-label="档案号 / 标题"><b>{{ record.record_no }}</b><small>{{ record.title }}</small></td>
                <td data-label="来源">{{ record.source_type }}<small>{{ record.source_id }}</small></td>
                <td data-label="密级">{{ record.confidentiality }}</td>
                <td data-label="保管">{{ record.retention_mode === 'PERMANENT' ? '永久' : record.retention_until }}</td>
                <td data-label="状态"><span class="status" :class="statusClass(record.status)">{{ record.status }}</span></td>
                <td data-label="操作"><button class="link-btn" type="button" :aria-label="`查看档案 ${record.record_no}`" @click="openRecord(record.id)">查看</button></td>
              </tr>
              <tr v-if="records.length === 0"><td colspan="6" class="empty">没有符合权限范围的档案</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <template v-else-if="activeTab === 'seals'">
      <section class="card panel">
        <div class="section-head">
          <div><p class="eyebrow">CUSTODY REGISTER</p><h2>印章台账与保管链</h2></div>
          <button v-if="canSealManage" class="btn" type="button" data-testid="add-seal" @click="showSealForm = !showSealForm">登记印章</button>
        </div>
        <form v-if="showSealForm" class="form-grid wide" @submit.prevent="createSeal">
          <label>园区 ID（集团章可留空）<input v-model="sealDraft.park_id" class="input" type="number" min="1" /></label>
          <label>印章编码<input v-model="sealDraft.seal_code" class="input" required pattern="[A-Za-z0-9_-]+" /></label>
          <label>印章名称<input v-model="sealDraft.name" class="input" required /></label>
          <label>类型<select v-model="sealDraft.kind" class="input"><option value="OFFICIAL">公章</option><option value="CONTRACT">合同章</option><option value="FINANCE">财务章</option><option value="LEGAL_REPRESENTATIVE">法人章</option><option value="ELECTRONIC">电子章</option><option value="OTHER">其他</option></select></label>
          <label>保管人用户 ID<input v-model="sealDraft.custodian_user_id" class="input" type="number" min="1" required /></label>
          <label>说明<input v-model="sealDraft.description" class="input" /></label>
          <button class="btn align-end" type="submit" :disabled="saving">登记并建立保管链</button>
        </form>
        <div class="card-grid" data-testid="seal-list">
          <article v-for="seal in seals" :key="seal.id" class="item-card">
            <header><span>{{ seal.kind }}</span><span class="status" :class="statusClass(seal.status)">{{ seal.status }}</span></header>
            <h3>{{ seal.name }}</h3><p>{{ seal.seal_code }}</p>
            <footer><span>保管人 #{{ seal.custodian_user_id }}</span><button class="link-btn" type="button" :aria-label="`查看印章 ${seal.seal_code}`" @click="openSeal(seal.id)">保管链</button></footer>
          </article>
          <p v-if="seals.length === 0" class="empty">没有符合权限范围的印章</p>
        </div>
      </section>
      <section class="card panel">
        <div class="section-head"><div><p class="eyebrow">NATIVE APPROVAL</p><h2>用印申请</h2></div></div>
        <div class="compact-list"><p v-for="item in sealUses" :key="item.id"><b>#{{ item.id }}</b><span>{{ item.approval_status || '未提交审批' }}</span><span class="status" :class="statusClass(item.status)">{{ item.status }}</span></p><p v-if="sealUses.length === 0" class="empty">暂无用印申请；所有执行都必须绑定审批与档案校验值。</p></div>
      </section>
    </template>

    <template v-else>
      <section class="truth-banner">
        <strong>签章能力真实性门禁</strong>
        <span>本地沙箱仅验证流程，不具法律效力；外部平台在凭据、回调验签和联调完成前始终为 NOT_CONNECTED。</span>
      </section>
      <section class="card panel">
        <div class="section-head">
          <div><p class="eyebrow">PROVIDER TRUTH</p><h2>签章服务</h2></div>
          <button v-if="canSignatureManage" class="btn" type="button" data-testid="add-signature-provider" @click="showProviderForm = !showProviderForm">登记服务</button>
        </div>
        <form v-if="showProviderForm" class="form-grid" @submit.prevent="createProvider">
          <label>服务编码<input v-model="providerDraft.code" class="input" required pattern="[A-Za-z][A-Za-z0-9_-]*" /></label>
          <label>服务名称<input v-model="providerDraft.name" class="input" required /></label>
          <label>适配器<select v-model="providerDraft.adapter_kind" class="input"><option value="LOCAL_SANDBOX">本地非法律效力沙箱</option><option value="EXTERNAL">外部服务（未连接）</option></select></label>
          <button class="btn align-end" type="submit" :disabled="saving">登记真实状态</button>
        </form>
        <div class="provider-grid">
          <article v-for="provider in providers" :key="provider.id" class="provider-card">
            <div><strong>{{ provider.name }}</strong><small>{{ provider.code }} · {{ provider.adapter_kind }}</small></div>
            <span class="status" :class="provider.live_verified ? 'ok' : provider.status === 'SANDBOX' ? 'pending' : 'risk'">{{ provider.status }}</span>
            <p>{{ provider.live_verified ? '已完成真实连接验证' : provider.status === 'SANDBOX' ? '仅本地流程模拟 · 无法律效力' : '未连接 · 禁止发送' }}</p>
          </article>
          <p v-if="providers.length === 0" class="empty">尚未登记签章服务</p>
        </div>
      </section>
      <section class="card panel">
        <div class="section-head">
          <div><p class="eyebrow">BOUND ENVELOPES</p><h2>签署信封</h2></div>
          <button v-if="canSignatureWrite" class="btn" type="button" data-testid="add-signature-envelope" @click="showEnvelopeForm = !showEnvelopeForm">新建信封</button>
        </div>
        <form v-if="showEnvelopeForm" class="form-grid wide" @submit.prevent="createEnvelope">
          <label>签章服务<select v-model="envelopeDraft.provider_id" class="input" required><option disabled value="">请选择</option><option v-for="provider in providers" :key="provider.id" :value="String(provider.id)">{{ provider.code }} · {{ provider.status }}</option></select></label>
          <label>档案 ID<input v-model="envelopeDraft.record_id" class="input" type="number" min="1" required /></label>
          <label>档案版本 ID<input v-model="envelopeDraft.revision_id" class="input" type="number" min="1" required /></label>
          <label>来源类型<input v-model="envelopeDraft.source_type" class="input" required /></label>
          <label>来源业务 ID<input v-model="envelopeDraft.source_id" class="input" required /></label>
          <label>用途<input v-model="envelopeDraft.purpose" class="input" required /></label>
          <label>签署人<input v-model="envelopeDraft.display_name" class="input" required /></label>
          <label>脱敏联系方式<input v-model="envelopeDraft.contact_masked" class="input" placeholder="138****8000" /></label>
          <button class="btn align-end" type="submit" :disabled="saving">绑定最新版本</button>
        </form>
        <div class="table-wrap">
          <table class="table" data-testid="signature-envelope-table"><thead><tr><th>信封号</th><th>档案 / 版本</th><th>校验值</th><th>真实性</th><th>状态</th><th>操作</th></tr></thead><tbody>
            <tr v-for="envelope in envelopes" :key="envelope.id"><td data-label="信封号"><b>{{ envelope.envelope_no }}</b><small>{{ envelope.purpose }}</small></td><td data-label="档案 / 版本">#{{ envelope.record_id }} / v{{ envelope.revision_id }}</td><td class="mono" data-label="校验值">{{ shortHash(envelope.revision_checksum) }}</td><td data-label="真实性">{{ envelope.live_verified ? '真实已验证' : '未验证 / 沙箱' }}</td><td data-label="状态"><span class="status" :class="statusClass(envelope.status)">{{ envelope.status }}</span></td><td data-label="操作"><button v-if="envelope.status === 'DRAFT' && canSignatureDispatch" class="link-btn" type="button" :disabled="saving" @click="dispatchEnvelope(envelope)">发送</button><span v-else>—</span></td></tr>
            <tr v-if="envelopes.length === 0"><td colspan="6" class="empty">暂无签署信封</td></tr>
          </tbody></table>
        </div>
      </section>
    </template>

    <aside v-if="detailRecord" class="drawer card" aria-label="档案详情">
      <div class="drawer-head"><div><p class="eyebrow">{{ detailRecord.record_no }}</p><h2>{{ detailRecord.title }}</h2></div><button type="button" aria-label="关闭档案详情" @click="detailRecord = null">×</button></div>
      <div class="facts"><p><span>状态</span><b>{{ detailRecord.status }}</b></p><p><span>密级</span><b>{{ detailRecord.confidentiality }}</b></p><p><span>来源</span><b>{{ detailRecord.source_type }}</b></p><p><span>锁版本</span><b>v{{ detailRecord.lock_version }}</b></p></div>
      <section class="drawer-section"><h3>版本链</h3><div v-for="revision in detailRecord.revisions" :key="revision.id" class="event-row"><div><b>修订 {{ revision.version_no }}</b><small>附件 #{{ revision.attachment_id }} · {{ revision.size_bytes }} B</small></div><code>{{ shortHash(revision.checksum_sha256) }}</code></div><p v-if="!detailRecord.revisions?.length" class="empty">尚未绑定附件版本</p></section>
      <form v-if="detailRecord.status === 'DRAFT' && canRecordWrite" class="inline-form" @submit.prevent="addRevision"><label>已上传附件 ID<input v-model="revisionAttachmentId" class="input" type="number" min="1" required /></label><button class="btn" type="submit" :disabled="saving">生成新版本</button></form>
      <div class="action-grid"><button v-if="detailRecord.status === 'DRAFT' && detailRecord.revisions?.length && canRecordWrite" class="btn" type="button" @click="fileRecord">正式归档</button><button v-if="['FILED','ON_HOLD'].includes(detailRecord.status) && canVerify" class="btn btn-quiet" type="button" @click="verifyRecord">校验完整性</button><button v-if="detailRecord.status === 'FILED' && canHold" class="btn btn-risk" type="button" @click="placeHold">证据保全</button></div>
      <section class="drawer-section"><h3>完整性与保全事件</h3><p v-for="event in detailRecord.integrity_events" :key="event.id" class="event-row"><b>{{ event.result }}</b><small>{{ event.verified_at }}</small></p><p v-for="hold in detailRecord.holds" :key="hold.id" class="event-row"><b>保全 · {{ hold.status }}</b><small>{{ hold.reason }}</small></p><p v-if="!detailRecord.integrity_events?.length && !detailRecord.holds?.length" class="empty">暂无治理事件</p></section>
    </aside>

    <aside v-if="detailSeal" class="drawer card" aria-label="印章详情">
      <div class="drawer-head"><div><p class="eyebrow">{{ detailSeal.seal_code }}</p><h2>{{ detailSeal.name }}</h2></div><button type="button" aria-label="关闭印章详情" @click="detailSeal = null">×</button></div>
      <div class="facts"><p><span>状态</span><b>{{ detailSeal.status }}</b></p><p><span>类型</span><b>{{ detailSeal.kind }}</b></p><p><span>保管人</span><b>#{{ detailSeal.custodian_user_id }}</b></p><p><span>锁版本</span><b>v{{ detailSeal.lock_version }}</b></p></div>
      <section class="drawer-section"><h3>不可覆盖保管链</h3><p v-for="event in detailSeal.custody_events" :key="event.id" class="event-row"><b>{{ event.event_type }} · {{ event.status }}</b><small>{{ event.reason }} · {{ event.occurred_at }}</small></p></section>
      <button v-if="detailSeal.status === 'ACTIVE' && canSealManage" class="btn btn-risk full" type="button" @click="markSealLost">报告遗失并冻结</button>
    </aside>
  </section>
</template>

<style scoped>
.governance-page { display: grid; gap: 1rem; width: 100%; min-width: 0; overflow-x: hidden; }
.governance-page > * { min-width: 0; max-width: 100%; }
.page-head, .section-head, .drawer-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.page-head > div, .section-head > div { min-width: 0; }
.page-head h1 { margin: .15rem 0; overflow-wrap: anywhere; font-size: clamp(1.6rem, 3vw, 2.35rem); letter-spacing: -.035em; }
.page-head p:last-child, .muted { color: var(--muted); }
.eyebrow { margin: 0; color: var(--primary); font-size: .68rem; font-weight: 900; letter-spacing: .14em; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; }
.metric { padding: 1rem; border-top: 3px solid #1484a8; }.metric span, .metric small { display: block; color: var(--muted); }.metric strong { display: block; margin: .2rem 0; color: #12394b; font-size: 1.8rem; }.risk-metric { border-top-color: #d85b39; }
.tabs { display: flex; gap: .4rem; padding: .45rem; }.tabs button { flex: 1; border: 0; border-radius: 9px; padding: .65rem; background: transparent; color: var(--muted); cursor: pointer; }.tabs button.active { background: #e7f3f7; color: #0c6e8d; font-weight: 800; }
.panel { min-width: 0; padding: 1rem; }.section-head h2 { margin: .15rem 0; font-size: 1.05rem; }
.form-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .7rem; padding: .85rem; margin: .8rem 0; border: 1px solid var(--border); border-radius: 12px; background: #f7fafb; }.form-grid.wide { grid-template-columns: repeat(3, minmax(0, 1fr)); }.form-grid label, .inline-form label { display: grid; gap: .3rem; color: var(--muted); font-size: .75rem; }.form-grid textarea, .form-grid select { font: inherit; }.span-2 { grid-column: span 2; }.align-end { align-self: end; }
.chip-list { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .8rem; }.chip { display: inline-flex; gap: .35rem; padding: .4rem .6rem; border-radius: 99px; background: #edf5f7; color: #355b69; font-size: .72rem; }
.table-wrap { width: 100%; max-width: 100%; overflow-x: auto; }.table small { display: block; color: var(--muted); font-size: .7rem; }.table td { vertical-align: middle; }.mono { font-family: Consolas, monospace; font-size: .75rem; }
.link-btn { border: 0; padding: .2rem; background: transparent; color: #0c6e8d; font-weight: 700; cursor: pointer; }.status { display: inline-flex; padding: .18rem .5rem; border-radius: 99px; font-size: .68rem; font-weight: 800; }.status.ok { background: #e5f5ef; color: #0f6e56; }.status.pending { background: #fff3d5; color: #8a5b00; }.status.risk { background: #ffebe5; color: #b53d23; }
.card-grid, .provider-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; margin-top: .8rem; }.item-card, .provider-card { padding: .85rem; border: 1px solid var(--border); border-radius: 12px; background: #fbfcfd; }.item-card header, .item-card footer { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }.item-card h3 { margin: .6rem 0 .1rem; }.item-card p, .item-card footer { color: var(--muted); font-size: .72rem; }.provider-card { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .45rem; }.provider-card div { display: grid; }.provider-card small, .provider-card p { color: var(--muted); font-size: .7rem; }.provider-card p { grid-column: 1 / -1; margin: 0; }
.compact-list p { display: grid; grid-template-columns: 1fr 1fr auto; align-items: center; gap: .7rem; padding: .65rem; margin: 0; border-bottom: 1px solid var(--border); }.truth-banner { display: grid; gap: .2rem; padding: .9rem 1rem; border-left: 4px solid #d85b39; border-radius: 10px; background: #fff3ed; color: #74341f; }.truth-banner span { font-size: .78rem; }
.notice { display: flex; align-items: center; gap: .7rem; padding: .7rem .9rem; border-radius: 10px; font-size: .8rem; }.notice button { margin-left: auto; border: 0; background: transparent; color: inherit; font-weight: 800; cursor: pointer; }.notice.success { background: #e7f5f0; color: #0f6e56; }.notice.warning { background: #fff4d9; color: #855d08; }.notice.danger { background: #ffebe5; color: #a63820; }.notice.danger span { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.drawer { position: fixed; z-index: 40; top: 1rem; right: 1rem; bottom: 1rem; width: min(440px, calc(100vw - 2rem)); overflow-y: auto; padding: 1rem; box-shadow: 0 20px 60px rgb(15 42 56 / 28%); }.drawer-head h2 { margin: .15rem 0; }.drawer-head button { border: 0; background: transparent; color: var(--muted); font-size: 1.7rem; cursor: pointer; }.facts { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: .8rem 0; }.facts p { display: grid; gap: .15rem; padding: .6rem; margin: 0; border-radius: 9px; background: #f3f7f8; }.facts span { color: var(--muted); font-size: .68rem; }.drawer-section { padding-top: .8rem; margin-top: .8rem; border-top: 1px solid var(--border); }.drawer-section h3 { font-size: .85rem; }.event-row { display: flex; align-items: center; justify-content: space-between; gap: .6rem; padding: .55rem; margin: .35rem 0; border-radius: 8px; background: #f7f9fa; font-size: .72rem; }.event-row div, .event-row { min-width: 0; }.event-row div { display: grid; }.event-row small { color: var(--muted); }.event-row code { color: #0c6e8d; font-size: .65rem; }.inline-form { display: grid; grid-template-columns: 1fr auto; align-items: end; gap: .5rem; margin-top: .8rem; }.action-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; margin: .8rem 0; }.btn-quiet { border: 1px solid #91b7c4; background: #fff; color: #0c6e8d; }.btn-risk { background: #b8462a; }.full { width: 100%; }
.state, .empty { min-height: 160px; display: grid; place-content: center; justify-items: center; color: var(--muted); text-align: center; }.spinner { width: 1.6rem; height: 1.6rem; border: 3px solid #dce8e4; border-top-color: #0c6e8d; border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1050px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.form-grid, .form-grid.wide { grid-template-columns: repeat(2, minmax(0, 1fr)); }.card-grid, .provider-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) {
  .page-head { align-items: flex-start; }
  .page-head .btn { flex: 0 0 auto; padding-inline: .7rem; }
  .metric-grid, .card-grid, .provider-grid, .form-grid, .form-grid.wide { grid-template-columns: 1fr; }
  .span-2 { grid-column: auto; }
  .tabs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); overflow: visible; }
  .tabs button { min-width: 0; padding-inline: .35rem; overflow-wrap: anywhere; }
  .panel { padding: .8rem; }
  .section-head { align-items: flex-start; }
  .table-wrap { overflow: visible; }
  .table, .table tbody { display: block; width: 100%; min-width: 0; }
  .table thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); white-space: nowrap; }
  .table tr { display: grid; gap: .45rem; width: 100%; padding: .75rem 0; border-bottom: 1px solid var(--border); }
  .table td { display: grid; grid-template-columns: minmax(6.5rem, 42%) minmax(0, 1fr); gap: .55rem; width: 100%; padding: 0; border: 0; overflow-wrap: anywhere; }
  .table td::before { content: attr(data-label); color: var(--muted); font-size: .72rem; font-weight: 700; }
  .table td.empty { display: grid; grid-template-columns: 1fr; }
  .table td.empty::before { content: none; }
  .notice { align-items: flex-start; flex-wrap: wrap; }
  .notice button { margin-left: 0; }
  .action-grid { grid-template-columns: 1fr; }
}
</style>
