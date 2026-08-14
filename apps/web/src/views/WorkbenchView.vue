<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { http } from "@/api/http";
import type { Envelope, PageResult, WorkbenchSummary } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type Metrics = WorkbenchSummary["metrics"];
type Todo = WorkbenchSummary["recent_todos"][number] & {
  deep_link?: string | null;
};
type Notification = {
  id: number;
  category: string;
  title: string;
  content: string;
  deep_link: string | null;
  status: "UNREAD" | "READ" | "ARCHIVED";
  delivered_at: string;
};
type NotificationPage = PageResult<Notification> & { unread_count: number };
type AutomationHealth = {
  dead_consumers: number;
  retry_consumers: number;
  failed_runs: number;
  active_rules: number;
};
type Widget = {
  widget_key: string;
  title: string;
  required_permission: string;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  visible: boolean;
  config: Record<string, unknown>;
  data: Metrics | PageResult<Todo> | NotificationPage | AutomationHealth | { value: number; deep_link: string } | null;
};
type WidgetDefinition = { widget_key: string; title: string; permission: string };
type WorkbenchLayout = {
  id: number | null;
  name: string;
  source: "USER" | "ROLE" | "SERVER_DEFAULT";
  lock_version: number;
  editable: boolean;
  widgets: Widget[];
  registry: WidgetDefinition[];
};
type RuleVersion = {
  id: number;
  version: number;
  status: string;
  event_type: string;
  priority: number;
  conditions: Array<Record<string, unknown>>;
  actions: Array<Record<string, unknown>>;
  published_at: string | null;
};
type AutomationRule = { id: number; code: string; name: string; status: string; current_version: number; lock_version: number; versions: RuleVersion[] };
type Schedule = { id: number; code: string; name: string; handler_key: string; enabled: boolean; next_run_at: string | null; last_run_at: string | null; lock_version: number };
type SchedulerRun = { id: number; schedule_id: number; status: string; started_at: string; finished_at: string | null };
type EventConsumer = { id: number; generation: number; status: string; attempt_count: number; last_error: string | null };
type BusinessEvent = { id: number; event_type: string; source_type: string; source_id: string; occurred_at: string; consumers: EventConsumer[] };
type EventPage = PageResult<BusinessEvent>;
type RoleLayoutSummary = { role_id: number; role_code: string; role_name: string; layout_id: number | null; layout_name: string | null; priority: number; lock_version: number };
type RoleLayoutDetail = { id: number | null; role_id: number; role_code: string; role_name: string; name: string; priority: number; lock_version: number; widgets: Widget[] };
type Tab = "dashboard" | "notifications" | "automation";

const router = useRouter();
const auth = useAuthStore();
const activeTab = ref<Tab>("dashboard");
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const success = ref("");
const layout = ref<WorkbenchLayout | null>(null);
const legacySummary = ref<WorkbenchSummary | null>(null);
const editing = ref(false);
const draftName = ref("");
const draftWidgets = ref<Widget[]>([]);
const notifications = ref<NotificationPage | null>(null);
const selectedNotificationIds = ref<number[]>([]);
const rules = ref<AutomationRule[]>([]);
const schedules = ref<Schedule[]>([]);
const runs = ref<SchedulerRun[]>([]);
const events = ref<BusinessEvent[]>([]);
const executions = ref<Array<{ id: number; event_id: number; status: string; matched: boolean; error_message: string | null }>>([]);
const roleLayouts = ref<RoleLayoutSummary[]>([]);
const editingRuleId = ref<number | null>(null);
const editingRoleLayout = ref(false);
const ruleForm = reactive({
  code: "",
  name: "",
  event_type: "WORK_ORDER_CREATED",
  action_type: "CREATE_WORK_ITEM",
  title: "处理：${payload.title}",
  content: "${payload.description}",
  deep_link: "${payload.deep_link}",
});
const ruleDraftForm = reactive({
  name: "",
  event_type: "",
  priority: 100,
  conditions_json: "[]",
  actions_json: "[]",
  expected_version: 0,
});
const scheduleForm = reactive({ code: "", name: "", handler_key: "OUTBOX_DISPATCH", cadence_seconds: 60 });
const roleLayoutDraft = reactive({
  role_id: 0,
  role_code: "",
  role_name: "",
  name: "",
  priority: 100,
  lock_version: 0,
  widgets: [] as Widget[],
});

const canNotifications = computed(() => auth.can("notification.read") || auth.can("*"));
const canOperateAutomation = computed(() =>
  ["automation.rule.read", "scheduler.read", "event.read"].some((code) => auth.can(code)) || auth.can("*")
);
const visibleWidgets = computed(() =>
  [...(layout.value?.widgets || [])]
    .filter((widget) => widget.visible)
    .sort((left, right) => left.position_y - right.position_y || left.position_x - right.position_x)
);

function asMetrics(widget: Widget): Metrics {
  return widget.data as Metrics;
}
function asTodoPage(widget: Widget): PageResult<Todo> {
  return widget.data as PageResult<Todo>;
}
function asNotificationPage(widget: Widget): NotificationPage {
  return widget.data as NotificationPage;
}
function asHealth(widget: Widget): AutomationHealth {
  return widget.data as AutomationHealth;
}
function asValue(widget: Widget): { value: number; deep_link: string } {
  return widget.data as { value: number; deep_link: string };
}
function formatDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}
function widgetStyle(widget: Widget) {
  return {
    gridColumn: `${widget.position_x + 1} / span ${widget.width}`,
    gridRow: `${widget.position_y + 1} / span ${widget.height}`,
  };
}
async function follow(deepLink: string | null | undefined) {
  if (deepLink?.startsWith("/")) await router.push(deepLink);
}

async function loadDashboard() {
  try {
    const { data: body } = await http.get<Envelope<WorkbenchLayout>>("/workbench/layout");
    layout.value = body.data;
    legacySummary.value = null;
  } catch {
    const { data: body } = await http.get<Envelope<WorkbenchSummary>>("/workbench/summary");
    legacySummary.value = body.data;
    layout.value = null;
  }
}

