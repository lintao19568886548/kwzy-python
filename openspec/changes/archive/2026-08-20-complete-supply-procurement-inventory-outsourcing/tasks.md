# Tasks

## 1. Independent evidence and specifications

- [x] 1.1 Inspect blueprint, current Python/PC code, both legacy Java copies, and legacy SQL for authoritative supply evidence.
- [x] 1.2 Classify Party supplier role and work-order costs as boundaries rather than completed supply capability.
- [x] 1.3 Define local product truth and explicit real-data/external-integration blockers.

## 2. Domain and persistence

- [x] 2.1 Implement supplier, material, warehouse, procurement, stock, inventory issue, stocktake, and outsourcing aggregates.
- [x] 2.2 Add tenant/park composite relationships, unique constraints, checks, indexes, and append-only histories.
- [x] 2.3 Add one additive Alembic revision and verify fresh PostgreSQL 16 upgrade/downgrade/upgrade.
- [x] 2.4 Compare ORM metadata with migrated schema and test core database constraints.

## 3. Supplier and catalogue workflows

- [x] 3.1 Implement supplier onboarding, scopes, qualifications, masking/fingerprinting, state transitions, and evaluations.
- [x] 3.2 Implement material catalogue, warehouse governance, search, paging, and permission/park scope.
- [x] 3.3 Add supplier eligibility and qualification expiry enforcement.
- [x] 3.4 Add supplier/catalogue regression and isolation tests.

## 4. Procurement and receiving

- [x] 4.1 Implement requisition drafts, immutable lines, submit/cancel, and native approval.
- [x] 4.2 Implement approved-requisition purchase orders and acknowledgement lifecycle.
- [x] 4.3 Implement idempotent partial/final receipt with over-receipt and concurrency protection.
- [x] 4.4 Add procurement/receipt regression, approval, isolation, idempotency, and concurrency tests.

## 5. Inventory and issue

- [x] 5.1 Implement balance query, ledger, reservation, inventory requisition, partial/final issue, and return.
- [x] 5.2 Implement stocktake, variance approval, adjustment, reversal, and audit evidence.
- [x] 5.3 Enforce non-negative stock and work-order linkage without treating work-order costs as stock truth.
- [x] 5.4 Add inventory regression, park isolation, idempotency, and concurrency tests.

## 6. Outsourcing

- [x] 6.1 Implement outsourcing draft, SLA/deliverable snapshots, supplier eligibility, and native approval.
- [x] 6.2 Implement execution events, completion, tenant acceptance, rework, cancellation, and evaluation.
- [x] 6.3 Preserve the settlement/invoice boundary and explicit external-adapter state.
- [x] 6.4 Add lifecycle, transition, isolation, idempotency, and approval tests.

## 7. API and security

- [x] 7.1 Mount strict supply routers and publish OpenAPI paths/schemas.
- [x] 7.2 Seed and enforce supply permissions with field masking and tenant/park 404 behavior.
- [x] 7.3 Add validation, IDOR, parameter-pollution, injection, secret, and audit tests.
- [x] 7.4 Add real HTTP workflow and OpenAPI contract coverage.

## 8. PC workspace

- [x] 8.1 Add permission-aware `/supply` navigation, typed API client, and overview KPIs from real APIs.
- [x] 8.2 Add supplier, procurement, inventory, and outsourcing tabs with operational drawers/actions.
- [x] 8.3 Add responsive desktop/tablet/390px loading, empty, permission, conflict, offline, and retry states.
- [x] 8.4 Add unit/build and browser E2E with screenshot evidence.

## 9. Migration and operations

- [x] 9.1 Add synthetic fixture import with dry run, checkpoint/resume, replay, quarantine, and provenance.
- [x] 9.2 Add reconciliation, rollback, backup/delete/restore rehearsal, and truthful real-data blocker.
- [x] 9.3 Add supply acceptance to local-staging runbook and operations evidence.

## 10. Exact acceptance and closure

- [x] 10.1 Run backend/unit/integration/security/concurrency suites.
- [x] 10.2 Run PostgreSQL 16, real HTTP, performance, and worker checks.
- [x] 10.3 Run PC lint, typecheck, unit, production build, and browser E2E.
- [x] 10.4 Run OpenAPI, OpenSpec, secret, dependency, and final-quality gates at one exact SHA.
- [x] 10.5 Update capability matrix, findings, evidence index, and status without overstating real migration/integrations.
- [x] 10.6 Commit, push normally, sync/archive specs only after exact-SHA acceptance, and do not merge main before all global gates close.
