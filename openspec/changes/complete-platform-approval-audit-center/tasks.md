## 1. Evidence and execution control

- [x] 1.1 Publish old Java/PC/database approval and audit evidence with explicit replace/retain/block disposition
- [x] 1.2 Record the current minimal Python approval/audit gaps without counting flat status, docs or unmounted code as complete
- [x] 1.3 Update roadmap, capability matrix and agent state for this vertical while preserving all external migration/production blockers

## 2. Database contract

- [x] 2.1 Add ORM models for definitions, immutable versions, ordered steps, assignees, tasks, delegations and tenant audit-chain heads
- [x] 2.2 Extend existing approval requests/events and audit logs with backward-compatible instance, idempotency, delegation and integrity fields
- [x] 2.3 Add one forward Alembic revision after `n0c68d3e5f42` with FKs, checks, partial/functional uniqueness and query indexes
- [x] 2.4 Backfill existing requests as explicit `LEGACY_COMPAT` and leave historical audit hashes null/`LEGACY_UNVERIFIED`
- [x] 2.5 Register metadata and verify PostgreSQL 16 fresh upgrade, current=heads, downgrade -1 and re-upgrade

## 3. Approval definition governance

- [x] 3.1 Add strict schemas for definition, draft version, step/assignee, publication and retirement commands
- [x] 3.2 Implement tenant/park-safe definition repositories without exposing ORM outside infrastructure
- [x] 3.3 Implement draft create/update and copy-from-published version behavior
- [x] 3.4 Validate contiguous steps, modes, thresholds, SLA and same-tenant user/role references before publication
- [x] 3.5 Implement optimistic publication with immutable published versions and concurrent 409 behavior
- [x] 3.6 Implement scoped definition list/detail/version history and safe retirement

## 4. Approval instance orchestration

- [x] 4.1 Add request/detail/task/event DTOs and compatibility projections for existing approval clients
- [x] 4.2 Implement definition selection, safe snapshot validation, tenant request numbering and idempotent submission
- [x] 4.3 Resolve current-step user candidates from user/role assignees and fail closed on an empty active set
- [x] 4.4 Implement `ANY` and thresholded `ALL` step progression with terminal sibling-task closure
- [x] 4.5 Implement reject, return, withdraw and applicant-only resubmit with immutable prior-round history
- [x] 4.6 Enforce self-approval separation and explicit high-risk override permission/reason
- [x] 4.7 Implement optimistic version and decision idempotency guarantees for retry/concurrent conflicts
- [x] 4.8 Preserve Lease-managed commit-free ports and same-transaction domain transitions

## 5. Task delegation, SLA and workbench

- [x] 5.1 Implement current-user pending/processed task queries with park scope and delegation visibility
- [x] 5.2 Implement effective-dated same-tenant delegation create/revoke/list with overlap and cycle guards
- [x] 5.3 Record original assignee and acting delegate on every delegated decision
- [x] 5.4 Project one idempotent work item per actionable task and close it with task terminal state
- [x] 5.5 Implement idempotent overdue sweep, escalation event and urgent work-item update

## 6. Audit ledger and query center

- [x] 6.1 Implement bounded canonical audit-detail sanitation with blocked secret keys and registered PII masking
- [x] 6.2 Implement tenant chain-head locking, sequence allocation and deterministic SHA-256 append in the business transaction
- [x] 6.3 Preserve existing AuditRecorder call sites and mark pre-chain rows `LEGACY_UNVERIFIED`
- [x] 6.4 Implement independent chain verification with verified/failed/legacy states and no evidence rewrite
- [x] 6.5 Implement tenant/park scoped paginated audit search/detail filters through an infrastructure repository
- [x] 6.6 Implement formula-safe bounded CSV export with separate permission and an export audit summary

## 7. APIs, permissions and contracts

- [x] 7.1 Seed definition/task/delegation/audit read/export/override permissions idempotently
- [x] 7.2 Mount definition, instance, task, delegation, overdue-sweep and audit-center APIs with Router-to-ORM prohibition
- [x] 7.3 Keep Lease business types blocked from generic bypass endpoints and retain existing compatible `/approvals` behavior
- [x] 7.4 Update canonical OpenAPI with exact schemas, enums, filters, errors, idempotency and CSV response
- [x] 7.5 Add runtime-to-YAML drift assertions for every new or modified route/method

## 8. PC approval and audit centers

- [x] 8.1 Add typed live-API state for applications, pending/processed tasks, definitions, delegations and audit search/export
- [x] 8.2 Rebuild approvals view with tabs, filters, KPI counts and timeline drawer using only committed server state
- [x] 8.3 Add definition draft/step administration, publish/retire controls and published read-only behavior
- [x] 8.4 Add decision/return/withdraw/resubmit/delegation actions with idempotency and 403/409-safe feedback
- [x] 8.5 Add audit-center search, integrity badges, redacted detail drawer and controlled CSV export
- [x] 8.6 Add loading, empty, read-only, permission, conflict, offline/retry, keyboard and desktop/tablet/mobile states

## 9. Migration readiness

- [x] 9.1 Publish legacy field/status/route disposition for reimbursement, leave, outreach-template and operation-log evidence
- [x] 9.2 Implement schema-versioned synthetic approval/audit ETL dry-run/apply/idempotent/reconcile/rollback with test-DB safety
- [x] 9.3 Prove fixture rollback isolation, no fabricated decisions, no raw PII and unchanged authorization rows

## 10. Automated verification

- [x] 10.1 Add definition lifecycle and validation unit/application tests
- [x] 10.2 Add instance state-machine, self-approval, delegation, SLA, idempotency and work-item tests
- [x] 10.3 Add tenant/park/permission/IDOR/parameter-pollution tests for approval and audit APIs
- [x] 10.4 Add audit sanitization, hash verification, legacy state, tamper detection and export-injection tests
- [x] 10.5 Add PostgreSQL 16 concurrent publish, decision, task uniqueness and audit-chain append tests
- [x] 10.6 Add real HTTP journey for publish → submit → multi-step/delegated decision → audit query/export
- [x] 10.7 Add Playwright desktop/tablet/mobile approval and audit journeys including read-only, 409 and retry states
- [x] 10.8 Capture and visually review key approval/audit screenshots with no fake controls, clipping or unreadable evidence

## 11. Closure and delivery

- [x] 11.1 Run focused backend/frontend tests, type checks, build, migration drill and strict OpenSpec validation
- [x] 11.2 Run full PostgreSQL 16 acceptance and update evidence, matrix, roadmap and agent state with exact results
- [ ] 11.3 Commit and normally push the complete vertical, re-run clean-SHA gates, sync main specs and archive without force