async function loadNotifications() {
  if (!canNotifications.value) return;
  const { data: body } = await http.get<Envelope<NotificationPage>>("/notifications", { params: { page_size: 50 } });
  notifications.value = body.data;
  selectedNotificationIds.value = [];
}

async function loadAutomation() {
  const jobs: Array<Promise<void>> = [];
  if (auth.can("automation.rule.read") || auth.can("*")) {
    jobs.push(http.get<Envelope<AutomationRule[]>>("/automation-rules").then(({ data }) => { rules.value = data.data; }));
    jobs.push(http.get<Envelope<typeof executions.value>>("/automation-executions").then(({ data }) => { executions.value = data.data; }));
  }
  if (auth.can("scheduler.read") || auth.can("*")) {
    jobs.push(http.get<Envelope<Schedule[]>>("/scheduler/definitions").then(({ data }) => { schedules.value = data.data; }));
    jobs.push(http.get<Envelope<SchedulerRun[]>>("/scheduler/runs", { params: { limit: 30 } }).then(({ data }) => { runs.value = data.data; }));
  }
  if (auth.can("event.read") || auth.can("*")) {
    jobs.push(http.get<Envelope<EventPage>>("/business-events", { params: { page_size: 30 } }).then(({ data }) => { events.value = data.data.items; }));
  }
  if (auth.can("workbench.layout.admin") || auth.can("*")) {
    jobs.push(http.get<Envelope<RoleLayoutSummary[]>>("/workbench/layout/roles").then(({ data }) => { roleLayouts.value = data.data; }));
  }
  await Promise.all(jobs);
}

async function load() {
  loading.value = true;
  error.value = "";
  success.value = "";
  try {
    await loadDashboard();
    if (canNotifications.value) await loadNotifications();
    if (canOperateAutomation.value) await loadAutomation();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "工作台加载失败";
  } finally {
    loading.value = false;
  }
}

function beginLayoutEdit() {
  if (!layout.value) return;
  draftName.value = layout.value.name;
  const widgets = layout.value.widgets.map((widget) => ({ ...widget, config: { ...widget.config }, data: null }));
  for (const definition of layout.value.registry) {
    if (!widgets.some((widget) => widget.widget_key === definition.widget_key)) {
      widgets.push({
        widget_key: definition.widget_key,
        title: definition.title,
        required_permission: definition.permission,
        position_x: 0,
        position_y: 99,
        width: 4,
        height: 2,
        visible: false,
        config: {},
        data: null,
      });
    }
  }
  draftWidgets.value = widgets;
  editing.value = true;
}

function moveWidget(index: number, offset: number) {
  const target = index + offset;
  if (target < 0 || target >= draftWidgets.value.length) return;
  const next = [...draftWidgets.value];
  [next[index], next[target]] = [next[target], next[index]];
  draftWidgets.value = next;
}

function packWidgets(source: Widget[]) {
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  return source.map((widget) => {
    if (!widget.visible) return { ...widget, position_x: 0, position_y: 99 };
    const width = Math.min(12, Math.max(1, widget.width));
    if (x + width > 12) {
      y += rowHeight;
      x = 0;
      rowHeight = 0;
    }
    const packed = { ...widget, width, position_x: x, position_y: y };
    x += width;
    rowHeight = Math.max(rowHeight, widget.height);
    if (x === 12) {
      y += rowHeight;
      x = 0;
      rowHeight = 0;
    }
    return packed;
  });
}

async function saveLayout() {
  if (!layout.value) return;
  saving.value = true;
  error.value = "";
  try {
    const widgets = packWidgets(draftWidgets.value);
    const { data: body } = await http.put<Envelope<WorkbenchLayout>>("/workbench/layout", {
      expected_version: layout.value.source === "USER" ? layout.value.lock_version : 0,
      name: draftName.value,
      widgets: widgets.map(({ widget_key, position_x, position_y, width, height, visible, config }) => ({
        widget_key, position_x, position_y, width, height, visible, config,
      })),
    });
    layout.value = body.data;
    editing.value = false;
    success.value = "工作台布局已保存";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "布局保存失败";
  } finally {
    saving.value = false;
  }
}

async function resetLayout() {
  saving.value = true;
  error.value = "";
  try {
    const { data: body } = await http.delete<Envelope<WorkbenchLayout>>("/workbench/layout");
    layout.value = body.data;
    editing.value = false;
    success.value = "已恢复角色或系统默认布局";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "布局重置失败";
  } finally {
    saving.value = false;
  }
}

async function markNotification(row: Notification, archive = false) {
  await http.post(`/notifications/${row.id}/${archive ? "archive" : "read"}`);
  await Promise.all([loadNotifications(), loadDashboard()]);
}

async function bulkRead() {
  if (!selectedNotificationIds.value.length) return;
  await http.post("/notifications/bulk-read", { ids: selectedNotificationIds.value });
  await Promise.all([loadNotifications(), loadDashboard()]);
  success.value = "选中消息已标记为已读";
}

async function createRule() {
  saving.value = true;
  error.value = "";
  try {
    const action = ruleForm.action_type === "CREATE_NOTIFICATION"
      ? { type: "CREATE_NOTIFICATION", title: ruleForm.title, content: ruleForm.content, recipient_user_id: auth.userId, deep_link: ruleForm.deep_link }
      : { type: "CREATE_WORK_ITEM", title: ruleForm.title, item_type: "AUTOMATION", priority: "MEDIUM", assignee_user_id: auth.userId, deep_link: ruleForm.deep_link };
    await http.post("/automation-rules", {
      code: ruleForm.code,
      name: ruleForm.name,
      event_type: ruleForm.event_type,
      conditions: [],
      actions: [action],
    });
    Object.assign(ruleForm, { code: "", name: "" });
    await loadAutomation();
    success.value = "自动化规则草稿已创建，发布后生效";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "规则创建失败";
  } finally {
    saving.value = false;
  }
}

