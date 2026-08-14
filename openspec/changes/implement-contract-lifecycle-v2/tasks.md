## 1. Baseline, scope and compatibility

- [x] 1.1 Inventory current Lease domain/service/repository/API/PC/tests and Party/Unit/CRM-lock/Billing/Approval/Attachment/WorkItem transaction boundaries
- [x] 1.2 Sync five implemented basic Lease delta specs to main specs and archive `implement-lease-contract`
- [x] 1.3 Create proposal/design and ten delta specs, then pass `openspec validate implement-contract-lifecycle-v2 --strict`
- [x] 1.4 Publish legacy `rental_tenant`/image/reminder endpoint disposition and field/enum/PII mapping without claiming real schema verification
- [x] 1.5 Publish V1→V2 API/status compatibility, including submit approval, legacy RENEWED read and stable 409 migration behavior
- [x] 1.6 Confirm phase boundaries for Billing/Collection money movement, signature/OCR providers, employee mobile, tenant mini-program and production operations

## 2. PostgreSQL schema and Alembic migration

- [x] 2.1 Extend `lease_contracts` with contract type, currency, approval/effective/signing/termination, source, current-version and lock-version projections
- [x] 2.2 Add append-only `lease_contract_versions` with schema version, canonical snapshot, checksum and unique contract/version constraints
- [x] 2.3 Add structured current `lease_charge_items` and version-bound `lease_performance_schedules` with deterministic unique keys
- [x] 2.4 Add `lease_change_orders` with typed state, base/applied version, proposal snapshot, approval and idempotency fields
- [x] 2.5 Add `lease_contract_documents` with attachment/version/change/exit linkage, checksum and signature readiness fields
- [x] 2.6 Add `lease_exit_settlements` and `lease_exit_items` with clearance, evidence, totals and optimistic version fields
- [x] 2.7 Add tenant/source uniqueness, one in-flight change/exit partial indexes and tenant/park/status/date query indexes
- [x] 2.8 Backfill lock/current versions and immutable version 1 snapshots for existing effective/terminal contracts with stable checksums
- [x] 2.9 Convert only proven INCREASE/RENT_FREE terms to charge rules and preserve ambiguous OTHER terms as review-required evidence
- [x] 2.10 Preserve legacy RENEWED rows as readable history while preventing new writes and reporting successor mapping
- [x] 2.11 Keep JSON/Decimal/index behavior compatible with SQLite tests and PostgreSQL 16 authority
- [x] 2.12 Pass unique-head, fresh base→head and contract-V2 head→-1→head checks without editing historical migrations

## 3. Domain rules and canonical versioning

- [x] 3.1 Extend Lease entities/value objects for root versioning, charges, schedules, change orders, documents and exit settlements without framework dependencies
- [x] 3.2 Implement the V2 lifecycle and submission/approval/activation/exit transition rules with legacy RENEWED read compatibility
- [x] 3.3 Implement canonical sorted snapshot serialization, schema-version validation and SHA-256 checksum generation
- [x] 3.4 Enforce DRAFT-only direct edits and `LEASE_CHANGE_ORDER_REQUIRED` for effective contract business-field patches
- [x] 3.5 Implement structured charge enums, Decimal validation, currency/date constraints and tenant-unique charge codes
- [x] 3.6 Implement deterministic schedule generation, cycle alignment, 0.01 HALF_UP rounding and stable idempotency keys
- [x] 3.7 Implement full-cycle rent-free and ordered escalation rules while rejecting unsupported partial-cycle proration
- [x] 3.8 Implement all seven change-type invariants over a complete proposed future snapshot
- [x] 3.9 Implement exit item types, meter validation, deposit/receivable/refund totals and unambiguous net-direction values
- [x] 3.10 Implement expected-version and tenant-scoped command idempotency helpers with stable conflict semantics
- [x] 3.11 Add focused pure-domain tests for lifecycle, snapshot checksums, pricing, changes, settlement and rounding edge cases

## 4. Repositories, scope and transaction primitives

- [x] 4.1 Add tenant/park-scoped repositories and mappers for versions, charges/schedules, changes, documents and settlements/items
- [x] 4.2 Implement shared Lease filters for park, Party, status, type, expiry, approval, change, exit, keyword and UTC/as-of ranges
- [x] 4.3 Implement contract `FOR UPDATE` and ascending current-Unit row locking primitives for PostgreSQL
- [x] 4.4 Implement append-only version/document/history writes and prevent service/API mutation of immutable rows
- [x] 4.5 Implement atomic replacement of current unit/charge/schedule projections while retaining previous-version evidence
- [x] 4.6 Implement database-enforced one in-flight submitted/approved change and one open exit settlement per contract
- [x] 4.7 Implement scoped Party eligibility, current Unit selectors and Billing outstanding read port without cross-domain ORM imports
- [x] 4.8 Add DDD architecture regression tests preventing Lease application from importing foreign infrastructure models/repositories directly

