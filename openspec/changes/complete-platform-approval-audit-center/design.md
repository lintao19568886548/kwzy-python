## Context

The current `workflow` module stores one `approval_requests` row and a flat event list. Generic decisions mutate the request directly; only the Lease adapter provides partial same-transaction composition and self-approval protection. `ApprovalsView.vue` is explicitly a minimal non-BPM page. `audit_logs` records successful writes in the caller transaction but has no query API, integrity metadata or export control. Old Java evidence contains isolated reimbursement, leave, outreach-template and compliance approvals with inconsistent status fields rather than a reusable engine.

The change must remain compatible with Python 3.10, FastAPI, SQLAlchemy and PostgreSQL 16, preserve the current Alembic chain, retain tenant/park isolation, avoid Router-to-ORM and Application-to-ORM dependencies, and keep production/real legacy databases out of the local workflow.

## Goals / Non-Goals

**Goals:**

- Deliver a complete lightweight platform approval center: versioned definitions, multi-step instances, stable user tasks, delegation, SLA escalation, responsibilities separation and live PC workflows.
- Preserve business-domain authority and commit-free composition for Lease and future bounded contexts.
- Make new audit records append-only and deterministically verifiable, with scoped search/detail/export and a PC audit center.
- Provide PostgreSQL concurrency evidence, real HTTP/browser journeys and a reversible synthetic migration drill.

**Non-Goals:**

- Implement arbitrary BPMN, executable user scripts, dynamic SQL conditions or an external workflow engine.
- Migrate old reimbursement/leave/history without authorized source schema and desensitized data.
- Implement HR, reimbursement or other missing business domains merely because their eventual commands will use this platform.
- Record failed business transactions in the same ledger after rollback; authentication/security failures continue through the existing durable security-event/log path.
- Connect production, publish remote deployments or weaken human gates for production/cutover.

## Decisions

### 1. Use a constrained versioned workflow model, not BPMN

Add `approval_definitions`, immutable `approval_definition_versions`, normalized `approval_definition_steps` and `approval_step_assignees`. Steps are ordered and support `ANY` or thresholded `ALL`. This is sufficient for verified park operations while keeping validation, indexing and migration understandable. BPMN libraries and JSON-only definitions were rejected because they either add an unneeded runtime or hide referential integrity.

### 2. Extend the existing request as the instance root

Keep `approval_requests` and add request number, definition version, current step/round, priority, due/completion times, safe snapshot, optimistic version and idempotency key. Add `approval_tasks`, `approval_delegations` and decision idempotency fields. Existing ids and Lease foreign references stay valid; a forward migration backfills old rows as versionless `LEGACY_COMPAT` instances rather than rewriting history.

### 3. Resolve stable user tasks when each step opens

Definition steps reference users or roles, but opening a step materializes one task per active same-tenant user. Current-step role membership is therefore stable, while future steps resolve at open time. An empty candidate set fails the surrounding transaction. This avoids authorization changes silently rewriting already-issued work.

### 4. Make the instance transition the only orchestration authority

Application services lock the instance/current tasks on PostgreSQL, verify expected version and idempotency key, write one decision, close sibling tasks according to step mode, open the next step and update work items/events/audit in one transaction. Unique constraints guard duplicate decisions, current candidate tasks, request numbers and idempotency keys. The repository constructs ORM rows; application code consumes domain-shaped records/DTOs and does not import ORM models.

### 5. Preserve domain callbacks through ports

The workflow engine never guesses how Lease, finance or HR state should change. Existing Lease commands continue to own activation/change/exit transitions and call commit-free workflow ports. Generic approvals without a registered domain callback only update their approval instance. This prevents a generic approval endpoint from bypassing domain invariants.

### 6. Model delegation as effective-dated acting authority

Delegations are same-tenant, user-to-user, optional business-type, start/end bounded and revocable. The original assignee remains on the task; decisions record both original and acting users. Validation blocks self-delegation, immediate/indirect active cycles and overlapping duplicate grants. Delegation does not add RBAC or park scope; the task's park must still be visible to the acting user.

