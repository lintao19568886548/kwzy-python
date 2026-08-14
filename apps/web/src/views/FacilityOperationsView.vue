<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type Device = {
  id: number;
  park_id: number;
  device_code: string;
  name: string;
  device_type: string;
  location: string;
  criticality: string;
  status: string;
  lock_version: number;
  history?: Array<{
    version_no: number;
    action: string;
    reason: string;
    changed_at: string;
  }>;
};
type InspectionSchedule = {
  id: number;
  park_id: number;
  code: string;
  name: string;
  device_id: number;
  template_version_id: number;
  assignee_user_id: number;
  weekday: number;
  local_due_time: string;
  status: string;
  lock_version: number;
};
type InspectionItem = {
  item_code: string;
  label: string;
  result_type: string;
  required: boolean;
  critical: boolean;
  minimum?: string | null;
  maximum?: string | null;
  options?: string[];
};
type InspectionTask = {
  id: number;
  park_id: number;
  device_id: number;
  assignee_user_id: number;
  status: string;
  window_start: string;
  window_due_at: string;
  lock_version: number;
  template_snapshot?: { items: InspectionItem[] };
  results?: Array<{ item_code: string; passed: boolean; text_value?: string | null }>;
  exceptions?: Array<{
    id: number;
    item_code: string;
    severity: string;
    summary: string;
    status: string;
    work_order_id?: number | null;
  }>;
  events?: Array<{ id: number; event_type: string; occurred_at: string }>;
};
type Alarm = {
  id: number;
  park_id: number;
  device_id: number;
  alarm_type: string;
  title: string;
  severity: string;
  status: string;
  occurrence_count: number;
  last_seen_at: string;
  work_order_id?: number | null;
  lock_version: number;
  events?: Array<{
    id: number;
    source_event_id: string;
    source_time: string;
    canonical_severity: string;
  }>;
  escalations?: Array<{ level: number; reason: string; occurred_at: string }>;
};
type Provider = {
  id: number;
  code: string;
  name: string;
  adapter_kind: string;
  status: string;
  capability_state: string;
};
type Template = {
  id: number;
  code: string;
  name: string;
  status: string;
  versions: Array<{
    id: number;
    version_no: number;
    status: string;
    lock_version: number;
    items: InspectionItem[];
  }>;
};

const auth = useAuthStore();
const activeTab = ref<"devices" | "inspections" | "alarms">("devices");
const devices = ref<Device[]>([]);
const schedules = ref<InspectionSchedule[]>([]);
const tasks = ref<InspectionTask[]>([]);
const alarms = ref<Alarm[]>([]);
const providers = ref<Provider[]>([]);
const templates = ref<Template[]>([]);
const detailDevice = ref<Device | null>(null);
const detailTask = ref<InspectionTask | null>(null);
const detailAlarm = ref<Alarm | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const errorStatus = ref(0);
const success = ref("");
const showDeviceForm = ref(false);
const showTemplateForm = ref(false);
const showScheduleForm = ref(false);
const showProviderForm = ref(false);
const showBindingForm = ref(false);
const showIngestForm = ref(false);
const taskValues = ref<Record<string, string | boolean>>({});
const taskRemarks = ref<Record<string, string>>({});
const reassignUserId = ref("");
const resolutionReason = ref("");
const deviceEdit = ref({ name: "", location: "", criticality: "MEDIUM", reason: "" });
const retireReason = ref("");

const deviceDraft = ref({
  park_id: "",
  device_code: "",
  name: "",
  device_type: "FIRE",
  location: "",
  criticality: "MEDIUM",
});
const templateDraft = ref({
  code: "",
  name: "",
  device_type: "FIRE",
  item_code: "RUNNING",
  label: "运行状态",
  result_type: "BOOLEAN",
  critical: true,
});
const scheduleDraft = ref({
  park_id: "",
  code: "",
  name: "",
  device_id: "",
  template_version_id: "",
  assignee_user_id: "",
  weekday: "1",
  local_due_time: "09:00",
  completion_window_minutes: "1440",
  missed_work_order: true,
});
const providerDraft = ref({ code: "", name: "", adapter_kind: "SANDBOX" });
const bindingDraft = ref({
  provider_id: "",
  device_id: "",
  external_device_key: "",
  reason: "沙箱设备绑定",
});
const ingestDraft = ref({
  provider_id: "",
  external_device_key: "",
  alarm_type: "DEVICE_FAULT",
  title: "",
  severity: "WARNING",
  error_code: "",
});

const canDeviceRead = computed(() => auth.can("*") || auth.can("facility_device:read"));
const canDeviceWrite = computed(() => auth.can("*") || auth.can("facility_device:write"));
const canDeviceRetire = computed(() => auth.can("*") || auth.can("facility_device:retire"));
const canInspectionRead = computed(
  () => auth.can("*") || auth.can("inspection:read") || auth.can("inspection:execute")
);
const canInspectionScheduleRead = computed(
  () => auth.can("*") || auth.can("inspection:read") || auth.can("inspection:schedule_manage")
);
const canInspectionExecute = computed(
  () => auth.can("*") || auth.can("inspection:execute")
);
const canInspectionDispatch = computed(
  () => auth.can("*") || auth.can("inspection:dispatch")
);
const canTemplateManage = computed(
  () => auth.can("*") || auth.can("inspection:template_manage")
);
const canScheduleManage = computed(
  () => auth.can("*") || auth.can("inspection:schedule_manage")
);
const canInspectionSweep = computed(() => auth.can("*") || auth.can("inspection:sweep"));
const canAlarmRead = computed(() => auth.can("*") || auth.can("iot:alarm_read"));
const canAlarmManage = computed(() => auth.can("*") || auth.can("iot:alarm_manage"));
const canProviderManage = computed(() => auth.can("*") || auth.can("iot:provider_manage"));
const canBindingManage = computed(() => auth.can("*") || auth.can("iot:binding_manage"));
const canIngest = computed(() => auth.can("*") || auth.can("iot:ingest"));

