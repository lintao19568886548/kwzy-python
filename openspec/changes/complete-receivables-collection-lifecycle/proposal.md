## Why

The current V2 finance path stops at manual Bill drafts, direct Payment registration, basic allocations/reversal and manually created CollectionCase rows. It cannot replace the real receivables journey because contract schedules do not produce bills, incoming funds have no governed pending-match pool, matching and exception review do not exist, unapplied receipts cannot be allocated later, collection has no aging strategy/history, and waiver/extension/bad-debt/dispute actions have no approval gate.

## What Changes

- Generate issued Bills deterministically from the current approved Lease performance schedule, with preview/apply modes, schedule lineage and concurrent replay safety.
- Add a tenant/park-scoped receipt transaction inbox for finance import and offline channels; expose truthful adapter capability states for bank-enterprise, payment-link, WeChat, Alipay and aggregate-payment providers.
- Add deterministic match candidates, pending/exception/dispute/review states and finance confirmation that creates the authoritative Payment plus one-or-many Bill allocations.
- Make unapplied Payment balance explicit and allow later idempotent, row-locked allocation across multiple Bills; preserve reversal and audit history.
- Replace the minimal collection case with aging-derived L1-L4 cases, append-only action records, idempotent automatic dunning runs, holds and automatic settlement closure.
- Add approval-backed waiver, extension, bad-debt and dispute adjustments. Money or risk effects cannot apply before an approved request, and applicant/approver separation remains governed by the shared workflow.
- Replace the basic finance pages with a live receivables workspace covering scheduled billing, inbox matching, multi-bill allocation, exceptions, disputes, aging and collection history at desktop/tablet/mobile widths.
- Add synthetic migration rehearsal for legacy amount bills, receipt fields and rent-verification tasks. Real migration remains blocked pending an authorized legacy schema dump and desensitized sample.
- Add strict OpenAPI, tenant/park/field permission, parameter-pollution, PostgreSQL concurrency, true HTTP and Playwright evidence.

## Capabilities

### New Capabilities

- `billing-schedule-generation`: deterministic Lease schedule to issued Bill conversion.
- `receipt-ingestion-matching`: receipt inbox, candidates, exceptions and two-role review.
- `payment-allocation`: explicit unapplied balances and later multi-bill application.
- `collection-dunning`: aging levels, cases, action history and repeat-safe dunning runs.
- `receivable-adjustments`: approval-gated waiver, extension, bad debt and disputes.
- `receivables-pc`: responsive, live API-backed finance workspace.
- `receivables-data-migration`: synthetic legacy finance migration and real-data gates.
- `receivables-api`: strict mounted contracts and capability truth.

## Impact

- Backend: Billing, Collection, Lease schedule read port, Workflow approval adapter, Workbench automation, permissions and OpenAPI.
- Persistence: one forward Alembic revision after `t6c24e9f1a08`; no historical migration is edited.
- Frontend: bills, receipts/payments and collection pages become one coherent finance journey without local business fixtures.
- Operations: PG16 fresh/down-up, concurrent generation/matching/allocation/dunning, synthetic ETL, true HTTP, performance and backup/restore evidence expand to this slice.
- External systems: bank-enterprise, live payment links, WeChat/Alipay/aggregate gateways and production notification providers remain `NOT_CONNECTED` until credentials and provider evidence exist.