### 7. Project one work item per materialized task

Use `source_type=APPROVAL_TASK`, `source_id=<task_id>` and `item_type=APPROVAL_TASK`. Existing source uniqueness naturally supports one projection per task. Workflow owns commit-free open/complete/cancel projection calls. Direct work-item completion cannot decide an approval and UI deep-links back to the approval center.

### 8. Add a tenant hash head for new audit records

Add `audit_chain_heads(tenant_id, sequence_no, last_hash)` and nullable integrity columns on `audit_logs`. `AuditRecorder` obtains/locks the tenant head, canonicalizes a bounded redacted payload, calculates SHA-256 over sequence/previous hash/core fields, appends the row and advances the head in the caller transaction. Pre-existing rows remain null-hash `LEGACY_UNVERIFIED`. Independent verification recalculates hashes without modifying evidence. A database role/grant and no mutation API are the operational append-only controls; destructive superuser access remains an infrastructure concern documented in the Runbook.

### 9. Keep audit query/export behind infrastructure repositories

Audit repositories enforce tenant and park filters before pagination. Detail never returns secret material. CSV export reuses the same filter builder, requires `audit.export`, caps rows and audits only filter metadata/count. PC components consume typed APIs and never load local JSON or compute integrity themselves.

### 10. Treat timeout processing as an idempotent application command

Provide a protected sweep command used by tests/local scheduler and later by the platform job runner. It locks due pending tasks, adds one overdue event, raises the existing work item to urgent and leaves approval outcome unchanged. No new external queue is required for this vertical.

## Risks / Trade-offs

- [Risk] Role-based steps can resolve many users and create many rows. → Cap candidates per step, index tenant/status/assignee/due fields and reject definitions exceeding the configured safe limit.
- [Risk] Audit-head locking can become a hot row for high-volume tenants. → Keep canonicalization short, benchmark concurrent appends and document later sharding as a measured follow-up rather than weakening ordering now.
- [Risk] Existing approval rows have no definition version or hash history. → Preserve them as explicit compatibility/legacy-unverified records; never fabricate lineage.
- [Risk] Generic decision endpoints could bypass Lease invariants. → Continue rejecting Lease-managed business types from generic submission/decision paths and retain domain-owned ports/tests.
- [Risk] Delegation could amplify access. → Require same tenant, effective period, task park visibility and original task candidacy; delegation never grants general permissions.
- [Risk] CSV formula injection. → Prefix cells beginning with spreadsheet formula characters and set safe content disposition/UTF-8 output.
- [Trade-off] A constrained ordered-step engine cannot express arbitrary graphs. → It covers evidenced operational approvals and remains inspectable; complex conditional graphs require a later separately approved change.

## Migration Plan

1. Add a forward revision after `n0c68d3e5f42`; create definition/task/delegation/hash-head tables, add nullable compatibility columns and indexes, and backfill existing requests as `LEGACY_COMPAT` without semantic rewriting.
2. Seed new permissions and a safe default local/test definition idempotently; production receives no implicit published business definition.
3. Deploy backward-compatible reads and Lease adapter changes before enabling definition administration UI.
4. Run PostgreSQL 16 fresh upgrade, downgrade/re-upgrade, schema/constraint/concurrency tests and synthetic migration dry/apply/idempotent/reconcile/rollback.
5. Verify full API/PC journeys, audit-chain verification, export safety, performance and backup/restore.
6. Rollback by disabling new routes/UI, draining no new submissions, and downgrading only in disposable/staging rehearsals; production rollback requires the separate human-approved Runbook.

## Open Questions

- Real old reimbursement/leave status codes, reviewer fields and timestamp reliability remain unknown until an authorized schema dump and desensitized sample are supplied.
- Production scheduler ownership for overdue sweeps remains an operations decision; this vertical delivers an idempotent command and local evidence, not remote scheduling authorization.
- Audit retention, cold archive and legal hold periods require policy-owner approval and are not guessed in code.
