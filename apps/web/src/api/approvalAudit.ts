import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "RETURNED" | "WITHDRAWN";
export type ApprovalPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export type TaskStatus = "PENDING" | "APPROVED" | "REJECTED" | "RETURNED" | "SKIPPED" | "CANCELLED";
export type IntegrityState = "VERIFIED" | "FAILED" | "LEGACY_UNVERIFIED";

export type Approval = {
  id: number;
  request_no: string | null;
  park_id: number | null;
  biz_type: string;
  biz_id: string;
  title: string;
  status: ApprovalStatus;
  priority: ApprovalPriority;
  applicant_user_id: number | null;
  approver_user_id: number | null;
  remark: string | null;
  decision_remark: string | null;
  definition_version_id: number | null;
  current_step_order: number | null;
  round_no: number;
  due_at: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  snapshot: Record<string, unknown> | null;
  lock_version: number;
  compatibility_mode: "NATIVE" | "LEGACY_COMPAT";
  created_at: string | null;
  updated_at: string | null;
  tasks?: ApprovalTask[];
  events?: ApprovalEvent[];
};

export type ApprovalTask = {
  id: number;
  approval_id: number;
  request_no: string | null;
  title: string;
  biz_type: string;
  biz_id: string;
  park_id: number | null;
  priority: ApprovalPriority;
  approval_status: ApprovalStatus;
  approval_lock_version: number;
  round_no: number;
  step_order: number;
  assignee_user_id: number;
  status: TaskStatus;
  due_at: string | null;
  decided_at: string | null;
  acted_by_user_id: number | null;
  delegation_id: number | null;
  escalated_at: string | null;
};

export type ApprovalEvent = {
  id: number;
  action: string;
  actor_user_id: number | null;
  remark: string | null;
  round_no: number;
  step_order: number | null;
  task_id: number | null;
  original_assignee_user_id: number | null;
  detail: Record<string, unknown> | null;
  created_at: string | null;
};

export type DefinitionAssignee = { user_id: number | null; role_id: number | null };
export type DefinitionStep = {
  id?: number;
  step_order: number;
  name: string;
  approval_mode: "ANY" | "ALL";
  min_approvals: number;
  sla_hours: number;
  assignees: DefinitionAssignee[];
};
export type DefinitionVersion = {
  id: number;
  version: number;
  status: "DRAFT" | "PUBLISHED" | "RETIRED";
  published_at: string | null;
  steps: DefinitionStep[];
};
export type ApprovalDefinition = {
  id: number;
  code: string;
  name: string;
  biz_type: string;
  park_id: number | null;
  status: "ACTIVE" | "RETIRED";
  current_version: number;
  lock_version: number;
  description: string | null;
  versions?: DefinitionVersion[];
  created_at: string | null;
  updated_at: string | null;
};

export type ApprovalDelegation = {
  id: number;
  grantor_user_id: number;
  delegate_user_id: number;
  biz_type: string | null;
  starts_at: string;
  ends_at: string;
  status: "ACTIVE" | "REVOKED";
  revoked_at: string | null;
};

export type AuditEvidence = {
  id: number;
  user_id: number | null;
  request_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  park_id: number | null;
  detail: Record<string, unknown> | null;
  client_ip: string | null;
  created_at: string;
  sequence_no: number | null;
  previous_hash: string | null;
  record_hash: string | null;
  integrity_version: number | null;
  integrity_state: IntegrityState;
};

export type AuditFilters = {
  user_id?: string;
  park_id?: string;
  action?: string;
  resource_type?: string;
  resource_id?: string;
  request_id?: string;
  integrity_state?: IntegrityState | "";
  created_from?: string;
  created_to?: string;
};

function compactAuditFilters(filters: AuditFilters): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== "" && value !== undefined)
  ) as Record<string, string>;
}

export async function listApprovals(params: Record<string, unknown> = {}) {
  const response = await http.get<Envelope<PageResult<Approval>>>("/approvals", { params });
  return response.data.data;
}

export async function getApproval(id: number) {
  const response = await http.get<Envelope<Approval>>(`/approvals/${id}`);
  return response.data.data;
}

