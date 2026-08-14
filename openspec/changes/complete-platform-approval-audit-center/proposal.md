## Why

The current platform exposes only a one-step approval adapter and a transaction-bound audit table; it has no versioned workflow definitions, stable approver tasks, delegation/SLA, unified decision workspace, searchable audit center, or tamper-evidence verification. Old Java evidence shows approvals fragmented across reimbursement, leave, outreach-template and other domain-specific status fields, while the V2 blueprint requires explicit state machines and first-class audit, so treating the current shell as complete would preserve the legacy weakness.

## What Changes

- Replace the generic one-approver path with published, immutable workflow-definition versions containing ordered serial or parallel steps and same-tenant role/user assignees.
- Orchestrate approval instances and stable task snapshots with separation of duties, scoped visibility, optimistic concurrency, idempotent decisions, withdraw/reject/return semantics, delegation and overdue escalation.
- Preserve domain ownership: Lease and future bounded contexts submit/decide through commit-free ports and remain authoritative for their business state transitions.
- Project actionable approval tasks into the unified workbench without making work items the approval source of truth.
- Rebuild the PC approval center around live APIs for my applications, pending/processed tasks, definition administration, detail timeline, conflicts, read-only and retry states.
- Add an append-only, hash-verifiable audit ledger over new records plus a tenant/park/permission-scoped audit query/export center; historical rows remain explicitly `LEGACY_UNVERIFIED` rather than receiving fabricated hashes.
- Publish exact OpenAPI contracts, legacy disposition and a schema-versioned synthetic migration drill with dry-run, idempotent apply, reconciliation and rollback.
- Do not connect production, migrate unauthorized legacy data, or claim old scattered reimbursement/leave approvals are migrated without an authorized schema and desensitized sample.

## Capabilities

### New Capabilities

- `approval-definition-governance`: Versioned workflow definitions, ordered steps, assignee rules, publication and retirement.
- `approval-instance-orchestration`: Scoped approval instances, multi-step state machine, decision concurrency/idempotency and domain callbacks.
- `approval-task-delegation`: Stable approver tasks, effective-dated delegation, SLA and escalation semantics.
- `approval-center-pc`: Live PC definition administration, application/inbox/processed views and timeline-driven actions.
- `audit-ledger-integrity`: Append-only, non-sensitive audit records with deterministic hashes and integrity verification.
- `audit-center-query-pc`: Scoped audit search, detail, integrity state and controlled export in API and PC.
- `approval-audit-data-migration`: Legacy disposition plus synthetic migration/reconciliation/rollback evidence without claiming unauthorized data migration.

### Modified Capabilities

- `identity-authorization`: Add database-derived approval-definition, approval-task, audit-read and audit-export permissions without client-claim bypass.
- `workbench-ops`: Project pending approval tasks into idempotent work items and close them when tasks cease to be actionable.

## Impact

- Adds one forward Alembic revision after `n0c68d3e5f42`, new workflow/audit tables and non-destructive columns on existing approval/audit tables.
- Reworks `modules/workflow` into explicit application, infrastructure and interface boundaries while keeping existing `/approvals` and Lease adapter compatibility.
- Adds `/approval-definitions`, expanded `/approvals`, `/approval-tasks`, `/approval-delegations`, `/audit-logs` and integrity/export contracts under `/api/v1`.
- Rebuilds `ApprovalsView.vue`, adds an audit-center view and integrates approval tasks with workbench projections.
- Adds PostgreSQL 16 concurrency/integrity tests, real HTTP and Playwright journeys, synthetic ETL evidence, screenshots and full acceptance-gate coverage.