async function ruleCommand(rule: AutomationRule, command: "publish" | "draft" | "retire") {
  error.value = "";
  try {
    await http.post(`/automation-rules/${rule.id}/${command}`, { expected_version: rule.lock_version });
    await loadAutomation();
    success.value = command === "publish" ? "规则已发布" : command === "draft" ? "新草稿已创建" : "规则已停用";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "规则操作失败";
  }
}

function beginRuleDraftEdit(rule: AutomationRule) {
  const draft = rule.versions.find((item) => item.status === "DRAFT");
  if (!draft) return;
  editingRuleId.value = rule.id;
  Object.assign(ruleDraftForm, {
    name: rule.name,
    event_type: draft.event_type,
    priority: draft.priority,
    conditions_json: JSON.stringify(draft.conditions, null, 2),
    actions_json: JSON.stringify(draft.actions, null, 2),
    expected_version: rule.lock_version,
  });
}

async function saveRuleDraft() {
  if (!editingRuleId.value) return;
  saving.value = true;
  error.value = "";
  try {
    const conditions = JSON.parse(ruleDraftForm.conditions_json) as unknown;
    const actions = JSON.parse(ruleDraftForm.actions_json) as unknown;
    if (!Array.isArray(conditions) || !Array.isArray(actions)) throw new Error("条件与动作必须是 JSON 数组");
    await http.put(`/automation-rules/${editingRuleId.value}/draft`, {
      expected_version: ruleDraftForm.expected_version,
      name: ruleDraftForm.name,
      event_type: ruleDraftForm.event_type,
      priority: ruleDraftForm.priority,
      conditions,
      actions,
    });
    editingRuleId.value = null;
    await loadAutomation();
    success.value = "规则草稿已保存，发布前不会生效";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "规则草稿保存失败";
  } finally {
    saving.value = false;
  }
}

async function createSchedule() {
  saving.value = true;
  error.value = "";
  try {
    const parameters = scheduleForm.handler_key === "OUTBOX_DISPATCH" ? { limit: 100 }
      : scheduleForm.handler_key === "LEASE_TODO_SYNC" ? { within_days: 90 } : { limit: 200 };
    await http.post("/scheduler/definitions", { ...scheduleForm, parameters, enabled: false, concurrency_policy: "FORBID" });
    Object.assign(scheduleForm, { code: "", name: "" });
    await loadAutomation();
    success.value = "调度定义已创建（默认停用）";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "调度创建失败";
  } finally {
    saving.value = false;
  }
}

async function runSchedule(row: Schedule) {
  await http.post(`/scheduler/definitions/${row.id}/run`, { idempotency_key: `manual:${row.id}:${Date.now()}` });
  await loadAutomation();
  success.value = "调度执行完成";
}

async function toggleSchedule(row: Schedule) {
  error.value = "";
  try {
    await http.put(`/scheduler/definitions/${row.id}`, {
      expected_version: row.lock_version,
      enabled: !row.enabled,
    });
    await loadAutomation();
    success.value = row.enabled ? "调度已停用" : "调度已启用";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "调度状态更新失败";
  }
}

async function replayConsumer(consumer: EventConsumer) {
  const reason = window.prompt("请输入死信重放原因（至少 5 个字符）", "修复依赖后由管理员重放")?.trim();
  if (!reason) return;
  if (reason.length < 5) {
    error.value = "死信重放原因至少 5 个字符";
    return;
  }
  error.value = "";
  try {
    await http.post(`/event-consumers/${consumer.id}/replay`, { reason });
    await loadAutomation();
    success.value = `消费记录 #${consumer.id} 已创建新一代重放`;
  } catch (reasonValue) {
    error.value = reasonValue instanceof Error ? reasonValue.message : "死信重放失败";
  }
}

async function beginRoleLayoutEdit(role: RoleLayoutSummary) {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<RoleLayoutDetail>>(`/workbench/layout/roles/${role.role_id}`);
    const detail = data.data;
    Object.assign(roleLayoutDraft, {
      role_id: detail.role_id,
      role_code: detail.role_code,
      role_name: detail.role_name,
      name: detail.name,
      priority: detail.priority,
      lock_version: detail.lock_version,
      widgets: detail.widgets.map((widget) => ({ ...widget, config: { ...widget.config }, data: null })),
    });
    editingRoleLayout.value = true;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "角色默认布局读取失败";
  }
}

function moveRoleWidget(index: number, offset: number) {
  const target = index + offset;
  if (target < 0 || target >= roleLayoutDraft.widgets.length) return;
  const next = [...roleLayoutDraft.widgets];
  [next[index], next[target]] = [next[target], next[index]];
  roleLayoutDraft.widgets = next;
}

async function saveRoleLayout() {
  saving.value = true;
  error.value = "";
  try {
    const widgets = packWidgets(roleLayoutDraft.widgets);
    await http.put(`/workbench/layout/roles/${roleLayoutDraft.role_id}`, {
      role_id: roleLayoutDraft.role_id,
      expected_version: roleLayoutDraft.lock_version,
      name: roleLayoutDraft.name,
      priority: roleLayoutDraft.priority,
      widgets: widgets.map(({ widget_key, position_x, position_y, width, height, visible, config }) => ({
        widget_key, position_x, position_y, width, height, visible, config,
      })),
    });
    editingRoleLayout.value = false;
    await Promise.all([loadAutomation(), loadDashboard()]);
    success.value = `${roleLayoutDraft.role_name} 的默认布局已保存`;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "角色默认布局保存失败";
  } finally {
    saving.value = false;
  }
}

async function operate(path: string, message: string) {
  await http.post(path);
  await Promise.all([loadAutomation(), loadDashboard()]);
  success.value = message;
}

onMounted(load);
</script>