export async function submitApproval(body: Record<string, unknown>) {
  const response = await http.post<Envelope<Approval>>("/approvals", body);
  return response.data.data;
}

export async function withdrawApproval(id: number, body: Record<string, unknown>) {
  const response = await http.post<Envelope<Approval>>(`/approvals/${id}/withdraw`, body);
  return response.data.data;
}

export async function resubmitApproval(id: number, body: Record<string, unknown>) {
  const response = await http.post<Envelope<Approval>>(`/approvals/${id}/resubmit`, body);
  return response.data.data;
}

export async function listTasks(processed: boolean) {
  const response = await http.get<Envelope<PageResult<ApprovalTask>>>("/approval-tasks", {
    params: { processed, page: 1, page_size: 100 },
  });
  return response.data.data;
}

export async function decideTask(id: number, body: Record<string, unknown>) {
  const response = await http.post<Envelope<Approval>>(`/approval-tasks/${id}/decide`, body);
  return response.data.data;
}

export async function listDefinitions() {
  const response = await http.get<Envelope<PageResult<ApprovalDefinition>>>(
    "/approval-definitions",
    { params: { page: 1, page_size: 100 } }
  );
  return response.data.data;
}

export async function getDefinition(id: number) {
  const response = await http.get<Envelope<ApprovalDefinition>>(`/approval-definitions/${id}`);
  return response.data.data;
}

export async function createDefinition(body: Record<string, unknown>) {
  const response = await http.post<Envelope<ApprovalDefinition>>("/approval-definitions", body);
  return response.data.data;
}

export async function updateDefinition(id: number, body: Record<string, unknown>) {
  const response = await http.patch<Envelope<ApprovalDefinition>>(
    `/approval-definitions/${id}`,
    body
  );
  return response.data.data;
}

export async function createDefinitionDraft(id: number, expectedLockVersion: number) {
  const response = await http.post<Envelope<ApprovalDefinition>>(
    `/approval-definitions/${id}/draft`,
    { expected_lock_version: expectedLockVersion }
  );
  return response.data.data;
}

export async function publishDefinition(
  id: number,
  versionId: number,
  expectedLockVersion: number
) {
  const response = await http.post<Envelope<ApprovalDefinition>>(
    `/approval-definitions/${id}/publish`,
    { version_id: versionId, expected_lock_version: expectedLockVersion }
  );
  return response.data.data;
}

export async function retireDefinition(id: number, expectedLockVersion: number) {
  const response = await http.post<Envelope<ApprovalDefinition>>(
    `/approval-definitions/${id}/retire`,
    { expected_lock_version: expectedLockVersion }
  );
  return response.data.data;
}

export async function listDelegations() {
  const response = await http.get<Envelope<ApprovalDelegation[]>>("/approval-delegations");
  return response.data.data;
}

export async function createDelegation(body: Record<string, unknown>) {
  const response = await http.post<Envelope<ApprovalDelegation>>("/approval-delegations", body);
  return response.data.data;
}

export async function revokeDelegation(id: number) {
  const response = await http.post<Envelope<ApprovalDelegation>>(
    `/approval-delegations/${id}/revoke`
  );
  return response.data.data;
}

export async function listAuditLogs(filters: AuditFilters) {
  const response = await http.get<Envelope<PageResult<AuditEvidence>>>("/audit-logs", {
    params: { ...compactAuditFilters(filters), page: 1, page_size: 100 },
  });
  return response.data.data;
}

export async function getAuditLog(id: number) {
  const response = await http.get<Envelope<AuditEvidence>>(`/audit-logs/${id}`);
  return response.data.data;
}

export type AuditVerification = {
  state: "VERIFIED" | "FAILED" | "LEGACY_UNVERIFIED";
  verified_count: number;
  legacy_count: number;
  failed_count: number;
  first_failed_sequence: number | null;
  head_matches: boolean;
  verified_at: string;
};

export async function verifyAuditChain() {
  const response = await http.get<Envelope<AuditVerification>>("/audit-logs/verify");
  return response.data.data;
}

export async function exportAuditLogs(filters: AuditFilters) {
  const response = await http.get<Blob>("/audit-logs/export", {
    params: compactAuditFilters(filters),
    responseType: "blob",
  });
  return response.data;
}
