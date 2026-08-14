## 1. Evidence and specification

- [x] 1.1 Reconcile docs, legacy Java/frontend/schema evidence and current FacilityOps gaps
- [x] 1.2 Record legacy string CRUD, physical deletion and anonymous default-tenant registration risks
- [x] 1.3 Define device, weekly inspection, alarm, IoT truth and external blocker boundaries

## 2. Domain and persistence

- [x] 2.1 Add pure domain rules for device lifecycle, typed checks, weekly windows, alarms and escalation
- [x] 2.2 Add device/history, inspection definition/execution and IoT/alarm ORM models
- [x] 2.3 Add forward Alembic revision(s) after `y1b79d4e6f53` without editing applied history
- [x] 2.4 Add composite tenant/park FKs, checks, partial uniques, indexes and metadata parity tests

## 3. Facility device registry

- [x] 3.1 Add park/unit-scoped device create/list/detail with type-profile validation
- [x] 3.2 Add optimistic update and append-only before/after history with reason
- [x] 3.3 Add controlled retirement blocked by active inspections or alarms
- [x] 3.4 Add cross-tenant/park/unit/device-code and concurrent update tests

## 4. Inspection definition and scheduling

- [x] 4.1 Add draft/publish/retire template versions and ordered typed checklist items
- [x] 4.2 Add exact-device weekly schedules with timezone, assignee and completion window
- [x] 4.3 Add deterministic repeat-safe/concurrent-safe task generation and field WorkItems
- [x] 4.4 Add schedule pause/retire and immutable task template snapshots

## 5. Inspection execution and exceptions

- [x] 5.1 Add assigned start/reassign and versioned task lifecycle
- [x] 5.2 Add exact typed checklist submission with safe evidence and atomic validation
- [x] 5.3 Add failed exceptions and one stable linked WorkOrder for critical/promoted failures
- [x] 5.4 Add repeat-safe missed sweep, escalation, WorkItem, outbox and audit synchronization

## 6. IoT providers bindings and alarms

- [x] 6.1 Add provider truth states, secretless credential references and fail-closed health checks
- [x] 6.2 Add versioned tenant/park-consistent provider-device bindings and history
- [x] 6.3 Add authorized strict source-event ingestion, exact replay and bounded correlation
- [x] 6.4 Add severity projection, acknowledgement/resolution/closure and optimistic concurrency
- [x] 6.5 Add repeat-safe escalation and one linked WorkOrder for policy-qualified alarms

## 7. API and security

- [x] 7.1 Add explicit mounted schemas/routes and database-derived FacilityOps permissions
- [x] 7.2 Add tenant/park/unit/device/child-resource IDOR and forged-token tests
- [x] 7.3 Add unknown field, duplicate parameter, idempotency, stale version and race tests
- [x] 7.4 Align runtime and YAML OpenAPI exact method sets with no evidence DELETE routes

## 8. PC facility operations workspace

- [x] 8.1 Add live device registry, filters, detail/history and governed drawers
- [x] 8.2 Add template/schedule/task generation and typed inspection execution workspace
- [x] 8.3 Add alarm queue/timeline/correlation/escalation and WorkOrder drill-down
- [x] 8.4 Add role-aware loading/empty/403/409/offline/retry states at desktop/tablet/mobile widths

## 9. Migration and verification

- [x] 9.1 Add versioned synthetic maintenance/alarm fixture, field map and quarantine rules
- [x] 9.2 Implement dry/apply/interruption/reapply/reconcile/rollback without raw PII or fake live delivery
- [x] 9.3 Add domain/repository/API/PG concurrency/real HTTP regression coverage
- [x] 9.4 Add Playwright role, responsive, conflict/error and visual evidence
- [x] 9.5 Run focused and full PG16/backend/frontend/OpenAPI/OpenSpec/stub/secrets/performance/backup gates

## 10. Closure

- [x] 10.1 Run clean-SHA acceptance and update matrix/register/roadmap/state/evidence
- [ ] 10.2 Normally commit/push, sync specs and archive without force
