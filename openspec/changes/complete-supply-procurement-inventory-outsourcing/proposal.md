# Change: Complete supply, procurement, inventory, and outsourcing operations

## Why

The rebuilt product currently has a governed Party role for suppliers and append-only work-order cost evidence, but it has no mounted supply module, no procurement lifecycle, and no inventory source of truth. Independent inspection of both legacy Java copies and the legacy SQL dump found no authoritative supplier, purchase, warehouse, stock, issue, or outsourcing aggregate to port. This change therefore rebuilds the local product capability from documented business needs while keeping real legacy-data migration explicitly blocked until an authoritative export is supplied.

## What Changes

- Add tenant- and park-scoped supplier onboarding, qualifications, service scope, evaluation, suspension, and audit history.
- Add governed material catalogue, warehouses, stock balances, append-only stock movements, stocktake, variance approval, adjustment, and reversal.
- Add purchase requisitions with native approval, immutable approval snapshots, purchase orders, acknowledgements, and receipt-driven stock increases.
- Add inventory requisitions, reservations, partial/final issue, return, work-order linkage, concurrency protection, and idempotency.
- Add outsourcing service orders with supplier scope checks, SLA/deliverables, approval, event history, acceptance, rework, and evaluation.
- Mount strict HTTP APIs and a permission-aware PC workspace with overview, supplier, procurement, inventory, and outsourcing views.
- Add PostgreSQL migration, synthetic repeatable/interruption-safe migration harness, reconciliation, rollback rehearsal, real HTTP, browser, security, concurrency, and performance evidence.

## Explicit Boundaries

- Local purchase orders, receipts, inventory, and outsourcing records are the product source of truth only after locally authorized transitions.
- ERP/WMS/procurement-platform/supplier-portal integrations, invoice settlement, tax, e-signature, messaging, and production credentials are not claimed by this change.
- Real old-system data migration remains `BLOCKED` until an authoritative schema/export and reconciliation owner are provided; synthetic rehearsal must not be represented as production migration.

## Impact

- Affected specs: supplier governance, material/warehouse catalogue, procurement requisition approval, purchase order receipt, inventory ledger control, inventory requisition/issue, outsourcing service order, supply API, supply PC, and supply data migration.
- Affected code: API domain/application/infrastructure/presentation layers, Alembic, permission catalogue, OpenAPI, PC routes/API/view, tests, local-staging acceptance, and evidence.