## 5. Approval, document and work-item governance

- [x] 5.1 Define commit-free `ApprovalCommandPort` and infrastructure adapter for submit/approve/reject/withdraw/get/events
- [x] 5.2 Support revisioned `LEASE_CONTRACT_VERSION`, `LEASE_CHANGE_ORDER` and `LEASE_EXIT_SETTLEMENT` approvals without duplicate active decisions
- [x] 5.3 Make generic approval decision commands fail closed with `APPROVAL_DOMAIN_COMMAND_REQUIRED` for Lease-managed business types
- [x] 5.4 Enforce `approval:decide` + `lease:approve`, park scope and applicant/approver segregation with reasoned override auditing
- [x] 5.5 Add `lease:change`, `lease:approve`, `lease:approve_override`, `lease:document` and `lease:settle` bootstrap permissions and server checks
- [x] 5.6 Integrate attachment ownership checks and append-only contract document version/status metadata
- [x] 5.7 Implement main-document approval/signature readiness gate before activation
- [x] 5.8 Define `SignaturePort` local fake and production fail-closed adapter with explicit `live_verified=false` evidence
- [x] 5.9 Create/close idempotent approval, document, signature, change-due and exit WorkItems and reconcile the governance timeline
- [x] 5.10 Add API/repository tests for self-approval denial, override reason, generic approval fail-closed, foreign attachment and provider 503

## 6. Contract submit, activation and change application

- [x] 6.1 Make contract create/update validate real Party/park/current Units, multi-unit capacity, charges and schedule preview in one draft transaction
- [x] 6.2 Change submit to create domain approval and move DRAFT→PENDING_APPROVAL with expected version
- [x] 6.3 Implement contract approve/reject/withdraw commands that update approval, Lease, work items and audit atomically
- [x] 6.4 Make activation require PENDING_ACTIVE, approved/signed main document and confirmed snapshot, then insert version 1 and occupancy atomically
- [x] 6.5 Implement change draft creation and type-specific proposal patching from the current canonical snapshot
- [x] 6.6 Implement change edit/submit/approve/reject/withdraw/cancel commands with one-in-flight and segregation rules
- [x] 6.7 Implement due change apply with base-version recheck, sorted Unit locks, CRM-lock reconciliation and full rollback
- [x] 6.8 Implement renewal, expansion, reduction, unit transfer, price adjustment and Party transfer projection updates
- [x] 6.9 Make EARLY_TERMINATION application create/link an exit settlement and enter EXIT_PENDING without releasing occupancy
- [x] 6.10 Implement idempotent `apply-due` service/admin command without representing local invocation as production scheduling
- [x] 6.11 Add PostgreSQL race tests for concurrent submit, change apply, unit capacity, CRM lock and stale approved base versions
- [x] 6.12 Add failure-injection tests proving approval/version/schedule/Unit/WorkItem/audit transaction rollback

## 7. Exit handover and settlement

- [x] 7.1 Implement one-open-settlement creation with current contract/version/unit/deposit/Billing-outstanding snapshots
- [x] 7.2 Implement settlement item and meter editing with expected version, deterministic totals and checksum
- [x] 7.3 Implement exit submit/approve/reject/withdraw and retain occupancy through EXIT_PENDING
- [x] 7.4 Implement finance-authorized clearance confirmation that records evidence only and never moves funds
- [x] 7.5 Enforce non-zero balance evidence, approved main/exit documents and unexplained-balance close blockers
- [x] 7.6 Implement atomic idempotent close: terminal version, TERMINATED contract, Unit recompute, todo closure and audit
- [x] 7.7 Route post-activation breach through EXIT_PENDING/settlement while preserving pre-activation cancellation semantics
- [x] 7.8 Add API/PostgreSQL tests for deposit coverage/shortfall, occupancy retention, clearance, replay and close rollback

## 8. Queries and REST/OpenAPI surface