const metrics = computed(() => ({
  activeDevices: devices.value.filter((row) => row.status !== "RETIRED").length,
  dueTasks: tasks.value.filter((row) => ["PENDING", "IN_PROGRESS"].includes(row.status)).length,
  failedTasks: tasks.value.filter((row) => ["FAILED", "MISSED"].includes(row.status)).length,
  criticalAlarms: alarms.value.filter(
    (row) => row.severity === "CRITICAL" && !["RESOLVED", "CLOSED"].includes(row.status)
  ).length,
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

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function activeDeviceTaskCount(deviceId: number) {
  return tasks.value.filter(
    (row) => row.device_id === deviceId && ["PENDING", "IN_PROGRESS"].includes(row.status)
  ).length;
}

function activeDeviceAlarmCount(deviceId: number) {
  return alarms.value.filter(
    (row) => row.device_id === deviceId && ["OPEN", "ACKNOWLEDGED"].includes(row.status)
  ).length;
}

async function loadAll() {
  clearMessages();
  loading.value = true;
  try {
    const calls: Promise<void>[] = [];
    if (canDeviceRead.value) {
      calls.push(
        http
          .get<Envelope<PageResult<Device>>>("/facility-devices", {
            params: { page: 1, page_size: 200 },
          })
          .then((response) => {
            devices.value = response.data.data.items;
          })
      );
    }
    if (canInspectionRead.value) {
      calls.push(
        http
          .get<Envelope<PageResult<InspectionTask>>>("/inspection-tasks", {
            params: { page: 1, page_size: 200 },
          })
          .then((response) => {
            tasks.value = response.data.data.items;
          })
      );
    }
    if (canInspectionScheduleRead.value) {
      calls.push(
        http.get<Envelope<InspectionSchedule[]>>("/inspection-schedules").then((response) => {
          schedules.value = response.data.data;
        })
      );
    }
    if (canTemplateManage.value || auth.can("inspection:read")) {
      calls.push(
        http.get<Envelope<Template[]>>("/inspection-templates").then((response) => {
          templates.value = response.data.data;
        })
      );
    }
    if (canAlarmRead.value) {
      calls.push(
        http
          .get<Envelope<PageResult<Alarm>>>("/iot-alarms", {
            params: { page: 1, page_size: 200 },
          })
          .then((response) => {
            alarms.value = response.data.data.items;
          })
      );
    }
    if (canProviderManage.value || canBindingManage.value || canAlarmRead.value) {
      calls.push(
        http.get<Envelope<Provider[]>>("/iot-providers").then((response) => {
          providers.value = response.data.data;
        })
      );
    }
    await Promise.all(calls);
  } catch (value) {
    requestError(value, "设施运营数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function mutate(call: () => Promise<unknown>, message: string) {
  clearMessages();
  saving.value = true;
  try {
    await call();
    await loadAll();
    success.value = message;
  } catch (value) {
    requestError(value, `${message}失败，输入内容已保留`);
  } finally {
    saving.value = false;
  }
}

async function createDevice() {
  await mutate(
    () =>
      http.post("/facility-devices", {
        ...deviceDraft.value,
        park_id: Number(deviceDraft.value.park_id),
      }),
    "设备已纳入统一台账"
  );
  if (!error.value) {
    showDeviceForm.value = false;
    deviceDraft.value.device_code = "";
    deviceDraft.value.name = "";
  }
}

async function createTemplate() {
  await mutate(
    async () => {
      const response = await http.post<Envelope<Template>>("/inspection-templates", {
        code: templateDraft.value.code,
        name: templateDraft.value.name,
        device_type: templateDraft.value.device_type,
        items: [
          {
            item_code: templateDraft.value.item_code,
            label: templateDraft.value.label,
            result_type: templateDraft.value.result_type,
            required: true,
            critical: templateDraft.value.critical,
          },
        ],
      });
      const version = response.data.data.versions[0];
      await http.post(`/inspection-template-versions/${version.id}/publish`, {
        expected_version: version.lock_version,
      });
    },
    "巡检模板已创建并发布"
  );
  if (!error.value) showTemplateForm.value = false;
}

async function createSchedule() {
  await mutate(
    () =>
      http.post("/inspection-schedules", {
        park_id: Number(scheduleDraft.value.park_id),
        code: scheduleDraft.value.code,
        name: scheduleDraft.value.name,
        device_id: Number(scheduleDraft.value.device_id),
        template_version_id: Number(scheduleDraft.value.template_version_id),
        assignee_user_id: Number(scheduleDraft.value.assignee_user_id),
        timezone: "Asia/Shanghai",
        weekday: Number(scheduleDraft.value.weekday),
        local_due_time: scheduleDraft.value.local_due_time,
        completion_window_minutes: Number(scheduleDraft.value.completion_window_minutes),
        missed_work_order: scheduleDraft.value.missed_work_order,
      }),
    "周巡检计划已创建"
  );
  if (!error.value) showScheduleForm.value = false;
}

async function generateWeeklyTasks() {
  await mutate(
    () => http.post("/inspection-tasks/generate", { as_of: new Date().toISOString() }),
    "本周巡检任务已幂等生成"
  );
}

async function transitionSchedule(row: InspectionSchedule) {
  const target = row.status === "ACTIVE" ? "pause" : "resume";
  await mutate(
    () =>
      http.post(`/inspection-schedules/${row.id}/${target}`, {
        expected_version: row.lock_version,
        reason: target === "pause" ? "PC 暂停巡检计划" : "PC 恢复巡检计划",
      }),
    target === "pause" ? "巡检计划已暂停" : "巡检计划已恢复"
  );
}

async function openDevice(id: number, preserveMessages = false) {
  if (!preserveMessages) clearMessages();
  try {
    const response = await http.get<Envelope<Device>>(`/facility-devices/${id}`);
    detailDevice.value = response.data.data;
    deviceEdit.value = {
      name: response.data.data.name,
      location: response.data.data.location,
      criticality: response.data.data.criticality,
      reason: "",
    };
    retireReason.value = "";
  } catch (value) {
    requestError(value, "设备详情不可见或加载失败");
  }
}

async function updateDevice() {
  if (!detailDevice.value) return;
  const id = detailDevice.value.id;
  await mutate(
    () =>
      http.put(`/facility-devices/${id}`, {
        expected_version: detailDevice.value!.lock_version,
        ...deviceEdit.value,
      }),
    "设备档案已更新并保留版本历史"
  );
  if (!error.value) await openDevice(id, true);
}

async function retireDevice() {
  if (!detailDevice.value) return;
  const id = detailDevice.value.id;
  await mutate(
    () =>
      http.post(`/facility-devices/${id}/retire`, {
        expected_version: detailDevice.value!.lock_version,
        reason: retireReason.value,
      }),
    "设备已受控退役"
  );
  if (!error.value) await openDevice(id, true);
}

async function createProvider() {
  await mutate(
    () =>
      http.post("/iot-providers", {
        ...providerDraft.value,
        environment: "LOCAL",
        correlation_minutes: 30,
        severity_mapping: {},
      }),
    providerDraft.value.adapter_kind === "HTTP"
      ? "外部提供方已登记为未验证，未宣称已连接"
      : "IoT 沙箱提供方已创建"
  );
  if (!error.value) showProviderForm.value = false;
}

async function createBinding() {
  await mutate(
    () =>
      http.post("/iot-device-bindings", {
        ...bindingDraft.value,
        provider_id: Number(bindingDraft.value.provider_id),
        device_id: Number(bindingDraft.value.device_id),
      }),
    "IoT 设备绑定已生效"
  );
  if (!error.value) showBindingForm.value = false;
}

async function ingestAlarm() {
  await mutate(
    () =>
      http.post("/iot-alarm-events/ingest", {
        provider_id: Number(ingestDraft.value.provider_id),
        external_device_key: ingestDraft.value.external_device_key,
        source_event_id: commandKey("pc-sandbox-event"),
        source_time: new Date().toISOString(),
        alarm_type: ingestDraft.value.alarm_type,
        title: ingestDraft.value.title,
        severity: ingestDraft.value.severity,
        payload: { error_code: ingestDraft.value.error_code || undefined },
      }),
    "沙箱告警事件已接收"
  );
  if (!error.value) showIngestForm.value = false;
}

async function openTask(id: number, preserveMessages = false) {
  if (!preserveMessages) clearMessages();
  try {
    const response = await http.get<Envelope<InspectionTask>>(`/inspection-tasks/${id}`);
    detailTask.value = response.data.data;
    reassignUserId.value = String(response.data.data.assignee_user_id);
    taskValues.value = {};
    taskRemarks.value = {};
    for (const item of detailTask.value.template_snapshot?.items || []) {
      taskValues.value[item.item_code] = item.result_type === "BOOLEAN" ? true : "";
    }
  } catch (value) {
    requestError(value, "巡检任务不可见或加载失败");
  }
}

async function reassignTask() {
  if (!detailTask.value) return;
  const id = detailTask.value.id;
  await mutate(
    () =>
      http.post(`/inspection-tasks/${id}/reassign`, {
        expected_version: detailTask.value!.lock_version,
        assignee_user_id: Number(reassignUserId.value),
        reason: "PC 设施运营调度改派",
      }),
    "巡检任务已改派"
  );
  if (!error.value) await openTask(id, true);
}

async function startTask() {
  if (!detailTask.value) return;
  await mutate(
    () =>
      http.post(
        `/inspection-tasks/${detailTask.value!.id}/start`,
        { expected_version: detailTask.value!.lock_version },
        { headers: { "Idempotency-Key": commandKey("pc-inspection-start") } }
      ),
    "巡检任务已开始"
  );
  if (!error.value) await openTask(detailTask.value.id, true);
}

async function submitTask() {
  if (!detailTask.value) return;
  const items = detailTask.value.template_snapshot?.items || [];
  await mutate(
    () =>
      http.post(
        `/inspection-tasks/${detailTask.value!.id}/submit`,
        {
          expected_version: detailTask.value!.lock_version,
          results: items.map((item) => ({
            item_code: item.item_code,
            value: taskValues.value[item.item_code],
            remark: taskRemarks.value[item.item_code] || undefined,
            evidence_refs: [],
          })),
        },
        { headers: { "Idempotency-Key": commandKey("pc-inspection-submit") } }
      ),
    "巡检结果已提交"
  );
  if (!error.value) await openTask(detailTask.value.id, true);
}

async function openAlarm(id: number, preserveMessages = false) {
  if (!preserveMessages) clearMessages();
  try {
    const response = await http.get<Envelope<Alarm>>(`/iot-alarms/${id}`);
    detailAlarm.value = response.data.data;
    if (!preserveMessages) resolutionReason.value = "";
  } catch (value) {
    requestError(value, "告警不可见或加载失败");
  }
}

async function moveAlarm(target: "acknowledge" | "resolve" | "close") {
  if (!detailAlarm.value) return;
  await mutate(
    () =>
      http.post(`/iot-alarms/${detailAlarm.value!.id}/${target}`, {
        expected_version: detailAlarm.value!.lock_version,
        reason: resolutionReason.value || undefined,
      }),
    target === "acknowledge" ? "告警已确认" : target === "resolve" ? "告警已解决" : "告警已关闭"
  );
  if (!error.value) await openAlarm(detailAlarm.value.id, true);
}

onMounted(loadAll);
</script>

<template>
  <main class="facility-page">
    <header class="hero card">
      <div>
        <p class="eyebrow">FACILITY OPERATIONS · GOVERNED LIVE DATA</p>
        <h1 data-testid="facility-title">设施设备、周巡检与 IoT 告警</h1>
        <p>统一设备台账、不可变巡检快照、异常转工单与告警关联升级</p>
      </div>
      <button class="btn btn-ghost" type="button" :disabled="loading" @click="loadAll">
        {{ loading ? "刷新中…" : "刷新真实数据" }}
      </button>
    </header>

    <section class="metric-grid" aria-label="设施运营指标">
      <article class="metric card"><span>在册设备</span><strong>{{ metrics.activeDevices }}</strong></article>
      <article class="metric card"><span>待执行巡检</span><strong>{{ metrics.dueTasks }}</strong></article>
      <article class="metric risk card"><span>异常 / 逾期</span><strong>{{ metrics.failedTasks }}</strong></article>
      <article class="metric risk card"><span>未闭环严重告警</span><strong>{{ metrics.criticalAlarms }}</strong></article>
    </section>

    <nav class="tabs card" aria-label="设施运营视图">
      <button type="button" :class="{ active: activeTab === 'devices' }" @click="activeTab = 'devices'">设备台账</button>
      <button type="button" :class="{ active: activeTab === 'inspections' }" @click="activeTab = 'inspections'">周巡检</button>
      <button type="button" :class="{ active: activeTab === 'alarms' }" @click="activeTab = 'alarms'">IoT 告警</button>
    </nav>

    <p v-if="error" class="notice error" role="alert" data-testid="facility-error">
      {{ errorStatus === 409 ? "并发冲突：" : errorStatus === 0 ? "网络或离线：" : "" }}{{ error }}
      <button type="button" @click="loadAll">重新加载后重试</button>
    </p>
    <p v-if="success" class="notice ok" role="status">{{ success }}</p>

    <template v-if="activeTab === 'devices'">
      <section class="toolbar card">
        <div><b>统一设备台账</b><span>退役保留历史，不提供物理删除</span></div>
        <button v-if="canDeviceWrite" class="btn" type="button" data-testid="facility-add-device" @click="showDeviceForm = !showDeviceForm">{{ showDeviceForm ? "收起" : "新增设备" }}</button>
      </section>
      <form v-if="showDeviceForm" class="form-grid card" @submit.prevent="createDevice">
        <label>园区 ID<input v-model="deviceDraft.park_id" class="input" inputmode="numeric" required /></label>
        <label>设备编码<input v-model="deviceDraft.device_code" class="input" maxlength="64" required /></label>
        <label>设备名称<input v-model="deviceDraft.name" class="input" maxlength="128" required /></label>
        <label>设备类型<select v-model="deviceDraft.device_type" class="input"><option>FIRE</option><option>ELEVATOR</option><option>TRANSFORMER</option><option>ELECTRICAL</option><option>HVAC</option><option>WATER</option><option>SECURITY</option><option>CUSTOM</option></select></label>
        <label>位置<input v-model="deviceDraft.location" class="input" maxlength="255" required /></label>
        <label>关键等级<select v-model="deviceDraft.criticality" class="input"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label>
        <button class="btn" :disabled="saving">保存设备</button>
      </form>
      <section class="queue card">
        <div v-if="loading" class="state">设备台账加载中…</div>
        <div v-else-if="!canDeviceRead" class="state">当前角色无设备台账查看权限</div>
        <div v-else-if="!devices.length" class="state">暂无设备；可由有权限人员建立统一台账</div>
        <div v-else class="table-wrap">
          <table class="table" data-testid="facility-device-table">
            <thead><tr><th>设备</th><th>园区 / 位置</th><th>类型</th><th>关键等级</th><th>状态</th></tr></thead>
            <tbody><tr v-for="row in devices" :key="row.id"><td data-label="设备"><button class="link-button" type="button" :aria-label="`查看设备 ${row.device_code}`" @click="openDevice(row.id)"><b>{{ row.device_code }}</b><span>{{ row.name }}</span></button></td><td data-label="园区 / 位置"><b>#{{ row.park_id }}</b><span>{{ row.location }}</span></td><td data-label="类型">{{ row.device_type }}</td><td data-label="关键等级"><span class="pill" :class="row.criticality.toLowerCase()">{{ row.criticality }}</span></td><td data-label="状态">{{ row.status }}</td></tr></tbody>
          </table>
        </div>
      </section>
    </template>

    <template v-else-if="activeTab === 'inspections'">
      <section class="toolbar card">
        <div><b>周巡检任务</b><span>任务保存已发布模板快照，后续模板变更不回写历史</span></div>
        <div class="actions"><button v-if="canTemplateManage" class="btn btn-ghost" type="button" @click="showTemplateForm = !showTemplateForm">{{ showTemplateForm ? "收起模板" : "新建检查模板" }}</button><button v-if="canScheduleManage" class="btn btn-ghost" type="button" @click="showScheduleForm = !showScheduleForm">{{ showScheduleForm ? "收起计划" : "新建周检计划" }}</button><button v-if="canInspectionSweep" class="btn" type="button" :disabled="saving" @click="generateWeeklyTasks">生成本周任务</button></div>
      </section>
      <form v-if="showTemplateForm" class="form-grid card" @submit.prevent="createTemplate">
        <label>模板编码<input v-model="templateDraft.code" class="input" required /></label><label>模板名称<input v-model="templateDraft.name" class="input" required /></label><label>设备类型<select v-model="templateDraft.device_type" class="input"><option>FIRE</option><option>ELEVATOR</option><option>TRANSFORMER</option><option>ELECTRICAL</option><option>HVAC</option><option>WATER</option><option>SECURITY</option><option>CUSTOM</option></select></label><label>检查项编码<input v-model="templateDraft.item_code" class="input" required /></label><label>检查项名称<input v-model="templateDraft.label" class="input" required /></label><label>结果类型<select v-model="templateDraft.result_type" class="input"><option>BOOLEAN</option><option>NUMBER</option><option>TEXT</option></select></label><label class="check"><input v-model="templateDraft.critical" type="checkbox" /> 关键检查项</label><button class="btn" :disabled="saving">创建并发布 v1</button>
      </form>
      <form v-if="showScheduleForm" class="form-grid card" data-testid="inspection-schedule-form" @submit.prevent="createSchedule">
        <label>计划园区 ID<input v-model="scheduleDraft.park_id" class="input" inputmode="numeric" required /></label><label>计划编码<input v-model="scheduleDraft.code" class="input" required /></label><label>计划名称<input v-model="scheduleDraft.name" class="input" required /></label><label>计划设备 ID<input v-model="scheduleDraft.device_id" class="input" inputmode="numeric" required /></label><label>模板版本 ID<input v-model="scheduleDraft.template_version_id" class="input" inputmode="numeric" required /></label><label>执行人用户 ID<input v-model="scheduleDraft.assignee_user_id" class="input" inputmode="numeric" required /></label><label>周几<select v-model="scheduleDraft.weekday" class="input"><option value="1">周一</option><option value="2">周二</option><option value="3">周三</option><option value="4">周四</option><option value="5">周五</option><option value="6">周六</option><option value="7">周日</option></select></label><label>当地截止时间<input v-model="scheduleDraft.local_due_time" class="input" type="time" required /></label><label>完成窗口（分钟）<input v-model="scheduleDraft.completion_window_minutes" class="input" type="number" min="1" max="10080" required /></label><label class="check"><input v-model="scheduleDraft.missed_work_order" type="checkbox" /> 逾期自动转工单</label><button class="btn" :disabled="saving">保存周检计划</button>
      </form>
      <section v-if="canInspectionRead && schedules.length" class="provider-strip card" aria-label="生效巡检计划"><article v-for="row in schedules" :key="row.id"><b>{{ row.name }}</b><span>{{ row.code }} · {{ row.status }}</span><small>设备 #{{ row.device_id }} · 周{{ row.weekday }} {{ row.local_due_time }} · 执行人 #{{ row.assignee_user_id }}</small><button v-if="canScheduleManage && row.status !== 'RETIRED'" class="btn btn-ghost" type="button" @click="transitionSchedule(row)">{{ row.status === "ACTIVE" ? "暂停计划" : "恢复计划" }}</button></article></section>
      <section class="queue card">
        <div v-if="loading" class="state">巡检队列加载中…</div><div v-else-if="!canInspectionRead" class="state">当前角色无巡检查看或执行权限</div><div v-else-if="!tasks.length" class="state">暂无巡检任务；管理员需先发布模板、创建计划并生成本周任务</div>
        <div v-else class="task-grid"><button v-for="row in tasks" :key="row.id" class="task-card" type="button" :data-testid="`inspection-task-${row.id}`" @click="openTask(row.id)"><span>{{ row.status }}</span><b>巡检 #{{ row.id }} · 设备 #{{ row.device_id }}</b><small>截止 {{ formatTime(row.window_due_at) }} · 执行人 #{{ row.assignee_user_id }}</small></button></div>
      </section>
    </template>

    <template v-else>
      <section class="toolbar card"><div><b>IoT 告警队列</b><span>高风险告警自动转工单；外部平台未验证时明确显示 NOT_CONNECTED</span></div><div class="actions"><button v-if="canProviderManage" class="btn btn-ghost" type="button" @click="showProviderForm = !showProviderForm">登记提供方</button><button v-if="canBindingManage" class="btn btn-ghost" type="button" @click="showBindingForm = !showBindingForm">绑定设备</button><button v-if="canIngest" class="btn" type="button" @click="showIngestForm = !showIngestForm">注入沙箱事件</button></div></section>
      <form v-if="showProviderForm" class="form-grid card" @submit.prevent="createProvider"><label>编码<input v-model="providerDraft.code" class="input" required /></label><label>名称<input v-model="providerDraft.name" class="input" required /></label><label>适配器<select v-model="providerDraft.adapter_kind" class="input"><option>SANDBOX</option><option>LOCAL</option><option>HTTP</option></select></label><button class="btn" :disabled="saving">登记真实状态</button></form>
      <form v-if="showBindingForm" class="form-grid card" @submit.prevent="createBinding"><label>提供方 ID<input v-model="bindingDraft.provider_id" class="input" required /></label><label>设备 ID<input v-model="bindingDraft.device_id" class="input" required /></label><label>外部设备键<input v-model="bindingDraft.external_device_key" class="input" required /></label><label>绑定原因<input v-model="bindingDraft.reason" class="input" required /></label><button class="btn" :disabled="saving">创建绑定</button></form>
      <form v-if="showIngestForm" class="form-grid card" @submit.prevent="ingestAlarm"><label>提供方 ID<input v-model="ingestDraft.provider_id" class="input" required /></label><label>外部设备键<input v-model="ingestDraft.external_device_key" class="input" required /></label><label>告警类型<input v-model="ingestDraft.alarm_type" class="input" required /></label><label>告警标题<input v-model="ingestDraft.title" class="input" required /></label><label>严重度<select v-model="ingestDraft.severity" class="input"><option>INFO</option><option>WARNING</option><option>HIGH</option><option>CRITICAL</option></select></label><label>错误码<input v-model="ingestDraft.error_code" class="input" /></label><button class="btn" :disabled="saving">发送沙箱事件</button></form>
      <section class="provider-strip card"><article v-for="row in providers" :key="row.id"><b>{{ row.name }}</b><span>{{ row.adapter_kind }} · {{ row.status }}</span><small>{{ row.capability_state }}</small></article><p v-if="!providers.length">暂无已授权的 IoT 提供方</p></section>
      <section class="queue card"><div v-if="loading" class="state">告警队列加载中…</div><div v-else-if="!canAlarmRead" class="state">当前角色无告警查看权限</div><div v-else-if="!alarms.length" class="state">当前没有真实或沙箱告警事件</div><div v-else class="task-grid"><button v-for="row in alarms" :key="row.id" class="task-card alarm" type="button" @click="openAlarm(row.id)"><span :class="row.severity.toLowerCase()">{{ row.severity }}</span><b>{{ row.title }}</b><small>{{ row.status }} · {{ row.occurrence_count }} 次 · {{ formatTime(row.last_seen_at) }}</small></button></div></section>
    </template>

    <div v-if="detailTask" class="drawer-mask" @click.self="detailTask = null"><aside class="drawer" aria-label="巡检任务详情"><header class="drawer-head"><div><span>INSPECTION #{{ detailTask.id }}</span><h2>设备 #{{ detailTask.device_id }} 周巡检</h2></div><button type="button" @click="detailTask = null">×</button></header><div class="drawer-body"><section class="status-band"><div><span>状态</span><strong>{{ detailTask.status }}</strong></div><div><span>执行人</span><strong>#{{ detailTask.assignee_user_id }}</strong></div><div><span>版本</span><strong>v{{ detailTask.lock_version }}</strong></div></section><button v-if="canInspectionExecute && detailTask.status === 'PENDING'" class="btn" type="button" :disabled="saving" @click="startTask">开始巡检</button><form v-if="canInspectionExecute && detailTask.status === 'IN_PROGRESS'" class="result-form" @submit.prevent="submitTask"><article v-for="item in detailTask.template_snapshot?.items" :key="item.item_code"><b>{{ item.label }} <em v-if="item.critical">关键</em></b><select v-if="item.result_type === 'BOOLEAN'" v-model="taskValues[item.item_code]" class="input"><option :value="true">通过</option><option :value="false">不通过</option></select><input v-else v-model="taskValues[item.item_code]" class="input" :type="item.result_type === 'NUMBER' ? 'number' : 'text'" required /><input v-model="taskRemarks[item.item_code]" class="input" placeholder="异常说明" /></article><button class="btn" :disabled="saving">提交全部检查结果</button></form><section v-if="detailTask.exceptions?.length" class="detail-section"><h3>异常与工单</h3><article v-for="item in detailTask.exceptions" :key="item.id" class="record"><b>{{ item.severity }} · {{ item.summary }}</b><span>{{ item.status }} · 工单 {{ item.work_order_id ? `#${item.work_order_id}` : "未转" }}</span></article></section></div></aside></div>

    <div v-if="detailAlarm" class="drawer-mask" @click.self="detailAlarm = null"><aside class="drawer" aria-label="IoT 告警详情"><header class="drawer-head"><div><span>{{ detailAlarm.severity }} · {{ detailAlarm.alarm_type }}</span><h2>{{ detailAlarm.title }}</h2></div><button type="button" @click="detailAlarm = null">×</button></header><div class="drawer-body"><section class="status-band"><div><span>状态</span><strong>{{ detailAlarm.status }}</strong></div><div><span>关联次数</span><strong>{{ detailAlarm.occurrence_count }}</strong></div><div><span>工单</span><strong>{{ detailAlarm.work_order_id ? `#${detailAlarm.work_order_id}` : "—" }}</strong></div></section><section v-if="canAlarmManage" class="action-section"><button v-if="detailAlarm.status === 'OPEN'" class="btn" type="button" @click="moveAlarm('acknowledge')">确认告警</button><form v-if="['OPEN', 'ACKNOWLEDGED'].includes(detailAlarm.status)" class="resolve" @submit.prevent="moveAlarm('resolve')"><input v-model="resolutionReason" class="input" maxlength="1000" placeholder="解决原因（必填）" required /><button class="btn" :disabled="saving">解决告警</button></form><button v-if="detailAlarm.status === 'RESOLVED'" class="btn btn-ghost" type="button" @click="moveAlarm('close')">关闭归档</button></section><section class="detail-section"><h3>来源事件</h3><article v-for="item in detailAlarm.events" :key="item.id" class="record"><b>{{ item.canonical_severity }} · {{ item.source_event_id }}</b><span>{{ formatTime(item.source_time) }}</span></article></section><section v-if="detailAlarm.escalations?.length" class="detail-section"><h3>升级记录</h3><article v-for="item in detailAlarm.escalations" :key="item.level" class="record"><b>L{{ item.level }} · {{ item.reason }}</b><span>{{ formatTime(item.occurred_at) }}</span></article></section></div></aside></div>
    <div v-if="detailDevice" class="drawer-mask" @click.self="detailDevice = null">
      <aside class="drawer" aria-label="设备档案详情">
        <header class="drawer-head"><div><span>{{ detailDevice.device_type }} · {{ detailDevice.device_code }}</span><h2>{{ detailDevice.name }}</h2></div><button type="button" aria-label="关闭设备档案" @click="detailDevice = null">×</button></header>
        <div class="drawer-body">
          <section class="status-band"><div><span>状态</span><strong>{{ detailDevice.status }}</strong></div><div><span>园区</span><strong>#{{ detailDevice.park_id }}</strong></div><div><span>版本</span><strong>v{{ detailDevice.lock_version }}</strong></div></section>
          <section class="status-band"><div><span>位置</span><strong>{{ detailDevice.location }}</strong></div><div><span>待执行巡检</span><strong>{{ activeDeviceTaskCount(detailDevice.id) }}</strong></div><div><span>活动告警</span><strong>{{ activeDeviceAlarmCount(detailDevice.id) }}</strong></div></section>
          <form v-if="canDeviceWrite && detailDevice.status !== 'RETIRED'" class="result-form" @submit.prevent="updateDevice"><label>设备名称<input v-model="deviceEdit.name" class="input" required /></label><label>设备位置<input v-model="deviceEdit.location" class="input" required /></label><label>关键等级<select v-model="deviceEdit.criticality" class="input"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label><label>变更原因<input v-model="deviceEdit.reason" class="input" required /></label><button class="btn" :disabled="saving">保存设备变更</button></form>
          <form v-if="canDeviceRetire && detailDevice.status !== 'RETIRED'" class="resolve" @submit.prevent="retireDevice"><input v-model="retireReason" class="input" maxlength="1000" placeholder="退役原因（受控操作）" required /><button class="btn btn-ghost" :disabled="saving">退役设备</button></form>
          <section class="detail-section"><h3>不可变版本历史</h3><article v-for="item in detailDevice.history" :key="item.version_no" class="record"><b>v{{ item.version_no }} · {{ item.action }}</b><span>{{ item.reason }} · {{ formatTime(item.changed_at) }}</span></article></section>
        </div>
      </aside>
    </div>
    <section v-if="detailTask && canInspectionDispatch && ['PENDING', 'IN_PROGRESS'].includes(detailTask.status)" class="drawer-floating-action" aria-label="巡检调度操作"><form class="resolve" @submit.prevent="reassignTask"><label>改派用户 ID<input v-model="reassignUserId" class="input" inputmode="numeric" required /></label><button class="btn" :disabled="saving">确认改派</button></form></section>
    <RouterLink v-if="detailTask?.exceptions?.some((item) => item.work_order_id)" class="linked-work-order" :to="{ path: '/work-orders', query: { work_order_id: detailTask.exceptions?.find((item) => item.work_order_id)?.work_order_id } }">打开关联工单 #{{ detailTask.exceptions?.find((item) => item.work_order_id)?.work_order_id }}</RouterLink>
    <RouterLink v-if="detailAlarm?.work_order_id" class="linked-work-order alarm-link" :to="{ path: '/work-orders', query: { work_order_id: detailAlarm.work_order_id } }">打开告警工单 #{{ detailAlarm.work_order_id }}</RouterLink>
  </main>
</template>

<style scoped>
.link-button{display:grid;gap:.1rem;padding:0;border:0;color:inherit;background:transparent;text-align:left;cursor:pointer}.link-button:hover b,.link-button:focus b{color:#087f8d;text-decoration:underline}
.drawer-floating-action{position:fixed;right:1rem;bottom:4.5rem;z-index:72;width:min(680px,calc(94vw - 2rem));padding:.7rem;border-radius:12px;background:#fff;box-shadow:0 12px 34px rgba(5,25,40,.18)}.linked-work-order{position:fixed;right:1rem;bottom:1rem;z-index:73;padding:.65rem .9rem;border-radius:9px;color:#fff;background:#0c7180;text-decoration:none}.linked-work-order.alarm-link{background:#bd432f}
.facility-page{display:grid;min-width:0;gap:1rem;color:#173247}.hero{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1.25rem;background:linear-gradient(135deg,#fff 54%,#e9f7f8)}.hero h1{margin:.15rem 0;font-size:clamp(1.45rem,3vw,2.1rem)}.hero p{margin:.2rem 0;color:#607887}.eyebrow{color:#158493!important;font-size:.7rem;font-weight:900;letter-spacing:.14em}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem}.metric{padding:.85rem 1rem;border-top:3px solid #1ca1ad}.metric span{color:#6a808c;font-size:.72rem}.metric strong{display:block;font-size:1.6rem}.metric.risk{border-color:#e05b3f}.metric.risk strong,.critical{color:#bd432f}.tabs{display:flex;gap:.35rem;padding:.45rem}.tabs button{border:0;border-radius:9px;padding:.55rem .85rem;color:#5c7481;background:transparent;cursor:pointer}.tabs button.active{color:#fff;background:#0c7180}.notice{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin:0;padding:.75rem 1rem;border-radius:10px;background:#edf8f4}.notice.error{background:#fff0ed}.notice button{border:0;color:#087f8d;background:transparent;cursor:pointer;text-decoration:underline}.ok{color:#08755d}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:.7rem;padding:.85rem 1rem}.toolbar>div:first-child{display:grid}.toolbar span{color:#718894;font-size:.72rem}.actions{display:flex;gap:.45rem;flex-wrap:wrap}.form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;padding:1rem}.form-grid label{display:grid;gap:.3rem;color:#526b78;font-size:.72rem;font-weight:700}.form-grid .check{display:flex;align-items:center}.form-grid .btn{align-self:end}.queue{min-width:0;overflow:hidden}.table-wrap{max-width:100%;overflow-x:auto}.table{min-width:760px}.table td b,.table td span{display:block}.table td span{color:#708692;font-size:.72rem}.pill,.task-card>span{width:max-content;padding:.16rem .42rem;border-radius:6px;background:#edf2f5;font-size:.66rem;font-weight:900}.pill.high,.pill.critical,.task-card.alarm>span.high,.task-card.alarm>span.critical{color:#b64029;background:#fff0eb}.state{padding:2.5rem 1rem;color:#708692;text-align:center}.task-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem;padding:.8rem}.task-card{display:grid;gap:.35rem;min-width:0;padding:.8rem;border:1px solid #dce7eb;border-radius:11px;color:#173247;background:#fff;text-align:left;cursor:pointer}.task-card:hover,.task-card:focus{outline:2px solid #83cbd1}.task-card b,.task-card small{overflow-wrap:anywhere}.task-card small{color:#6a808c}.provider-strip{display:flex;gap:.6rem;overflow-x:auto;padding:.7rem}.provider-strip article{display:grid;flex:0 0 230px;padding:.65rem;border-radius:9px;background:#0b3348;color:#e7f5f7}.provider-strip span,.provider-strip small{color:#a8c7d2;font-size:.68rem}.drawer-mask{position:fixed;inset:0;z-index:60;display:flex;justify-content:flex-end;background:rgba(5,25,40,.46);backdrop-filter:blur(2px)}.drawer{width:min(720px,94vw);height:100%;overflow-y:auto;background:#f5f8fa}.drawer-head{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;gap:1rem;padding:1rem 1.2rem;border-bottom:1px solid #d9e5ea;background:#fff}.drawer-head span{color:#14838f;font-size:.7rem;font-weight:800}.drawer-head h2{margin:.2rem 0;overflow-wrap:anywhere}.drawer-head button{border:0;color:#627986;background:transparent;font-size:1.8rem;cursor:pointer}.drawer-body{display:grid;gap:.8rem;padding:1rem}.status-band{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem}.status-band>div{min-width:0;padding:.7rem;border-radius:10px;background:#0b3348;color:#e6f2f5}.status-band span{display:block;color:#a8c7d2;font-size:.65rem}.result-form,.detail-section,.action-section{display:grid;gap:.65rem;padding:.9rem;border-radius:12px;background:#fff}.result-form article{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem;align-items:center}.result-form em{color:#bd432f;font-style:normal;font-size:.65rem}.resolve{display:grid;grid-template-columns:1fr auto;gap:.5rem}.record{display:grid;gap:.25rem;padding:.65rem;border-radius:9px;background:#f2f7f8;font-size:.75rem}
@media(max-width:900px){.metric-grid{grid-template-columns:repeat(2,1fr)}.form-grid{grid-template-columns:repeat(2,1fr)}.task-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.hero,.toolbar{align-items:stretch;flex-direction:column}.metric-grid,.form-grid,.task-grid,.status-band{grid-template-columns:1fr}.tabs{overflow-x:auto}.drawer{width:100%}.result-form article{grid-template-columns:1fr}.resolve{grid-template-columns:1fr}.table{display:block;min-width:0}.table thead{display:none}.table tbody,.table tr,.table td{display:block;width:100%}.table tr{margin:.65rem;padding:.7rem;border:1px solid #dce7eb;border-radius:12px}.table td{display:grid;grid-template-columns:105px minmax(0,1fr);padding:.3rem 0;border:0}.table td::before{content:attr(data-label);color:#718894;font-size:.68rem}}
</style>
