<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ApiRequestError, http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

type Park = { id: number; name: string };
type Assignee = { id: number; username: string; real_name: string };
type Activity = {
  id: number;
  activity_type: string;
  content: string | null;
  occurred_at: string;
  next_follow_up_at: string | null;
  stage_from: string | null;
  stage_to: string | null;
};
type Assignment = {
  id: number;
  event_type: string;
  from_owner_user_id: number | null;
  to_owner_user_id: number | null;
  reason: string | null;
  occurred_at: string;
  rule_version_id: number | null;
  trigger: string | null;
  decision: Record<string, unknown>;
};
type UnitLock = {
  id: number;
  lead_id: number;
  unit_id: number;
  lease_id: number | null;
  status: string;
  expires_at: string;
  released_at: string | null;
  consumed_at: string | null;
  lock_version: number;
  intent_application_id: number | null;
  intent_version_id: number | null;
};
type Viewing = {
  id: number;
  lead_id: number;
  owner_user_id: number;
  status: string;
  starts_at: string;
  ends_at: string;
  visitor_name: string | null;
  visitor_count: number;
  outcome: string | null;
  cancellation_reason: string | null;
  lock_version: number;
  units: Array<{ unit_id: number; unit_version: number }>;
};
type IntentVersion = {
  id: number;
  version: number;
  starts_on: string;
  ends_on: string;
  valid_until: string;
  proposed_unit_price: string;
  currency: string;
  checksum: string;
  units: Array<{ unit_id: number; unit_version: number; requested_area: string }>;
};
type LeadIntent = {
  id: number;
  lead_id: number;
  status: string;
  current_version: number;
  approval_request_id: number | null;
  approval_deep_link: string | null;
  lock_version: number;
  versions: IntentVersion[];
};
type AssignmentRule = {
  id: number;
  park_id: number;
  code: string;
  name: string;
  trigger: string;
  status: string;
  current_version: number;
  lock_version: number;
};
type ChannelEvent = {
  id: number;
  status: string;
  external_event_id: string;
  failure_code: string | null;
  lead_id: number | null;
  replay_count: number;
};
type LeadChannel = {
  id: number;
  park_id: number;
  code: string;
  name: string;
  public_id: string;
  enabled: boolean;
  secret_env_key: string;
  secret_configured: boolean;
  verification_status: string;
  lock_version: number;
  events?: ChannelEvent[];
};
type Lead = {
  id: number;
  park_id: number;
  name: string;
  contact_phone: string;
  contact_name: string | null;
  status: string;
  intent_level: string | null;
  intent_area: string | null;
  desired_usage: string | null;
  budget_unit_price: string | null;
  source_type: string;
  source_ref: string | null;
  pool_status: string;
  owner_user_id: number | null;
  remark: string | null;
  next_follow_up_at: string | null;
  overdue: boolean;
  lock_version: number;
  public_summary: boolean;
  party_id: number | null;
  lease_id: number | null;
  lost_reason: string | null;
  created_at: string | null;
};
type LeadDetail = Lead & {
  activities: Activity[];
  assignment_events: Assignment[];
  merged_sources: number[];
  unit_locks: UnitLock[];
};
type Summary = {
  counts: {
    total: number;
    new: number;
    open: number;
    won: number;
    lost: number;
    public: number;
    overdue: number;
  };
  conversion_rate: number;
  average_first_follow_seconds: number | null;
  stage_counts: Record<string, number>;
};
type BoardColumn = { status: string; count: number; items: Lead[] };
type Board = { total: number; columns: BoardColumn[] };
type DuplicateCandidate = {
  id: number;
  park_id: number;
  name: string;
  contact_phone: string;
  status: string;
  reasons: string[];
};
type UnitMatch = {
  unit_id: number;
  code: string;
  name: string;
  usage_type: string;
  rentable_area: string;
  base_rent_price: string;
  score: number;
  score_breakdown: Record<string, { score: number; max: number; reason: string }>;
};
type DialogKind =
  | "create"
  | "activity"
  | "assign"
  | "merge"
  | "lose"
  | "convert"
  | "viewing"
  | "viewing-complete"
  | "intent"
  | "intent-submit"
  | "rule"
  | "channel"
  | null;

const STAGES = ["NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING", "WON", "LOST", "CANCELLED"];
const OPEN_STAGES = new Set(["NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING"]);
const auth = useAuthStore();
const parks = ref<Park[]>([]);
const assignees = ref<Assignee[]>([]);
const items = ref<Lead[]>([]);
const board = ref<Board>({ total: 0, columns: [] });
const summary = ref<Summary | null>(null);
const selected = ref<LeadDetail | null>(null);
const unitMatches = ref<UnitMatch[]>([]);
const viewings = ref<Viewing[]>([]);
const selectedIntent = ref<LeadIntent | null>(null);
const selectedViewing = ref<Viewing | null>(null);
const assignmentRules = ref<AssignmentRule[]>([]);
const channels = ref<LeadChannel[]>([]);
const duplicates = ref<DuplicateCandidate[]>([]);
const dialog = ref<DialogKind>(null);
const viewMode = ref<"board" | "list">("board");
const loading = ref(false);
const saving = ref(false);
const detailLoading = ref(false);
const error = ref("");
const success = ref("");
const now = ref(Date.now());

const filters = reactive({
  park_id: "",
  status: "",
  owner_user_id: "",
  pool_status: "",
  source_type: "",
  keyword: "",
  created_from: "",
  created_to: "",
});
const createForm = reactive({
  park_id: "",
  name: "",
  contact_phone: "",
  contact_name: "",
  intent_level: "HIGH",
  intent_area: "",
  desired_usage: "FACTORY",
  budget_unit_price: "",
  source_type: "MANUAL",
  source_ref: "",
  pool_status: "PRIVATE",
  owner_user_id: "",
  duplicate_override_reason: "",
});
const activityForm = reactive({
  activity_type: "CALL",
  content: "",
  next_follow_up_at: "",
  stage_to: "",
});
const assignForm = reactive({ owner_user_id: "", reason: "" });
const mergeForm = reactive({ target_lead_id: "", reason: "" });
const loseForm = reactive({ reason: "" });
const convertForm = reactive({
  with_lease: false,
  unit_id: "",
  start_date: "",
  end_date: "",
  occupied_area: "",
  unit_rent_price: "",
  deposit_amount: "",
});
const viewingForm = reactive({
  unit_id: "",
  starts_at: "",
  ends_at: "",
  visitor_name: "",
  visitor_count: "1",
  outcome: "",
  next_follow_up_at: "",
});
const intentForm = reactive({
  unit_id: "",
  requested_area: "",
  starts_on: "",
  ends_on: "",
  valid_until: "",
  proposed_unit_price: "",
  remark: "",
});
const intentSubmitForm = reactive({ definition_code: "LEAD_INTENT_DEFAULT", remark: "" });
const ruleForm = reactive({
  park_id: "",
  code: "",
  name: "",
  trigger: "MANUAL_CREATE",
  user_id: "",
  capacity: "100",
  recycle_after_hours: "72",
});
const channelForm = reactive({
  park_id: "",
  code: "",
  name: "",
  secret_env_key: "",
  enabled: false,
  allow_auto_assign: true,
});

const canManage = computed(() => auth.can("lead:manage") || auth.can("*"));
const canWrite = computed(() => auth.can("lead:write") || auth.can("*"));
const canClaim = computed(() => auth.can("lead:claim") || auth.can("*"));
const canLock = computed(() => auth.can("lead:lock") || auth.can("*"));
const canConvert = computed(() => auth.can("lead:convert") || auth.can("*"));
const canViewViewings = computed(() => auth.can("lead.viewing.read") || auth.can("*"));
const canWriteViewings = computed(() => auth.can("lead.viewing.write") || auth.can("*"));
const canViewIntent = computed(() => auth.can("lead.intent.read") || auth.can("*"));
const canWriteIntent = computed(() => auth.can("lead.intent.write") || auth.can("*"));
const canSubmitIntent = computed(() => auth.can("lead.intent.submit") || auth.can("*"));
const canManageRules = computed(() => auth.can("lead.assignment_rule.write") || auth.can("*"));
const canManageChannels = computed(() => auth.can("lead.channel.write") || auth.can("*"));
const approvedIntent = computed(() =>
  selectedIntent.value?.status === "APPROVED" ? selectedIntent.value : null
);
const activeLocks = computed(() =>
  (selected.value?.unit_locks || []).filter((row) => row.status === "ACTIVE")
);
const mergeTargets = computed(() =>
  items.value.filter(
    (row) =>
      selected.value &&
      row.id !== selected.value.id &&
      row.park_id === selected.value.park_id &&
      OPEN_STAGES.has(row.status)
  )
);

function failure(reason: unknown, fallback = "请求失败，请稍后重试") {
  error.value = reason instanceof Error ? reason.message : fallback;
}