<template>
  <section class="workbench-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">UNIFIED OPERATIONS</p>
        <h1 data-testid="workbench-title">运营工作台</h1>
        <p class="muted">实时指标、自动待办、站内消息与任务调度使用同一套租户和园区权限。</p>
      </div>
      <div class="head-actions">
        <button v-if="layout?.editable && activeTab === 'dashboard'" class="btn btn-ghost" type="button" data-testid="layout-edit" @click="beginLayoutEdit">配置首页</button>
        <button class="btn" type="button" data-testid="workbench-refresh" :disabled="loading" @click="load">刷新</button>
      </div>
    </header>

    <nav class="tabs card" aria-label="工作台分类" data-testid="workbench-tabs">
      <button :class="{ active: activeTab === 'dashboard' }" type="button" data-testid="workbench-tab-dashboard" @click="activeTab = 'dashboard'">我的工作台</button>
      <button v-if="canNotifications" :class="{ active: activeTab === 'notifications' }" type="button" data-testid="workbench-tab-notifications" @click="activeTab = 'notifications'">消息中心 <span v-if="notifications?.unread_count" class="count">{{ notifications.unread_count }}</span></button>
      <button v-if="canOperateAutomation" :class="{ active: activeTab === 'automation' }" type="button" data-testid="workbench-tab-automation" @click="activeTab = 'automation'">自动化运维</button>
    </nav>

    <p v-if="success" class="notice success" data-testid="workbench-success">{{ success }}</p>
    <div v-if="loading" class="state card" data-testid="workbench-loading"><span class="spinner"></span><b>正在读取实时工作台</b><small>布局和组件数据均来自当前租户数据库</small></div>
    <div v-else-if="error" class="state card error-state" data-testid="workbench-error"><b>工作台暂时不可用</b><span>{{ error }}</span><button class="btn" type="button" @click="load">重试</button></div>

    <template v-else-if="activeTab === 'dashboard'">
      <div v-if="layout" class="layout-meta"><span>{{ layout.name }}</span><span>来源：{{ layout.source }} · 版本 {{ layout.lock_version }}</span></div>
      <div v-if="layout && visibleWidgets.length" class="widget-grid" data-testid="workbench-metrics">
        <article v-for="widget in visibleWidgets" :key="widget.widget_key" class="widget card" :class="`widget-${widget.widget_key.toLowerCase()}`" :style="widgetStyle(widget)" :data-testid="`widget-${widget.widget_key.toLowerCase()}`">
          <header><div><p class="widget-code">{{ widget.widget_key }}</p><h2>{{ widget.title }}</h2></div><span class="live-dot">实时</span></header>
          <div v-if="widget.widget_key === 'OPERATIONS_METRICS'" class="grid-metrics">
            <button type="button" @click="router.push('/todos')"><span>开放待办</span><strong data-testid="metric-open-todos">{{ asMetrics(widget).open_todos }}</strong></button>
            <button type="button" @click="router.push('/todos')"><span>逾期风险</span><strong data-testid="metric-overdue-todos">{{ asMetrics(widget).overdue_todos }}</strong></button>
            <button type="button" @click="router.push('/todos')"><span>7 日内到期</span><strong data-testid="metric-due-soon">{{ asMetrics(widget).due_soon_todos }}</strong></button>
            <button type="button" @click="router.push('/bills')"><span>未结账单</span><strong data-testid="metric-unpaid-bills">{{ asMetrics(widget).unpaid_bills }}</strong></button>
            <button type="button" @click="router.push('/leases')"><span>到期合同</span><strong data-testid="metric-expiring">{{ asMetrics(widget).expiring_contracts }}</strong></button>
          </div>
          <div v-else-if="widget.widget_key === 'MY_TODOS'" class="table-wrap">
            <table class="table" data-testid="workbench-todo-table"><thead><tr><th>任务</th><th>优先级</th><th>截止</th><th></th></tr></thead><tbody>
              <tr v-for="todo in asTodoPage(widget).items" :key="todo.id" :data-testid="`wb-todo-${todo.id}`"><td><b>{{ todo.title }}</b><small>{{ todo.item_type }}</small></td><td><span class="badge">{{ todo.priority }}</span></td><td>{{ formatDate(todo.due_at) }}</td><td><button class="text-button" type="button" @click="follow(todo.deep_link || '/todos')">处理</button></td></tr>
              <tr v-if="!asTodoPage(widget).items.length"><td colspan="4" class="empty-cell">当前没有开放待办</td></tr>
            </tbody></table>
          </div>
          <div v-else-if="widget.widget_key === 'NOTIFICATIONS'" class="notification-list">
            <button v-for="note in asNotificationPage(widget).items" :key="note.id" type="button" :class="{ unread: note.status === 'UNREAD' }" @click="follow(note.deep_link)"><b>{{ note.title }}</b><span>{{ note.content }}</span><small>{{ formatDate(note.delivered_at) }}</small></button>
            <p v-if="!asNotificationPage(widget).items.length" class="empty-copy">暂无站内消息</p>
          </div>
          <dl v-else-if="widget.widget_key === 'AUTOMATION_HEALTH'" class="health-grid"><div><dt>死信</dt><dd :class="{ danger: asHealth(widget).dead_consumers }">{{ asHealth(widget).dead_consumers }}</dd></div><div><dt>重试</dt><dd>{{ asHealth(widget).retry_consumers }}</dd></div><div><dt>失败任务</dt><dd :class="{ danger: asHealth(widget).failed_runs }">{{ asHealth(widget).failed_runs }}</dd></div><div><dt>生效规则</dt><dd>{{ asHealth(widget).active_rules }}</dd></div></dl>
          <button v-else class="signal-card" type="button" @click="follow(asValue(widget).deep_link)"><strong>{{ asValue(widget).value }}</strong><span>查看原始记录并下钻</span></button>
        </article>
      </div>
      <div v-else-if="legacySummary" class="grid-metrics card legacy" data-testid="workbench-metrics"><div><span>开放待办</span><strong data-testid="metric-open-todos">{{ legacySummary.metrics.open_todos }}</strong></div><div><span>逾期</span><strong>{{ legacySummary.metrics.overdue_todos }}</strong></div><div><span>未结账单</span><strong>{{ legacySummary.metrics.unpaid_bills }}</strong></div></div>
      <div v-else class="state card"><b>没有可见组件</b><span>当前角色尚未配置任何具有权限的工作台组件。</span><button v-if="layout?.editable" class="btn" type="button" @click="beginLayoutEdit">配置首页</button></div>
    </template>

    <section v-else-if="activeTab === 'notifications'" class="panel card" data-testid="notification-center">
      <header class="section-head"><div><p class="eyebrow">IN-APP INBOX</p><h2>消息中心</h2></div><button class="btn btn-ghost" type="button" :disabled="!selectedNotificationIds.length" data-testid="notification-bulk-read" @click="bulkRead">批量已读</button></header>
      <div v-if="notifications?.items.length" class="inbox-list"><article v-for="note in notifications.items" :key="note.id" :class="{ unread: note.status === 'UNREAD' }" :data-testid="`notification-${note.id}`"><input v-if="note.status !== 'ARCHIVED'" v-model="selectedNotificationIds" type="checkbox" :value="note.id" :aria-label="`选择消息 ${note.title}`" /><div><span class="badge">{{ note.category }}</span><h3>{{ note.title }}</h3><p>{{ note.content }}</p><small>{{ formatDate(note.delivered_at) }}</small></div><div class="row-actions"><button v-if="note.status === 'UNREAD'" type="button" @click="markNotification(note)">已读</button><button v-if="note.status !== 'ARCHIVED'" type="button" @click="markNotification(note, true)">归档</button><button v-if="note.deep_link" type="button" @click="follow(note.deep_link)">前往处理</button></div></article></div>
      <div v-else class="state compact"><b>消息已清空</b><span>规则生成的站内消息会出现在这里。</span></div>
    </section>

    <section v-else class="automation-space" data-testid="automation-ops">
      <div class="ops-actions card"><div><p class="eyebrow">CONTROL PLANE</p><h2>自动化控制面</h2><p>所有手工触发均保留审计和幂等记录。</p></div><div><button v-if="auth.can('event.dispatch') || auth.can('*')" class="btn" type="button" data-testid="dispatch-events" @click="operate('/business-events/dispatch', '事件分发完成')">分发事件</button><button v-if="auth.can('scheduler.run') || auth.can('*')" class="btn btn-ghost" type="button" @click="operate('/scheduler/poll', '到期任务轮询完成')">轮询任务</button><button v-if="auth.can('scheduler.run') || auth.can('*')" class="btn btn-ghost" type="button" @click="operate('/scheduler/recover', '超时任务恢复检查完成')">恢复超时</button></div></div>

      <div class="ops-grid">
        <section v-if="auth.can('automation.rule.read') || auth.can('*')" class="panel card">
          <header class="section-head"><h2>规则治理</h2><span>{{ rules.length }} 条</span></header>
          <form v-if="auth.can('automation.rule.write') || auth.can('*')" class="compact-form" data-testid="rule-create-form" @submit.prevent="createRule"><input v-model.trim="ruleForm.code" class="input" required pattern="[A-Z][A-Z0-9_]+" placeholder="规则编码" /><input v-model.trim="ruleForm.name" class="input" required placeholder="规则名称" /><select v-model="ruleForm.event_type" class="input"><option>WORK_ORDER_CREATED</option><option>BILL_ISSUED</option><option>LEASE_ACTIVATED</option><option>LEAD_CREATED</option><option>APPROVAL_TASK_OVERDUE</option><option>TEST_AUTOMATION_EVENT</option></select><select v-model="ruleForm.action_type" class="input"><option value="CREATE_WORK_ITEM">创建待办</option><option value="CREATE_NOTIFICATION">创建站内消息</option></select><input v-model.trim="ruleForm.title" class="input span-two" required placeholder="标题模板" /><input v-if="ruleForm.action_type === 'CREATE_NOTIFICATION'" v-model.trim="ruleForm.content" class="input span-two" required placeholder="消息内容模板" /><button class="btn span-two" type="submit" :disabled="saving">创建安全草稿</button></form>
          <div class="rule-list"><article v-for="rule in rules" :key="rule.id" :data-testid="`automation-rule-${rule.id}`"><div><b>{{ rule.name }}</b><span>{{ rule.code }} · v{{ rule.current_version || '草稿' }} · {{ rule.status }}</span><details><summary>版本与动作</summary><div v-for="version in rule.versions" :key="version.id" class="version-line"><b>v{{ version.version }} · {{ version.status }}</b><span>{{ version.event_type }} · 优先级 {{ version.priority }} · {{ version.actions.map((item) => item.type).join(' / ') }}</span></div></details></div><div class="row-actions"><button v-if="rule.versions.some((v) => v.status === 'DRAFT') && (auth.can('automation.rule.write') || auth.can('*'))" type="button" @click="beginRuleDraftEdit(rule)">编辑草稿</button><button v-if="rule.versions.some((v) => v.status === 'DRAFT') && (auth.can('automation.rule.write') || auth.can('*'))" type="button" @click="ruleCommand(rule, 'publish')">发布</button><button v-else-if="rule.status !== 'RETIRED' && (auth.can('automation.rule.write') || auth.can('*'))" type="button" @click="ruleCommand(rule, 'draft')">新草稿</button><button v-if="rule.status !== 'RETIRED' && (auth.can('automation.rule.write') || auth.can('*'))" type="button" class="danger-text" @click="ruleCommand(rule, 'retire')">停用</button></div></article><p v-if="!rules.length" class="empty-copy">尚未创建规则。</p></div>
        </section>

        <section v-if="auth.can('scheduler.read') || auth.can('*')" class="panel card"><header class="section-head"><h2>调度定义</h2><span>{{ schedules.length }} 项</span></header><form v-if="auth.can('scheduler.write') || auth.can('*')" class="compact-form" data-testid="schedule-create-form" @submit.prevent="createSchedule"><input v-model.trim="scheduleForm.code" class="input" required pattern="[A-Z][A-Z0-9_]+" placeholder="调度编码" /><input v-model.trim="scheduleForm.name" class="input" required placeholder="调度名称" /><select v-model="scheduleForm.handler_key" class="input"><option>OUTBOX_DISPATCH</option><option>LEASE_TODO_SYNC</option><option>APPROVAL_OVERDUE_SWEEP</option></select><input v-model.number="scheduleForm.cadence_seconds" class="input" type="number" min="10" max="2678400" /><button class="btn span-two" type="submit" :disabled="saving">创建停用定义</button></form><div class="rule-list"><article v-for="schedule in schedules" :key="schedule.id" :data-testid="`schedule-${schedule.id}`"><div><b>{{ schedule.name }}</b><span>{{ schedule.handler_key }} · {{ schedule.enabled ? '启用' : '停用' }} · 下次 {{ formatDate(schedule.next_run_at) }}</span></div><div class="row-actions"><button v-if="auth.can('scheduler.write') || auth.can('*')" type="button" @click="toggleSchedule(schedule)">{{ schedule.enabled ? '停用' : '启用' }}</button><button v-if="auth.can('scheduler.run') || auth.can('*')" type="button" @click="runSchedule(schedule)">立即运行</button></div></article><p v-if="!schedules.length" class="empty-copy">尚未创建调度定义。</p></div></section>

        <section v-if="auth.can('event.read') || auth.can('*')" class="panel card"><header class="section-head"><h2>事件与投递</h2><span>最近 {{ events.length }}</span></header><div class="audit-list"><article v-for="event in events" :key="event.id"><b>{{ event.event_type }}</b><span>{{ event.source_type }}#{{ event.source_id }}</span><div v-for="consumer in event.consumers" :key="consumer.id" class="consumer-line"><small :class="{ danger: consumer.status === 'DEAD' }">投递 #{{ consumer.id }} · 第 {{ consumer.generation }} 代 · {{ consumer.status }} · 尝试 {{ consumer.attempt_count }} 次<span v-if="consumer.last_error"> · {{ consumer.last_error }}</span></small><button v-if="consumer.status === 'DEAD' && (auth.can('event.replay') || auth.can('*'))" type="button" @click="replayConsumer(consumer)">受控重放</button></div><small v-if="!event.consumers.length">{{ formatDate(event.occurred_at) }} · 待分发</small></article><p v-if="!events.length" class="empty-copy">尚无业务事件。</p></div></section>

        <section v-if="auth.can('workbench.layout.admin') || auth.can('*')" class="panel card" data-testid="role-layout-admin"><header class="section-head"><h2>角色默认首页</h2><span>{{ roleLayouts.length }} 个角色</span></header><p class="muted">个人布局优先于角色默认；角色默认不会放大组件或数据权限。</p><div class="rule-list"><article v-for="role in roleLayouts" :key="role.role_id"><div><b>{{ role.role_name }}</b><span>{{ role.role_code }} · {{ role.layout_name || '使用服务器默认' }} · v{{ role.lock_version }}</span></div><button type="button" @click="beginRoleLayoutEdit(role)">配置</button></article><p v-if="!roleLayouts.length" class="empty-copy">当前租户没有可配置的活动角色。</p></div></section>

        <section v-if="auth.can('automation.rule.read') || auth.can('*')" class="panel card"><header class="section-head"><h2>执行与任务记录</h2><span>{{ executions.length }} 次规则 / {{ runs.length }} 次任务</span></header><div class="audit-list"><article v-for="execution in executions.slice(0, 12)" :key="`e-${execution.id}`"><b>规则执行 #{{ execution.id }}</b><span>事件 #{{ execution.event_id }} · {{ execution.matched ? '命中' : '未命中' }}</span><small :class="{ danger: execution.status === 'FAILED' }">{{ execution.status }} {{ execution.error_message || '' }}</small></article><article v-for="run in runs.slice(0, 12)" :key="`r-${run.id}`"><b>调度运行 #{{ run.id }}</b><span>定义 #{{ run.schedule_id }}</span><small :class="{ danger: run.status === 'FAILED' || run.status === 'TIMED_OUT' }">{{ run.status }} · {{ formatDate(run.started_at) }}</small></article><p v-if="!executions.length && !runs.length" class="empty-copy">尚无执行记录。</p></div></section>
      </div>
    </section>

    <aside v-if="editing" class="layout-drawer card" data-testid="layout-drawer" aria-label="首页组件配置">
      <header><div><p class="eyebrow">PERSONAL LAYOUT</p><h2>配置首页组件</h2></div><button class="close" type="button" aria-label="关闭" @click="editing = false">×</button></header>
      <label>布局名称<input v-model.trim="draftName" class="input" maxlength="128" /></label>
      <p class="muted">启用、排序后保存；服务端会重新检查权限、网格冲突和版本。</p>
      <div class="layout-items"><article v-for="(widget, index) in draftWidgets" :key="widget.widget_key"><label><input v-model="widget.visible" type="checkbox" /> <b>{{ widget.title }}</b><span>{{ widget.widget_key }}</span></label><div><button type="button" :disabled="index === 0" @click="moveWidget(index, -1)">↑</button><button type="button" :disabled="index === draftWidgets.length - 1" @click="moveWidget(index, 1)">↓</button></div></article></div>
      <footer><button class="btn btn-ghost" type="button" :disabled="saving" data-testid="layout-reset" @click="resetLayout">恢复默认</button><button class="btn" type="button" :disabled="saving || !draftName" data-testid="layout-save" @click="saveLayout">保存布局</button></footer>
    </aside>

    <aside v-if="editingRuleId" class="layout-drawer card" data-testid="rule-draft-drawer" aria-label="规则草稿编辑">
      <header><div><p class="eyebrow">VERSIONED RULE</p><h2>编辑规则草稿</h2></div><button class="close" type="button" aria-label="关闭" @click="editingRuleId = null">×</button></header>
      <label>规则名称<input v-model.trim="ruleDraftForm.name" class="input" maxlength="128" /></label>
      <label>事件类型<input v-model.trim="ruleDraftForm.event_type" class="input" readonly /></label>
      <label>优先级<input v-model.number="ruleDraftForm.priority" class="input" type="number" min="0" max="1000" /></label>
      <label>条件 JSON<textarea v-model="ruleDraftForm.conditions_json" class="input code-editor" rows="7"></textarea></label>
      <label>动作 JSON<textarea v-model="ruleDraftForm.actions_json" class="input code-editor" rows="12"></textarea></label>
      <p class="muted">仅允许注册字段、比较符和动作；服务端会再次拒绝密钥、外链、脚本及未注册字段。</p>
      <footer><button class="btn btn-ghost" type="button" @click="editingRuleId = null">取消</button><button class="btn" type="button" :disabled="saving || !ruleDraftForm.name" @click="saveRuleDraft">保存草稿</button></footer>
    </aside>

    <aside v-if="editingRoleLayout" class="layout-drawer card" data-testid="role-layout-drawer" aria-label="角色默认首页配置">
      <header><div><p class="eyebrow">ROLE DEFAULT</p><h2>{{ roleLayoutDraft.role_name }}</h2><span>{{ roleLayoutDraft.role_code }} · v{{ roleLayoutDraft.lock_version }}</span></div><button class="close" type="button" aria-label="关闭" @click="editingRoleLayout = false">×</button></header>
      <label>布局名称<input v-model.trim="roleLayoutDraft.name" class="input" maxlength="128" /></label>
      <label>优先级（越小越优先）<input v-model.number="roleLayoutDraft.priority" class="input" type="number" min="0" max="1000" /></label>
      <div class="layout-items"><article v-for="(widget, index) in roleLayoutDraft.widgets" :key="widget.widget_key"><label><input v-model="widget.visible" type="checkbox" /> <b>{{ widget.title || widget.widget_key }}</b><span>{{ widget.widget_key }}</span></label><div><button type="button" :disabled="index === 0" @click="moveRoleWidget(index, -1)">↑</button><button type="button" :disabled="index === roleLayoutDraft.widgets.length - 1" @click="moveRoleWidget(index, 1)">↓</button></div></article></div>
      <footer><button class="btn btn-ghost" type="button" @click="editingRoleLayout = false">取消</button><button class="btn" type="button" :disabled="saving || !roleLayoutDraft.name" data-testid="role-layout-save" @click="saveRoleLayout">保存角色默认</button></footer>
    </aside>
  </section>
