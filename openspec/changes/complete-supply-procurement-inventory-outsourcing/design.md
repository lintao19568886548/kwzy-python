# Design: Governed supply operations

## Context

Existing Party records can identify a supplier and existing work orders can retain material/outsourcing cost evidence, but neither is stock truth. There is no legacy aggregate to reproduce. The new slice must preserve tenant/park isolation, native approvals, append-only operational evidence, database-enforced relationships, and explicit external boundaries.

## Decisions

### Supplier governance

A supply supplier links to an organization Party in the same tenant. Eligibility requires an active supplier, an active park scope, and non-expired required qualifications. Qualification credential values are never stored raw: only a masked display value and keyed fingerprint are retained. Evaluations are append-only.

### Catalogue, warehouse, and stock truth

Material codes are unique per tenant and warehouses belong to one park. Each `(tenant, park, warehouse, material)` balance is unique. Stock movements are append-only and typed as receipt, issue, return, adjustment, or reversal. A mutable balance is only a projection updated atomically with the immutable movement.

### Procurement and receipt

A requisition contains an immutable line snapshot and is submitted to the native approval aggregate. A purchase order can only be created from an approved requisition. Orders state whether they are local truth or awaiting an external adapter. Receipt locks the purchase-order line and stock balance, rejects over-receipt, writes receipt evidence and stock movement atomically, and supports idempotent replay.

### Inventory requisition, issue, and stocktake

Inventory requisitions may reference a work order. Approval reserves stock. Issue can be partial or final, never below zero, and produces immutable issue movement. Return creates a separate compensating movement. Stocktakes snapshot expected quantity, calculate variance, require native approval for non-zero variance, and adjust only through a traceable movement. Corrections use reversal rather than mutation.

### Outsourcing

An outsourcing order binds tenant, park, eligible supplier, optional work order, SLA, deliverables, and price snapshot. Submission uses native approval. Execution is append-only events; completion enters tenant acceptance, rejection creates rework, and acceptance may append a supplier evaluation. Invoice/payment settlement is outside this aggregate.

### Security and concurrency

Permissions are database-derived. Tenant/park mismatches return 404. Composite foreign keys prevent cross-tenant/cross-park references. Request schemas reject unknown fields. Mutations use idempotency keys plus request fingerprints. Row locks and conditional transitions protect receipts, balances, issues, and acceptance. Supplier credentials and PII are masked in API and logs.

### PC experience

`/supply` provides overview, suppliers, procurement, inventory, and outsourcing tabs. Actions use drawers and explicit confirmation for high-risk transitions. Desktop, tablet, and 390px layouts include loading, empty, permission, conflict, offline, and retry states; no local JSON or fabricated chart data is allowed.

### Migration truth

The local harness imports a documented synthetic old-schema fixture, supports dry run, checkpoint/resume, repeat execution, reconciliation, quarantine, rollback, and deletion/restore rehearsal. Real legacy closure stays blocked without authoritative export evidence.

## Risks and mitigations

- Lost stock updates: balance uniqueness, row locks, non-negative checks, atomic movement/projection writes.
- Approval drift: native approval instance and immutable submitted snapshot.
- False integration claims: explicit local/external truth flag and evidence labels.
- Credential leakage: masked values, keyed fingerprints, scan and response tests.
- Data invention: synthetic provenance and real-data blocker remain visible in the final matrix.
