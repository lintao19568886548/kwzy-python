## Why

The current V2 FacilityOps path is only an internal four-state WorkOrder with create/start/complete/cancel. It cannot replace the tenant-service journey because tenant identity is not bound to a Party, dispatch is manual, SLA clocks and escalation do not exist, completion bypasses quote and acceptance, labor/material evidence is absent, and tenants cannot reject work or rate service. Legacy Java preserves useful repair fields and an old UI describes accept/finish/verify/return, but the backend evidence is CRUD-only and explicitly does not trigger dispatch notifications; neither system provides governed quotation, actual-cost or rating history.

## What Changes

- Add a tenant-service principal binding from an authenticated user to one Party and bounded parks; tenant-facing request/list/detail operations derive Party scope from that binding rather than accepting arbitrary Party ids.
- Expand WorkOrder into a versioned, numbered service aggregate with `SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`, `WAITING_QUOTE_APPROVAL`, `IN_PROGRESS_AFTER_QUOTE`, `WAITING_ACCEPTANCE`, `COMPLETED` and terminal cancellation states.
- Add deterministic, versioned assignment rules with response/resolution SLA policies, automatic dispatch, explicit manual reassignment reason and append-only timeline evidence.
- Add versioned quotation headers/lines, exact Decimal totals, submit/tenant accept/reject decisions and a gate that prevents quoted work from continuing before tenant acceptance.
- Add append-only labor, material, outsource and other actual-cost entries with quantity/price checks; completion submission records result evidence without claiming tenant acceptance.
- Add tenant acceptance/rework attempts and one post-acceptance rating with bounded score/tags/comment. Rework reopens the same aggregate and SLA history rather than cloning or deleting it.
- Replace the basic PC table with a live role-aware service workspace for intake, dispatch/SLA, quote, execution, acceptance and rating history at desktop/tablet/mobile widths.
- Add synthetic migration rehearsal for legacy `repair_order` fields and explicit quarantine for ambiguous Party, park, status, phone/image and workflow data. Real migration remains blocked pending authorized schema and desensitized rows.
- Add strict OpenAPI, tenant/Party/park/field permission, IDOR, parameter-pollution, idempotency, PostgreSQL concurrency, true HTTP and Playwright evidence.

## Capabilities

### New Capabilities

- `tenant-service-intake`: database-bound tenant principals and scoped service request intake.
- `work-order-dispatch-sla`: deterministic dispatch, reassignment, SLA clocks and escalation evidence.
- `work-order-quotation`: versioned quotes, lines and tenant decisions.
- `work-order-fulfillment`: labor/material execution evidence and completion submission.
- `work-order-acceptance-rating`: tenant acceptance, rework and post-service rating.
- `tenant-service-api`: strict mounted staff and tenant-facing contracts.
- `tenant-service-pc`: responsive live service operations workspace.
- `tenant-service-data-migration`: synthetic repair-order migration and real-data gates.

## Impact

- Backend: FacilityOps domain/application/repositories, Party and User ownership checks, Workbench tasks/events, permissions and OpenAPI.
- Persistence: forward Alembic revision(s) after `w9f57b2c4d31`; applied history remains unchanged.
- Frontend: `/work-orders` becomes a role-aware service control center without local business fixtures or fixed-success actions.
- Operations: PG16 fresh/down-up, concurrent intake/dispatch/transition/quote decisions, synthetic ETL, true HTTP, performance and backup/restore evidence expand to this slice.
- External systems: SMS/WeCom/mini-program push and production object storage remain `NOT_CONNECTED`; local in-app work items and safe attachment references cannot be reported as external delivery.
