## 1. Evidence and specification

- [x] 1.1 Reconcile product request, docs, legacy Java/old UI/schema evidence and current WorkOrder gaps
- [x] 1.2 Record that the legacy backend is CRUD/no-dispatch despite frontend workflow affordances
- [x] 1.3 Define Party-bound tenant identity, state/quote/SLA/cost/acceptance rules and external blockers

## 2. Domain and persistence

- [x] 2.1 Add pure-domain state, SLA, dispatch, quote, cost, acceptance and rating rules
- [x] 2.2 Expand WorkOrder and add principal/rule/event/quote/line/cost/acceptance/rating models
- [x] 2.3 Add forward Alembic revision(s) after `w9f57b2c4d31` without editing applied history
- [x] 2.4 Add bounded checks, indexes, partial uniques, composite tenant foreign keys and metadata parity tests

## 3. Tenant service intake

- [x] 3.1 Add database-derived User→Party→park principal grants and admin lifecycle
- [x] 3.2 Add tenant self-service request/list/detail with derived identity and source idempotency
- [x] 3.3 Add staff on-behalf intake with Party/park/unit/contact ownership validation
- [x] 3.4 Mask contact data and preserve safe request/evidence references

## 4. Dispatch and SLA

- [x] 4.1 Add draft/publish/retire assignment rules with immutable versions and deterministic match order
- [x] 4.2 Auto-dispatch on intake or create an explicit unassigned triage task
- [x] 4.3 Add accept/start/manual reassign with version checks, reasons, timeline and WorkItem ownership
- [x] 4.4 Add repeat-safe response/resolution breach sweep and truthful SLA projection

## 5. Quote and fulfillment

- [x] 5.1 Add versioned Decimal quote headers/lines and server-calculated totals
- [x] 5.2 Add submit and Party-bound accept/reject with quote-required execution gate
- [x] 5.3 Add append-only labor/material/outsource/other actual entries and reversal
- [x] 5.4 Add processing result/evidence and submit-for-acceptance transition

## 6. Acceptance and rating

- [x] 6.1 Add Party-bound accept/rework attempts with reason and optimistic concurrency
- [x] 6.2 Reopen rejected work without deleting quote, cost or prior completion evidence
- [x] 6.3 Add one immutable post-completion 1–5 rating with bounded tags/comment
- [x] 6.4 Synchronize work items, events and audit across completion/rework/acceptance

## 7. API and security

- [x] 7.1 Add strict mounted staff/tenant schemas and database-derived permissions
- [x] 7.2 Add tenant/Party/park/unit/user/child-resource IDOR and forged-token tests
- [x] 7.3 Add duplicate parameter, unknown field, idempotency, stale version and concurrent decision tests
- [x] 7.4 Align runtime and YAML OpenAPI exact method sets and error contracts

## 8. PC service workspace

- [x] 8.1 Add live queue, SLA, tenant/park/category/status filters and detail timeline
- [x] 8.2 Add intake/dispatch/reassign and quote builder/decision drawers
- [x] 8.3 Add fulfillment cost/evidence, acceptance/rework and rating views
- [x] 8.4 Add role-aware tenant-principal view with no cross-Party data fetch
- [x] 8.5 Add loading/empty/403/409/offline/retry/no-overflow desktop/tablet/mobile states

## 9. Migration and verification

- [x] 9.1 Add versioned synthetic `repair_order` fixture, field map and quarantine rules
- [x] 9.2 Implement dry/apply/interruption/reapply/reconcile/rollback without raw PII
- [x] 9.3 Add domain/repository/API/PG concurrency/real HTTP regression coverage
- [x] 9.4 Add Playwright role, responsive, conflict/error and visual evidence
- [x] 9.5 Run focused and full PG16/backend/frontend/OpenAPI/OpenSpec/stub/secrets/performance/backup gates

## 10. Closure

- [ ] 10.1 Run clean-SHA acceptance and update matrix/register/roadmap/state/evidence
- [ ] 10.2 Normally commit/push, sync specs and archive without force