function queryParams() {
  return {
    park_id: filters.park_id ? Number(filters.park_id) : undefined,
    status: filters.status || undefined,
    owner_user_id: filters.owner_user_id ? Number(filters.owner_user_id) : undefined,
    pool_status: filters.pool_status || undefined,
    source_type: filters.source_type || undefined,
    keyword: filters.keyword.trim() || undefined,
    created_from: filters.created_from || undefined,
    created_to: filters.created_to || undefined,
  };
}

async function loadSelectors() {
  const parkResponse = await http.get<Envelope<PageResult<Park>>>("/parks", {
    params: { page_size: 200 },
  });
  parks.value = parkResponse.data.data.items;
  if (!filters.park_id && parks.value.length) filters.park_id = String(parks.value[0].id);
  if (!createForm.park_id && parks.value.length) createForm.park_id = String(parks.value[0].id);
  if (!ruleForm.park_id && parks.value.length) ruleForm.park_id = String(parks.value[0].id);
  if (!channelForm.park_id && parks.value.length) channelForm.park_id = String(parks.value[0].id);
  if (canManage.value) {
    const users = await http.get<Envelope<Assignee[]>>("/crm/assignees");
    assignees.value = users.data.data;
    if (!ruleForm.user_id && assignees.value.length) {
      ruleForm.user_id = String(assignees.value[0].id);
    }
  }
  await loadGovernance();
}

async function loadGovernance() {
  const requests: Promise<unknown>[] = [];
  if (auth.can("lead.assignment_rule.read") || auth.can("*")) {
    requests.push(
      http.get<Envelope<AssignmentRule[]>>("/crm/assignment-rules").then((response) => {
        assignmentRules.value = response.data.data;
      })
    );
  }
  if (auth.can("lead.channel.read") || auth.can("*")) {
    requests.push(
      http.get<Envelope<LeadChannel[]>>("/crm/channels").then((response) => {
        channels.value = response.data.data;
      })
    );
  }
  await Promise.all(requests);
}

async function loadWorkspace() {
  loading.value = true;
  error.value = "";
  try {
    const params = queryParams();
    const [listResponse, boardResponse, summaryResponse] = await Promise.all([
      http.get<Envelope<PageResult<Lead>>>("/leads", {
        params: { ...params, page: 1, page_size: 200 },
      }),
      http.get<Envelope<Board>>("/crm/board", { params }),
      http.get<Envelope<Summary>>("/crm/summary", { params }),
    ]);
    items.value = listResponse.data.data.items;
    board.value = boardResponse.data.data;
    summary.value = summaryResponse.data.data;
    if (selected.value && !items.value.some((row) => row.id === selected.value?.id)) {
      selected.value = null;
      unitMatches.value = [];
    }
  } catch (reason) {
    failure(reason, "招商工作台加载失败");
  } finally {
    loading.value = false;
  }
}

async function refreshAll(detailId?: number) {
  await loadWorkspace();
  if (detailId) await openDetail(detailId);
}

async function openDetail(id: number) {
  detailLoading.value = true;
  error.value = "";
  unitMatches.value = [];
  try {
    const response = await http.get<Envelope<LeadDetail>>(`/leads/${id}`);
    selected.value = response.data.data;
    const related: Promise<unknown>[] = [];
    viewings.value = [];
    selectedIntent.value = null;
    if (canViewViewings.value) {
      related.push(
        http.get<Envelope<Viewing[]>>(`/leads/${id}/viewings`).then((item) => {
          viewings.value = item.data.data;
        })
      );
    }
    if (canViewIntent.value) {
      related.push(
        http.get<Envelope<LeadIntent | null>>(`/leads/${id}/intent`).then((item) => {
          selectedIntent.value = item.data.data;
        })
      );
    }
    await Promise.all(related);
  } catch (reason) {
    failure(reason, "线索详情加载失败");
  } finally {
    detailLoading.value = false;
  }
}

function openCreate() {
  duplicates.value = [];
  createForm.duplicate_override_reason = "";
  dialog.value = "create";
}

async function createLead() {
  saving.value = true;
  error.value = "";
  try {
    const response = await http.post<Envelope<Lead>>("/leads", {
      park_id: Number(createForm.park_id),
      name: createForm.name.trim(),
      contact_phone: createForm.contact_phone.trim(),
      contact_name: createForm.contact_name.trim() || undefined,
      intent_level: createForm.intent_level || undefined,
      intent_area: createForm.intent_area || undefined,
      desired_usage: createForm.desired_usage || undefined,
      budget_unit_price: createForm.budget_unit_price || undefined,
      source_type: createForm.source_type,
      source_ref: createForm.source_ref.trim() || undefined,
      pool_status: createForm.pool_status,
      owner_user_id: createForm.owner_user_id ? Number(createForm.owner_user_id) : undefined,
      duplicate_override_reason: createForm.duplicate_override_reason.trim() || undefined,
    });
    const created = response.data.data;
    success.value = "线索已创建";
    dialog.value = null;
    createForm.name = "";
    createForm.contact_phone = "";
    createForm.contact_name = "";
    createForm.source_ref = "";
    duplicates.value = [];
    await refreshAll(created.id);
  } catch (reason) {
    if (reason instanceof ApiRequestError && reason.code === "LEAD_DUPLICATE") {
      const payload = reason.data as { candidates?: DuplicateCandidate[] } | null;
      duplicates.value = payload?.candidates || [];
      error.value = "发现重复候选。核实后填写覆盖理由，或打开候选详情。";
    } else {
      failure(reason, "创建失败");
    }
  } finally {
    saving.value = false;
  }
}

function openActivity() {
  if (!selected.value) return;
  activityForm.activity_type = "CALL";
  activityForm.content = "";
  activityForm.next_follow_up_at = "";
  activityForm.stage_to = selected.value.status;
  dialog.value = "activity";
}

async function addActivity() {
  if (!selected.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/activities`, {
        expected_version: selected.value?.lock_version,
        activity_type: activityForm.activity_type,
        content: activityForm.content,
        next_follow_up_at: activityForm.next_follow_up_at || undefined,
        stage_to:
          activityForm.stage_to && activityForm.stage_to !== selected.value?.status
            ? activityForm.stage_to
            : undefined,
      }),
    "跟进活动已记录",
    id
  );
}

function openAssign() {
  if (!selected.value) return;
  assignForm.owner_user_id = selected.value.owner_user_id
    ? String(selected.value.owner_user_id)
    : assignees.value[0]
      ? String(assignees.value[0].id)
      : "";
  assignForm.reason = "";
  dialog.value = "assign";
}

async function assignLead() {
  if (!selected.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/assign`, {
        expected_version: selected.value?.lock_version,
        owner_user_id: Number(assignForm.owner_user_id),
        reason: assignForm.reason || undefined,
      }),
    "负责人已更新",
    id
  );
}

async function claimLead(row: Lead) {
  await mutate(
    () => http.post(`/leads/${row.id}/claim`, { expected_version: row.lock_version }),
    "公海线索已领取",
    row.id
  );
}

async function releaseLead() {
  if (!selected.value || !window.confirm("确认将该线索释放到公海？")) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/release`, {
        expected_version: selected.value?.lock_version,
        reason: "人工释放到公海",
      }),
    "线索已释放到公海",
    id
  );
}

function openMerge() {
  mergeForm.target_lead_id = mergeTargets.value[0] ? String(mergeTargets.value[0].id) : "";
  mergeForm.reason = "";
  dialog.value = "merge";
}

async function mergeLead() {
  if (!selected.value) return;
  const target = mergeTargets.value.find((row) => row.id === Number(mergeForm.target_lead_id));
  if (!target) return;
  const sourceId = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${sourceId}/merge`, {
        expected_version: selected.value?.lock_version,
        target_lead_id: target.id,
        target_expected_version: target.lock_version,
        reason: mergeForm.reason,
      }),
    "重复线索已合并",
    target.id
  );
}

function openLose() {
  loseForm.reason = "";
  dialog.value = "lose";
}

async function loseLead() {
  if (!selected.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/lose`, {
        expected_version: selected.value?.lock_version,
        reason: loseForm.reason,
      }),
    "线索已标记输单",
    id
  );
}

async function loadUnitMatches() {
  if (!selected.value) return;
  detailLoading.value = true;
  error.value = "";
  try {
    const response = await http.get<Envelope<{ items: UnitMatch[] }>>(
      `/leads/${selected.value.id}/unit-matches`
    );
    unitMatches.value = response.data.data.items;
  } catch (reason) {
    failure(reason, "房源匹配失败");
  } finally {
    detailLoading.value = false;
  }
}

async function lockUnit(unitId: number) {
  if (!selected.value) return;
  if (!approvedIntent.value) {
    error.value = "锁房前须创建意向并完成审批。";
    return;
  }
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/unit-locks`, {
        expected_version: selected.value?.lock_version,
        unit_id: unitId,
        intent_id: approvedIntent.value?.id,
        duration_hours: 48,
      }),
    "房源已锁定 48 小时",
    id
  );
  unitMatches.value = [];
}

