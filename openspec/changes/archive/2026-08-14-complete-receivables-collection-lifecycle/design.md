## Context

Lease V2 already persists immutable versioned `lease_performance_schedules`; Billing already supports Bill/BillLine issue/void, while Collection supports Payment/PaymentAllocation with PostgreSQL row locks and idempotency. These foundations are valid but disconnected. Legacy Java evidence shows amount-bill receipt fields, finance double-write and `rent_verify_task` confirmation/abnormal states; V2 must preserve the operator journey without copying the unsafe wide-table or implicit side effects.

## Goals / Non-Goals

**Goals:** close the local receivables journey from an approved contract schedule through issued receivable, inbound receipt, deterministic suggestion, human confirmation, allocation, exception/dispute review, aging and collection; preserve tenant/park scope, immutable evidence, idempotency and PostgreSQL concurrency; make disconnected providers explicit.

**Non-goals:** live bank or payment-provider calls, accounting general ledger, tax-invoice issuance, production notification delivery, real legacy migration or production deployment. These require separate credentials/data/authorization and cannot be represented as completed by fixtures.

## Decisions

### 1. Lease schedule is billing intent, Bill is the financial document

Only schedules on the contract's current version and contract states `ACTIVE/EXPIRING/EXIT_PENDING` are eligible. Apply groups due schedule rows by contract, period, due date and currency, creates an issued Bill, records one `source_schedule_id` per BillLine and marks each schedule billed in the same transaction. Unique schedule lineage and ordered row locks make concurrent/repeated runs deterministic. Contract changes never rewrite an already issued Bill; differences require a governed adjustment/change path.

### 2. Receipt transaction is not Payment

`receipt_transactions` represents observed incoming money before finance confirmation. It stores only bounded business fields and a masked payer account; unique `(tenant, source_provider, source_ref)` prevents duplicate import. `Payment` remains confirmed money and is created only by direct authorized registration or receipt confirmation. A receipt cannot claim a disconnected provider channel.

### 3. Matching is deterministic advice, never silent financial authority

Candidates use explainable rules: exact Bill number/reference, same scoped Party, exact/open amount and oldest due order. Scores and rule codes are persisted. A run may set `SUGGESTED`, `EXCEPTION` or retain `PENDING`, but never creates Payment. `payment:review` confirmation locks the receipt and candidate Bills, records explicit allocations and creates Payment. Exceptions are reviewed by finance; business disputes require `payment:dispute_review` before returning to finance or rejection.

### 4. Unapplied balance is first-class

`unapplied_amount = payment.amount - sum(active allocations)` is server-derived. A confirmed Payment may have zero, partial or multiple allocations. Later allocation requires `payment:allocate`, Idempotency-Key, same Party/park, ordered Payment/Bill locks and remaining-balance checks. Allocation rows are append-only; Payment reversal marks the Payment reversed and applies compensating Bill deltas without deleting history.

### 5. Aging drives collection; dispute/extension holds suppress automation

Effective due date is the approved deferred date when present, otherwise Bill due date. Collectible open amount subtracts approved waiver/bad-debt amounts from total before paid amount. A repeat-safe dunning run derives L1=1-7, L2=8-30, L3=31-60 and L4=61+ days, creates or escalates one active case per Bill, appends a SYSTEM action and creates work items. Disputed, deferred-not-due, fully settled, void/discarded and collection-held Bills are skipped. External delivery is a separate explicit action and fails closed when its provider is unconfigured.

### 6. Receivable treatments use shared approval evidence

`WAIVER`, `EXTENSION`, `BAD_DEBT`, `DISPUTE` and `DISPUTE_RESOLUTION` requests snapshot the Bill version, open amount, requested effect and reason into a tenant-scoped adjustment row and shared `ApprovalRequest`. Application is impossible until approval is `APPROVED`; stale/open-amount conflicts return 409. Waiver/bad debt amounts are bounded by current open amount, extension must move the effective due date forward, dispute places a collection hold, and dispute resolution removes it only after a second explicit approval. Applied effects and audit are committed atomically.

### 7. Scope, permissions and API are fail closed

All identifiers are resolved through tenant and park scope. Dedicated permissions are `bill:generate`, `payment:import`, `payment:review`, `payment:allocate`, `payment:dispute_review`, `collection:run` and `receivable:adjust`. Strict request models forbid tenant ids and unknown fields. List filters on finance records never widen scope.

### 8. PC workspace uses live server truth

The finance UI exposes run preview/apply, inbox and candidate details, finance review drawer, explicit unapplied balance/allocation, aging cases and history. It shows provider capability states and never simulates a provider callback. Loading, empty, forbidden, conflict, offline and retry states are testable at 1440/820/390 widths.

### 9. Migration remains synthetic until authorized evidence exists

The ETL accepts versioned legacy-shaped amount-bill, receipt and rent-verification rows. Dry-run/apply/interruption/reapply/reconcile/rollback are transactional and redact account/phone data. Unsupported or ambiguous rows are quarantined. Success means tooling readiness, not real-data cutover.

## Migration Plan

1. Add a forward revision after `t6c24e9f1a08` with new tables, bounded checks, composite tenant foreign keys, partial uniques and performance indexes.
2. Backfill existing Bill treatment amounts/locks to safe zero defaults; existing Payment unapplied balance is derived and needs no destructive rewrite.
3. Deploy APIs/UI, run PG16 fresh upgrade and `head -> -1 -> head`, metadata parity and concurrent replay tests.
4. Run synthetic finance ETL and preserve redacted reconciliation evidence.
5. Downgrade only in a disposable environment after dependent code is stopped. Production and real legacy execution require human authorization.

## Risks / Trade-offs

- Matching false positives could misapply cash; human confirmation is therefore mandatory and every score is explainable.
- Contract-version changes can overlap already billed periods; automatic rewriting is forbidden and the run reports the conflict for adjustment review.
- Notification providers are unavailable; local dunning cases/actions/work items are complete, while delivery status remains unconfigured rather than fabricated.
- Legacy receipt data may not identify payer, Party or Bill; such rows remain in the exception/quarantine path.