- [x] 8.1 Implement reconciled contract list/summary/detail with current projection, versions, changes, approvals, documents, schedules and exit state
- [x] 8.2 Implement Party-centered tenant contract profile with scoped current/history contracts and source/as-of-labeled Billing summary
- [x] 8.3 Implement zero-safe KPI counts/amounts for current, expiring, pending approval, due change, exit pending and unresolved clearance
- [x] 8.4 Implement authorized Park/eligible Party/current Unit selectors with human-readable labels and no cross-scope leakage
- [x] 8.5 Add request/response schemas and APIs for charge preview, versions, changes, domain approvals, documents/signature and settlements
- [x] 8.6 Require `expected_version` on every mutation and idempotency keys on retryable apply/close commands in OpenAPI and runtime
- [x] 8.7 Map stale, in-flight, occupancy, approval, document, clearance and provider failures to stable 403/404/409/503 codes
- [x] 8.8 Add reconciliation, pagination/order, privacy, empty, cross-tenant/park and business-code API tests

## 9. PC contract lifecycle workspace

- [x] 9.1 Replace manual park/Party/Unit IDs with authorized selectors and rebuild KPI/filter/list/expiry workspace
- [x] 9.2 Add multi-unit, multi-charge draft editor with occupancy and deterministic schedule preview/confirmation
- [x] 9.3 Add detail drawer/tabs for current facts, unit/charge schedule, immutable versions/diff and governance timeline
- [x] 9.4 Add submit/approve/reject/withdraw/document/signature-readiness/activate flows with permission-consistent controls
- [x] 9.5 Add typed change creation, before/after diff, approval and due-apply flows for all seven change types
- [x] 9.6 Add exit handover, meters, settlement items/totals, evidence, clearance and close flows without implying money movement
- [x] 9.7 Implement loading, empty, validation, forbidden, read-only, success, stale 409, occupancy conflict and recoverable 503 states
- [x] 9.8 Prevent older async responses/timers from overwriting newer contract action feedback and preserve draft context on conflict
- [x] 9.9 Pass desktop/768px responsive, no page overflow, semantic label/dialog, visible focus and keyboard journey checks

## 10. Migration and compatibility evidence

- [x] 10.1 Publish old contract/tenant/image/reminder API disposition and V1/legacy field, enum, source-key and PII mapping
- [x] 10.2 Implement synthetic traditional-contract/attachment/reminder fixtures including multi-contract Party, multi-unit, terms and ambiguous quarantine
- [x] 10.3 Implement loopback-only isolated PostgreSQL dry-run, first apply and idempotent re-apply drill
- [x] 10.4 Reconcile Party/contract counts, status/type/park distributions, versions/units/charges/schedules/documents/reminders, area/amounts, source refs, orphans and PII
- [x] 10.5 Prove isolated schema rollback and add contract ETL to full local acceptance
- [x] 10.6 Keep real schema/data, external signature/payment facts, CDC, stop-write, production migration and cutover behind explicit human approval

## 11. Contracts, full acceptance and checkpoint

- [x] 11.1 Update OpenAPI YAML and runtime contract tests for every contract V2 method, schema, expected version, idempotency and stable error code
- [x] 11.2 Add Playwright primary journey for create/preview/submit/approve/document/activate/version detail
- [x] 11.3 Add Playwright change apply and exit close journeys with API/UI reconciliation
- [x] 11.4 Add Playwright read-only, self-approval/403, stale 409, provider/backend 503 and tablet keyboard scenarios with no skips
- [x] 11.5 Pass focused domain/API/SQLite and PostgreSQL concurrency/rollback tests
- [x] 11.6 Pass backend full tests, DDD architecture checks and Alembic fresh/down-up gates
- [x] 11.7 Pass frontend lint/typecheck/unit/build and full browser E2E
- [x] 11.8 Pass contract ETL, backup restore, OpenAPI, OpenSpec, secrets, diff and cleanup gates
- [x] 11.9 Perform real browser visual QA on desktop and tablet and repair shared layout regressions in scope
- [x] 11.10 Commit implementation, run full acceptance on the exact clean implementation SHA and record the report/head/hash evidence
- [x] 11.11 Update controlling rebuild/acceptance documents with truthful local scope and remaining external/product blockers
- [x] 11.12 Commit and non-force push a clean non-production checkpoint when explicit remote egress authorization is available

## Non-goals

Automatic Bill creation/adjustment, Payment/refund/allocation/accounting writes, live signature/OCR/archive providers, real legacy data, CDC/cutover, employee mobile, tenant mini-program and production deployment remain outside this change and MUST NOT be represented as completed by its local acceptance.