async function releaseLock(lock: UnitLock) {
  if (!selected.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/unit-locks/${lock.id}/release`, {
        expected_version: lock.lock_version,
      }),
    "房源锁已释放",
    id
  );
}

async function renewLock(lock: UnitLock) {
  if (!selected.value) return;
  if (!lock.intent_application_id || selectedIntent.value?.status !== "APPROVED") {
    error.value = "当前批准意向无效，不能续期房源锁。";
    return;
  }
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/unit-locks/${lock.id}/renew`, {
        expected_version: lock.lock_version,
        duration_hours: 48,
        intent_id: lock.intent_application_id,
      }),
    "房源锁已续期 48 小时",
    id
  );
}

function openViewing() {
  if (!selected.value) return;
  const match = unitMatches.value[0];
  viewingForm.unit_id = match ? String(match.unit_id) : "";
  viewingForm.starts_at = "";
  viewingForm.ends_at = "";
  viewingForm.visitor_name = selected.value.contact_name || "";
  viewingForm.visitor_count = "1";
  dialog.value = "viewing";
}

async function createViewing() {
  if (!selected.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/viewings`, {
        starts_at: viewingForm.starts_at,
        ends_at: viewingForm.ends_at,
        unit_ids: [Number(viewingForm.unit_id)],
        visitor_name: viewingForm.visitor_name.trim() || undefined,
        visitor_count: Number(viewingForm.visitor_count),
      }),
    "带看已排期",
    id
  );
}

async function transitionViewing(viewing: Viewing, status: string) {
  if (!selected.value) return;
  if (status === "COMPLETED") {
    selectedViewing.value = viewing;
    viewingForm.outcome = "";
    viewingForm.next_follow_up_at = "";
    dialog.value = "viewing-complete";
    return;
  }
  await mutate(
    () =>
      http.post(`/crm/viewings/${viewing.id}/transition`, {
        expected_version: viewing.lock_version,
        status,
        reason: status === "CANCELLED" || status === "NO_SHOW" ? "现场状态确认" : undefined,
      }),
    status === "CONFIRMED" ? "带看已确认" : "带看状态已更新",
    selected.value.id
  );
}

async function completeViewing() {
  if (!selected.value || !selectedViewing.value) return;
  const idempotencyKey = `viewing-${selectedViewing.value.id}-${Date.now()}`;
  await mutate(
    () =>
      http.post(`/crm/viewings/${selectedViewing.value?.id}/transition`, {
        expected_version: selectedViewing.value?.lock_version,
        status: "COMPLETED",
        outcome: viewingForm.outcome,
        next_follow_up_at: viewingForm.next_follow_up_at || undefined,
        idempotency_key: idempotencyKey,
      }),
    "带看结果已归档到活动时间线",
    selected.value.id
  );
}

function openIntent(unitId?: number) {
  if (!selected.value) return;
  const match = unitMatches.value.find((row) => row.unit_id === unitId) || unitMatches.value[0];
  intentForm.unit_id = match ? String(match.unit_id) : "";
  intentForm.requested_area = selected.value.intent_area || match?.rentable_area || "";
  intentForm.proposed_unit_price = selected.value.budget_unit_price || match?.base_rent_price || "";
  intentForm.starts_on = "";
  intentForm.ends_on = "";
  intentForm.valid_until = "";
  intentForm.remark = "";
  dialog.value = "intent";
}

async function createIntent() {
  if (!selected.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/intent`, {
        starts_on: intentForm.starts_on,
        ends_on: intentForm.ends_on,
        valid_until: intentForm.valid_until,
        proposed_unit_price: intentForm.proposed_unit_price,
        currency: "CNY",
        remark: intentForm.remark || undefined,
        units: [
          {
            unit_id: Number(intentForm.unit_id),
            requested_area: intentForm.requested_area,
          },
        ],
      }),
    "意向草稿已创建",
    id
  );
}

function openIntentSubmit() {
  intentSubmitForm.definition_code = "LEAD_INTENT_DEFAULT";
  intentSubmitForm.remark = "";
  dialog.value = "intent-submit";
}