</template>

<style scoped>
.workbench-page { min-width: 0; }
.page-head, .section-head, .ops-actions, .layout-drawer > header, .layout-drawer footer { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.page-head { margin-bottom: .8rem; }
.page-head h1, h2, h3, p { margin-top: 0; }
.page-head h1 { margin-bottom: .2rem; font-size: clamp(1.5rem, 2vw, 2.1rem); }
.eyebrow, .widget-code { margin: 0 0 .2rem; color: #157f91; font-size: .68rem; font-weight: 900; letter-spacing: .14em; }
.head-actions, .ops-actions > div:last-child, .row-actions { display: flex; flex-wrap: wrap; gap: .45rem; }
.tabs { display: flex; gap: .25rem; margin-bottom: 1rem; padding: .35rem; overflow-x: auto; }
.tabs button { border: 0; border-radius: 9px; padding: .55rem .85rem; background: transparent; color: var(--muted); white-space: nowrap; cursor: pointer; }
.tabs button.active { background: #dff3f5; color: #0f6776; font-weight: 800; }
.count { display: inline-grid; min-width: 1.25rem; height: 1.25rem; place-items: center; margin-left: .25rem; border-radius: 99px; background: #e35d35; color: #fff; font-size: .68rem; }
.notice { padding: .65rem .85rem; border-radius: 10px; }.success { background: #e5f6ef; color: #08654e; }.error-state { color: var(--danger); }
.state { min-height: 250px; display: grid; place-content: center; justify-items: center; gap: .6rem; padding: 2rem; text-align: center; }.state.compact { min-height: 150px; }.state small, .state span { color: var(--muted); }
.spinner { width: 1.8rem; height: 1.8rem; border: 3px solid #d8e5e7; border-top-color: #157f91; border-radius: 50%; animation: spin .8s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
.layout-meta { display: flex; justify-content: space-between; gap: 1rem; margin: 0 .2rem .65rem; color: var(--muted); font-size: .78rem; }
.layout-meta span:first-child { color: var(--text); font-weight: 800; }
.widget-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); grid-auto-rows: minmax(48px, auto); gap: .8rem; }
.widget { min-width: 0; padding: 1rem; overflow: hidden; }
.widget > header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: .7rem; }.widget h2 { margin: 0; font-size: 1rem; }.live-dot { color: #0f8064; font-size: .68rem; }.live-dot::before { content: ''; display: inline-block; width: 6px; height: 6px; margin-right: .3rem; border-radius: 50%; background: #1bb887; }
.grid-metrics { display: grid; grid-template-columns: repeat(5, minmax(110px, 1fr)); gap: .55rem; }.grid-metrics button, .legacy > div { display: grid; gap: .2rem; border: 0; border-radius: 11px; padding: .75rem; background: #f3f7f8; color: var(--text); text-align: left; cursor: pointer; }.grid-metrics button:nth-child(2) { background: #fff1eb; }.grid-metrics span { color: var(--muted); font-size: .74rem; }.grid-metrics strong { color: #123d4a; font-size: 1.45rem; }
.table-wrap { overflow-x: auto; }.table { min-width: 560px; }.table td b, .table td small { display: block; }.table td small { color: var(--muted); font-size: .7rem; }.text-button, .row-actions button, .rule-list article > button { border: 0; background: transparent; color: #0f7586; cursor: pointer; }.empty-cell, .empty-copy { padding: 1rem; color: var(--muted); text-align: center; }
.notification-list { display: grid; gap: .4rem; }.notification-list button { display: grid; gap: .12rem; border: 0; border-left: 3px solid transparent; border-radius: 8px; padding: .55rem; background: #f7f9fa; text-align: left; cursor: pointer; }.notification-list button.unread { border-left-color: #e35d35; background: #fff8f4; }.notification-list span, .notification-list small { overflow: hidden; color: var(--muted); font-size: .7rem; text-overflow: ellipsis; white-space: nowrap; }
.health-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: 0; }.health-grid div { padding: .6rem; border-radius: 8px; background: #f3f7f8; }.health-grid dt { color: var(--muted); font-size: .7rem; }.health-grid dd { margin: 0; color: #125a68; font-size: 1.3rem; font-weight: 900; }.danger { color: #c44728 !important; }
.signal-card { width: 100%; display: grid; justify-items: start; border: 0; border-radius: 10px; padding: 1rem; background: linear-gradient(135deg, #112f42, #155f70); color: #fff; cursor: pointer; }.signal-card strong { font-size: 2rem; }.signal-card span { color: #b9e5ea; font-size: .75rem; }
.legacy { padding: 1rem; }
.panel { min-width: 0; padding: 1rem; }.section-head h2 { margin: 0; }.section-head > span { color: var(--muted); font-size: .75rem; }
.inbox-list { display: grid; gap: .55rem; margin-top: 1rem; }.inbox-list article { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: .8rem; align-items: start; padding: .85rem; border: 1px solid var(--border); border-radius: 10px; }.inbox-list article.unread { border-color: #efaa91; background: #fff9f6; }.inbox-list h3 { margin: .3rem 0 .1rem; }.inbox-list p { margin: 0 0 .2rem; color: var(--muted); }.inbox-list small { color: var(--muted); }
.automation-space { display: grid; gap: .8rem; }.ops-actions { padding: 1rem; background: linear-gradient(135deg, #0e2a3c, #164c5d); color: #fff; }.ops-actions p { margin-bottom: 0; color: #bad9df; }.ops-actions .btn-ghost { border-color: #8fcbd4; color: #d9f4f7; }.ops-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }
.compact-form { display: grid; grid-template-columns: 1fr 1fr; gap: .45rem; padding: .75rem 0; border-bottom: 1px solid var(--border); }.span-two { grid-column: 1 / -1; }.rule-list, .audit-list { display: grid; gap: .4rem; margin-top: .65rem; }.rule-list article { display: flex; justify-content: space-between; gap: .6rem; padding: .65rem; border-radius: 8px; background: #f6f8f9; }.rule-list article > div:first-child, .audit-list article { display: grid; }.rule-list span, .audit-list span, .audit-list small { color: var(--muted); font-size: .72rem; }.rule-list details { margin-top: .3rem; }.rule-list summary { color: #0f7586; font-size: .7rem; cursor: pointer; }.version-line { display: grid; gap: .1rem; margin-top: .25rem; padding-left: .5rem; border-left: 2px solid #b8dfe4; }.consumer-line { display: flex; align-items: center; justify-content: space-between; gap: .45rem; margin-top: .2rem; }.consumer-line button { flex: 0 0 auto; border: 1px solid #c44728; border-radius: 6px; background: #fff; color: #a9361d; cursor: pointer; }.danger-text { color: #bd3d24 !important; }
.layout-drawer { position: fixed; z-index: 50; top: 1rem; right: 1rem; bottom: 1rem; width: min(440px, calc(100vw - 2rem)); overflow-y: auto; padding: 1rem; box-shadow: 0 25px 70px rgba(5, 24, 35, .28); }.layout-drawer h2 { margin: 0; }.layout-drawer .close { border: 0; background: transparent; font-size: 1.7rem; cursor: pointer; }.layout-drawer > label { display: grid; gap: .3rem; margin: 1rem 0; }.layout-items { display: grid; gap: .45rem; margin: .8rem 0; }.layout-items article { display: flex; justify-content: space-between; gap: .6rem; align-items: center; padding: .7rem; border-radius: 9px; background: #f5f8f8; }.layout-items label { display: grid; grid-template-columns: auto 1fr; gap: .1rem .45rem; align-items: center; }.layout-items label span { grid-column: 2; color: var(--muted); font-size: .66rem; }.layout-items article > div { display: flex; gap: .25rem; }.layout-items button { width: 2rem; border: 1px solid var(--border); border-radius: 6px; background: #fff; cursor: pointer; }
.code-editor { min-height: 8rem; resize: vertical; font-family: ui-monospace, Consolas, monospace; font-size: .72rem; }
@media (max-width: 1180px) { .widget-grid { display: grid; grid-template-columns: 1fr 1fr; }.widget { grid-column: auto !important; grid-row: auto !important; }.widget-operations_metrics, .widget-my_todos { grid-column: 1 / -1 !important; }.ops-grid { grid-template-columns: 1fr; } }
@media (max-width: 720px) { .page-head, .ops-actions { align-items: stretch; flex-direction: column; }.head-actions .btn, .ops-actions .btn { flex: 1; }.widget-grid { grid-template-columns: 1fr; }.widget { grid-column: auto !important; }.grid-metrics { grid-template-columns: 1fr 1fr; }.grid-metrics button:last-child { grid-column: 1 / -1; }.layout-meta { flex-direction: column; gap: .15rem; }.inbox-list article { grid-template-columns: auto 1fr; }.inbox-list .row-actions { grid-column: 2; }.compact-form { grid-template-columns: 1fr; }.span-two { grid-column: auto; } }
</style>