async function submitIntent() {
  if (!selected.value || !selectedIntent.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/crm/intents/${selectedIntent.value?.id}/submit`, {
        expected_version: selectedIntent.value?.lock_version,
        definition_code: intentSubmitForm.definition_code,
        idempotency_key: `intent-${selectedIntent.value?.id}-${Date.now()}`,
        priority: "HIGH",
        remark: intentSubmitForm.remark || undefined,
      }),
    "意向已提交审批",
    id
  );
}

function openRule() {
  ruleForm.code = "";
  ruleForm.name = "";
  dialog.value = "rule";
}

async function createRule() {
  await mutate(
    () =>
      http.post("/crm/assignment-rules", {
        park_id: Number(ruleForm.park_id),
        code: ruleForm.code.trim().toUpperCase(),
        name: ruleForm.name.trim(),
        trigger: ruleForm.trigger,
        recycle_after_hours: Number(ruleForm.recycle_after_hours),
        members: [
          {
            user_id: Number(ruleForm.user_id),
            capacity: Number(ruleForm.capacity),
            weight: 1,
            member_order: 1,
          },
        ],
      }),
    "分配规则草稿已创建"
  );
  await loadGovernance();
}

async function publishRule(rule: AssignmentRule) {
  await mutate(
    () =>
      http.post(`/crm/assignment-rules/${rule.id}/publish`, {
        expected_lock_version: rule.lock_version,
      }),
    "分配规则已发布"
  );
  await loadGovernance();
}

function openChannel() {
  channelForm.code = "";
  channelForm.name = "";
  channelForm.secret_env_key = "";
  channelForm.enabled = false;
  dialog.value = "channel";
}

async function createChannel() {
  await mutate(
    () =>
      http.post("/crm/channels", {
        park_id: Number(channelForm.park_id),
        code: channelForm.code.trim().toUpperCase(),
        name: channelForm.name.trim(),
        secret_env_key: channelForm.secret_env_key.trim().toUpperCase(),
        enabled: channelForm.enabled,
        allow_auto_assign: channelForm.allow_auto_assign,
      }),
    "渠道配置已创建"
  );
  await loadGovernance();
}

async function replayChannelEvent(channel: LeadChannel, event: ChannelEvent) {
  await mutate(
    () => http.post(`/crm/channels/${channel.id}/events/${event.id}/replay`),
    "隔离事件已安全重放"
  );
  const detail = await http.get<Envelope<LeadChannel>>(`/crm/channels/${channel.id}`);
  channel.events = detail.data.data.events || [];
}

async function loadChannelEvents(channel: LeadChannel) {
  try {
    const detail = await http.get<Envelope<LeadChannel>>(`/crm/channels/${channel.id}`);
    channel.events = detail.data.data.events || [];
  } catch (reason) {
    failure(reason, "渠道接收箱加载失败");
  }
}

function openConvert() {
  const lock = activeLocks.value[0];
  convertForm.with_lease = Boolean(lock);
  convertForm.unit_id = lock ? String(lock.unit_id) : "";
  convertForm.start_date = "";
  convertForm.end_date = "";
  convertForm.occupied_area = selected.value?.intent_area || "";
  convertForm.unit_rent_price = selected.value?.budget_unit_price || "";
  convertForm.deposit_amount = "0";
  dialog.value = "convert";
}

async function convertLead() {
  if (!selected.value) return;
  const id = selected.value.id;
  await mutate(
    () =>
      http.post(`/leads/${id}/convert`, {
        expected_version: selected.value?.lock_version,
        unit_ids: convertForm.with_lease ? [Number(convertForm.unit_id)] : [],
        start_date: convertForm.with_lease ? convertForm.start_date : undefined,
        end_date: convertForm.with_lease ? convertForm.end_date : undefined,
        occupied_area: convertForm.with_lease ? convertForm.occupied_area : undefined,
        unit_rent_price: convertForm.with_lease ? convertForm.unit_rent_price : undefined,
        deposit_amount: convertForm.with_lease ? convertForm.deposit_amount : undefined,
      }),
    convertForm.with_lease ? "主体与合同草稿已原子创建" : "主体已创建",
    id
  );
}

async function mutate<T>(action: () => Promise<T>, message: string, detailId?: number) {
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const result = await action();
    dialog.value = null;
    success.value = message;
    await refreshAll(detailId);
    return result;
  } catch (reason) {
    if (reason instanceof ApiRequestError && reason.status === 409) {
      const conflictMessage = `${reason.message}。数据已刷新，请确认当前状态后重试。`;
      if (detailId) await refreshAll(detailId);
      error.value = conflictMessage;
    } else {
      failure(reason);
    }
    return null;
  } finally {
    saving.value = false;
  }
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function ownerName(id: number | null) {
  if (!id) return "公海";
  const row = assignees.value.find((user) => user.id === id);
  if (row) return row.real_name || row.username;
  if (id === auth.userId && auth.realName) return auth.realName;
  return `用户 ${id}`;
}

function stageLabel(stage: string) {
  return (
    {
      NEW: "新线索",
      CONTACTING: "联系中",
      VISITING: "已带看",
      QUOTING: "报价中",
      NEGOTIATING: "谈判中",
      WON: "已转化",
      LOST: "已输单",
      CANCELLED: "已取消",
      MERGED: "已合并",
    } as Record<string, string>
  )[stage] || stage;
}

function lockCountdown(lock: UnitLock) {
  const remaining = Math.max(0, new Date(lock.expires_at).getTime() - now.value);
  const hours = Math.floor(remaining / 3_600_000);
  const minutes = Math.floor((remaining % 3_600_000) / 60_000);
  return remaining ? `${hours}小时${minutes}分` : "已到期，等待释放";
}

const ticker = window.setInterval(() => (now.value = Date.now()), 30_000);
onBeforeUnmount(() => window.clearInterval(ticker));

onMounted(async () => {
  loading.value = true;
  try {
    await loadSelectors();
    await loadWorkspace();
  } catch (reason) {
    failure(reason, "招商工作台初始化失败");
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="crm-page" data-testid="crm-page" @keydown.esc="dialog = null">
    <header class="page-head">
      <div>
        <p class="eyebrow">INVESTMENT CRM</p>
        <h1 data-testid="leads-title">招商机会工作台</h1>
        <p class="muted">从线索治理、跟进推进到房源锁定和合同草稿，保持一条可追溯业务链。</p>
      </div>
      <div class="head-actions">
        <button class="btn btn-ghost" type="button" data-testid="lead-refresh" @click="loadWorkspace">刷新</button>
        <button v-if="canWrite" class="btn" type="button" data-testid="lead-create-open" @click="openCreate">＋ 新建线索</button>
      </div>
    </header>

    <p v-if="error" class="notice notice-error" role="alert" data-testid="lead-error">{{ error }}</p>
    <p v-if="success" class="notice notice-success" role="status" data-testid="lead-success">{{ success }}</p>

    <div v-if="summary" class="metric-strip" aria-label="招商指标" data-testid="crm-summary">
      <article><span>当前线索</span><strong>{{ summary.counts.total }}</strong><small>条</small></article>
      <article><span>开放机会</span><strong>{{ summary.counts.open }}</strong><small>条</small></article>
      <article><span>已转化</span><strong>{{ summary.counts.won }}</strong><small>{{ (summary.conversion_rate * 100).toFixed(1) }}%</small></article>
      <article><span>公海待领</span><strong>{{ summary.counts.public }}</strong><small>条</small></article>
      <article :class="{ warning: summary.counts.overdue > 0 }"><span>跟进逾期</span><strong>{{ summary.counts.overdue }}</strong><small>条</small></article>
      <article><span>平均首跟</span><strong>{{ summary.average_first_follow_seconds == null ? "—" : (summary.average_first_follow_seconds / 3600).toFixed(1) }}</strong><small>小时</small></article>
    </div>

    <div v-if="assignmentRules.length || channels.length || canManageRules || canManageChannels" class="governance-grid">
      <details v-if="auth.can('lead.assignment_rule.read') || auth.can('*')" class="card governance-card" data-testid="assignment-rule-panel">
        <summary><span><strong>自动分配规则</strong><small>已发布版本决定创建、渠道和回收归属</small></span><b>{{ assignmentRules.length }}</b></summary>
        <div class="governance-actions"><button v-if="canManageRules" class="btn btn-quiet" type="button" data-testid="assignment-rule-create" @click="openRule">新建规则</button><button class="text-btn" type="button" @click="loadGovernance">刷新</button></div>
        <div v-for="rule in assignmentRules" :key="rule.id" class="governance-row">
          <div><strong>{{ rule.name }}</strong><span>{{ rule.trigger }} · v{{ rule.current_version || '草稿' }}</span></div>
          <span class="status-pill">{{ rule.status }}</span>
          <button v-if="canManageRules && !rule.current_version" class="text-btn" type="button" @click="publishRule(rule)">发布</button>
        </div>
        <p v-if="!assignmentRules.length" class="mini-empty">暂无配置；无规则时沿用人工归属，不伪造自动分配。</p>
      </details>
      <details v-if="auth.can('lead.channel.read') || auth.can('*')" class="card governance-card" data-testid="lead-channel-panel">
        <summary><span><strong>渠道接收与隔离箱</strong><small>HMAC 验证、幂等接收和加密重放</small></span><b>{{ channels.length }}</b></summary>
        <div class="governance-actions"><button v-if="canManageChannels" class="btn btn-quiet" type="button" data-testid="lead-channel-create" @click="openChannel">配置渠道</button><button class="text-btn" type="button" @click="loadGovernance">刷新</button></div>
        <div v-for="channel in channels" :key="channel.id" class="channel-block">
          <div class="governance-row"><div><strong>{{ channel.name }}</strong><span>{{ channel.code }} · {{ channel.verification_status }}</span></div><span class="status-pill" :class="{ 'stage-lost': !channel.enabled }">{{ channel.enabled ? '已启用' : '默认关闭' }}</span><button class="text-btn" type="button" @click="loadChannelEvents(channel)">接收箱</button></div>
          <div v-if="channel.events?.length" class="channel-events"><div v-for="event in channel.events" :key="event.id"><span>{{ event.external_event_id }}</span><b>{{ event.status }}</b><button v-if="event.status === 'QUARANTINED'" type="button" @click="replayChannelEvent(channel, event)">重放</button></div></div>
        </div>
        <p v-if="!channels.length" class="mini-empty">没有真实渠道连接；此处不会把本地合约验证标记为生产联调。</p>
      </details>
    </div>

    <form class="filters card" aria-label="招商筛选" @submit.prevent="loadWorkspace">
      <label>园区
        <select v-model="filters.park_id" class="input" data-testid="lead-park-filter">
          <option value="">全部授权园区</option>
          <option v-for="park in parks" :key="park.id" :value="String(park.id)">{{ park.name }}</option>
        </select>
      </label>
      <label>阶段
        <select v-model="filters.status" class="input" data-testid="lead-stage-filter">
          <option value="">全部阶段</option>
          <option v-for="stage in STAGES" :key="stage" :value="stage">{{ stageLabel(stage) }}</option>
        </select>
      </label>
      <label>归属
        <select v-model="filters.pool_status" class="input" data-testid="lead-pool-filter">
          <option value="">私有 + 公海</option><option value="PRIVATE">私有</option><option value="PUBLIC">公海</option>
        </select>
      </label>
      <label v-if="canManage">负责人
        <select v-model="filters.owner_user_id" class="input" data-testid="lead-owner-filter">
          <option value="">全部负责人</option>
          <option v-for="user in assignees" :key="user.id" :value="String(user.id)">{{ user.real_name || user.username }}</option>
        </select>
      </label>
      <label>来源
        <select v-model="filters.source_type" class="input"><option value="">全部来源</option><option value="MANUAL">手工</option><option value="IMPORT">导入</option><option value="RADAR">雷达</option></select>
      </label>
      <label class="keyword">搜索
        <input v-model="filters.keyword" class="input" placeholder="企业、联系人或电话" data-testid="lead-keyword" />
      </label>
      <button class="btn filter-submit" type="submit" :disabled="loading" data-testid="lead-filter-btn">{{ loading ? "查询中…" : "应用筛选" }}</button>
    </form>

    <div class="view-toolbar">
      <div><strong>{{ board.total }}</strong><span> 条符合条件</span></div>
      <div class="view-switch" role="group" aria-label="视图切换">
        <button type="button" :aria-pressed="viewMode === 'board'" data-testid="lead-board-view" @click="viewMode = 'board'">阶段看板</button>
        <button type="button" :aria-pressed="viewMode === 'list'" data-testid="lead-list-view" @click="viewMode = 'list'">紧凑列表</button>
      </div>
    </div>

    <div v-if="loading" class="state card"><span class="spinner"></span><strong>正在校准招商数据…</strong></div>
    <div v-else-if="viewMode === 'board'" class="pipeline" data-testid="lead-board">
      <section v-for="column in board.columns" :key="column.status" class="stage-column card" :data-stage="column.status">
        <header><span class="stage-dot"></span><strong>{{ stageLabel(column.status) }}</strong><b>{{ column.count }}</b></header>
        <div class="stage-stack">
          <button
            v-for="row in column.items"
            :key="row.id"
            class="lead-card"
            type="button"
            :class="{ overdue: row.overdue, selected: selected?.id === row.id }"
            :data-testid="`lead-row-${row.id}`"
            @click="openDetail(row.id)"
          >
            <span class="lead-top"><strong data-testid="lead-name-cell">{{ row.name }}</strong><i v-if="row.pool_status === 'PUBLIC'">公海</i></span>
            <span>{{ row.intent_area ? `${row.intent_area} ㎡` : "面积待确认" }} · {{ row.desired_usage || "用途待确认" }}</span>
            <span>{{ ownerName(row.owner_user_id) }} · {{ formatDate(row.next_follow_up_at) }}</span>
            <em v-if="row.overdue">跟进已逾期</em>
          </button>
          <div v-if="!column.items.length" class="mini-empty">本阶段暂无机会</div>
        </div>
      </section>
    </div>

    <div v-else class="card table-wrap" data-testid="lead-table">
      <table class="table">
        <thead><tr><th>客户</th><th>园区</th><th>阶段</th><th>归属</th><th>需求</th><th>下一跟进</th><th>动作</th></tr></thead>
        <tbody>
          <tr v-for="row in items" :key="row.id" :data-testid="`lead-row-${row.id}`">
            <td><button class="link-btn" type="button" data-testid="lead-name-cell" @click="openDetail(row.id)">{{ row.name }}</button><small>{{ row.contact_phone }}</small></td>
            <td>{{ parks.find((park) => park.id === row.park_id)?.name || row.park_id }}</td>
            <td><span class="status-pill" :class="`stage-${row.status.toLowerCase()}`" data-testid="lead-status-cell">{{ stageLabel(row.status) }}</span></td>
            <td>{{ ownerName(row.owner_user_id) }}</td>
            <td>{{ row.intent_area || "—" }} ㎡ / {{ row.desired_usage || "—" }}</td>
            <td :class="{ 'danger-text': row.overdue }">{{ formatDate(row.next_follow_up_at) }}</td>
            <td><button v-if="row.pool_status === 'PUBLIC' && canClaim" class="text-btn" type="button" data-testid="lead-claim-btn" @click="claimLead(row)">领取</button><button class="text-btn" type="button" @click="openDetail(row.id)">详情</button></td>
          </tr>
          <tr v-if="!items.length"><td colspan="7" class="empty-cell">没有符合筛选条件的线索</td></tr>
        </tbody>
      </table>
    </div>

    <aside v-if="selected || detailLoading" class="detail-drawer card" aria-label="线索详情" data-testid="lead-detail">
      <div v-if="detailLoading && !selected" class="state compact"><span class="spinner"></span></div>
      <template v-else-if="selected">
        <header class="drawer-head">
          <div><span>#{{ selected.id }} · {{ parks.find((park) => park.id === selected?.park_id)?.name }}</span><h2>{{ selected.name }}</h2></div>
          <button class="close-btn" type="button" aria-label="关闭详情" @click="selected = null">×</button>
        </header>
        <div class="detail-badges"><span class="status-pill">{{ stageLabel(selected.status) }}</span><span>{{ selected.pool_status === "PUBLIC" ? "公海" : ownerName(selected.owner_user_id) }}</span><span v-if="selected.overdue" class="danger-text">跟进逾期</span></div>
        <dl class="fact-grid">
          <div><dt>联系人</dt><dd>{{ selected.contact_name || "—" }}</dd></div><div><dt>联系电话</dt><dd>{{ selected.contact_phone }}</dd></div>
          <div><dt>意向面积</dt><dd>{{ selected.intent_area || "—" }} ㎡</dd></div><div><dt>预算单价</dt><dd>{{ selected.budget_unit_price || "—" }}</dd></div>
          <div><dt>意向用途</dt><dd>{{ selected.desired_usage || "—" }}</dd></div><div><dt>来源</dt><dd>{{ selected.source_type }}</dd></div>
        </dl>
        <p v-if="selected.remark" class="detail-note">{{ selected.remark }}</p>
        <div class="action-grid">
          <button v-if="selected.pool_status === 'PUBLIC' && canClaim" class="btn" type="button" data-testid="lead-claim-btn" @click="claimLead(selected)">领取线索</button>
          <button v-if="OPEN_STAGES.has(selected.status) && canWrite && selected.pool_status !== 'PUBLIC'" class="btn" type="button" data-testid="lead-activity-open" @click="openActivity">记录跟进</button>
          <button v-if="OPEN_STAGES.has(selected.status) && canConvert && selected.pool_status !== 'PUBLIC'" class="btn btn-dark" type="button" data-testid="lead-convert-btn" @click="openConvert">转化客户</button>
          <button v-if="OPEN_STAGES.has(selected.status) && canWrite && selected.pool_status !== 'PUBLIC'" class="btn btn-quiet" type="button" data-testid="lead-lose-btn" @click="openLose">标记输单</button>
          <button v-if="canManage && OPEN_STAGES.has(selected.status)" class="btn btn-quiet" type="button" data-testid="lead-assign-open" @click="openAssign">分配负责人</button>
          <button v-if="canManage && selected.pool_status === 'PRIVATE' && OPEN_STAGES.has(selected.status)" class="btn btn-quiet" type="button" data-testid="lead-release-btn" @click="releaseLead">释放公海</button>
          <button v-if="canManage && OPEN_STAGES.has(selected.status)" class="btn btn-quiet" type="button" data-testid="lead-merge-open" @click="openMerge">合并重复</button>
        </div>

        <section v-if="canViewViewings" class="detail-section" data-testid="lead-viewings">
          <div class="section-head"><h3>带看计划</h3><button v-if="canWriteViewings && OPEN_STAGES.has(selected.status) && selected.pool_status !== 'PUBLIC'" class="text-btn" type="button" data-testid="viewing-create-open" @click="openViewing">安排带看</button></div>
          <div v-for="viewing in viewings" :key="viewing.id" class="history-row viewing-row">
            <strong>{{ viewing.status }} · {{ viewing.units.map((item) => `#${item.unit_id}`).join(' / ') }}</strong>
            <span>{{ formatDate(viewing.starts_at) }} — {{ formatDate(viewing.ends_at) }}</span>
            <small>{{ viewing.outcome || viewing.cancellation_reason || `访客 ${viewing.visitor_count} 人` }}</small>
            <div v-if="canWriteViewings && ['SCHEDULED', 'CONFIRMED'].includes(viewing.status)" class="row-actions"><button v-if="viewing.status === 'SCHEDULED'" type="button" @click="transitionViewing(viewing, 'CONFIRMED')">确认</button><button v-if="viewing.status === 'CONFIRMED'" type="button" data-testid="viewing-complete-open" @click="transitionViewing(viewing, 'COMPLETED')">完成</button><button type="button" @click="transitionViewing(viewing, 'CANCELLED')">取消</button></div>
          </div>
          <p v-if="!viewings.length" class="mini-empty">尚无带看排期；先加载房源匹配，再安排现场带看。</p>
        </section>

        <section v-if="canViewIntent" class="detail-section" data-testid="lead-intent-panel">
          <div class="section-head"><h3>意向与审批门禁</h3><button v-if="canWriteIntent && !selectedIntent" class="text-btn" type="button" data-testid="intent-create-open" @click="openIntent()">创建意向</button></div>
          <div v-if="selectedIntent" class="intent-card" :class="`intent-${selectedIntent.status.toLowerCase()}`">
            <div><span class="status-pill">{{ selectedIntent.status }}</span><strong>v{{ selectedIntent.current_version }}</strong><small v-if="selectedIntent.versions[0]">有效至 {{ formatDate(selectedIntent.versions[0].valid_until) }}</small></div>
            <p v-if="selectedIntent.versions[0]">{{ selectedIntent.versions[0].units.map((item) => `单元 #${item.unit_id} / ${item.requested_area}㎡`).join('；') }} · ¥{{ selectedIntent.versions[0].proposed_unit_price }}</p>
            <div class="row-actions"><button v-if="canSubmitIntent && selectedIntent.status === 'DRAFT'" type="button" data-testid="intent-submit-open" @click="openIntentSubmit">提交审批</button><a v-if="selectedIntent.approval_request_id" href="/approvals">审批 #{{ selectedIntent.approval_request_id }}</a></div>
          </div>
          <p v-else class="mini-empty">没有意向草稿；房源锁只有在意向审批通过且仍有效时开放。</p>
        </section>

        <section v-if="canLock && OPEN_STAGES.has(selected.status) && selected.pool_status !== 'PUBLIC'" class="detail-section">
          <div class="section-head"><h3>房源机会</h3><button class="text-btn" type="button" data-testid="unit-match-load" @click="loadUnitMatches">解释性匹配</button></div>
          <div v-for="lock in selected.unit_locks" :key="lock.id" class="lock-row" :class="lock.status.toLowerCase()">
            <div><strong>单元 #{{ lock.unit_id }}</strong><span>{{ lock.status === "ACTIVE" ? lockCountdown(lock) : lock.status }}</span></div>
            <div v-if="lock.status === 'ACTIVE'" class="row-actions"><button type="button" @click="renewLock(lock)">续期</button><button type="button" @click="releaseLock(lock)">释放</button></div>
          </div>
          <div v-for="match in unitMatches" :key="match.unit_id" class="match-card" :data-testid="`unit-match-${match.unit_id}`">
            <header><div><strong>{{ match.name }}</strong><span>{{ match.code }} · {{ match.usage_type }}</span></div><b>{{ match.score }}<small>/100</small></b></header>
            <p>{{ match.rentable_area }} ㎡ · ¥{{ match.base_rent_price }}</p>
            <ul><li v-for="part in match.score_breakdown" :key="part.reason">{{ part.reason }}</li></ul>
            <button class="btn btn-quiet" type="button" :disabled="!approvedIntent" :title="approvedIntent ? '使用已批准意向锁房' : '须先通过意向审批'" @click="lockUnit(match.unit_id)">{{ approvedIntent ? '锁定 48 小时' : '审批通过后锁房' }}</button>
          </div>
          <p v-if="!unitMatches.length && !selected.unit_locks.length" class="mini-empty">点击“解释性匹配”查看同园区可租房源。</p>
        </section>

        <section class="detail-section"><h3>活动时间线</h3>
          <ol v-if="selected.activities.length" class="timeline"><li v-for="activity in selected.activities" :key="activity.id"><i></i><div><strong>{{ activity.activity_type }} · {{ activity.content }}</strong><span>{{ formatDate(activity.occurred_at) }}<template v-if="activity.stage_to"> · {{ stageLabel(activity.stage_from || "") }} → {{ stageLabel(activity.stage_to) }}</template></span></div></li></ol>
          <p v-else class="mini-empty">尚无跟进活动。</p>
        </section>
        <section class="detail-section"><h3>归属记录</h3>
          <div v-for="event in selected.assignment_events" :key="event.id" class="history-row"><strong>{{ event.event_type }}<template v-if="event.trigger"> · {{ event.trigger }}</template></strong><span>{{ ownerName(event.from_owner_user_id) }} → {{ ownerName(event.to_owner_user_id) }}</span><small>{{ formatDate(event.occurred_at) }}<template v-if="event.rule_version_id"> · 规则版本 #{{ event.rule_version_id }}</template></small></div>
        </section>
      </template>
    </aside>

    <div v-if="dialog" class="modal-backdrop" role="presentation" @click.self="dialog = null">
      <section class="modal card" role="dialog" aria-modal="true" :aria-label="dialog">
        <header><h2>{{ dialog === "create" ? "新建招商线索" : dialog === "activity" ? "记录跟进活动" : dialog === "assign" ? "分配负责人" : dialog === "merge" ? "合并重复线索" : dialog === "lose" ? "确认输单" : dialog === "viewing" ? "安排带看" : dialog === "viewing-complete" ? "完成带看" : dialog === "intent" ? "创建意向快照" : dialog === "intent-submit" ? "提交意向审批" : dialog === "rule" ? "新建自动分配规则" : dialog === "channel" ? "配置签名渠道" : "转化客户" }}</h2><button class="close-btn" type="button" aria-label="关闭" @click="dialog = null">×</button></header>

        <form v-if="dialog === 'create'" class="modal-form" data-testid="lead-create-form" @submit.prevent="createLead">
          <label>园区<select v-model="createForm.park_id" class="input" data-testid="lead-park-id" required><option v-for="park in parks" :key="park.id" :value="String(park.id)">{{ park.name }}</option></select></label>
          <label>客户/企业名称<input v-model="createForm.name" class="input" data-testid="lead-name" required /></label>
          <label>联系电话<input v-model="createForm.contact_phone" class="input" data-testid="lead-phone" required /></label>
          <label>联系人<input v-model="createForm.contact_name" class="input" /></label>
          <label>意向等级<select v-model="createForm.intent_level" class="input" data-testid="lead-intent"><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></label>
          <label>意向面积（㎡）<input v-model="createForm.intent_area" class="input" type="number" min="0" /></label>
          <label>意向用途<select v-model="createForm.desired_usage" class="input"><option value="FACTORY">厂房</option><option value="OFFICE">办公</option><option value="WAREHOUSE">仓储</option></select></label>
          <label>预算单价<input v-model="createForm.budget_unit_price" class="input" type="number" min="0" /></label>
          <label>来源<select v-model="createForm.source_type" class="input"><option value="MANUAL">手工</option><option value="IMPORT">导入</option><option value="RADAR">雷达</option></select></label>
          <label>来源外部键<input v-model="createForm.source_ref" class="input" /></label>
          <label>初始归属<select v-model="createForm.pool_status" class="input"><option value="PRIVATE">我的私有</option><option value="PUBLIC">进入公海</option></select></label>
          <label v-if="canManage && createForm.pool_status === 'PRIVATE'">负责人<select v-model="createForm.owner_user_id" class="input"><option value="">当前用户</option><option v-for="user in assignees" :key="user.id" :value="String(user.id)">{{ user.real_name || user.username }}</option></select></label>
          <div v-if="duplicates.length" class="duplicate-panel wide" data-testid="lead-duplicate-panel"><strong>发现 {{ duplicates.length }} 条候选</strong><button v-for="candidate in duplicates" :key="candidate.id" type="button" @click="openDetail(candidate.id); dialog = null"><span>{{ candidate.name }} · {{ candidate.contact_phone }}</span><small>{{ candidate.reasons.join(" / ") }} · {{ stageLabel(candidate.status) }}</small></button><label>确认独立机会的覆盖理由<textarea v-model="createForm.duplicate_override_reason" class="input" required data-testid="lead-override-reason"></textarea></label></div>
          <button class="btn modal-submit" type="submit" data-testid="lead-create-btn" :disabled="saving">{{ saving ? "保存中…" : duplicates.length ? "带理由创建" : "创建线索" }}</button>
        </form>

        <form v-else-if="dialog === 'activity'" class="modal-form" @submit.prevent="addActivity">
          <label>活动类型<select v-model="activityForm.activity_type" class="input"><option>CALL</option><option>NOTE</option><option>VISIT</option><option>QUOTE</option><option>NEGOTIATION</option></select></label>
          <label>推进阶段<select v-model="activityForm.stage_to" class="input" data-testid="lead-edit-status"><option v-for="stage in STAGES.slice(0, 5)" :key="stage" :value="stage">{{ stageLabel(stage) }}</option></select></label>
          <label class="wide">跟进内容<textarea v-model="activityForm.content" class="input" data-testid="lead-remark" required></textarea></label>
          <label class="wide">下一跟进时间<input v-model="activityForm.next_follow_up_at" class="input" type="datetime-local" /></label>
          <button class="btn modal-submit" type="submit" data-testid="lead-update-btn" :disabled="saving">保存活动</button>
        </form>

        <form v-else-if="dialog === 'assign'" class="modal-form" @submit.prevent="assignLead"><label class="wide">负责人<select v-model="assignForm.owner_user_id" class="input" required data-testid="lead-assignee"><option v-for="user in assignees" :key="user.id" :value="String(user.id)">{{ user.real_name || user.username }}</option></select></label><label class="wide">分配原因<textarea v-model="assignForm.reason" class="input" data-testid="lead-assign-reason"></textarea></label><button class="btn modal-submit" type="submit" data-testid="lead-assign-submit" :disabled="saving">确认分配</button></form>
        <form v-else-if="dialog === 'merge'" class="modal-form" @submit.prevent="mergeLead"><label class="wide">保留线索<select v-model="mergeForm.target_lead_id" class="input" required data-testid="lead-merge-target"><option v-for="row in mergeTargets" :key="row.id" :value="String(row.id)">#{{ row.id }} {{ row.name }} · {{ stageLabel(row.status) }}</option></select></label><label class="wide">合并原因<textarea v-model="mergeForm.reason" class="input" required data-testid="lead-merge-reason"></textarea></label><p v-if="!mergeTargets.length" class="form-note">当前筛选内没有同园区可合并线索。</p><button class="btn modal-submit" type="submit" data-testid="lead-merge-submit" :disabled="saving || !mergeTargets.length">确认合并</button></form>
        <form v-else-if="dialog === 'lose'" class="modal-form" @submit.prevent="loseLead"><label class="wide">输单原因<textarea v-model="loseForm.reason" class="input" required data-testid="lead-lose-reason"></textarea></label><button class="btn danger-btn modal-submit" type="submit" :disabled="saving">确认输单</button></form>
        <form v-else-if="dialog === 'viewing'" class="modal-form" data-testid="viewing-create-form" @submit.prevent="createViewing"><label class="wide">带看单元<select v-model="viewingForm.unit_id" class="input" required><option value="" disabled>请选择已匹配单元</option><option v-for="match in unitMatches" :key="match.unit_id" :value="String(match.unit_id)">{{ match.name }} · #{{ match.unit_id }}</option></select></label><label>开始时间<input v-model="viewingForm.starts_at" class="input" type="datetime-local" required /></label><label>结束时间<input v-model="viewingForm.ends_at" class="input" type="datetime-local" required /></label><label>访客姓名<input v-model="viewingForm.visitor_name" class="input" /></label><label>访客人数<input v-model="viewingForm.visitor_count" class="input" type="number" min="1" max="100" required /></label><p v-if="!unitMatches.length" class="form-note wide">请先关闭弹窗并点击“解释性匹配”，再安排带看。</p><button class="btn modal-submit" type="submit" :disabled="saving || !unitMatches.length">确认排期</button></form>
        <form v-else-if="dialog === 'viewing-complete'" class="modal-form" @submit.prevent="completeViewing"><label class="wide">带看结果<textarea v-model="viewingForm.outcome" class="input" required data-testid="viewing-outcome"></textarea></label><label class="wide">下一跟进<input v-model="viewingForm.next_follow_up_at" class="input" type="datetime-local" /></label><button class="btn modal-submit" type="submit" :disabled="saving">完成并归档</button></form>
        <form v-else-if="dialog === 'intent'" class="modal-form" data-testid="intent-create-form" @submit.prevent="createIntent"><label class="wide">意向单元<select v-model="intentForm.unit_id" class="input" required><option value="" disabled>请选择已匹配单元</option><option v-for="match in unitMatches" :key="match.unit_id" :value="String(match.unit_id)">{{ match.name }} · #{{ match.unit_id }}</option></select></label><label>申请面积（㎡）<input v-model="intentForm.requested_area" class="input" type="number" min="0.01" step="0.01" required /></label><label>意向单价<input v-model="intentForm.proposed_unit_price" class="input" type="number" min="0" step="0.01" required /></label><label>租期开始<input v-model="intentForm.starts_on" class="input" type="date" required /></label><label>租期结束<input v-model="intentForm.ends_on" class="input" type="date" required /></label><label class="wide">意向有效至<input v-model="intentForm.valid_until" class="input" type="datetime-local" required /></label><label class="wide">说明<textarea v-model="intentForm.remark" class="input"></textarea></label><p v-if="!unitMatches.length" class="form-note wide">请先加载解释性房源匹配。</p><button class="btn modal-submit" type="submit" :disabled="saving || !unitMatches.length">冻结意向版本</button></form>
        <form v-else-if="dialog === 'intent-submit'" class="modal-form" @submit.prevent="submitIntent"><label class="wide">审批定义编码<input v-model="intentSubmitForm.definition_code" class="input" required data-testid="intent-definition-code" /></label><label class="wide">提交说明<textarea v-model="intentSubmitForm.remark" class="input"></textarea></label><p class="form-note wide">提交后商业快照不可修改；审批结论以统一审批中心为准。</p><button class="btn modal-submit" type="submit" :disabled="saving">提交统一审批</button></form>
        <form v-else-if="dialog === 'rule'" class="modal-form" data-testid="assignment-rule-form" @submit.prevent="createRule"><label>园区<select v-model="ruleForm.park_id" class="input" required><option v-for="park in parks" :key="park.id" :value="String(park.id)">{{ park.name }}</option></select></label><label>触发器<select v-model="ruleForm.trigger" class="input"><option>MANUAL_CREATE</option><option>CHANNEL_INTAKE</option><option>RECYCLE</option></select></label><label>规则编码<input v-model="ruleForm.code" class="input" required /></label><label>规则名称<input v-model="ruleForm.name" class="input" required /></label><label>成员<select v-model="ruleForm.user_id" class="input" required><option v-for="user in assignees" :key="user.id" :value="String(user.id)">{{ user.real_name || user.username }}</option></select></label><label>容量<input v-model="ruleForm.capacity" class="input" type="number" min="1" max="10000" required /></label><label>回收小时<input v-model="ruleForm.recycle_after_hours" class="input" type="number" min="1" max="8760" required /></label><p class="form-note">创建后为草稿，须在治理面板显式发布。</p><button class="btn modal-submit" type="submit" :disabled="saving">创建草稿</button></form>
        <form v-else-if="dialog === 'channel'" class="modal-form" data-testid="lead-channel-form" @submit.prevent="createChannel"><label>园区<select v-model="channelForm.park_id" class="input" required><option v-for="park in parks" :key="park.id" :value="String(park.id)">{{ park.name }}</option></select></label><label>渠道编码<input v-model="channelForm.code" class="input" required /></label><label class="wide">渠道名称<input v-model="channelForm.name" class="input" required /></label><label class="wide">密钥环境变量名<input v-model="channelForm.secret_env_key" class="input" placeholder="KWZY_LEAD_CHANNEL_SECRET" required /></label><label class="checkbox"><input v-model="channelForm.enabled" type="checkbox" /> 立即启用（环境变量必须存在）</label><label class="checkbox"><input v-model="channelForm.allow_auto_assign" type="checkbox" /> 接收后自动分配</label><p class="form-note wide">系统不接收或展示明文密钥；未取得厂商凭据时保持关闭和 NOT_CONNECTED。</p><button class="btn modal-submit" type="submit" :disabled="saving">保存渠道配置</button></form>
        <form v-else class="modal-form" @submit.prevent="convertLead">
          <label class="wide checkbox"><input v-model="convertForm.with_lease" type="checkbox" :disabled="!activeLocks.length" /> 同时创建合同草稿（须使用本线索有效房源锁）</label>
          <template v-if="convertForm.with_lease"><label class="wide">锁定房源<select v-model="convertForm.unit_id" class="input" required><option v-for="lock in activeLocks" :key="lock.id" :value="String(lock.unit_id)">单元 #{{ lock.unit_id }} · {{ lockCountdown(lock) }}</option></select></label><label>开始日期<input v-model="convertForm.start_date" class="input" type="date" required /></label><label>结束日期<input v-model="convertForm.end_date" class="input" type="date" required /></label><label>占用面积<input v-model="convertForm.occupied_area" class="input" type="number" min="0.01" step="0.01" required /></label><label>租金单价<input v-model="convertForm.unit_rent_price" class="input" type="number" min="0" step="0.01" required /></label><label>押金<input v-model="convertForm.deposit_amount" class="input" type="number" min="0" step="0.01" /></label></template>
          <p v-else class="form-note">仅创建主体，不会生成合同或占用房源。匹配并锁定房源后可一次性创建合同草稿。</p>
          <button class="btn modal-submit" type="submit" :disabled="saving" data-testid="lead-convert-confirm">{{ convertForm.with_lease ? "创建主体和合同草稿" : "仅转化为主体" }}</button>
        </form>
      </section>
    </div>
  </section>
</template>

<style scoped>
.crm-page { position: relative; display: grid; gap: 1rem; }
.page-head, .drawer-head, .section-head, .view-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.page-head h1 { margin: .1rem 0; font-size: clamp(1.65rem, 3vw, 2.35rem); letter-spacing: -.04em; }.eyebrow, .section-head h3 { margin: 0; color: var(--primary); font-size: .72rem; font-weight: 900; letter-spacing: .14em; }.head-actions, .row-actions { display: flex; gap: .55rem; }
.notice { margin: 0; padding: .72rem .9rem; border-radius: 10px; }.notice-error { color: var(--danger); background: #fff0ef; }.notice-success { color: #087052; background: #e8f7f1; }
.metric-strip { display: grid; grid-template-columns: repeat(6, minmax(110px, 1fr)); overflow: hidden; border: 1px solid var(--border); border-radius: 14px; background: #fff; box-shadow: var(--shadow); }.metric-strip article { padding: .9rem 1rem; border-right: 1px solid var(--border); }.metric-strip article:last-child { border: 0; }.metric-strip span, .metric-strip small { display: block; color: var(--muted); font-size: .72rem; }.metric-strip strong { margin-right: .3rem; font-size: 1.55rem; }.metric-strip .warning { background: #fff7ed; }.metric-strip .warning strong { color: #b45309; }
.filters { display: grid; grid-template-columns: repeat(7, minmax(115px, 1fr)); gap: .7rem; padding: .85rem; }.filters label, .modal-form label { display: grid; gap: .3rem; color: var(--muted); font-size: .73rem; font-weight: 800; }.filters .keyword { grid-column: span 2; }.filter-submit { align-self: end; }
.view-toolbar { padding: .15rem .2rem; }.view-toolbar span { color: var(--muted); }.view-switch { display: flex; padding: .2rem; border-radius: 9px; background: #e9eeec; }.view-switch button { border: 0; padding: .45rem .8rem; border-radius: 7px; background: transparent; color: var(--muted); cursor: pointer; }.view-switch button[aria-pressed="true"] { background: #fff; color: var(--text); box-shadow: 0 2px 8px rgba(15, 23, 42, .08); }
.pipeline { display: grid; grid-template-columns: repeat(8, minmax(190px, 1fr)); gap: .75rem; overflow-x: auto; padding-bottom: .5rem; }.stage-column { min-height: 360px; background: #f7f9f8; box-shadow: none; }.stage-column > header { display: flex; align-items: center; gap: .45rem; padding: .7rem; border-bottom: 1px solid var(--border); }.stage-column > header b { margin-left: auto; color: var(--muted); font-size: .75rem; }.stage-dot { width: .5rem; height: .5rem; border-radius: 50%; background: var(--primary); }.stage-stack { display: grid; align-content: start; gap: .55rem; padding: .55rem; }.lead-card { display: grid; gap: .42rem; width: 100%; padding: .75rem; border: 1px solid var(--border); border-radius: 10px; background: #fff; color: var(--text); text-align: left; cursor: pointer; }.lead-card:hover, .lead-card.selected { border-color: var(--primary); transform: translateY(-1px); box-shadow: var(--shadow); }.lead-card > span { color: var(--muted); font-size: .72rem; }.lead-top { display: flex; justify-content: space-between; color: var(--text) !important; }.lead-top i { padding: .08rem .4rem; border-radius: 99px; background: #e8f7f1; color: var(--primary); font-style: normal; font-size: .65rem; }.lead-card em { color: #b45309; font-size: .68rem; font-style: normal; }.lead-card.overdue { border-left: 3px solid #e09120; }
.table-wrap { overflow-x: auto; padding: .45rem .8rem; }.table td small { display: block; color: var(--muted); }.link-btn, .text-btn { border: 0; padding: .2rem; background: transparent; color: var(--primary); cursor: pointer; }.status-pill { display: inline-flex; padding: .18rem .52rem; border-radius: 99px; background: #e8f5f0; color: var(--primary); font-size: .72rem; font-weight: 800; }.danger-text { color: var(--danger) !important; }.empty-cell { padding: 3rem !important; color: var(--muted); text-align: center !important; }
.detail-drawer { position: fixed; z-index: 35; top: 1rem; right: 1rem; bottom: 1rem; width: min(430px, calc(100vw - 2rem)); overflow-y: auto; padding: 1rem; box-shadow: 0 20px 55px rgba(15, 23, 42, .22); }.drawer-head h2 { margin: .15rem 0; }.drawer-head span { color: var(--muted); font-size: .78rem; }.close-btn { border: 0; background: transparent; color: var(--muted); font-size: 1.6rem; cursor: pointer; }.detail-badges { display: flex; gap: .5rem; align-items: center; margin: .75rem 0; color: var(--muted); font-size: .75rem; }.fact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: 0; }.fact-grid div { padding: .65rem; border-radius: 9px; background: #f6f8f8; }.fact-grid dt { color: var(--muted); font-size: .68rem; }.fact-grid dd { margin: .1rem 0 0; font-weight: 800; }.detail-note { padding: .65rem; border-radius: 9px; background: #f7f9f8; color: var(--muted); font-size: .78rem; }.action-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: .85rem 0; }.btn-dark { background: #173d35; }.btn-quiet { border: 1px solid var(--border); background: #fff; color: var(--primary); }.detail-section { padding-top: .9rem; margin-top: .9rem; border-top: 1px solid var(--border); }.detail-section h3 { margin: 0 0 .6rem; font-size: .86rem; }.lock-row, .history-row { display: grid; gap: .15rem; padding: .6rem; margin-bottom: .45rem; border-radius: 9px; background: #f7f9f8; font-size: .75rem; }.lock-row > div { display: flex; justify-content: space-between; gap: .5rem; }.lock-row span, .history-row span, .history-row small { color: var(--muted); }.lock-row.active { border-left: 3px solid #d18a13; background: #fff8e8; }.row-actions button { border: 0; background: transparent; color: var(--primary); cursor: pointer; }.match-card { padding: .7rem; margin-top: .55rem; border: 1px solid var(--border); border-radius: 10px; }.match-card header { display: flex; justify-content: space-between; }.match-card header div { display: grid; }.match-card header span, .match-card p, .match-card li { color: var(--muted); font-size: .7rem; }.match-card header b { color: var(--primary); font-size: 1.3rem; }.match-card header small { font-size: .6rem; }.match-card ul { padding-left: 1rem; }.match-card .btn { width: 100%; }.timeline { display: grid; gap: .55rem; padding: 0; list-style: none; }.timeline li { display: grid; grid-template-columns: 10px 1fr; gap: .5rem; }.timeline i { width: 8px; height: 8px; margin-top: .3rem; border-radius: 50%; background: var(--primary); }.timeline div { display: grid; }.timeline span { color: var(--muted); font-size: .7rem; }.mini-empty { padding: 1rem .4rem; color: var(--muted); font-size: .75rem; text-align: center; }
.state { min-height: 260px; display: grid; place-content: center; justify-items: center; gap: .5rem; color: var(--muted); }.state.compact { min-height: 120px; }.spinner { width: 1.7rem; height: 1.7rem; border: 3px solid #dce8e4; border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; }
.modal-backdrop { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 1rem; background: rgba(15, 30, 35, .52); backdrop-filter: blur(3px); }.modal { width: min(680px, 100%); max-height: calc(100vh - 2rem); overflow-y: auto; padding: 1.05rem; }.modal > header { display: flex; justify-content: space-between; align-items: center; padding-bottom: .7rem; border-bottom: 1px solid var(--border); }.modal h2 { margin: 0; }.modal-form { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-top: .8rem; }.modal-form .wide, .modal-submit, .form-note, .duplicate-panel { grid-column: 1 / -1; }.modal-form textarea { min-height: 78px; resize: vertical; }.checkbox { grid-template-columns: auto 1fr !important; align-items: center; justify-content: start; }.duplicate-panel { display: grid; gap: .55rem; padding: .7rem; border-radius: 10px; background: #fff8e8; }.duplicate-panel button { display: grid; padding: .55rem; border: 1px solid #ead6a9; border-radius: 8px; background: #fff; text-align: left; cursor: pointer; }.duplicate-panel small { color: var(--muted); }.form-note { margin: 0; padding: .7rem; border-radius: 8px; background: #eef6f3; color: #35534b; font-size: .8rem; }.danger-btn { background: var(--danger); }
.governance-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .85rem; }.governance-card { overflow: hidden; }.governance-card > summary { display: flex; align-items: center; gap: .8rem; padding: .85rem 1rem; cursor: pointer; list-style: none; }.governance-card > summary::-webkit-details-marker { display: none; }.governance-card > summary span { display: grid; gap: .15rem; }.governance-card > summary small { color: var(--muted); font-weight: 500; }.governance-card > summary b { margin-left: auto; color: var(--primary); }.governance-actions { display: flex; align-items: center; justify-content: flex-end; gap: .65rem; padding: .7rem 1rem; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); background: #f7f9f8; }.governance-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: .65rem; padding: .7rem 1rem; border-bottom: 1px solid var(--border); }.governance-row > div { display: grid; min-width: 0; }.governance-row > div span { overflow: hidden; color: var(--muted); font-size: .7rem; text-overflow: ellipsis; white-space: nowrap; }.channel-block:last-of-type .governance-row { border-bottom: 0; }.channel-events { display: grid; gap: .35rem; padding: .6rem 1rem; background: #f7f9f8; }.channel-events > div { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: .5rem; font-size: .72rem; }.channel-events span { overflow: hidden; color: var(--muted); text-overflow: ellipsis; white-space: nowrap; }.channel-events button { border: 0; background: transparent; color: var(--primary); cursor: pointer; }
.viewing-row { border-left: 3px solid #77a99a; }.row-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; }.row-actions button, .row-actions a { border: 0; background: transparent; color: var(--primary); font-size: .74rem; text-decoration: none; cursor: pointer; }.intent-card { display: grid; gap: .55rem; padding: .7rem; border: 1px solid var(--border); border-left: 3px solid #8798a3; border-radius: 9px; background: #f7f9f8; }.intent-card.intent-approved { border-left-color: var(--primary); background: #eff9f5; }.intent-card.intent-rejected, .intent-card.intent-returned { border-left-color: var(--danger); background: #fff4f1; }.intent-card > div:first-child { display: flex; align-items: center; gap: .55rem; }.intent-card > div:first-child small { margin-left: auto; color: var(--muted); }.intent-card p { margin: 0; color: var(--muted); font-size: .72rem; }
button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 3px solid rgba(15, 110, 86, .28); outline-offset: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1180px) { .metric-strip { grid-template-columns: repeat(3, 1fr); }.metric-strip article:nth-child(3) { border-right: 0; }.filters { grid-template-columns: repeat(4, 1fr); }.pipeline { grid-template-columns: repeat(8, 210px); } }
@media (max-width: 900px) { .governance-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .page-head { align-items: stretch; flex-direction: column; }.head-actions { justify-content: stretch; }.head-actions .btn { flex: 1; }.metric-strip { grid-template-columns: repeat(2, 1fr); }.metric-strip article:nth-child(3) { border-right: 1px solid var(--border); }.filters { grid-template-columns: 1fr 1fr; }.filters .keyword { grid-column: span 2; }.pipeline { grid-template-columns: repeat(8, 82vw); }.detail-drawer { top: .5rem; right: .5rem; bottom: .5rem; width: calc(100vw - 1rem); }.modal-form { grid-template-columns: 1fr; }.modal-form .wide, .modal-submit, .form-note, .duplicate-panel { grid-column: auto; }.governance-row { grid-template-columns: minmax(0, 1fr) auto; }.governance-row > button { grid-column: 1 / -1; justify-self: start; }.channel-events > div { grid-template-columns: minmax(0, 1fr) auto; }.channel-events button { grid-column: 1 / -1; justify-self: start; } }
</style>
